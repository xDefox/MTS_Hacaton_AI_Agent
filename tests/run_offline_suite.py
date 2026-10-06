#!/usr/bin/env python3
"""Один прогон всех offline-тестов (пока качается Ollama)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

SUITE = [
    "tests/test_routing_matrix.py",
    "tests/test_api_contract.py",
    "tests/test_fallback_pipeline.py",
    "tests/test_tz_control_plane.py",
    "tests/smoke_tz_backend.py",
]


def main() -> None:
    failed = 0
    print(f"Offline suite ({len(SUITE)} runners)\n")
    for rel in SUITE:
        print("=" * 60)
        print(f"RUN {rel}")
        print("=" * 60)
        proc = subprocess.run([PY, str(ROOT / rel)], cwd=str(ROOT))
        if proc.returncode != 0:
            failed += 1
            print(f"\n!! {rel} exit={proc.returncode}\n")
        else:
            print(f"\n>> {rel} OK\n")
    print("=" * 60)
    if failed:
        print(f"SUITE FAILED: {failed}/{len(SUITE)}")
        raise SystemExit(1)
    print(f"SUITE OK: {len(SUITE)}/{len(SUITE)} (no Ollama required)")


if __name__ == "__main__":
    main()
