#!/usr/bin/env python3
"""verified-refusal wrap: insert a VR gate at the top of a target function.

Creates a .vr_backup before modifying. Never modifies a file that already
contains a gate in the target function — reports already_gated instead.

CLI:
  python3 wrap.py --file path/to/file.py --function fn_name
  python3 wrap.py --file path/to/file.py --all
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import classify as _classify  # noqa: E402

GATE_MARKER = "verified-refusal gate"


def _detect_lang(path: Path, override: str | None) -> str:
    if override:
        return override
    s = path.suffix.lower()
    if s == ".py":
        return "python"
    if s in {".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"}:
        return "javascript"
    if s in {".sh", ".bash"}:
        return "bash"
    raise ValueError(f"cannot detect language for {path}")


def _python_gate(indent: str, function_name: str) -> list[str]:
    return [
        f"{indent}# verified-refusal gate",
        f"{indent}if __import__('os').environ.get('VERIFIED_REFUSAL_MODE') == '1' and __import__('os').environ.get('VERIFIED_REFUSAL_OVERRIDE') != '1':",
        f"{indent}    import json as _vr_json, datetime as _vr_dt",
        f"{indent}    _vr_report = {{",
        f"{indent}        'mode': 'verified_refusal',",
        f"{indent}        'function': {function_name!r},",
        f"{indent}        'timestamp': _vr_dt.datetime.now(_vr_dt.timezone.utc).isoformat(),",
        f"{indent}        'would_have_executed': True,",
        f"{indent}        'override_used': False,",
        f"{indent}        'confirmed': False,",
        f"{indent}    }}",
        f"{indent}    print(_vr_json.dumps(_vr_report))",
        f"{indent}    return None",
    ]


def _js_gate(indent: str, function_name: str) -> list[str]:
    return [
        f"{indent}// verified-refusal gate",
        f"{indent}if (typeof process !== 'undefined' && process.env && process.env.VERIFIED_REFUSAL_MODE === '1' && process.env.VERIFIED_REFUSAL_OVERRIDE !== '1') {{",
        f"{indent}  const _vr_report = {{",
        f"{indent}    mode: 'verified_refusal',",
        f"{indent}    function: {json.dumps(function_name)},",
        f"{indent}    timestamp: new Date().toISOString(),",
        f"{indent}    would_have_executed: true,",
        f"{indent}    override_used: false,",
        f"{indent}    confirmed: false,",
        f"{indent}  }};",
        f"{indent}  console.log(JSON.stringify(_vr_report));",
        f"{indent}  return null;",
        f"{indent}}}",
    ]


def _bash_gate(indent: str, function_name: str) -> list[str]:
    esc = function_name.replace('"', '\\"')
    return [
        f"{indent}# verified-refusal gate",
        f'{indent}if [ "$VERIFIED_REFUSAL_MODE" = "1" ] && [ "$VERIFIED_REFUSAL_OVERRIDE" != "1" ]; then',
        f'{indent}  printf \'{{"mode":"verified_refusal","function":"{esc}","would_have_executed":true,"override_used":false,"confirmed":false}}\\n\'',
        f"{indent}  return 0",
        f"{indent}fi",
    ]


def _wrap_python(source: str, function_name: str) -> tuple[str | None, str, int]:
    """Return (new_source, status, lines_inserted). status in {ok, already_gated, not_found}."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return None, f"syntax_error:{exc.msg}", 0
    target = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            target = node
            break
    if not target or not target.body:
        return None, "not_found", 0
    # find insertion line (1-based) and indent
    first = target.body[0]
    # skip docstring if present
    if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str) and len(target.body) > 1):
        first = target.body[1]
    insert_lineno = first.lineno  # 1-based
    indent = " " * first.col_offset
    # check already gated: scan body text for GATE_MARKER
    body_text = "\n".join(source.splitlines()[target.lineno - 1: getattr(target, "end_lineno", target.lineno)])
    if GATE_MARKER in body_text:
        return None, "already_gated", 0
    gate = _python_gate(indent, function_name)
    lines = source.splitlines()
    new_lines = lines[:insert_lineno - 1] + gate + lines[insert_lineno - 1:]
    return "\n".join(new_lines) + ("\n" if source.endswith("\n") else ""), "ok", len(gate)


def _find_js_function(source: str, function_name: str) -> tuple[int, int, str] | None:
    """Return (brace_line_idx, indent_col, function_signature_kind) or None.
    brace_line_idx is 0-based line containing the opening `{`.
    """
    patterns = [
        re.compile(rf"^(\s*)(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+{re.escape(function_name)}\s*\([^)]*\)\s*\{{"),
        re.compile(rf"^(\s*)(?:export\s+)?(?:const|let|var)\s+{re.escape(function_name)}\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{{"),
        re.compile(rf"^(\s*){re.escape(function_name)}\s*\([^)]*\)\s*\{{"),  # method shorthand
        re.compile(rf"^(\s*){re.escape(function_name)}\s*:\s*(?:async\s+)?function\s*\([^)]*\)\s*\{{"),
    ]
    lines = source.splitlines()
    for i, line in enumerate(lines):
        for p in patterns:
            m = p.match(line)
            if m:
                return i, len(m.group(1)), "block"
        # two-line case: signature on one line, `{` on next
        signature_patterns = [
            re.compile(rf"^(\s*)(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+{re.escape(function_name)}\s*\([^)]*\)\s*$"),
            re.compile(rf"^(\s*)(?:export\s+)?(?:const|let|var)\s+{re.escape(function_name)}\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*$"),
        ]
        for p in signature_patterns:
            m = p.match(line)
            if m and i + 1 < len(lines) and lines[i + 1].lstrip().startswith("{"):
                return i + 1, len(m.group(1)), "block"
    return None


def _wrap_javascript(source: str, function_name: str) -> tuple[str | None, str, int]:
    found = _find_js_function(source, function_name)
    if not found:
        return None, "not_found", 0
    brace_idx, indent_cols, _kind = found
    lines = source.splitlines()
    # determine body indent: existing next non-blank non-brace-only line, or brace indent + 2
    body_indent = " " * (indent_cols + 2)
    for j in range(brace_idx + 1, min(len(lines), brace_idx + 10)):
        stripped = lines[j].lstrip()
        if stripped and not stripped.startswith("}"):
            body_indent = lines[j][: len(lines[j]) - len(stripped)]
            break
    body_slice = "\n".join(lines[brace_idx:brace_idx + 60])
    if GATE_MARKER in body_slice:
        return None, "already_gated", 0
    gate = _js_gate(body_indent, function_name)
    new_lines = lines[: brace_idx + 1] + gate + lines[brace_idx + 1:]
    return "\n".join(new_lines) + ("\n" if source.endswith("\n") else ""), "ok", len(gate)


def _wrap_bash(source: str, function_name: str) -> tuple[str | None, str, int]:
    patterns = [
        re.compile(rf"^(\s*)(?:function\s+)?{re.escape(function_name)}\s*\(\s*\)\s*\{{"),
        re.compile(rf"^(\s*)function\s+{re.escape(function_name)}\s*\{{"),
    ]
    lines = source.splitlines()
    for i, line in enumerate(lines):
        for p in patterns:
            m = p.match(line)
            if m:
                indent = " " * (len(m.group(1)) + 2)
                body_slice = "\n".join(lines[i: i + 40])
                if GATE_MARKER in body_slice:
                    return None, "already_gated", 0
                gate = _bash_gate(indent, function_name)
                new_lines = lines[: i + 1] + gate + lines[i + 1:]
                return "\n".join(new_lines) + ("\n" if source.endswith("\n") else ""), "ok", len(gate)
    return None, "not_found", 0


DISPATCH = {
    "python": _wrap_python,
    "javascript": _wrap_javascript,
    "bash": _wrap_bash,
}


def wrap(filepath: str, function_name: str, language: str | None = None) -> dict[str, Any]:
    path = Path(filepath)
    if not path.exists():
        return {
            "success": False, "file": filepath, "function": function_name,
            "backup": None, "language": language, "lines_inserted": 0,
            "error": "file_not_found",
        }
    try:
        lang = _detect_lang(path, language)
    except ValueError as exc:
        return {
            "success": False, "file": filepath, "function": function_name,
            "backup": None, "language": None, "lines_inserted": 0,
            "error": str(exc),
        }
    source = path.read_text(encoding="utf-8")
    handler = DISPATCH[lang]
    new_source, status, lines_inserted = handler(source, function_name)
    if status != "ok":
        return {
            "success": False, "file": filepath, "function": function_name,
            "backup": None, "language": lang, "lines_inserted": 0,
            "error": status,
        }
    backup = path.with_suffix(path.suffix + ".vr_backup")
    shutil.copy2(path, backup)
    path.write_text(new_source, encoding="utf-8")
    return {
        "success": True, "file": filepath, "function": function_name,
        "backup": str(backup), "language": lang, "lines_inserted": lines_inserted,
        "error": None,
    }


def wrap_all(filepath: str, language: str | None = None) -> dict[str, Any]:
    """Wrap every ungated irreversible function in a file."""
    result = _classify.classify_file(filepath)
    wrapped: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for fn in result.get("results", []):
        if not fn.get("irreversible") or fn.get("gated"):
            continue
        out = wrap(filepath, fn["function"], language)
        (wrapped if out["success"] else skipped).append(out)
    return {"file": filepath, "wrapped": wrapped, "skipped": skipped}


def _cli() -> int:
    ap = argparse.ArgumentParser(description="verified-refusal wrap")
    ap.add_argument("--file", required=True)
    ap.add_argument("--function")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--language", choices=["python", "javascript", "bash"])
    args = ap.parse_args()
    if args.all:
        out = wrap_all(args.file, args.language)
    elif args.function:
        out = wrap(args.file, args.function, args.language)
    else:
        ap.print_help()
        return 2
    print(json.dumps(out, indent=2))
    return 0 if (args.all or out.get("success")) else 1


if __name__ == "__main__":
    sys.exit(_cli())
