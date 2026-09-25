import tomllib
from pathlib import Path


def _project():
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]


def test_v0_1_declares_only_qualified_python_floor():
    assert _project()["requires-python"] == ">=3.12"


def test_postgres_runtime_extra_does_not_require_test_framework():
    extras = _project()["optional-dependencies"]
    assert "postgres" in extras
    assert any(item.startswith("psycopg") for item in extras["postgres"])
    assert all(not item.startswith("pytest") for item in extras["postgres"])