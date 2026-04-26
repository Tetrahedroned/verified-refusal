"""Drop-in Python verified-refusal gate.

Works as:
  - decorator (sync and async)
  - inline check (vr_gate(...))
Self-contained. Stdlib only.

Environment:
  VERIFIED_REFUSAL_MODE=1         activate gate globally
  VERIFIED_REFUSAL_OVERRIDE=1     bypass (still logs, always)
  VR_LOG_PATH                     full log file path override (canonical)
  VR_DATA_DIR                     base data dir; log goes to <dir>/vr_log.jsonl (default ~/.vr)
  OPENCLAW_VR_LOG                 deprecated alias for VR_LOG_PATH; still honored
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import functools
import inspect
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable


def _resolve_log_path() -> Path:
    explicit = os.environ.get("VR_LOG_PATH") or os.environ.get("OPENCLAW_VR_LOG")
    if explicit:
        return Path(os.path.expanduser(explicit))
    base = os.environ.get("VR_DATA_DIR", "~/.vr")
    return Path(os.path.expanduser(base)) / "vr_log.jsonl"


LOG_PATH = _resolve_log_path()


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _active() -> bool:
    return os.environ.get("VERIFIED_REFUSAL_MODE") == "1"


def _overridden() -> bool:
    return os.environ.get("VERIFIED_REFUSAL_OVERRIDE") == "1"


def _append_log(entry: dict[str, Any]) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str, ensure_ascii=False) + "\n")
    except Exception:
        # never let logging failures crash the host program
        pass


def _report(
    *,
    function: str,
    file: str | None,
    category: str | None,
    confidence: float,
    gates_passed: list[str],
    gates_failed: list[str],
    would_have_executed: bool,
    consequence: str | None,
    override_used: bool,
    confirmed: bool,
) -> dict[str, Any]:
    return {
        "mode": "verified_refusal",
        "timestamp": _now(),
        "function": function,
        "file": file,
        "classification": "irreversible" if category else "uncertain",
        "confidence": confidence,
        "category": category,
        "gates_passed": gates_passed,
        "gates_failed": gates_failed,
        "would_have_executed": would_have_executed,
        "consequence": consequence,
        "override_used": override_used,
        "confirmed": confirmed,
        "report_path": str(LOG_PATH),
    }


def vr_gate(
    *,
    category: str = "external_api_side_effect",
    confidence: float = 0.9,
    consequence: str = "irreversible action",
    checks: list[Callable[[], bool | tuple[bool, str]]] | None = None,
    function: str | None = None,
    file: str | None = None,
    emit: bool = True,
) -> dict[str, Any] | None:
    """Inline gate. Returns a report dict if execution should be blocked, else None.

    - If VERIFIED_REFUSAL_MODE is not set and no override: returns None (pass-through).
    - If active: runs checks, emits a structured report, returns the report. Caller
      must stop execution.
    - If override is set: emits a report with override_used=True and returns None.
    """
    passed: list[str] = []
    failed: list[str] = []
    for i, check in enumerate(checks or ()):
        try:
            r = check()
        except Exception as exc:
            failed.append(f"check_{i}:error:{exc}")
            continue
        if isinstance(r, tuple):
            ok, label = r
        else:
            ok, label = bool(r), f"check_{i}"
        (passed if ok else failed).append(label)

    if _overridden():
        report = _report(
            function=function or _caller_name(),
            file=file or _caller_file(),
            category=category,
            confidence=confidence,
            gates_passed=passed,
            gates_failed=failed,
            would_have_executed=True,
            consequence=consequence,
            override_used=True,
            confirmed=False,
        )
        _append_log(report)
        if emit:
            sys.stderr.write(json.dumps(report) + "\n")
        return None

    if not _active():
        return None

    report = _report(
        function=function or _caller_name(),
        file=file or _caller_file(),
        category=category,
        confidence=confidence,
        gates_passed=passed,
        gates_failed=failed,
        would_have_executed=not failed,
        consequence=consequence,
        override_used=False,
        confirmed=False,
    )
    _append_log(report)
    if emit:
        sys.stdout.write(json.dumps(report) + "\n")
    return report


def _caller_name() -> str:
    try:
        return inspect.stack()[2].function
    except Exception:
        return "<unknown>"


def _caller_file() -> str | None:
    try:
        return inspect.stack()[2].filename
    except Exception:
        return None


def vr_protect(
    *,
    category: str = "external_api_side_effect",
    confidence: float = 0.9,
    consequence: str = "irreversible action",
    checks: list[Callable[[], bool | tuple[bool, str]]] | None = None,
) -> Callable:
    """Decorator. Works for sync and async functions."""
    def decorator(func: Callable) -> Callable:
        fname = getattr(func, "__name__", "<anon>")
        ffile = getattr(func, "__code__", None) and func.__code__.co_filename

        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def awrap(*args, **kwargs):
                report = vr_gate(
                    category=category, confidence=confidence, consequence=consequence,
                    checks=checks, function=fname, file=ffile,
                )
                if report is not None:
                    return report
                return await func(*args, **kwargs)
            return awrap

        @functools.wraps(func)
        def swrap(*args, **kwargs):
            report = vr_gate(
                category=category, confidence=confidence, consequence=consequence,
                checks=checks, function=fname, file=ffile,
            )
            if report is not None:
                return report
            return func(*args, **kwargs)
        return swrap
    return decorator


__all__ = ["vr_gate", "vr_protect", "LOG_PATH"]
