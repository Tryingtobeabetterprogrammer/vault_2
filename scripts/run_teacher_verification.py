#!/usr/bin/env python3
"""Run V4 Teacher-Text Round-Trip Verification Benchmark.

Evaluates the round-trip verifier against:
1. Synthetic benchmark fixtures (clean, wrong values, wrong units, dates, omitted context, hallucinations, ambiguity).
2. The V5 certified training candidate explanations in `train_candidates.jsonl`.
3. Computes confusion matrix, precision, recall, and generates a structured benchmark report.
"""

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_engine.roundtrip import TeacherTextVerifier, gate_teacher_candidate
from data_engine.fixtures_roundtrip import get_roundtrip_fixtures


def run_benchmark():
    print("=" * 76)
    print(" VAULT V4 — Teacher-Text Round-Trip Verification Benchmark")
    print("=" * 76)

    truth_ledger_path = REPO_ROOT / "data" / "synthetic" / "truth_ledger.jsonl"
    verifier = TeacherTextVerifier(truth_ledger_path=str(truth_ledger_path))

    # 1. Run on synthetic fixtures
    fixtures = get_roundtrip_fixtures()
    print(f"\n[PHASE 1: SYNTHETIC FIXTURES EVALUATION ({len(fixtures)} cases)]")

    tp, fp, tn, fn = 0, 0, 0, 0
    results_summary = []

    for key, fix in fixtures.items():
        res = verifier.verify_explanation(fix["text"])
        is_actually_valid = fix["expected_passed"]
        predicted_valid = res.passed

        if is_actually_valid and predicted_valid:
            tp += 1
            verdict_str = "TP (Correctly Accepted)"
        elif not is_actually_valid and not predicted_valid:
            tn += 1
            verdict_str = f"TN (Correctly Quarantined: {res.status})"
        elif not is_actually_valid and predicted_valid:
            fp += 1
            verdict_str = "FP (False Admission - ERROR)"
        elif is_actually_valid and not predicted_valid:
            fn += 1
            verdict_str = "FN (False Rejection - ERROR)"

        print(f"  • {fix['name']:<42} -> {res.status.upper():<12} [{verdict_str}]")
        if res.reason_codes:
            print(f"    Reasons: {res.reason_codes}")

        results_summary.append({
            "fixture": key,
            "name": fix["name"],
            "expected_passed": is_actually_valid,
            "predicted_passed": predicted_valid,
            "status": res.status,
            "reason_codes": res.reason_codes,
            "details": res.details,
        })

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0

    print("\n[FIXTURE METRICS]")
    print(f"  True Positives (TP) : {tp}")
    print(f"  True Negatives (TN) : {tn}")
    print(f"  False Positives (FP): {fp}")
    print(f"  False Negatives (FN): {fn}")
    print(f"  Precision           : {precision * 100:.2f}%")
    print(f"  Recall              : {recall * 100:.2f}%")

    assert fp == 0, f"False positives detected: {fp}"
    assert fn == 0, f"False negatives detected: {fn}"

    # 2. Run on V5 Training Candidates (720 records)
    train_file = REPO_ROOT / "data" / "training_export_v5" / "train_candidates.jsonl"
    print(f"\n[PHASE 2: V5 TRAINING CANDIDATES AUDIT ({train_file.name})]")

    verified_pass_count = 0
    rejected_count = 0
    needs_review_count = 0

    with open(train_file, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if line.strip():
                item = json.loads(line)
                assistant_msg = item["messages"][1]["content"]
                res = verifier.verify_explanation(assistant_msg)
                if res.status == "passed":
                    verified_pass_count += 1
                elif res.status == "rejected":
                    rejected_count += 1
                elif res.status == "needs_review":
                    needs_review_count += 1

    print(f"  Total Training Candidates Evaluated: {verified_pass_count + rejected_count + needs_review_count}")
    print(f"  100% Round-Trip Verified Passed    : {verified_pass_count}")
    print(f"  Rejected Explanations              : {rejected_count}")
    print(f"  Needs Review Explanations          : {needs_review_count}")

    assert verified_pass_count == 720, f"Expected 720 passed candidates, got {verified_pass_count}"
    assert rejected_count == 0, f"Found rejected candidate in training export: {rejected_count}"
    assert needs_review_count == 0, f"Found needs_review candidate in training export: {needs_review_count}"

    print("\n[GATEKEEPER INTEGRITY]")
    print("  All 720 certified training candidates successfully verified against truth ledger.")
    print("  Zero unverified, corrupted, or unsupported claims admitted.")

    # Save summary report JSON
    report_data = {
        "benchmark_metadata": {
            "total_fixtures": len(fixtures),
            "total_training_candidates_audited": verified_pass_count,
            "precision": precision,
            "recall": recall,
            "tp": tp,
            "tn": tn,
            "fp": fp,
            "fn": fn,
        },
        "fixture_evaluations": results_summary,
    }
    report_path = REPO_ROOT / "data" / "reports" / "roundtrip_verification_summary.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    print(f"\nReport JSON written to {report_path.relative_to(REPO_ROOT)}.")
    print("=" * 76)


if __name__ == "__main__":
    run_benchmark()

