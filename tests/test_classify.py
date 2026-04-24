"""Tests for scripts/classify.py."""
import json

import classify as C


def test_post_payment_is_irreversible_financial():
    r = C.classify("requests.post('https://api.stripe.com/v1/charges', json={'amount': 100})")
    assert r["irreversible"] is True
    assert r["category"] == "financial_transaction"
    assert 0.0 <= r["confidence"] <= 1.0
    assert r["recommended_gate"] == "verified_refusal"


def test_get_request_is_not_financial():
    r = C.classify("requests.get('https://api.example.com/users/me')")
    # GET alone should not flag financial or destructive
    assert r["category"] not in ("financial_transaction", "database_write", "file_destructive")


def test_safe_only_read():
    r = C.classify("open('file.txt', 'r').read()")
    assert r["irreversible"] is False
    assert r["recommended_gate"] in ("none", "review")


def test_idempotent_violation_detected():
    r = C.classify("requests.post('https://api.example.com/orders', json={'x': 1})")
    assert r["irreversible"] is True
    assert any("idempot" in s.lower() for s in r["subtle_risks"])


def test_symlink_pattern_detected():
    r = C.classify("os.symlink('/tmp/a', '/tmp/b')")
    assert r["irreversible"] is True or "symlink" in (r.get("reason") or "").lower()
    # Confidence band
    assert 0.0 <= r["confidence"] <= 1.0


def test_cache_flush_async_detected():
    r = C.classify("cdn.purge('https://example.com/asset.js')")
    assert r["irreversible"] is True
    assert r["category"] == "cache_flush_async"


def test_confidence_bounds():
    for text in [
        "",
        "x = 1",
        "DROP TABLE users",
        "stripe.PaymentIntent.create(amount=100)",
        "shutil.rmtree('/')",
        "SELECT * FROM users",
    ]:
        r = C.classify(text)
        assert 0.0 <= r["confidence"] <= 1.0


def test_invalid_input_no_crash():
    r = C.classify("")  # empty
    assert "confidence" in r
    r = C.classify("💣" * 10)  # weird
    assert "confidence" in r


def test_destructive_file_ops():
    r = C.classify("shutil.rmtree('/tmp/build')")
    assert r["irreversible"] is True
    assert r["category"] == "file_destructive"


def test_db_write_sql():
    r = C.classify("cursor.execute('DELETE FROM accounts WHERE id = 42')")
    assert r["irreversible"] is True
    assert r["category"] == "database_write"


def test_cli_json_output(tmp_path):
    """The CLI emits JSON to stdout."""
    import subprocess, sys, os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    proc = subprocess.run(
        [sys.executable, os.path.join(root, "scripts", "classify.py"),
         "--text", "stripe.Charge.create(amount=100)"],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(proc.stdout)
    assert data["category"] == "financial_transaction"
