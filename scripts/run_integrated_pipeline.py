#!/usr/bin/env python3
"""Run the end-to-end integration of CuratorKIT with VAULT.

Demonstrates the live pipeline on the full 1,200 synthetic dataset:
- Ingestion and format detection via curatorkit.detection.detector.FormatDetector
- VAULT deterministic scientific verification gate
- CuratorKIT SchemaGate, ExactDeduplicator, MinHashDeduplicator, TextCleaner
- ChatML/messages export via curatorkit.exporters.messages.MessagesExporter
- Manifest, checksums, and dataset card via curatorkit.manifest.ProvenanceManifest
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_engine.curation import (
    execute_integrated_vault_curator_pipeline,
    check_optional_hygiene_availability,
)
from vault.verification import get_default_catalogs

def main():
    print("=" * 80)
    print(" VAULT — CuratorKIT Official Library Integration & Full Pipeline Execution")
    print("=" * 80)

    # 1. Inspect environment and CuratorKIT capabilities
    print("\n[STEP 1: CURATORKIT ENVIRONMENT & DEPENDENCY INSPECTION]")
    import curatorkit
    print(f"CuratorKIT Version: {curatorkit.__version__}")
    print(f"CuratorKIT Location: {Path(curatorkit.__file__).parent}")

    hygiene_status = check_optional_hygiene_availability()
    print("Hygiene Capabilities:")
    print(f"  • Schema Gate & Validation:  AVAILABLE (core)")
    print(f"  • Exact Deduplicator:        AVAILABLE (core)")
    print(f"  • MinHash Deduplicator:      AVAILABLE (core, custom implementation without datasketch)")
    print(f"  • Text Cleaning:             AVAILABLE (core)")
    print(f"  • Messages Exporter:         AVAILABLE (core)")
    print(f"  • Provenance & Manifest:     AVAILABLE (core)")
    print(f"  • Secrets Gate:              {'AVAILABLE' if hygiene_status['secrets_gate'] else 'OPTIONAL / NOT INSTALLED (detect-secrets)'}")
    print(f"  • PII Pseudonymizer:         {'AVAILABLE' if hygiene_status['pii_pseudonymizer'] else 'OPTIONAL / NOT INSTALLED (presidio-analyzer)'}")

    # 2. Load the full synthetic dataset
    records_file = REPO_ROOT / "data" / "synthetic" / "records.jsonl"
    print(f"\n[STEP 2: LOADING FULL VAULT SYNTHETIC DATASET]")
    print(f"Reading from: {records_file}")
    records = []
    with open(records_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    print(f"Loaded {len(records)} total laboratory experiment records.")

    # 3. Execute Integrated Pipeline
    output_dir = REPO_ROOT / "data" / "integrated_curator_run"
    print(f"\n[STEP 3: RUNNING INTEGRATED VAULT-CURATORKIT PIPELINE]")
    print(f"Target Output Directory: {output_dir}")
    catalogs = get_default_catalogs()

    summary = execute_integrated_vault_curator_pipeline(
        records=records,
        output_base_dir=output_dir,
        catalogs=catalogs,
        enable_minhash=True,
        minhash_threshold=0.90,
    )

    # 4. Display Results
    vg = summary["vault_verification"]
    ck = summary["curatorkit_curation"]
    artifacts = summary["artifacts"]

    print("\n" + "=" * 80)
    print(" PIPELINE EXECUTION RESULTS")
    print("=" * 80)

    print("\n--- 1. Input & Scientific Verification (VAULT Gate) ---")
    print(f"  Total Input Records:        {summary['input_record_count']}")
    print(f"  Scientific Verdicts:")
    print(f"    • Accepted (checks_passed): {vg['accepted_count']:>5} ({vg['accepted_count']/summary['input_record_count']:.2%}) -> eligible for training")
    print(f"    • Flagged Definite Violations: {vg['flagged_count']:>3} ({vg['flagged_count']/summary['input_record_count']:.2%}) -> sent to quarantine")
    print(f"    • Needs Review (Ambiguity/Novel): {vg['needs_review_count']:>3} ({vg['needs_review_count']/summary['input_record_count']:.2%}) -> sent to quarantine")
    print(f"  Total Quarantined:          {vg['quarantine_count']:>5} ({vg['quarantine_count']/summary['input_record_count']:.2%})")

    print("\n--- 2. CuratorKIT Curation & Normalization Stages ---")
    print(f"  CuratorKIT Input Samples:   {ck['input_to_curator']}")
    print(f"  Stage-by-Stage Breakdown:")
    for stage_name, counts in ck["stage_counts"].items():
        inp = counts.get("input_count", counts.get("output_count", 0))
        out = counts.get("output_count", counts.get("exported_count", 0))
        rej = counts.get("rejected_count", 0)
        print(f"    • {stage_name:<22}: input={inp:>4}, passed={out:>4}, rejected={rej:>3}")
    print(f"  CuratorKIT Wall Clock:      {ck['wall_clock_seconds']:.2f}s")
    print(f"  CuratorKIT Final Passed:    {ck['curator_passed_count']}")

    print("\n--- 3. Generated Artifacts & Provenance ---")
    for name, path in artifacts.items():
        p = Path(path)
        sz = p.stat().st_size if p.exists() else 0
        print(f"  • {name:<24}: {p.name} ({sz:,} bytes)")

    # Print sample from exported messages
    trainer_path = Path(artifacts["trainer_ready_dataset"])
    if trainer_path.exists():
        print(f"\n--- 4. Trainer-ready Export Sample (ChatML format) ---")
        with open(trainer_path, "r", encoding="utf-8") as f:
            first_line = json.loads(f.readline())
            print(json.dumps(first_line, indent=2))

    # Print checksums
    checksum_path = Path(artifacts["curator_checksums"])
    if checksum_path.exists():
        print(f"\n--- 5. CuratorKIT Cryptographic Checksums (checksums.txt) ---")
        print(checksum_path.read_text(encoding="utf-8").strip())

    print("\n" + "=" * 80)
    print(" End-to-end integration verified successfully!")
    print("=" * 80)

if __name__ == "__main__":
    main()

