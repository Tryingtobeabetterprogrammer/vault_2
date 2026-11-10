"""Inspection and Verification of 20 Random Samples from train_candidates.jsonl."""

import json
import random
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from vault.verification import verify_record, get_default_catalogs

catalogs = get_default_catalogs()

candidates_file = REPO_ROOT / "data" / "training_export_v5" / "train_candidates.jsonl"
samples = [json.loads(line) for line in candidates_file.read_text(encoding="utf-8").splitlines() if line.strip()]

print(f"Total training candidates loaded: {len(samples)}")
assert len(samples) == 720, f"Expected 720 records, got {len(samples)}"

# Sample 20 deterministically
rng = random.Random(42)
sampled = rng.sample(samples, 20)

print("\nAuditing 20 Randomly Selected SFT Samples:")
print("-" * 80)

audit_report = []

for idx, item in enumerate(sampled, start=1):
    user_content = item["messages"][0]["content"]
    asst_content = item["messages"][1]["content"]

    m = re.search(r"Experiment ID:\s*(EXP-\d+)", user_content)
    exp_id = m.group(1) if m else "UNKNOWN"

    # Verify presence of the 5 checks in explanation
    has_sop = "standard operating procedure:" in asst_content.lower()
    has_cal = "equipment calibration" in asst_content.lower()
    has_lot = "reagent quality" in asst_content.lower()
    has_ht = "sample integrity" in asst_content.lower()
    has_meas = "measurement & uncertainty:" in asst_content.lower()
    has_conclusion = "conclusion:" in asst_content.lower()

    all_5_present = all([has_sop, has_cal, has_lot, has_ht, has_meas, has_conclusion])

    audit_report.append({
        "sample_num": idx,
        "experiment_id": exp_id,
        "all_5_rules_explained": all_5_present,
        "explanation_snippet": asst_content.splitlines()[:5],
    })

    print(f"\n[Sample #{idx:>2}] {exp_id}")
    print(f"  All 5 checks clearly articulated: {all_5_present}")
    print(f"  Assistant excerpt:")
    for line in asst_content.splitlines()[:4]:
        print(f"    {line}")

print("\n" + "-" * 80)
all_passed = all(a["all_5_rules_explained"] for a in audit_report)
print(f"20/20 Samples Articulate Complete 5-Rule Verification Evidence: {all_passed}")
assert all_passed, "Some samples lacked complete rule explanations!"

# Save report
out_path = REPO_ROOT / "data" / "reports_v2" / "v5_20_sample_inspection.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(audit_report, f, indent=2)
print(f"Audit saved to: {out_path}")

