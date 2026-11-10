#!/usr/bin/env python3
"""VAULT Demonstration Runner.

Executes deterministic verification against the four mandatory Scintest scientific fixtures:
1. Arithmetic contradiction
2. Retrospective audit
3. Valid alternative method
4. Novel method

Usage:
    python -m scripts.run_demo
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from vault.verification import verify_record, get_default_catalogs
from vault.memory import ScientificMemory
from vault.examples import (
    get_arithmetic_contradiction_fixture,
    get_retrospective_audit_fixture,
    get_valid_alternative_method_fixture,
    get_novel_method_fixture,
)


def run_demo() -> None:
    print("=" * 72)
    print(" VAULT — Evidence-Gated Laboratory Verification Demo (Tiny Aya RC)")
    print(" Fictional Scintest Research Labs | Scientific Data Substrate")
    print("=" * 72)

    catalogs = get_default_catalogs()
    memory = ScientificMemory(storage_dir="data/memory")

    # Fixture 1: Arithmetic contradiction
    print("\n[FIXTURE 1: Arithmetic Contradiction]")
    f1 = get_arithmetic_contradiction_fixture()
    print(f"Record: {f1['record_id']} | Reported: {f1['reported_mass']} mg / {f1['reported_volume']} L as {f1['measured_value']} {f1['measurement_unit']}")
    res1 = verify_record(f1, catalogs)
    print(f"Verdict: {res1['verdict'].upper()} | Status: {res1['status']} | Abstain: {res1['abstain']}")
    print(f"Issues:  {res1['issues']}")
    for ev in res1["evidence"]:
        if ev["rule_name"] == "arithmetic_verification":
            print(f"Evidence: {ev['details']}")

    # Fixture 2: Retrospective audit
    print("\n[FIXTURE 2: Retrospective Audit Invalidation]")
    f2_data = get_retrospective_audit_fixture()
    f2_rec = f2_data["original_record"]
    f2_audit = f2_data["audit_dispute"]

    # Initial intake
    memory.register_source(f2_rec["record_id"], f2_rec)
    res2_init = verify_record(f2_rec, catalogs)
    memory.record_assessment(res2_init)
    print(f"Initial Verdict: {res2_init['verdict'].upper()} | Status: {res2_init['status']}")

    # Subsequent calibration audit
    print(f"Audit event {f2_audit['audit_event_id']} detects drift on {f2_audit['drift_detected_date']}.")
    res2_disp = memory.record_retrospective_dispute(
        record_id=f2_rec["record_id"],
        prior_assessment_id=res2_init["assessment_id"],
        dispute_reason=f2_audit["dispute_reason"],
        audit_event_id=f2_audit["audit_event_id"],
        reviewer="Lead-Auditor-Scintest"
    )
    print(f"Updated Verdict: {res2_disp['verdict'].upper()} | Status: {res2_disp['status']} | Supersedes: {res2_disp['supersedes_id']}")
    print(f"Source hash immutable: {memory.get_source(f2_rec['record_id'])['source_hash'][:16]}...")

    # Fixture 3: Valid alternative method
    print("\n[FIXTURE 3: Valid Alternative Analytical Method]")
    f3 = get_valid_alternative_method_fixture()
    print(f"Record: {f3['record_id']} | Method: {f3['method_id']} (measuring bioavailable concentration)")
    res3 = verify_record(f3, catalogs)
    print(f"Verdict: {res3['verdict'].upper()} | Status: {res3['status']} | Abstain: {res3['abstain']}")
    for ev in res3["evidence"]:
        if ev["rule_name"] == "method_verification":
            print(f"Evidence: {ev['details']}")

    # Fixture 4: Novel method
    print("\n[FIXTURE 4: Novel Analytical Method (Safe Mechanical Check)]")
    f4 = get_novel_method_fixture()
    print(f"Record: {f4['record_id']} | Method: {f4['method_id']} (unvalidated research formula)")
    res4 = verify_record(f4, catalogs)
    print(f"Verdict: {res4['verdict'].upper()} | Status: {res4['status']} | Abstain: {res4['abstain']}")
    print(f"Issues:  {res4['issues']}")
    print("Action: Preserved for expert human review; NOT falsely rejected as error.")

    print("\n" + "=" * 72)
    print(" Demo complete: All 4 fixtures processed with deterministic audit trails.")
    print("=" * 72)


if __name__ == "__main__":
    run_demo()
