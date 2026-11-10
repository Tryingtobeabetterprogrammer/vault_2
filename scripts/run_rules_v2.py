#!/usr/bin/env python3
"""VAULT V2 Ground-Truth Ledger CLI Generator.

Executes all five deterministic laboratory validation rules against raw V2 datasets,
resolves final verdicts following strict fail-safe precedence, and writes:
- data/ground_truth_v2/ground_truth_ledger_v2.jsonl
- data/reports_v2/ground_truth_summary_v2.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from synth.ledger_v2 import build_ground_truth_ledger_v2


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate VAULT V2 Ground-Truth Ledger.")
    parser.add_argument("--raw-dir", type=str, default=None, help="Raw datasets directory (default: data/raw_v2)")
    parser.add_argument("--output-dir", type=str, default=None, help="Ledger output directory (default: data/ground_truth_v2)")
    parser.add_argument("--reports-dir", type=str, default=None, help="Reports directory (default: data/reports_v2)")

    args = parser.parse_args()

    print("=== VAULT V2 Ground-Truth Ledger Generation ===")
    ledger_p, summary_p, summary = build_ground_truth_ledger_v2(
        raw_dir=args.raw_dir,
        output_dir=args.output_dir,
        reports_dir=args.reports_dir,
    )

    print(f"Ledger written:  {ledger_p}")
    print(f"Summary written: {summary_p}\n")

    v_dist = summary.get("verdict_distribution", {})
    v_pct = summary.get("verdict_percentages", {})
    total = summary.get("total_experiments_processed", 0)

    print(f"Total Experiments: {total}")
    print(f"  Valid:        {v_dist.get('valid', 0):>5} ({v_pct.get('valid_pct', 0.0):>5.2f}%)")
    print(f"  Invalid:      {v_dist.get('invalid', 0):>5} ({v_pct.get('invalid_pct', 0.0):>5.2f}%)")
    print(f"  Needs Review: {v_dist.get('needs_review', 0):>5} ({v_pct.get('needs_review_pct', 0.0):>5.2f}%)")
    print(f"  Abstain:      {summary.get('abstain_count', 0):>5}\n")

    print("Compound Scenarios:")
    for k, v in summary.get("compound_scenarios", {}).items():
        print(f"  {k:<35}: {v}")

    print("\nReason Code Frequencies:")
    for code, cnt in sorted(summary.get("reason_code_frequencies", {}).items(), key=lambda x: -x[1]):
        print(f"  {code:<35}: {cnt}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

