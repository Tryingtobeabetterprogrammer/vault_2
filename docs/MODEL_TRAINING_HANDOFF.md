# VAULT — Model Lead Fine-Tuning Handoff (Cohere Tiny Aya)

**Target Role:** Model Training Lead / ML Engineer  
**Dataset Version:** V5 Final Certified Export  
**Status:** Approved for Post-Training  
**Date:** 2026-11-09  

---

## 1. Executive Summary & Training Philosophy

This document provides complete instructions for fine-tuning **Cohere Tiny Aya** on the VAULT V5 Scientific Compliance Dataset.

### Core Training Philosophy: Positive-Only Explanatory Scope
1. **The LLM is an Explainer, NOT the Verifier:**  
   In VAULT's architecture, the deterministic verifier (`vault.verification.verify_record`) is the sole authority for PASS/FAIL decisions.
2. **Positive-Only SFT Scope:**  
   The training dataset consists exclusively of **720 verified compliant records (`checks_passed`)**. The model is trained to generate structured, auditable explanations showing how calibration currency, reagent lots, sample holding times, and expanded measurement uncertainties satisfy SOP specifications.
3. **Quarantine Isolation:**  
   All 480 defective or ambiguous records (`flagged` and `needs_review`) are strictly quarantined in `data/training_export_v5/quarantine.jsonl` and **never** fed into training. This prevents hallucinated explanations for non-compliant or ambiguous phenomena.

---

## 2. Dataset Files & Checksums

All certified dataset artifacts reside in `data/training_export_v5/`:

| Artifact | File Name | Size (Bytes) | SHA-256 Checksum | Description |
|---|---|---|---|---|
| **Training Candidates** | `train_candidates.jsonl` | 1,368,629 | `b7c20e71421ab47d17908a9b8d661414907b72db3070db10bcd57cb93858af48` | 720 trainer-ready ChatML records |
| **Accepted Manifest** | `accepted_manifest.json` | 210,847 | `452382f5bd3eb3eedd899fb3eea712da974ce5690309d4c0a05aae07712716b3` | Cryptographic ledger of all 720 accepted records |
| **Quarantine Ledger** | `quarantine.jsonl` | 1,083,296 | `9fa3102e8b4bdb5a65ab41d44f38eb89811352b3d6dfd8ee6b8b32925e687f4f` | 480 quarantined records with full defect reasons |
| **Dataset Card** | `dataset_card.md` | 944 | `a38bcb7977cb7dac8d76741395359aeb345ecfe2407ec31d15983848a8fedb10` | CuratorKIT provenance card |
| **Export Summary** | `export_summary.json` | ~3,200 | N/A | Machine-readable breakdown by status, SOP, & scenario |

---

## 3. Training Candidates Breakdown

- **Total Source Experiments:** 1,200
- **Accepted Compliant Candidates:** 720 (100% `checks_passed`)
  - *Nominal Valid:* 520 records
  - *Unit Conversion Valid:* 120 records
  - *Timezone Valid:* 80 records
- **SOP Distribution:**
  - SOP-001 (pH Value): 166 records
  - SOP-002 (Conductivity): 74 records
  - SOP-003 (Lead Content): 207 records
  - SOP-004 (Fluoride Content): 62 records
  - SOP-005 (Turbidity): 70 records
  - SOP-006 (Nitrate Content): 65 records
  - SOP-007 (Dissolved Oxygen): 44 records
  - SOP-008 (Total Organic Carbon): 32 records

---

## 4. ChatML Schema & Prompt Template

Each line in `train_candidates.jsonl` is a JSON object with a single `"messages"` key following OpenAI / Hugging Face ChatML conventions:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "You are an expert scientific validation assistant for Scintest Research Labs.\nEvaluate the analytical laboratory record below for {parameter}. Perform a comprehensive deterministic review covering:\n1. SOP Version authorization and effective validity on run date\n2. Instrument calibration currency and validity window\n3. Reagent lot qualification and expiration status\n4. Sample preservation and holding time limit compliance\n5. Measurement specification compliance including expanded uncertainty\nState the final compliance verdict and justify with evidence.\n\nLaboratory Record Details:\n• Experiment ID: {experiment_id}\n• SOP Reference: {sop_id} v{sop_version} (Clause: {clause_id})\n• Parameter: {parameter}\n• Run Date: {run_date}\n• Instrument ID: {instrument_id}\n• Reagent Lot ID: {lot_id}\n• Sample ID: {sample_id}\n• Collection Time: {collection_timestamp}\n• Analysis Time: {analysis_timestamp}\n• Max Holding Time: {max_holding_hours} hours\n• Reported Value: {measured_value} {measurement_unit} (± {measurement_uncertainty} {measurement_unit})\n• Analyst Claimed Status: PASS"
    },
    {
      "role": "assistant",
      "content": "Scientific Compliance Verification for {experiment_id} ({parameter}):\nVerdict: COMPLIANT (PASS) under {sop_id} Clause {clause_id}.\n\nEvidence Breakdown:\n1. Standard Operating Procedure: SOP version '{sop_version}' is valid and authorized on {run_date}.\n2. Equipment Calibration ({instrument_id}): Instrument calibration is valid through {cal_end} (inclusive).\n3. Reagent Quality ({lot_id}): Reagent lot is valid through {lot_exp} (inclusive).\n4. Sample Integrity ({sample_id}): Sample analyzed within holding time: {elapsed:.2f} hours <= limit {max_holding:.2f} hours.\n5. Measurement & Uncertainty: Uncertainty interval [{lower:.4f}, {upper:.4f}] {canonical_unit} is within or on the inclusive specification boundaries [{min:.4f}, {max:.4f}] {canonical_unit}.\n\nConclusion: All 5 regulatory and physical compliance criteria are met without ambiguity or conflict."
    }
  ]
}
```

---

## 5. Model Loading & Fine-Tuning Code Examples

### 5.1 Hugging Face `datasets` Loading
```python
from datasets import load_dataset

dataset = load_dataset(
    "json",
    data_files={"train": "data/training_export_v5/train_candidates.jsonl"}
)

print(f"Loaded {len(dataset['train'])} training examples.")
sample = dataset["train"][0]
print("Sample user prompt preview:", sample["messages"][0]["content"][:150])
```

### 5.2 TRL `SFTTrainer` with LoRA (Cohere Tiny Aya)
```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from trl import SFTTrainer
from peft import LoraConfig, get_peft_model
from datasets import load_dataset

model_id = "CohereForAI/c4ai-command-r-v01-4bit" # Or Cohere Tiny Aya checkpoint
tokenizer = AutoTokenizer.from_pretrained(model_id)

dataset = load_dataset("json", data_files={"train": "data/training_export_v5/train_candidates.jsonl"})

peft_config = LoraConfig(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]
)

training_args = TrainingArguments(
    output_dir="./checkpoints/tiny_aya_vault_sft",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.1,
    logging_steps=10,
    save_strategy="epoch",
    fp16=torch.cuda.is_available(),
    report_to="none"
)

trainer = SFTTrainer(
    model=model_id,
    train_dataset=dataset["train"],
    peft_config=peft_config,
    dataset_text_field="messages",
    max_seq_length=1024,
    tokenizer=tokenizer,
    args=training_args,
)

# trainer.train()
```

---

## 6. Evaluation Framework & Ground Truth Isolation

Do **not** evaluate the model against the training set. VAULT provides two distinct evaluation suites:

### 1. In-Domain Retention Baseline (`data/evaluation_in_domain/`)
- **Size:** 100 valid compliant records.
- **Purpose:** Verifies that fine-tuning retained exact formatting, arithmetic precision, and inclusive boundary reasoning without catastrophic forgetting.

### 2. Independent Held-Out Evaluation (`data/evaluation_held_out/`)
- **Structure:**
  - `model_inputs.jsonl`: Contains 144 isolated experiment prompts with zero answers or defect codes.
  - `evaluation_answer_key.jsonl`: Evaluator-only ledger containing `expected_verdict`, `abstain_required`, and `reason_codes`.
- **Purpose:** Tests the model's ability to abstain on defective or out-of-distribution cases and maintain rigorous compliance reporting across:
  - Expired calibration & lots
  - Timestamp reversals
  - Uncertainty boundary straddling
  - Unknown / novel methods (`UNKNOWN_METHOD`)

---

## 7. Quality Assurance Checklist for ML Engineers

- [x] Exact count: 720 records in `train_candidates.jsonl`.
- [x] Zero duplicate IDs: 720 unique experiment IDs.
- [x] Zero leakage: No `ground_truth`, `defect_category`, or `answer_key` tokens in prompt or response.
- [x] Inclusive language: All 720 assistant responses state `"within or on the inclusive specification boundaries"`.
- [x] EXP-0359 verified: Uses v1.0 limits `[0.1, 2.0] mg/L` active on 2025-03-26.
- [x] SHA-256 verified against `checksums.txt`.

