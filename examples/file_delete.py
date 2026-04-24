"""Example: gated file deletion with symlink safety and backup detection.

Demonstrates:
  - refusing to operate outside the declared workspace
  - refusing when no backup was taken this session
  - emitting structured report under VR mode
  - real deletion only when the agent confirms (CONFIRM=1)

Run:
  python3 examples/file_delete.py
  VERIFIED_REFUSAL_MODE=1 python3 examples/file_delete.py
  VERIFIED_REFUSAL_MODE=1 CONFIRM=1 python3 examples/file_delete.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "templates"))
from gate import vr_gate  # noqa: E402

WORKSPACE_ROOT = Path(tempfile.gettempdir()) / "vr_example_workspace"
_backups_taken: set[str] = set()


def _took_backup(path: Path) -> bool:
    return str(path.resolve()) in _backups_taken


def _take_backup(path: Path) -> Path:
    backup = path.with_suffix(path.suffix + ".vr_backup")
    shutil.copy2(path, backup)
    _backups_taken.add(str(path.resolve()))
    return backup


def delete_path(target: str) -> dict:
    path = Path(target)
    real = path.resolve()

    report = vr_gate(
        function="delete_path",
        file=__file__,
        category="file_destructive",
        confidence=0.95,
        consequence=f"delete {real}",
        checks=[
            lambda: (path.exists(), "target_exists"),
            lambda: (
                str(real).startswith(str(WORKSPACE_ROOT.resolve())),
                "target_inside_workspace",
            ),
            lambda: (not path.is_symlink(), "target_is_not_symlink"),
            lambda: (_took_backup(path), "backup_taken_this_session"),
        ],
    )
    if report is not None:
        return report

    if os.environ.get("CONFIRM") != "1":
        return {
            "mode": "verified_refusal",
            "function": "delete_path",
            "would_have_executed": True,
            "confirmed": False,
            "deferred": True,
            "note": "set CONFIRM=1 to execute",
        }

    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return {
        "mode": "verified_refusal",
        "function": "delete_path",
        "would_have_executed": True,
        "confirmed": True,
        "outcome": {"deleted": str(real)},
    }


if __name__ == "__main__":
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    victim = WORKSPACE_ROOT / "scratch.txt"
    victim.write_text("some scratch content", encoding="utf-8")
    _take_backup(victim)

    result = delete_path(str(victim))
    print(json.dumps(result, indent=2, default=str))

    if victim.exists():
        # cleanup in prod-like path (no VR mode, no confirm) so repeated
        # runs don't accumulate scratch files.
        try:
            victim.unlink()
        except FileNotFoundError:
            pass
