"""Tests for scripts/wrap.py."""
import json
from pathlib import Path

import wrap as W


def test_wrap_python_creates_backup(tmp_path):
    f = tmp_path / "t.py"
    f.write_text("def delete_user(uid):\n    return True\n")
    r = W.wrap(str(f), "delete_user")
    assert r["success"]
    backup = Path(r["backup"])
    assert backup.exists()
    assert "verified-refusal gate" in f.read_text()
    assert backup.read_text() == "def delete_user(uid):\n    return True\n"


def test_wrap_python_inserts_correct_gate(tmp_path):
    f = tmp_path / "x.py"
    f.write_text("def my_fn(a):\n    return a + 1\n")
    r = W.wrap(str(f), "my_fn")
    assert r["success"]
    body = f.read_text()
    assert "VERIFIED_REFUSAL_MODE" in body
    assert "VERIFIED_REFUSAL_OVERRIDE" in body
    assert "'mode': 'verified_refusal'" in body
    # still parses
    import ast
    ast.parse(body)


def test_wrap_python_with_docstring(tmp_path):
    f = tmp_path / "x.py"
    f.write_text('def fn():\n    """Doc."""\n    return 1\n')
    r = W.wrap(str(f), "fn")
    assert r["success"]
    body = f.read_text()
    # gate must come AFTER docstring
    assert body.index('"""Doc."""') < body.index("verified-refusal gate")


def test_wrap_javascript(tmp_path):
    f = tmp_path / "t.js"
    f.write_text("function deleteUser(uid) {\n  return true;\n}\n")
    r = W.wrap(str(f), "deleteUser")
    assert r["success"]
    assert "VERIFIED_REFUSAL_MODE" in f.read_text()


def test_wrap_bash(tmp_path):
    f = tmp_path / "t.sh"
    f.write_text("delete_all() {\n  rm -rf /data\n}\n")
    r = W.wrap(str(f), "delete_all")
    assert r["success"]
    assert "VERIFIED_REFUSAL_MODE" in f.read_text()


def test_wrap_already_gated(tmp_path):
    f = tmp_path / "g.py"
    f.write_text(
        "def fn():\n"
        "    # verified-refusal gate\n"
        "    return 1\n"
    )
    r = W.wrap(str(f), "fn")
    assert not r["success"]
    assert r["error"] == "already_gated"


def test_wrap_missing_file(tmp_path):
    r = W.wrap(str(tmp_path / "nope.py"), "fn")
    assert not r["success"]
    assert r["error"] == "file_not_found"


def test_wrap_not_found(tmp_path):
    f = tmp_path / "t.py"
    f.write_text("def exists():\n    return 1\n")
    r = W.wrap(str(f), "missing")
    assert not r["success"]
    assert r["error"] == "not_found"


def test_wrap_all(tmp_path):
    f = tmp_path / "m.py"
    f.write_text(
        "def safe_read():\n"
        "    return open('/tmp/x.txt').read()\n"
        "\n"
        "def charge(amount):\n"
        "    import stripe\n"
        "    return stripe.Charge.create(amount=amount)\n"
        "\n"
        "def delete_user(uid):\n"
        "    import requests\n"
        "    return requests.delete(f'https://api.example.com/users/{uid}')\n"
    )
    out = W.wrap_all(str(f))
    assert len(out["wrapped"]) >= 2  # charge + delete_user
    body = f.read_text()
    assert body.count("verified-refusal gate") >= 2
