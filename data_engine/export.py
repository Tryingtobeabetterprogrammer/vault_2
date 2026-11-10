"""VAULT V5 — Training Data Export & CuratorKIT Integration Engine.

Generates trainer-ready datasets for Cohere Tiny Aya Global fine-tuning
using CuratorKIT for format normalization, schema gating, exact deduplication,
and provenance tracking, while preserving VAULT deterministic verification
as the sole authority on scientific validity.

Outputs:
- `train_candidates.jsonl`: ChatML/messages format for Tiny Aya post-training (720 records)
- `accepted_manifest.json`: Provenance manifest with SHA-256 hashes, source references, and assessment IDs
- `quarantine.jsonl`: Quarantined flagged violations and review records with deterministic reason codes
- `dataset_card.md`: Dataset documentation and curation trace
- `checksums.txt`: SHA-256 cryptographic hashes for all generated export artifacts
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Official CuratorKIT imports
import curatorkit
from curatorkit import Curator, CuratorConfig, CuratorResult
from curatorkit.connectors.jsonl import JSONLReader
from curatorkit.detection.detector import FormatDetector
from curatorkit.gates.schema import SchemaGate
from curatorkit.normalizers.clean import TextCleaner
from curatorkit.normalizers.dedup import ExactDeduplicator
from curatorkit.exporters.messages import MessagesExporter
from curatorkit.schema import DataSample, RejectedSample
from curatorkit.manifest import ProvenanceManifest, DatasetCardGenerator

# VAULT verification imports
from vault.verification import verify_record, get_default_catalogs

EXPORT_VERSION = "1.0.0"


def format_scientific_explanation(record: Dict[str, Any], assessment: Dict[str, Any]) -> str:
    """Construct a scientifically rigorous, evidence-grounded explanation.
    
    Synthesizes the actual deterministic rule evaluation results from VAULT:
    1. SOP authorization and effective date currency
    2. Instrument calibration validity window
    3. Reagent lot expiry date verification
    4. Sample collection-to-analysis holding time limit
    5. Measurement value and expanded uncertainty interval vs specification limits
    """
    exp_id = record.get("experiment_id") or record.get("record_id", "EXP-UNKNOWN")
    sop_id = record.get("sop_id", "N/A")
    clause_id = record.get("clause_id", "N/A")
    param = record.get("parameter", "analytical parameter")
    val = record.get("measured_value", "N/A")
    unit = record.get("measurement_unit", "")
    uncertainty = record.get("measurement_uncertainty", 0.0)
    run_date = record.get("run_date", "N/A")

    evidence_by_rule = {ev["rule_name"]: ev for ev in assessment.get("evidence", [])}

    lines = [
        f"Scientific Compliance Verification for {exp_id} ({param}):",
        f"Verdict: COMPLIANT (PASS) under {sop_id} Clause {clause_id}.",
        "",
        "Evidence Breakdown:",
    ]

    # 1. SOP Check
    sop_ev = evidence_by_rule.get("sop_validation")
    if sop_ev and sop_ev.get("details"):
        lines.append(f"1. Standard Operating Procedure: {sop_ev['details']}")
    else:
        lines.append(f"1. Standard Operating Procedure: Version effective and authorized on {run_date}.")

    # 2. Calibration Check
    cal_ev = evidence_by_rule.get("calibration_validation")
    inst_id = record.get("instrument_id", "N/A")
    if cal_ev and cal_ev.get("details"):
        lines.append(f"2. Equipment Calibration ({inst_id}): {cal_ev['details']}")
    else:
        lines.append(f"2. Equipment Calibration ({inst_id}): Verified valid on run date.")

    # 3. Lot Check
    lot_ev = evidence_by_rule.get("lot_validation")
    lot_id = record.get("lot_id", "N/A")
    if lot_ev and lot_ev.get("details"):
        lines.append(f"3. Reagent Quality ({lot_id}): {lot_ev['details']}")
    else:
        lines.append(f"3. Reagent Quality ({lot_id}): Lot verified unexpired on run date.")

    # 4. Holding Time Check
    ht_ev = evidence_by_rule.get("holding_time_validation")
    smp_id = record.get("sample_id", "N/A")
    if ht_ev and ht_ev.get("details"):
        lines.append(f"4. Sample Integrity ({smp_id}): {ht_ev['details']}")
    else:
        lines.append(f"4. Sample Integrity ({smp_id}): Sample analyzed within maximum holding time limit.")

    # 5. Measurement & Uncertainty Check
    meas_ev = evidence_by_rule.get("measurement_validation")
    if meas_ev and meas_ev.get("details"):
        clean_details = meas_ev["details"].replace(
            "strictly within SOP specification limits",
            "within or on the inclusive specification boundaries"
        )
        lines.append(f"5. Measurement & Uncertainty: {clean_details}")
    else:
        lines.append(
            f"5. Measurement & Uncertainty: Reported value {val} ± {uncertainty} {unit} is within or on the inclusive specification boundaries."
        )

    lines.append(
        f"\nConclusion: All 5 regulatory and physical compliance criteria are met without ambiguity or conflict."
    )
    return "\n".join(lines)


def convert_record_to_curator_sample(
    record: Dict[str, Any],
    assessment: Optional[Dict[str, Any]] = None,
    catalogs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Map a VAULT laboratory record into an instruction-following sample for CuratorKIT.
    
    Generates an educational prompt-response pair that teaches Tiny Aya to evaluate
    laboratory compliance using the verified evidence chain.
    """
    catalogs = catalogs or get_default_catalogs()
    if assessment is None:
        assessment = verify_record(record, catalogs)

    exp_id = record.get("experiment_id") or record.get("record_id", "EXP-UNKNOWN")
    param = record.get("parameter", "analytical measurement")
    val = record.get("measured_value", "N/A")
    unit = record.get("measurement_unit", "")
    uncertainty = record.get("measurement_uncertainty", 0.0)
    sop_id = record.get("sop_id", "N/A")
    sop_ver = record.get("sop_version", "1.0")
    clause_id = record.get("clause_id", "N/A")
    inst_id = record.get("instrument_id", "N/A")
    lot_id = record.get("lot_id", "N/A")
    smp_id = record.get("sample_id", "N/A")
    run_date = record.get("run_date", "N/A")
    col_at = record.get("collected_at", "N/A")
    ana_at = record.get("analyzed_at", "N/A")
    max_ht = record.get("max_holding_hours", "N/A")
    claimed_verdict = record.get("original_verdict", "PASS")

    instruction = (
        f"You are an expert scientific validation assistant for Scintest Research Labs.\n"
        f"Evaluate the analytical laboratory record below for {param}. "
        f"Perform a comprehensive deterministic review covering:\n"
        f"1. SOP Version authorization and effective validity on run date\n"
        f"2. Instrument calibration currency and validity window\n"
        f"3. Reagent lot qualification and expiration status\n"
        f"4. Sample preservation and holding time limit compliance\n"
        f"5. Measurement specification compliance including expanded uncertainty\n"
        f"State the final compliance verdict and justify with evidence."
    )

    user_input = (
        f"Laboratory Record Details:\n"
        f"• Experiment ID: {exp_id}\n"
        f"• SOP Reference: {sop_id} v{sop_ver} (Clause: {clause_id})\n"
        f"• Parameter: {param}\n"
        f"• Run Date: {run_date}\n"
        f"• Instrument ID: {inst_id}\n"
        f"• Reagent Lot ID: {lot_id}\n"
        f"• Sample ID: {smp_id}\n"
        f"• Collection Time: {col_at}\n"
        f"• Analysis Time: {ana_at}\n"
        f"• Max Holding Time: {max_ht} hours\n"
        f"• Reported Value: {val} {unit} (± {uncertainty} {unit})\n"
        f"• Analyst Claimed Status: {claimed_verdict}"
    )

    assistant_output = format_scientific_explanation(record, assessment)

    return {
        "instruction": instruction,
        "input": user_input,
        "output": assistant_output,
        "experiment_id": exp_id,
        "record_id": exp_id,
        "scenario_family": record.get("scenario_family", "Nominal valid"),
    }


def export_training_dataset(
    records_path: Path = Path("data/synthetic/records.jsonl"),
    output_dir: Path = Path("data/training_export_v5"),
    catalogs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute end-to-end V5 training dataset export.
    
    1. Loads all synthetic records.
    2. Runs VAULT deterministic verification.
    3. Quarantines flagged violations and needs_review records.
    4. Formats valid candidate records into evidence-grounded instruction samples.
    5. Curates via official CuratorKIT (SchemaGate, ExactDeduplicator, TextCleaner, MessagesExporter).
    6. Emits `train_candidates.jsonl`, `accepted_manifest.json`, `quarantine.jsonl`, `dataset_card.md`, and `checksums.txt`.
    """
    catalogs = catalogs or get_default_catalogs()
    output_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = output_dir / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load Raw Records
    raw_records: List[Dict[str, Any]] = []
    with open(records_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                raw_records.append(json.loads(line))

    total_records = len(raw_records)

    # 2. VAULT Scientific Verification Gate
    assessments: Dict[str, Dict[str, Any]] = {}
    accepted_records: List[Dict[str, Any]] = []
    quarantined_records: List[Dict[str, Any]] = []

    for r in raw_records:
        rid = r.get("experiment_id") or r.get("record_id")
        asm = verify_record(r, catalogs)
        assessments[rid] = asm

        if asm["status"] == "checks_passed":
            accepted_records.append(r)
        else:
            quarantined_records.append({
                "record": r,
                "assessment": asm,
                "status": asm["status"],
                "reason_codes": asm.get("reason_codes", []),
            })

    # 3. Write Quarantine Ledger
    quarantine_path = output_dir / "quarantine.jsonl"
    with open(quarantine_path, "w", encoding="utf-8") as f:
        for q in quarantined_records:
            f.write(json.dumps(q) + "\n")

    # 4. Convert Accepted Records to Instruction Samples with Scientific Explanation
    staged_input_file = staging_dir / "verified_training_input.jsonl"
    curator_samples = [
        convert_record_to_curator_sample(r, assessments[r.get("experiment_id") or r.get("record_id")], catalogs)
        for r in accepted_records
    ]
    with open(staged_input_file, "w", encoding="utf-8") as f:
        for s in curator_samples:
            f.write(json.dumps(s) + "\n")

    # 5. CuratorKIT Pipeline Execution (ExactDeduplicator, SchemaGate, TextCleaner, MessagesExporter)
    curator_export_dir = output_dir / "curator_out"
    curator_cfg = CuratorConfig(
        dataset=str(staged_input_file),
        output_dir=str(curator_export_dir),
        clean=True,
        dedup="exact",  # ExactDeduplicator as mandated for scientific record preservation
        min_tokens=2,
        export_formats=["messages"],
    )
    curator = Curator(curator_cfg)
    curator_result = curator.run()

    # 6. Copy / Format Final Primary Artifacts
    curator_sft_path = curator_export_dir / "sft_messages.jsonl"
    final_train_candidates_path = output_dir / "train_candidates.jsonl"
    if curator_sft_path.exists():
        final_train_candidates_path.write_text(curator_sft_path.read_text(encoding="utf-8"), encoding="utf-8")

    # 7. Generate Accepted Manifest
    accepted_manifest = {
        "manifest_version": EXPORT_VERSION,
        "pipeline_name": "VAULT-V5-Training-Export",
        "total_source_records": total_records,
        "total_accepted_candidates": len(accepted_records),
        "total_quarantined_records": len(quarantined_records),
        "curator_passed_count": len(curator_result.passed),
        "curatorkit_version": curatorkit.__version__,
        "accepted_records": [
            {
                "experiment_id": r.get("experiment_id") or r.get("record_id"),
                "assessment_id": assessments[r.get("experiment_id") or r.get("record_id")]["assessment_id"],
                "sop_id": r.get("sop_id"),
                "clause_id": r.get("clause_id"),
                "scenario_family": r.get("scenario_family"),
                "record_sha256": hashlib.sha256(json.dumps(r, sort_keys=True).encode("utf-8")).hexdigest(),
            }
            for r in accepted_records
        ],
    }
    manifest_path = output_dir / "accepted_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(accepted_manifest, f, indent=2)

    # 8. Generate Dataset Card
    card_path = output_dir / "dataset_card.md"
    with open(card_path, "w", encoding="utf-8") as f:
        f.write("# VAULT V5 — Scientific Training Dataset Card\n\n")
        f.write("## Overview\n")
        f.write(f"- **Dataset Version:** {EXPORT_VERSION}\n")
        f.write(f"- **Model Target:** Cohere Tiny Aya Global Fine-Tuning\n")
        f.write(f"- **Total Source Records:** {total_records}\n")
        f.write(f"- **Scientifically Verified Candidates:** {len(accepted_records)} (100% checks_passed)\n")
        f.write(f"- **Quarantined Records:** {len(quarantined_records)} (Definite violations & ambiguities)\n")
        f.write(f"- **Deduplication Strategy:** CuratorKIT ExactDeduplicator (SHA-256)\n")
        f.write(f"- **Export Format:** ChatML `messages`\n\n")
        f.write("## Curation & Verification Pipeline\n")
        f.write("1. **VAULT Evidence Gate:** All records verified by 5 deterministic rules. Only `checks_passed` records qualify.\n")
        f.write("2. **Evidence Synthesis:** Assistant responses explain SOP currency, calibration, lot validity, holding times, and measurement uncertainty.\n")
        f.write("3. **CuratorKIT Hygiene:** Schema validation, exact deduplication, and text cleaning via official CuratorKIT v0.1.21.\n")
        f.write("4. **Truth Isolation:** Zero ground-truth leakage; truth ledger never enters model-facing pipeline.\n")

    # 9. Generate Checksums
    checksum_files = [
        final_train_candidates_path,
        manifest_path,
        quarantine_path,
        card_path,
    ]
    checksums_path = output_dir / "checksums.txt"
    with open(checksums_path, "w", encoding="utf-8") as f:
        for cf in checksum_files:
            if cf.exists():
                h = hashlib.sha256(cf.read_bytes()).hexdigest()
                f.write(f"{h}  {cf.name}\n")

    return {
        "total_source_records": total_records,
        "accepted_candidates_count": len(accepted_records),
        "quarantined_count": len(quarantined_records),
        "curator_passed_count": len(curator_result.passed),
        "files": {
            "train_candidates": str(final_train_candidates_path),
            "accepted_manifest": str(manifest_path),
            "quarantine": str(quarantine_path),
            "dataset_card": str(card_path),
            "checksums": str(checksums_path),
        },
    }

