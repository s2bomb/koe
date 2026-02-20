from __future__ import annotations

from pathlib import Path


def test_readme_contains_m1_onboarding_contract_sections() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    required_tokens = [
        "System prerequisites",
        "Hardware requirements",
        "X11",
        "Install",
        "make lint",
        "make typecheck",
        "make test",
        "make run",
        "First-run success signals",
        "Troubleshooting",
        "no focus",
        "missing mic",
        "CUDA",
        "dependency",
    ]

    for token in required_tokens:
        assert token in readme
