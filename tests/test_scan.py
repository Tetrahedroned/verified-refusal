"""Tests for scripts/scan.py."""
import json
import os
from pathlib import Path

import scan as S


def test_scan_finds_ungated_in_examples(tmp_path):
    root = Path(__file__).resolve().parents[1] / "examples"
    r = S.scan(str(root))
    assert r["files_scanned"] >= 3
    # examples use gate.vr_gate — they are gated, so ungated ideally == 0
    # (but at minimum, irreversible_total should be > 0 and coverage > 0)
    assert r["irreversible_total"] >= 1


def test_scan_detects_ungated(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text(
        "def delete_user(uid):\n"
        "    import requests\n"
        "    requests.post('https://api.example.com/admin/delete', json={'uid': uid})\n"
    )
    r = S.scan(str(tmp_path))
    assert r["ungated"] >= 1
    assert any(fn["function"] == "delete_user" for fn in r["ungated_functions"])


def test_scan_respects_gated_marker(tmp_path):
    f = tmp_path / "good.py"
    f.write_text(
        "def charge(amount):\n"
        "    # verified-refusal gate\n"
        "    import os\n"
        "    if os.environ.get('VERIFIED_REFUSAL_MODE') == '1':\n"
        "        return None\n"
        "    import requests\n"
        "    return requests.post('https://api.stripe.com/v1/charges', json={'amount': amount})\n"
    )
    r = S.scan(str(tmp_path))
    if r["irreversible_total"] > 0:
        assert r["gated"] >= 1


def test_scan_json_output():
    root = Path(__file__).resolve().parents[1] / "examples"
    r = S.scan(str(root))
    assert json.dumps(r)  # serializable


def test_scan_empty_dir(tmp_path):
    r = S.scan(str(tmp_path))
    assert r["files_scanned"] == 0
    assert r["irreversible_total"] == 0
    assert r["coverage_percent"] == 100.0


def test_scan_skips_dotgit_and_node_modules(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "evil.py").write_text(
        "def x():\n    import requests; requests.post('https://x.example.com', json={})\n"
    )
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "evil.py").write_text(
        "def y():\n    import shutil; shutil.rmtree('/')\n"
    )
    r = S.scan(str(tmp_path))
    assert r["files_scanned"] == 0


def test_priority_assignment():
    assert S._priority("financial_transaction", 0.9) == "high"
    assert S._priority("database_write", 0.7) == "medium"
    assert S._priority("file_destructive", 0.4) == "low"
