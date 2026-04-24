#!/usr/bin/env python3
"""verified-refusal scan: walk a tree, classify functions, find ungated ones.

Calls into classify.py (same directory).
Writes JSON report to ~/.openclaw/vr_scan_{ts}.json.

CLI:
  python3 scan.py --root .
  python3 scan.py --root ./src --languages python javascript
  python3 scan.py --root . --json
  python3 scan.py --root . --ungated-only
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import classify as _classify  # noqa: E402

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", "venv", ".venv", "env", ".env",
    "dist", "build", ".mypy_cache", ".pytest_cache", ".tox", "target",
    ".next", ".nuxt", ".cache", "coverage", ".idea", ".vscode",
}

LANG_EXT = {
    "python": {".py"},
    "javascript": {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"},
    "bash": {".sh", ".bash"},
}
ALL_EXT = {e for exts in LANG_EXT.values() for e in exts}


def _iter_files(root: Path, languages: list[str] | None) -> list[Path]:
    exts = (
        {e for lang in languages for e in LANG_EXT.get(lang, set())}
        if languages else ALL_EXT
    )
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix in exts:
                out.append(p)
    return out


def _priority(category: str | None, confidence: float) -> str:
    if category in ("financial_transaction", "credential_operation") and confidence > 0.8:
        return "high"
    if confidence > 0.6:
        return "medium"
    return "low"


def scan(root_path: str, languages: list[str] | None = None) -> dict[str, Any]:
    root = Path(root_path).resolve()
    if not root.exists():
        raise FileNotFoundError(f"scan root not found: {root}")
    files = _iter_files(root, languages)
    gated: list[dict[str, Any]] = []
    ungated: list[dict[str, Any]] = []
    functions_found = 0
    for path in files:
        try:
            result = _classify.classify_file(str(path))
        except Exception as exc:  # don't let one bad file kill the scan
            result = {"file": str(path), "error": str(exc), "results": []}
        for fn in result.get("results", []):
            functions_found += 1
            if not fn.get("irreversible"):
                continue
            entry = {
                "file": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
                "function": fn.get("function"),
                "line": fn.get("line"),
                "category": fn.get("category"),
                "confidence": fn.get("confidence"),
                "priority": _priority(fn.get("category"), fn.get("confidence", 0.0)),
            }
            if fn.get("gated"):
                gated.append(entry)
            else:
                ungated.append(entry)
    irreversible_total = len(gated) + len(ungated)
    coverage = (len(gated) / irreversible_total * 100.0) if irreversible_total else 100.0
    return {
        "scan_root": str(root),
        "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "files_scanned": len(files),
        "functions_found": functions_found,
        "irreversible_total": irreversible_total,
        "gated": len(gated),
        "ungated": len(ungated),
        "ungated_functions": sorted(ungated, key=lambda e: (-(e["confidence"] or 0.0), e["file"], e["line"] or 0)),
        "gated_functions": gated,
        "coverage_percent": round(coverage, 2),
    }


def _log_dir() -> Path:
    d = Path(os.path.expanduser("~/.openclaw"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_report(report: dict[str, Any]) -> Path:
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = _log_dir() / f"vr_scan_{ts}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return out


def _human_summary(report: dict[str, Any]) -> str:
    lines = [
        "verified-refusal scan",
        f"  root: {report['scan_root']}",
        f"  files: {report['files_scanned']}  functions: {report['functions_found']}",
        f"  irreversible: {report['irreversible_total']}  "
        f"gated: {report['gated']}  ungated: {report['ungated']}  "
        f"coverage: {report['coverage_percent']}%",
    ]
    if report["ungated_functions"]:
        lines.append("  ungated (highest priority first):")
        for fn in report["ungated_functions"][:20]:
            lines.append(
                f"    [{fn['priority']:<6}] {fn['file']}:{fn['line']}  "
                f"{fn['function']}  ({fn['category']}, conf={fn['confidence']})"
            )
        if len(report["ungated_functions"]) > 20:
            lines.append(f"    ... and {len(report['ungated_functions']) - 20} more")
    return "\n".join(lines)


def _cli() -> int:
    ap = argparse.ArgumentParser(description="verified-refusal scanner")
    ap.add_argument("--root", default=".", help="directory to scan")
    ap.add_argument("--languages", nargs="*", choices=list(LANG_EXT.keys()))
    ap.add_argument("--json", action="store_true", help="JSON only, no human summary")
    ap.add_argument("--ungated-only", action="store_true", help="print only ungated list")
    ap.add_argument("--no-write", action="store_true", help="skip writing report file")
    args = ap.parse_args()

    try:
        report = scan(args.root, args.languages)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not args.no_write:
        report_path = _write_report(report)
        report["report_path"] = str(report_path)

    if args.ungated_only:
        print(json.dumps(report["ungated_functions"], indent=2))
    elif args.json:
        print(json.dumps(report, indent=2))
    else:
        print(_human_summary(report))
        if not args.no_write:
            print(f"  written: {report['report_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
