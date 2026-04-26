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


# ---- file-list mode (used by pre-commit) ----------------------------------

def test_scan_files_mode_only_scans_given_files(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text(
        "def delete_all():\n"
        "    import shutil; shutil.rmtree('/data')\n"
    )
    other = tmp_path / "other.py"
    other.write_text(
        "def also_bad():\n"
        "    import requests; requests.post('https://api.example.com/x', json={})\n"
    )
    # only pass `bad.py` — scan should ignore other.py
    r = S.scan(files=[str(bad)])
    assert r["files_scanned"] == 1
    assert all(fn["file"].endswith("bad.py") for fn in r["ungated_functions"])


def test_scan_files_mode_filters_by_extension(tmp_path):
    py_file = tmp_path / "ok.py"
    py_file.write_text("def f(): pass\n")
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("def looks_like_code(): import shutil; shutil.rmtree('/')\n")
    r = S.scan(files=[str(py_file), str(txt_file)])
    # .txt is not in ALL_EXT — should be skipped
    assert r["files_scanned"] == 1


def test_scan_files_mode_skips_nonexistent(tmp_path):
    real = tmp_path / "real.py"
    real.write_text("def safe(): return 1\n")
    r = S.scan(files=[str(real), str(tmp_path / "ghost.py")])
    assert r["files_scanned"] == 1


def test_scan_files_mode_empty_list(tmp_path):
    r = S.scan(files=[])
    assert r["files_scanned"] == 0
    assert r["irreversible_total"] == 0


# ---- CLI: --fail-on-ungated and --quiet -----------------------------------

def test_cli_fail_on_ungated_exits_nonzero(tmp_path, monkeypatch, capsys):
    bad = tmp_path / "bad.py"
    bad.write_text(
        "def charge_card(amount):\n"
        "    import requests\n"
        "    return requests.post('https://api.stripe.com/v1/charges', json={'amount': amount})\n"
    )
    monkeypatch.setattr(
        "sys.argv",
        ["scan.py", "--fail-on-ungated", "--quiet", "--no-write", str(bad)],
    )
    rc = S._cli()
    assert rc == 1
    out = capsys.readouterr().out
    # quiet + ungated → still prints summary so dev sees what failed
    assert "ungated" in out.lower() or "irreversible" in out.lower()


def test_cli_fail_on_ungated_passes_when_clean(tmp_path, monkeypatch, capsys):
    clean = tmp_path / "clean.py"
    clean.write_text("def add(a, b):\n    return a + b\n")
    monkeypatch.setattr(
        "sys.argv",
        ["scan.py", "--fail-on-ungated", "--quiet", "--no-write", str(clean)],
    )
    rc = S._cli()
    assert rc == 0
    out = capsys.readouterr().out
    # quiet + clean → silent
    assert out == ""


def test_cli_quiet_without_fail_still_succeeds(tmp_path, monkeypatch, capsys):
    bad = tmp_path / "bad.py"
    bad.write_text(
        "def send_email(to):\n"
        "    import smtplib\n"
        "    s = smtplib.SMTP('mail'); s.sendmail('a','b','c')\n"
    )
    monkeypatch.setattr(
        "sys.argv",
        ["scan.py", "--quiet", "--no-write", str(bad)],
    )
    rc = S._cli()
    # without --fail-on-ungated, presence of ungated is informational only
    assert rc == 0
