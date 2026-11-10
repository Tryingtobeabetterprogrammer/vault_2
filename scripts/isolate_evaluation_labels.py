"""Isolate Evaluation Inputs from Evaluator Answer Keys.

Reads held_out_evaluation_set.jsonl and creates:
1. model_inputs.jsonl: Contains ONLY the model prompt and metadata needed to map predictions (eval_id, experiment_id). ZERO ground-truth labels.
2. evaluation_answer_key.jsonl: Evaluator-only ground truth key mapping eval_id to expected_verdict, abstain_required, reason_codes, and evidence_count.
"""

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

eval_dir = REPO_ROOT / "data" / "evaluation_held_out"
source_file = eval_dir / "held_out_evaluation_set.jsonl"

eval_records = [json.loads(line) for line in source_file.read_text(encoding="utf-8").splitlines() if line.strip()]

print(f"Loaded {len(eval_records)} evaluation records from {source_file.name}.")

# 1. Write model_inputs.jsonl (Strictly zero ground-truth labels)
model_inputs_file = eval_dir / "model_inputs.jsonl"
with open(model_inputs_file, "w", encoding="utf-8") as f:
    for item in eval_records:
        model_sample = {
            "eval_id": item["eval_id"],
            "experiment_id": item["experiment_id"],
            "prompt": item["prompt"],
        }
        f.write(json.dumps(model_sample) + "\n")

# 2. Write evaluation_answer_key.jsonl (Evaluator-only ground-truth key)
answer_key_file = eval_dir / "evaluation_answer_key.jsonl"
with open(answer_key_file, "w", encoding="utf-8") as f:
    for item in eval_records:
        key_entry = {
            "eval_id": item["eval_id"],
            "experiment_id": item["experiment_id"],
            "sop_id": item.get("sop_id"),
            "clause_id": item.get("clause_id"),
            "scenario_family": item.get("scenario_family"),
            "expected_verdict": item["ground_truth_target"]["expected_verdict"],
            "expected_status": item["ground_truth_target"]["expected_status"],
            "abstain_required": item["ground_truth_target"]["abstain_required"],
            "reason_codes": item["ground_truth_target"]["reason_codes"],
            "evidence_count": item["ground_truth_target"]["evidence_count"],
        }
        f.write(json.dumps(key_entry) + "\n")

# 3. Update checksums
checksum_file = eval_dir / "checksums.txt"
with open(checksum_file, "w", encoding="utf-8") as f:
    for target in [source_file, model_inputs_file, answer_key_file, eval_dir / "eval_manifest.json"]:
        if target.exists():
            h = hashlib.sha256(target.read_bytes()).hexdigest()
            f.write(f"{h}  {target.name}\n")

print(f"Evaluation dataset separated successfully:")
print(f"  • model_inputs.jsonl:           {model_inputs_file.stat().st_size:,} bytes (Zero labels)")
print(f"  • evaluation_answer_key.jsonl:  {answer_key_file.stat().st_size:,} bytes (Evaluator only)")
print(f"  • Updated checksums.txt:        {checksum_file.stat().st_size:,} bytes")

