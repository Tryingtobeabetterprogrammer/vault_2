"""VAULT V2 Ground-Truth Ledger Generation Engine.

Applies the five deterministic validation rules to every experiment and assigns
the final verdict following strict precedence:
1. All five rules pass -> 'valid', abstain=False.
2. At least one definite rule failure exists and no unresolved review conditions -> 'invalid', abstain=False.
3. Any unresolved required evidence, ambiguity, conflict or needs_review result -> 'needs_review', abstain=True.

Critical guarantees:
- If a definite failure and an unresolved ambiguity occur together, final verdict is 'needs_review'.
- Every failure reason code and review reason code is preserved in the ledger.
- Never derives verdicts from scenario-family labels.
- Deterministic evaluation without floating-point artifacts or external calls.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from synth.rules_v2 import (
    get_v2_config,
    validate_sop_v2,
    validate_calibration_v2,
    validate_lot_v2,
    validate_holding_time_v2,
    validate_measurement_v2,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RAW_DIR = os.path.join(REPO_ROOT, "data", "raw_v2")
DEFAULT_GROUND_TRUTH_DIR = os.path.join(REPO_ROOT, "data", "ground_truth_v2")
DEFAULT_REPORTS_DIR = os.path.join(REPO_ROOT, "data", "reports_v2")


def evaluate_single_experiment_v2(
    exp: Dict[str, Any],
    sops: List[Dict[str, Any]],
    instruments: List[Dict[str, Any]],
    lots: List[Dict[str, Any]],
    samples: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute all five deterministic validation rules on a single experiment and resolve verdict."""
    cfg = config or get_v2_config()

    # 1. Execute all five deterministic rules
    r_sop = validate_sop_v2(experiment=exp, sops=sops, config=cfg)
    r_cal = validate_calibration_v2(experiment=exp, instruments=instruments, config=cfg)
    r_lot = validate_lot_v2(experiment=exp, lots=lots, config=cfg)
    r_hold = validate_holding_time_v2(experiment=exp, samples=samples, config=cfg)
    r_meas = validate_measurement_v2(experiment=exp, sops=sops, config=cfg)

    rule_results: Dict[str, Any] = {
        "sop": r_sop,
        "calibration": r_cal,
        "lot": r_lot,
        "holding_time": r_hold,
        "measurement": r_meas,
    }

    # 2. Collect statuses and reason codes
    failure_codes: List[str] = []
    review_codes: List[str] = []
    source_ids_set: set[str] = set()

    for r_name, r_out in rule_results.items():
        st = r_out.get("status")
        codes = r_out.get("reason_codes", [])
        srcs = r_out.get("source_ids", [])
        for sid in srcs:
            if sid:
                source_ids_set.add(str(sid))

        if st == "fail":
            failure_codes.extend(codes)
        elif st == "needs_review":
            review_codes.extend(codes)

    # Stable unique ordering
    failure_reason_codes = sorted(list(dict.fromkeys(failure_codes)))
    review_reason_codes = sorted(list(dict.fromkeys(review_codes)))
    all_reason_codes = sorted(list(dict.fromkeys(failure_codes + review_codes)))
    evidence_source_ids = sorted(list(source_ids_set))

    # 3. Determine final verdict via strict precedence
    statuses = [r["status"] for r in rule_results.values()]

    if any(s == "needs_review" for s in statuses):
        final_verdict = "needs_review"
        abstain = True
    elif any(s == "fail" for s in statuses):
        final_verdict = "invalid"
        abstain = False
    elif all(s == "pass" for s in statuses):
        final_verdict = "valid"
        abstain = False
    else:
        # Fallback for unexpected status
        final_verdict = "needs_review"
        abstain = True

    return {
        "experiment_id": exp.get("experiment_id"),
        "final_verdict": final_verdict,
        "abstain": abstain,
        "rule_results": rule_results,
        "failure_reason_codes": failure_reason_codes,
        "review_reason_codes": review_reason_codes,
        "all_reason_codes": all_reason_codes,
        "evidence_source_ids": evidence_source_ids,
        "scenario_family": exp.get("scenario_family", "UNKNOWN"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_summary_v2(
    ledger_records: List[Dict[str, Any]],
    raw_experiments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Compute comprehensive summary metrics from generated V2 ground truth ledger records."""
    total = len(ledger_records)
    v_counts = {"valid": 0, "invalid": 0, "needs_review": 0}
    abstain_cnt = 0

    rule_names = ["sop", "calibration", "lot", "holding_time", "measurement"]
    rule_status_counts: Dict[str, Dict[str, int]] = {
        rn: {"pass": 0, "fail": 0, "needs_review": 0} for rn in rule_names
    }

    reason_freqs: Dict[str, int] = {}
    family_verdict_dist: Dict[str, Dict[str, int]] = {}

    compound_failure_count = 0
    compound_review_count = 0
    compound_fail_and_review_count = 0
    broken_ref_count = 0
    missing_ref_count = 0

    exp_ids = set()
    for rec in ledger_records:
        eid = rec["experiment_id"]
        exp_ids.add(eid)
        v = rec["final_verdict"]
        v_counts[v] = v_counts.get(v, 0) + 1
        if rec.get("abstain", False):
            abstain_cnt += 1

        fam = rec.get("scenario_family", "UNKNOWN")
        if fam not in family_verdict_dist:
            family_verdict_dist[fam] = {"valid": 0, "invalid": 0, "needs_review": 0}
        family_verdict_dist[fam][v] = family_verdict_dist[fam].get(v, 0) + 1

        # Rule level counts
        fail_rules = 0
        review_rules = 0
        for rn in rule_names:
            st = rec.get("rule_results", {}).get(rn, {}).get("status", "unknown")
            if st in rule_status_counts[rn]:
                rule_status_counts[rn][st] += 1
            if st == "fail":
                fail_rules += 1
            elif st == "needs_review":
                review_rules += 1

        if fail_rules >= 2:
            compound_failure_count += 1
        if review_rules >= 2:
            compound_review_count += 1
        if fail_rules >= 1 and review_rules >= 1:
            compound_fail_and_review_count += 1

        # Reason code frequencies
        for code in rec.get("all_reason_codes", []):
            reason_freqs[code] = reason_freqs.get(code, 0) + 1
            if "FOREIGN_KEY_NOT_FOUND" in code:
                broken_ref_count += 1
            if "MISSING_" in code:
                missing_ref_count += 1

    unprocessed = 0
    if raw_experiments:
        unprocessed = len(raw_experiments) - len(exp_ids)

    valid_pct = round((v_counts["valid"] / total * 100.0), 2) if total > 0 else 0.0
    invalid_pct = round((v_counts["invalid"] / total * 100.0), 2) if total > 0 else 0.0
    review_pct = round((v_counts["needs_review"] / total * 100.0), 2) if total > 0 else 0.0

    return {
        "version": "2.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_experiments_processed": total,
        "verdict_distribution": {
            "valid": v_counts["valid"],
            "invalid": v_counts["invalid"],
            "needs_review": v_counts["needs_review"],
        },
        "verdict_percentages": {
            "valid_pct": valid_pct,
            "invalid_pct": invalid_pct,
            "needs_review_pct": review_pct,
        },
        "abstain_count": abstain_cnt,
        "rule_level_outcomes": rule_status_counts,
        "reason_code_frequencies": reason_freqs,
        "scenario_family_verdict_distribution": family_verdict_dist,
        "compound_scenarios": {
            "multi_failure_records": compound_failure_count,
            "multi_review_records": compound_review_count,
            "coexisting_fail_and_review_records": compound_fail_and_review_count,
        },
        "data_integrity_metrics": {
            "missing_evidence_reasons_count": missing_ref_count,
            "broken_foreign_key_reasons_count": broken_ref_count,
            "unprocessed_experiments": unprocessed,
        },
    }


def build_ground_truth_ledger_v2(
    raw_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
    reports_dir: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, Dict[str, Any]]:
    """Build the ground-truth ledger and summary JSON from raw V2 datasets."""
    in_dir = raw_dir or DEFAULT_RAW_DIR
    out_dir = output_dir or DEFAULT_GROUND_TRUTH_DIR
    rep_dir = reports_dir or DEFAULT_REPORTS_DIR

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(rep_dir, exist_ok=True)

    # 1. Load catalogs
    def load_jsonl(filename: str) -> List[Dict[str, Any]]:
        p = os.path.join(in_dir, filename)
        records = []
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    records.append(json.loads(line_str))
        return records

    sops = load_jsonl("sops_v2.jsonl")
    instruments = load_jsonl("instruments_v2.jsonl")
    lots = load_jsonl("lots_v2.jsonl")
    samples = load_jsonl("samples_v2.jsonl")
    experiments = load_jsonl("experiments_v2.jsonl")

    # 2. Evaluate all experiments
    cfg = config or get_v2_config()
    ledger_records: List[Dict[str, Any]] = []

    for exp in experiments:
        ledger_rec = evaluate_single_experiment_v2(
            exp=exp,
            sops=sops,
            instruments=instruments,
            lots=lots,
            samples=samples,
            config=cfg,
        )
        ledger_records.append(ledger_rec)

    # 3. Write ground truth ledger JSONL
    ledger_path = os.path.join(out_dir, "ground_truth_ledger_v2.jsonl")
    with open(ledger_path, "w", encoding="utf-8") as f:
        for rec in ledger_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # 4. Generate and write summary JSON
    summary_data = generate_summary_v2(ledger_records, raw_experiments=experiments)
    summary_path = os.path.join(rep_dir, "ground_truth_summary_v2.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)

    return ledger_path, summary_path, summary_data

