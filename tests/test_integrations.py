"""Validate that every /integrations/*.md file follows the contract.

Each integration file must carry the six canonical H2 section headers
in order. See /integrations/README.md for the contract.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INTEGRATIONS_DIR = ROOT / "integrations"

CANONICAL_HEADERS = [
    "Install",
    "Reload",
    "Verify",
    "Standing order",
    "Audit log path",
    "Slash commands",
]

H2 = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _integration_files() -> list[Path]:
    # README.md is the contract doc, not an integration. Subdirs hold
    # platform-shaped manifests (e.g. integrations/openclaw/SKILL.md),
    # not integration docs — exclude them.
    return sorted(
        p for p in INTEGRATIONS_DIR.glob("*.md")
        if p.is_file() and p.name != "README.md"
    )


@pytest.mark.parametrize("path", _integration_files(), ids=lambda p: p.name)
def test_integration_has_canonical_headers_in_order(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    found = H2.findall(text)
    assert found == CANONICAL_HEADERS, (
        f"{path.name}: H2 headers do not match the canonical contract.\n"
        f"  expected: {CANONICAL_HEADERS}\n"
        f"  found:    {found}\n"
        f"See integrations/README.md."
    )


def test_integrations_dir_has_at_least_one_file() -> None:
    assert _integration_files(), (
        "No integration files found. /integrations/*.md should contain at "
        "least openclaw.md, claude-code.md, generic-python-agent.md."
    )


def test_contract_doc_exists() -> None:
    assert (INTEGRATIONS_DIR / "README.md").is_file(), (
        "/integrations/README.md (the contract doc) is missing."
    )
