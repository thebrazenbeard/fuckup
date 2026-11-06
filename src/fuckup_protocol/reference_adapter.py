from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .execution import InjectorReadback, ReadbackDisposition
from .plugins import HandlerFamily, HandlerSpec, PluginRegistry, SideEffectClass


_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9._-]+$")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_plain(item) for item in value]
    if isinstance(value, set | frozenset):
        return sorted(_plain(item) for item in value)
    return value


class ReferenceFileInjector:
    """Small reversible file-backed injector used for qualification and examples."""

    def __init__(
        self,
        root: str | Path,
        *,
        name: str = "reference-file",
        version: str = "1",
    ) -> None:
        self.root = Path(root)
        self.name = name
        self.version = version

    @staticmethod
    def _is_redirect(path: Path) -> bool:
        """Reject symlinks and Windows junctions, including dangling links."""
        return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())

    def _guard_path(self, path: Path) -> Path:
        """Fail closed on existing redirected paths below the configured root.

        This check is appropriate for a trusted, access-controlled example
        root. It does not defeat a concurrent adversary with write permission
        who can swap parent directories between this check and I/O; a hostile
        multi-user filesystem needs platform-specific dirfd/reparse controls.
        """
        if self._is_redirect(self.root):
            raise ValueError("reference root must not be a symbolic link or junction")
        anchor = self.root.resolve(strict=False)
        try:
            relative = path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("reference-file path escapes configured root") from exc
        cursor = self.root
        for part in relative.parts:
            if part in (".", ".."):
                raise ValueError("reference-file path contains traversal component")
            cursor = cursor / part
            if self._is_redirect(cursor):
                raise ValueError("reference-file path traverses symbolic link or junction")
        if not path.resolve(strict=False).is_relative_to(anchor):
            raise ValueError("reference-file path resolves outside configured root")
        return path

    @property
    def spec(self) -> HandlerSpec:
        return HandlerSpec(
            name=self.name,
            family=HandlerFamily.INJECTOR,
            version=self.version,
            side_effect=SideEffectClass.REVERSIBLE_WRITE,
            idempotent=True,
            retryable=False,
        )

    def register(self, registry: PluginRegistry) -> None:
        registry.register_injector(self.spec, self.execute, self.readback)

    def execute(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        target_key = self._target_key(str(request.get("target", "")))
        operation_id = self._safe_component(
            str(request.get("operation_id", "")),
            field="operation_id",
        )
        effect_digest = str(request.get("effect_digest", ""))
        if not effect_digest:
            raise ValueError("effect_digest is required")
        payload = _plain(request.get("effect_payload", {}))
        if not isinstance(payload, dict):
            raise ValueError("effect_payload must be a mapping")

        target_dir = self._guard_path(self.root / target_key)
        versions = self._guard_path(target_dir / "versions")
        operations = self._guard_path(target_dir / "operations")
        versions.mkdir(parents=True, exist_ok=True)
        operations.mkdir(parents=True, exist_ok=True)

        current_path = self._guard_path(target_dir / "current.json")
        receipt_path = self._guard_path(operations / f"{operation_id}.json")
        version_name = self._digest_filename(effect_digest)
        version_path = self._guard_path(versions / version_name)

        if receipt_path.exists():
            receipt = self._read_json(receipt_path)
            if (
                receipt.get("effect_digest") != effect_digest
                or receipt.get("target") != str(request["target"])
                or receipt.get("operation_id") != operation_id
            ):
                raise ValueError("operation id was reused for a different reference-file effect")
            current = self._read_json(current_path) if current_path.exists() else None
            if (
                current is None
                or current.get("effect_digest") != effect_digest
                or current.get("operation_id") != operation_id
                or current.get("target") != str(request["target"])
            ):
                raise RuntimeError(
                    "recorded reference-file operation is not current; reconcile before retry"
                )
            if receipt.get("version_file") != version_name or not version_path.exists():
                raise RuntimeError("recorded reference-file version is absent or inconsistent")
            version = self._read_json(version_path)
            if (
                version.get("target") != str(request["target"])
                or version.get("operation_id") != operation_id
                or version.get("effect_digest") != effect_digest
                or version.get("payload") != payload
            ):
                raise ValueError("operation replay payload or immutable version differs")
            return {**receipt, "idempotent_replay": True}

        # A digest names one immutable reference version for this target.  A
        # second operation may not silently reuse it or replace its contents:
        # its own custody must be reconciled against the existing operation.
        if version_path.exists():
            raise RuntimeError(
                "effect digest already has a reference-file version; reconcile its operation"
            )

        previous_current = self._read_json(current_path) if current_path.exists() else None
        version_record = {
            "target": str(request["target"]),
            "operation_id": operation_id,
            "effect_digest": effect_digest,
            "payload": payload,
        }
        self._create_immutable_json(version_path, version_record)

        receipt = {
            "target": str(request["target"]),
            "operation_id": operation_id,
            "effect_digest": effect_digest,
            "previous_current": previous_current,
            "version_file": version_name,
            "idempotent_replay": False,
        }
        self._atomic_json(receipt_path, receipt)
        self._atomic_json(
            current_path,
            {
                "target": str(request["target"]),
                "operation_id": operation_id,
                "effect_digest": effect_digest,
                "version_file": version_name,
            },
        )
        return receipt

    def readback(
        self,
        request: Mapping[str, Any],
        _handler_result: Mapping[str, Any] | None,
    ) -> InjectorReadback:
        target_key = self._target_key(str(request.get("target", "")))
        effect_digest = str(request.get("effect_digest", ""))
        current_path = self._guard_path(self.root / target_key / "current.json")
        if not current_path.exists():
            return InjectorReadback(
                ReadbackDisposition.FAILED,
                evidence_ref=f"reference-file:{target_key}:missing",
            )

        current = self._read_json(current_path)
        if current.get("target") != str(request.get("target", "")):
            return InjectorReadback(
                ReadbackDisposition.AMBIGUOUS,
                evidence_ref=f"reference-file:{target_key}:target-mismatch",
            )
        if current.get("effect_digest") != effect_digest:
            return InjectorReadback(
                ReadbackDisposition.FAILED,
                evidence_ref=f"reference-file:{target_key}:different-current",
            )
        if current.get("operation_id") != str(request.get("operation_id", "")):
            return InjectorReadback(
                ReadbackDisposition.FAILED,
                evidence_ref=f"reference-file:{target_key}:different-operation",
            )

        version_file = current.get("version_file")
        if not isinstance(version_file, str) or not version_file:
            return InjectorReadback(
                ReadbackDisposition.AMBIGUOUS,
                evidence_ref=f"reference-file:{target_key}:invalid-pointer",
            )
        version_file = self._safe_component(version_file, field="version_file")
        if version_file != self._digest_filename(effect_digest):
            return InjectorReadback(
                ReadbackDisposition.AMBIGUOUS,
                evidence_ref=f"reference-file:{target_key}:noncanonical-version-pointer",
            )
        version_path = self._guard_path(self.root / target_key / "versions" / version_file)
        if not version_path.exists():
            return InjectorReadback(
                ReadbackDisposition.AMBIGUOUS,
                evidence_ref=f"reference-file:{target_key}:version-missing",
            )
        version = self._read_json(version_path)
        if version.get("effect_digest") != effect_digest:
            return InjectorReadback(
                ReadbackDisposition.AMBIGUOUS,
                evidence_ref=f"reference-file:{target_key}:version-mismatch",
            )
        if (
            version.get("target") != current.get("target")
            or version.get("operation_id") != current.get("operation_id")
        ):
            return InjectorReadback(
                ReadbackDisposition.AMBIGUOUS,
                evidence_ref=f"reference-file:{target_key}:version-identity-mismatch",
            )
        if "effect_payload" not in request:
            return InjectorReadback(
                ReadbackDisposition.AMBIGUOUS,
                evidence_ref=f"reference-file:{target_key}:missing-expected-payload",
            )
        if version.get("payload") != _plain(request["effect_payload"]):
            return InjectorReadback(
                ReadbackDisposition.AMBIGUOUS,
                evidence_ref=f"reference-file:{target_key}:payload-mismatch",
            )

        return InjectorReadback(
            ReadbackDisposition.VERIFIED,
            evidence_ref=f"reference-file:{target_key}:{effect_digest}",
            observed={
                "target": current["target"],
                "operation_id": current["operation_id"],
                "effect_digest": current["effect_digest"],
                "payload": version.get("payload", {}),
            },
            failure_occurred=False,
            prevented=False,
            regression=False,
        )

    def rollback(self, target: str, operation_id: str) -> Mapping[str, Any]:
        target_key = self._target_key(target)
        operation_id = self._safe_component(operation_id, field="operation_id")
        target_dir = self._guard_path(self.root / target_key)
        current_path = self._guard_path(target_dir / "current.json")
        receipt_path = self._guard_path(target_dir / "operations" / f"{operation_id}.json")
        if not receipt_path.exists():
            raise KeyError(f"unknown reference-file operation: {operation_id}")
        receipt = self._read_json(receipt_path)
        current = self._read_json(current_path) if current_path.exists() else None
        if (
            current is None
            or current.get("effect_digest") != receipt.get("effect_digest")
            or current.get("operation_id") != operation_id
            or current.get("target") != target
            or receipt.get("operation_id") != operation_id
            or receipt.get("target") != target
        ):
            raise RuntimeError("cannot rollback over a newer or missing current effect")

        previous = receipt.get("previous_current")
        if previous is None:
            current_path.unlink()
            restored = None
        else:
            self._atomic_json(current_path, previous)
            restored = previous.get("effect_digest")
        return {
            "operation_id": operation_id,
            "rolled_back_effect_digest": receipt.get("effect_digest"),
            "restored_effect_digest": restored,
        }

    def _target_key(self, target: str) -> str:
        prefix = f"{self.name}:"
        if not target.startswith(prefix):
            raise ValueError(f"target must use {prefix}<key>")
        key = target[len(prefix):]
        return self._safe_component(key, field="target")

    @staticmethod
    def _safe_component(value: str, *, field: str) -> str:
        if not value or value in (".", "..") or not _SAFE_COMPONENT.fullmatch(value):
            raise ValueError(f"{field} contains unsafe path characters")
        return value

    @staticmethod
    def _digest_filename(effect_digest: str) -> str:
        normalized = effect_digest.replace(":", "_")
        if not _SAFE_COMPONENT.fullmatch(normalized):
            raise ValueError("effect_digest contains unsafe path characters")
        return f"{normalized}.json"

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object in {path}")
        return value

    @staticmethod
    def _create_immutable_json(path: Path, value: Mapping[str, Any]) -> None:
        """Exclusively reserve a version across independent writers.

        O_CREAT|O_EXCL prevents two processes from acknowledging creation of
        the same digest filename. A crash while writing can leave a partial
        version; this deliberately fails closed for manual reconciliation.
        It is not an atomic transaction with the later receipt/current writes.
        """
        encoded = json.dumps(
            _plain(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise RuntimeError(
                "effect digest already has a reference-file version; reconcile its operation"
            ) from exc
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())

    @staticmethod
    def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.parent / f".{path.name}.{uuid4().hex}.tmp"
        try:
            temp.write_text(
                json.dumps(
                    _plain(value),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            os.replace(temp, path)
        finally:
            if temp.exists():
                temp.unlink()
