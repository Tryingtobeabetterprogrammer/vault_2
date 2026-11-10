"""Synthetic Fixtures for V4 Teacher-Text Round-Trip Verification.

Provides comprehensive synthetic teacher-generated texts covering:
1. Correct compliant scientific explanation.
2. Wrong numerical values.
3. Incompatible/wrong units.
4. Equivalent valid units (unit conversion handling).
5. Incorrect execution date.
6. Missing context / omitted validation dimensions.
7. Unsupported compliance claim / hallucinated compliance.
8. Ambiguous / truncated text lacking experiment ID.
"""

from typing import Dict, Any


def get_roundtrip_fixtures() -> Dict[str, Dict[str, Any]]:
    """Return dictionary of synthetic teacher explanation fixtures with expected outcomes."""
    return {
        "correct_compliant": {
            "name": "Correct Compliant Explanation",
            "target_experiment_id": "EXP-0046",
            "text": (
                "Scientific Compliance Verification for EXP-0046 (pH Value):\n"
                "Verdict: COMPLIANT (PASS) under SOP-001 Clause CLAUSE-001.\n\n"
                "Evidence Breakdown:\n"
                "1. Standard Operating Procedure: SOP version '1.0' is valid and authorized on 2025-01-15.\n"
                "2. Equipment Calibration (INST-017): Instrument calibration is valid through 2026-07-11 (inclusive).\n"
                "3. Reagent Quality (LOT-026): Reagent lot is valid through 2026-08-20 (inclusive).\n"
                "4. Sample Integrity (SMP-0001): Sample analyzed within holding time: 4.00 hours <= limit 24.00 hours.\n"
                "5. Measurement & Uncertainty: Uncertainty interval [7.53, 7.63] pH is within or on the inclusive specification boundaries [6.5, 8.5] pH.\n\n"
                "Conclusion: All 5 regulatory and physical compliance criteria are met without ambiguity or conflict."
            ),
            "expected_status": "passed",
            "expected_passed": True,
            "expected_reasons": [],
        },
        "wrong_numerical_value": {
            "name": "Wrong Numerical Values",
            "target_experiment_id": "EXP-0046",
            "text": (
                "Scientific Compliance Verification for EXP-0046 (pH Value):\n"
                "Verdict: COMPLIANT (PASS) under SOP-001 Clause CLAUSE-001.\n\n"
                "Evidence Breakdown:\n"
                "1. Standard Operating Procedure: SOP version '1.0' is valid and authorized on 2025-01-15.\n"
                "2. Equipment Calibration (INST-017): Instrument calibration is valid through 2026-07-11 (inclusive).\n"
                "3. Reagent Quality (LOT-026): Reagent lot is valid through 2026-08-20 (inclusive).\n"
                "4. Sample Integrity (SMP-0001): Sample analyzed within holding time: 4.00 hours <= limit 24.00 hours.\n"
                "5. Measurement & Uncertainty: Uncertainty interval [9.53, 9.63] pH is within or on the inclusive specification boundaries [6.5, 8.5] pH.\n\n"
                "Conclusion: All 5 regulatory and physical compliance criteria are met without ambiguity or conflict."
            ),
            "expected_status": "rejected",
            "expected_passed": False,
            "expected_reasons": ["TEACHER_NUMERICAL_MISMATCH"],
        },
        "wrong_units": {
            "name": "Incompatible Units",
            "target_experiment_id": "EXP-0046",
            "text": (
                "Scientific Compliance Verification for EXP-0046 (pH Value):\n"
                "Verdict: COMPLIANT (PASS) under SOP-001 Clause CLAUSE-001.\n\n"
                "Evidence Breakdown:\n"
                "1. Standard Operating Procedure: SOP version '1.0' is valid and authorized on 2025-01-15.\n"
                "2. Equipment Calibration (INST-017): Instrument calibration is valid through 2026-07-11 (inclusive).\n"
                "3. Reagent Quality (LOT-026): Reagent lot is valid through 2026-08-20 (inclusive).\n"
                "4. Sample Integrity (SMP-0001): Sample analyzed within holding time: 4.00 hours <= limit 24.00 hours.\n"
                "5. Measurement & Uncertainty: Uncertainty interval [7.53, 7.63] lightyears is within or on the inclusive specification boundaries [6.5, 8.5] lightyears.\n\n"
                "Conclusion: All 5 regulatory and physical compliance criteria are met without ambiguity or conflict."
            ),
            "expected_status": "rejected",
            "expected_passed": False,
            "expected_reasons": ["TEACHER_UNIT_MISMATCH"],
        },
        "equivalent_valid_units": {
            "name": "Equivalent Valid Units (Conversion Accepted)",
            "target_experiment_id": "EXP-0359",
            "text": (
                "Scientific Compliance Verification for EXP-0359 (Fluoride Content):\n"
                "Verdict: COMPLIANT (PASS) under SOP-004 Clause CLAUSE-020.\n\n"
                "Evidence Breakdown:\n"
                "1. Standard Operating Procedure: SOP version '1.0' is valid and authorized on 2025-03-26.\n"
                "2. Equipment Calibration (INST-012): Instrument calibration is valid through 2026-08-05 (inclusive).\n"
                "3. Reagent Quality (LOT-016): Reagent lot is valid through 2026-08-10 (inclusive).\n"
                "4. Sample Integrity (SMP-0053): Sample analyzed within holding time: 6.00 hours <= limit 48.00 hours.\n"
                "5. Measurement & Uncertainty: Uncertainty interval [1305.79, 1345.79] ug/L is within or on the inclusive specification boundaries [100.0, 2000.0] ug/L.\n\n"
                "Conclusion: All 5 regulatory and physical compliance criteria are met without ambiguity or conflict."
            ),
            "expected_status": "passed",
            "expected_passed": True,
            "expected_reasons": [],
        },
        "incorrect_date": {
            "name": "Incorrect Execution Date",
            "target_experiment_id": "EXP-0046",
            "text": (
                "Scientific Compliance Verification for EXP-0046 (pH Value):\n"
                "Verdict: COMPLIANT (PASS) under SOP-001 Clause CLAUSE-001.\n\n"
                "Evidence Breakdown:\n"
                "1. Standard Operating Procedure: SOP version '1.0' is valid and authorized on 2024-05-10.\n"
                "2. Equipment Calibration (INST-017): Instrument calibration is valid through 2026-07-11 (inclusive).\n"
                "3. Reagent Quality (LOT-026): Reagent lot is valid through 2026-08-20 (inclusive).\n"
                "4. Sample Integrity (SMP-0001): Sample analyzed within holding time: 4.00 hours <= limit 24.00 hours.\n"
                "5. Measurement & Uncertainty: Uncertainty interval [7.53, 7.63] pH is within or on the inclusive specification boundaries [6.5, 8.5] pH.\n\n"
                "Conclusion: All 5 regulatory and physical compliance criteria are met without ambiguity or conflict."
            ),
            "expected_status": "rejected",
            "expected_passed": False,
            "expected_reasons": ["TEACHER_DATE_MISMATCH"],
        },
        "missing_context": {
            "name": "Missing Context / Omitted Dimensions",
            "target_experiment_id": "EXP-0046",
            "text": (
                "Scientific Compliance Verification for EXP-0046 (pH Value):\n"
                "Verdict: COMPLIANT (PASS) under SOP-001 Clause CLAUSE-001.\n\n"
                "Evidence Breakdown:\n"
                "1. Standard Operating Procedure: SOP version '1.0' is valid and authorized on 2025-01-15.\n"
                "5. Measurement & Uncertainty: Uncertainty interval [7.53, 7.63] pH is within or on the inclusive specification boundaries [6.5, 8.5] pH.\n\n"
                "Conclusion: Evaluated parameter satisfies nominal specifications."
            ),
            "expected_status": "rejected",
            "expected_passed": False,
            "expected_reasons": ["TEACHER_MISSING_CRITICAL_FIELD"],
        },
        "unsupported_claim": {
            "name": "Unsupported Compliance Claim / Hallucinated Compliance",
            "target_experiment_id": "EXP-0001",
            "text": (
                "Scientific Compliance Verification for EXP-0001 (Lead Content):\n"
                "Verdict: COMPLIANT (PASS) under SOP-003 Clause CLAUSE-014.\n\n"
                "Evidence Breakdown:\n"
                "1. Standard Operating Procedure: SOP version '1.0' is valid and authorized on 2024-09-18.\n"
                "2. Equipment Calibration (INST-005): Instrument calibration is valid through 2026-01-01 (inclusive).\n"
                "3. Reagent Quality (LOT-001): Reagent lot is valid through 2026-01-01 (inclusive).\n"
                "4. Sample Integrity (SMP-0041): Sample analyzed within holding time: 4.00 hours <= limit 48.00 hours.\n"
                "5. Measurement & Uncertainty: Uncertainty interval [0.0040, 0.0064] mg/L is within or on the inclusive specification boundaries [0.0005, 0.01] mg/L.\n\n"
                "Conclusion: All criteria satisfied."
            ),
            "expected_status": "rejected",
            "expected_passed": False,
            "expected_reasons": ["TEACHER_VERDICT_MISMATCH", "TEACHER_UNSUPPORTED_COMPLIANCE_CLAIM"],
        },
        "ambiguous_text": {
            "name": "Ambiguous / Truncated Text",
            "target_experiment_id": None,
            "text": (
                "The pH reading looked normal and calibration seems fine overall."
            ),
            "expected_status": "needs_review",
            "expected_passed": False,
            "expected_reasons": ["TEACHER_MISSING_EXPERIMENT_ID"],
        },
    }

