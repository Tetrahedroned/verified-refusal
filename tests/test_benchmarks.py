"""Tests for benchmarks/run_benchmarks.py.

These tests exercise the benchmark harness without running the full
multi-iteration measurement. They verify:
  - every test case instantiates
  - classify flags every dangerous function as irreversible
  - the VR gate triggers on every case
  - results.json is valid and contains all 10 cases
  - summary numbers are consistent with test case definitions
  - BENCHMARK_REPORT.md is generated and non-empty

Running the benchmark fully takes a few seconds; we run once with a
small iteration count and reuse the output for every assertion below.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "scripts"))

import classify as _classify  # noqa: E402
import run_benchmarks as B  # noqa: E402


@pytest.fixture(scope="module")
def bench_data():
    """Run the benchmark once for the whole module at low iteration count."""
    return B.run_all(iterations=2)


def test_ten_test_cases_defined():
    assert len(B.TEST_CASES) == 10
    ids = [tc.id for tc in B.TEST_CASES]
    assert ids == list(range(1, 11))


def test_all_test_cases_instantiate_without_error():
    for tc in B.TEST_CASES:
        assert tc.name
        assert tc.scenario
        assert tc.source.strip().startswith("def ")
        assert tc.fn_name
        assert tc.live_cost_usd > 0
        assert sum(tc.live_cost_breakdown.values()) == pytest.approx(tc.live_cost_usd, abs=0.01)


def test_classify_flags_every_case_irreversible():
    for tc in B.TEST_CASES:
        r = _classify.classify(tc.source)
        assert r["irreversible"] is True, (
            f"case #{tc.id} {tc.name!r} was not classified irreversible; got {r}"
        )


def test_classify_category_matches_expected():
    mismatches = []
    for tc in B.TEST_CASES:
        r = _classify.classify(tc.source)
        if r["category"] != tc.expected_category:
            mismatches.append((tc.id, tc.expected_category, r["category"]))
    assert not mismatches, f"category mismatches: {mismatches}"


def test_vr_gate_triggers_on_every_case():
    for tc in B.TEST_CASES:
        report = B._gate_once(tc)
        assert isinstance(report, dict), f"case #{tc.id} did not trigger gate"
        assert report.get("mode") == "verified_refusal"
        assert report.get("classification") == "irreversible"


def test_dangerous_functions_raise_if_run_live():
    """Safety net: if anything misconfigures and the body runs, tests explode."""
    for tc in B.TEST_CASES:
        fn = B._make_callable(tc.source, tc.fn_name)
        with pytest.raises(AssertionError, match="live during benchmark"):
            fn(*tc.dummy_args, **tc.dummy_kwargs)


def test_results_json_valid(bench_data, tmp_path):
    out = tmp_path / "results.json"
    out.write_text(json.dumps(bench_data, default=str), encoding="utf-8")
    parsed = json.loads(out.read_text())
    assert parsed["benchmark_version"] == B.BENCH_VERSION
    assert "timestamp" in parsed
    assert "system" in parsed
    assert "summary" in parsed
    assert "tests" in parsed
    assert len(parsed["tests"]) == 10


def test_summary_total_vr_cost_is_zero(bench_data):
    assert bench_data["summary"]["total_vr_cost_usd"] == 0.00


def test_summary_tests_passed_is_ten(bench_data):
    assert bench_data["summary"]["tests_passed"] == 10
    assert bench_data["summary"]["tests_failed"] == 0


def test_all_overhead_values_are_positive(bench_data):
    for r in bench_data["tests"]:
        assert isinstance(r["vr_overhead_ms"], float)
        assert r["vr_overhead_ms"] > 0.0
        assert r["classify_ms"] > 0.0
        assert r["scan_ms"] > 0.0
        assert r["gate_ms"] > 0.0


def test_live_costs_match_definitions(bench_data):
    defined = {tc.id: tc.live_cost_usd for tc in B.TEST_CASES}
    for r in bench_data["tests"]:
        assert r["live_cost_usd"] == defined[r["id"]]


def test_cost_avoided_equals_sum_of_live_costs(bench_data):
    expected_total = round(sum(tc.live_cost_usd for tc in B.TEST_CASES), 2)
    assert bench_data["summary"]["total_live_cost_usd"] == expected_total
    assert bench_data["summary"]["cost_avoided_usd"] == expected_total


def test_average_overhead_is_mean_of_per_case_overhead(bench_data):
    total = sum(r["vr_overhead_ms"] for r in bench_data["tests"])
    expected_avg = total / len(bench_data["tests"])
    # generated summary rounds to 4 dp
    assert bench_data["summary"]["average_vr_overhead_ms"] == pytest.approx(expected_avg, abs=1e-3)


def test_all_cases_caught(bench_data):
    for r in bench_data["tests"]:
        assert r["gate_triggered"], f"case #{r['id']} gate did not trigger"
        assert r["report_generated"], f"case #{r['id']} report missing fields"
        assert r["error_caught"], f"case #{r['id']} error_caught was False"


def test_markdown_report_non_empty(bench_data):
    md = B.render_markdown(bench_data)
    assert "# Verified-Refusal Benchmark Report" in md
    assert "Total potential live cost" in md
    assert "10/10" in md
    # every test case should be present
    for tc in B.TEST_CASES:
        assert f"### Test {tc.id} —" in md
    # every pricing source should be cited somewhere in the report
    for src_url in B.SOURCES.values():
        assert src_url in md or src_url.startswith("US Bureau") or src_url.startswith("Conservative") or src_url.startswith("Assumed")
    assert len(md) > 2000


def test_artifacts_exist_on_disk():
    """The committed artifacts from the main runner."""
    assert (ROOT / "benchmarks" / "results.json").exists()
    assert (ROOT / "benchmarks" / "BENCHMARK_REPORT.md").exists()
    data = json.loads((ROOT / "benchmarks" / "results.json").read_text())
    assert data["summary"]["total_vr_cost_usd"] == 0.0
    assert data["summary"]["tests_passed"] == 10
