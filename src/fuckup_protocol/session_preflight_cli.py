"""Read-only session preflight preparation for hosts using F.U.C.K.U.P."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from .postgres_execution import PostgresExecutionStore
from .reference_adapter import ReferenceFileInjector
from .session_preflight import load_reference_session_preflight


_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SELECTOR_KEY = re.compile(r"^[A-Za-z0-9_.-]+$")


def _context(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in values:
        key, sep, value = item.partition("=")
        if not sep or not _SELECTOR_KEY.fullmatch(key) or not value.strip():
            raise ValueError("--context must be a nonempty key=value selector")
        if key in result:
            raise ValueError("duplicate --context key")
        result[key] = value
    if not result:
        raise ValueError("at least one --context selector is required")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare an authorized, verified correction for a future model request."
    )
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--context", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--dsn-env", default="FUCKUP_DATABASE_URL")
    parser.add_argument("--schema-env", default="FUCKUP_SCHEMA")
    args = parser.parse_args(argv)

    try:
        if not _NAME.fullmatch(args.dsn_env) or not _NAME.fullmatch(args.schema_env):
            raise ValueError("invalid credential/schema environment variable name")
        dsn = os.environ.get(args.dsn_env)
        schema = os.environ.get(args.schema_env)
        if not dsn or not schema or not _NAME.fullmatch(schema):
            raise ValueError("trusted database DSN and simple schema name must be configured")
        context = _context(args.context)
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError('install the optional "postgres" dependency') from exc

        store = PostgresExecutionStore(
            lambda: psycopg.connect(dsn, options=f"-c search_path={schema},pg_catalog")
        )
        prepared = load_reference_session_preflight(
            store=store,
            adapter=ReferenceFileInjector(args.reference_root),
            context=context,
            expected_target=args.target,
            operation_id=args.operation_id,
            session_id=args.session_id,
        )
    except (ValueError, RuntimeError, PermissionError, LookupError, KeyError) as exc:
        # Do not echo DSNs, SQL exceptions or other potentially sensitive data.
        print(f"SESSION_PREFLIGHT_BLOCKED: {type(exc).__name__}", file=sys.stderr)
        return 2
    except Exception:
        print("SESSION_PREFLIGHT_BLOCKED: external_store_or_readback_error", file=sys.stderr)
        return 2

    print(json.dumps({
        "status": "PREPARED_NOT_MATERIALIZED",
        "session_id": prepared.session_id,
        "correction_id": prepared.correction_id,
        "correction_revision": prepared.correction_revision,
        "binding_id": prepared.binding_id,
        "promotion_id": prepared.promotion_id,
        "effect_digest": prepared.effect_digest,
        "message_digest": prepared.message_digest,
        "message": prepared.message,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
