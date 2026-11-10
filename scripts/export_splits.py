#!/usr/bin/env python3
"""Run dataset splits export and leakage verification."""

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_engine.splits import generate_synthetic_splits

def main():
    manifest = generate_synthetic_splits()
    print("=== VAULT Synthetic Dataset Splits Export ===")
    print(f"Total Experiments: {manifest['total_experiments']}")
    print(f"Leakage Check:     {manifest['leakage_verification']['status']}")
    for s_name, s_data in manifest["splits"].items():
        print(f"  Split '{s_name}': count={s_data['count']}, clauses={s_data['clauses_count']}, verdicts={s_data['verdict_distribution']}")

if __name__ == "__main__":
    main()
