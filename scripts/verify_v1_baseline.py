#!/usr/bin/env python3
"""Verify cryptographic immutability of VAULT V1 baseline files.

Compares SHA-256 hashes of all V1 data, configuration, ledger, and report files
against the frozen manifest in data/reports/v1_baseline_hashes.json.
Exits with 0 if all hashes match exactly, or 1 if any drift is detected.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_PATH = os.path.join(REPO_ROOT, "data", "reports", "v1_baseline_hashes.json")


def verify_v1_baseline() -> bool:
    if not os.path.exists(MANIFEST_PATH):
        print(f"ERROR: Baseline manifest not found at: {MANIFEST_PATH}", file=sys.stderr)
        return False

    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    files_dict = manifest.get("files", {})
    all_ok = True
    print(f"=== VAULT V1 Baseline Immutability Verification ===")
    print(f"Manifest Version: {manifest.get('manifest_version')}")
    print(f"Verifying {len(files_dict)} files...\n")

    for rel_path, expected in files_dict.items():
        abs_path = os.path.join(REPO_ROOT, rel_path)
        expected_hash = expected.get("sha256")
        expected_size = expected.get("size_bytes")

        if not os.path.exists(abs_path):
            print(f"  [MISSING] {rel_path}")
            all_ok = False
            continue

        actual_size = os.path.getsize(abs_path)
        with open(abs_path, "rb") as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()

        if actual_hash == expected_hash and actual_size == expected_size:
            print(f"  [PASS] {rel_path} ({actual_size} bytes)")
        else:
            print(f"  [FAIL] {rel_path}")
            if actual_size != expected_size:
                print(f"         Size mismatch: expected {expected_size}, got {actual_size}")
            if actual_hash != expected_hash:
                print(f"         Hash mismatch: expected {expected_hash}")
                print(f"                        got      {actual_hash}")
            all_ok = False

    print()
    if all_ok:
        print("RESULT: ALL V1 FILES ARE 100% IDENTICAL TO BASELINE.")
        return True
    else:
        print("RESULT: DRIFT DETECTED IN V1 FILES!", file=sys.stderr)
        return False


if __name__ == "__main__":
    success = verify_v1_baseline()
    sys.exit(0 if success else 1)

