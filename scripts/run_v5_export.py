#!/usr/bin/env python3
"""Run VAULT V5 Training Export Pipeline."""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_engine.export import export_training_dataset

def main():
    print("=" * 76)
    print(" VAULT V5 — Scientific Training Dataset Export & CuratorKIT Pipeline")
    print("=" * 76)

    output_dir = REPO_ROOT / "data" / "training_export_v5"
    summary = export_training_dataset(
        records_path=REPO_ROOT / "data" / "synthetic" / "records.jsonl",
        output_dir=output_dir,
    )

    print("\n[EXPORT SUMMARY]")
    print(f"Total Source Records:          {summary['total_source_records']}")
    print(f"Accepted Valid Candidates:     {summary['accepted_candidates_count']} (100% checks_passed)")
    print(f"Quarantined Records:           {summary['quarantined_count']} (defects & ambiguities)")
    print(f"CuratorKIT Processed & Passed: {summary['curator_passed_count']}")

    print("\n[GENERATED FILES]")
    for name, path in summary["files"].items():
        p = Path(path)
        sz = p.stat().st_size if p.exists() else 0
        print(f"  • {name:<18}: {p.name} ({sz:,} bytes)")

    # Print sample record
    candidates_file = Path(summary["files"]["train_candidates"])
    if candidates_file.exists():
        print("\n[SAMPLE TRAINER-READY CHATML RECORD]")
        with open(candidates_file, "r", encoding="utf-8") as f:
            first_line = json.loads(f.readline())
            print(json.dumps(first_line, indent=2))

    # Print checksums
    checksum_file = Path(summary["files"]["checksums"])
    if checksum_file.exists():
        print("\n[SHA-256 CHECKSUMS]")
        print(checksum_file.read_text(encoding="utf-8").strip())

    print("\n" + "=" * 76)
    print(" V5 Training Export Completed Successfully!")
    print("=" * 76)

if __name__ == "__main__":
    main()

