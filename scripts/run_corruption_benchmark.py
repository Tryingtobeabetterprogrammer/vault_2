#!/usr/bin/env python3
"""Run the VAULT V4 Corruption Benchmark Suite."""

import json
import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_engine.curation import run_full_corruption_benchmark

def main():
    print("=" * 72)
    print(" VAULT V4 — Evidence Verification Gate & Corruption Benchmark")
    print(" Comparing CuratorKIT Baseline Hygiene vs VAULT Evidence Gate")
    print("=" * 72)

    report = run_full_corruption_benchmark()

    summary = report["benchmark_summary"]
    vg = report["vault_verification_gate"]
    ck = report["curatorkit_baseline_hygiene"]

    print(f"\n[BENCHMARK OVERVIEW]")
    print(f"Total Records Evaluated: {summary['total_records_evaluated']}")
    print(f"Defective Records:       {summary['defective_records_present']}")
    print(f"Clean Control Records:   {summary['clean_valid_records_present']}")
    print(f"Coverage:                {summary['coverage_pct']}%")

    print(f"\n[SYSTEM COMPARISON]")
    print(f"{'Metric':<24} | {'CuratorKIT Baseline':<20} | {'VAULT Evidence Gate':<20}")
    print("-" * 72)
    print(f"{'Precision':<24} | {ck['precision']:>18.2%} | {vg['precision']:>18.2%}")
    print(f"{'Recall':<24} | {ck['recall']:>18.2%} | {vg['recall']:>18.2%}")
    print(f"{'False Positive Rate':<24} | {ck['false_positive_rate']:>18.2%} | {vg['false_positive_rate']:>18.2%}")
    print(f"{'Accuracy':<24} | {ck['accuracy']:>18.2%} | {vg['accuracy']:>18.2%}")

    print(f"\n[INJECTED CORRUPTION DETECTION (5 Mandatory Types)]")
    for c_name, c_stats in report["corruption_type_breakdown"].items():
        rate = c_stats['detected_by_vault'] / c_stats['injected'] if c_stats['injected'] > 0 else 0
        print(f"  {c_name:<24}: {c_stats['detected_by_vault']}/{c_stats['injected']} detected ({rate:.1%})")

    print(f"\n[SCENARIO FAMILY BREAKDOWN (14 Families)]")
    for fam, f_stats in sorted(report["scenario_family_breakdown"].items()):
        det = f_stats['detected_by_vault']
        tot = f_stats['total']
        defect = f_stats['defective']
        print(f"  {fam:<40}: {det} detected / {defect} defective (total: {tot})")

    print("\n" + "=" * 72)
    print(" Benchmark completed successfully! Reports written to data/reports_v2/")
    print("=" * 72)

if __name__ == "__main__":
    main()

