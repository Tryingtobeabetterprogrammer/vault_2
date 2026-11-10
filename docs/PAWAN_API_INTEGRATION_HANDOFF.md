# VAULT — Pawan API Integration Contract & Handoff

**Target Team:** Backend & API Engineering (Pawan)  
**Author:** VAULT Architecture & Verification Team  
**Module:** `vault.verification` & `vault.memory.ScientificMemory`  
**Status:** Approved for Integration  
**Version:** 1.0.0  

---

## 1. Overview & Architectural Principles

This document defines the formal integration contract for embedding VAULT's deterministic scientific verifier and immutable memory into Pawan's API gateway.

### Core Architectural Principles:
1. **Deterministic Authority:** Scientific truth is verified deterministically by `vault.verification.verify_record()`. The LLM / assistant never overrides deterministic rules or invents compliance verdicts.
2. **Immutable Append-Only Memory:** Once written, original source records and evaluation assessments are never mutated or deleted. Corrections, re-analyses, and audits create new assessments explicitly linked via `supersedes_id`.
3. **Strict Schema Conformance:** Inbound records must adhere to [`contracts/record.schema.json`](file:///c:/VAULT/contracts/record.schema.json). Outbound assessments strictly conform to [`contracts/assessment.schema.json`](file:///c:/VAULT/contracts/assessment.schema.json).
4. **Isolated Evaluation Truth:** Truth ledgers, corruption benchmark labels, and test ground truth are completely isolated and never exposed to model inputs or API consumers.

---

## 2. API Endpoints

### Endpoint 1: `POST /records/review`
- **Purpose:** Synchronous deterministic verification and immutable audit storage.
- **Workflow:**
  1. Validates inbound JSON payload against `record.schema.json`.
  2. Stores original source record into `ScientificMemory` (stores raw payload, computes SHA-256).
  3. Executes `vault.verification.verify_record(record, catalogs)`.
  4. Persists resultant assessment in `ScientificMemory`.
  5. Returns standardized assessment response.

### Endpoint 2: `POST /assistant/review-record`
- **Purpose:** Model-assisted laboratory review endpoint combining deterministic verification with structured, audit-ready assistant explanations.
- **Workflow:**
  1. Executes identical deterministic verification and memory storage as `/records/review`.
  2. Synthesizes a structured, 5-point compliance rationale conforming to the Tiny Aya fine-tuned template.
  3. Returns both deterministic assessment payload and structured explanation.

---

## 3. Standard Request & Response Schemas

### 3.1 Request Schema (`POST /records/review` & `POST /assistant/review-record`)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "RecordReviewRequest",
  "type": "object",
  "required": [
    "experiment_id",
    "sop_id",
    "clause_id",
    "run_date",
    "instrument_id",
    "lot_id",
    "sample_id",
    "parameter",
    "measured_value",
    "measurement_unit",
    "measurement_uncertainty"
  ],
  "properties": {
    "experiment_id": { "type": "string", "pattern": "^EXP-[0-9]{4,}$" },
    "sop_id": { "type": "string" },
    "sop_version": { "type": "string" },
    "clause_id": { "type": "string" },
    "run_date": { "type": "string", "format": "date" },
    "instrument_id": { "type": "string" },
    "lot_id": { "type": "string" },
    "sample_id": { "type": "string" },
    "parameter": { "type": "string" },
    "measured_value": { "type": "number" },
    "measurement_unit": { "type": "string" },
    "measurement_uncertainty": { "type": "number", "minimum": 0 },
    "collection_timestamp": { "type": "string", "format": "date-time" },
    "analysis_timestamp": { "type": "string", "format": "date-time" },
    "method_id": { "type": "string" },
    "user_notes": { "type": "string" }
  }
}
```

### 3.2 Response Schema (`POST /records/review`)
Conforms to [`contracts/assessment.schema.json`](file:///c:/VAULT/contracts/assessment.schema.json):
```json
{
  "assessment_id": "ASM-XXXXXXXXXXXX",
  "record_id": "EXP-XXXX",
  "supersedes_id": null,
  "status": "checks_passed | flagged | needs_review",
  "verdict": "valid | invalid | unverified",
  "abstain": false,
  "original_verdict": null,
  "issues": [],
  "evidence": [
    {
      "rule_name": "sop_validation",
      "status": "pass | fail | needs_review",
      "reason": null,
      "details": "string",
      "evidence_refs": ["string"]
    }
  ],
  "derived": {
    "normalized_value": 7.58,
    "canonical_unit": "pH",
    "specification_limits": { "min": 6.5, "max": 8.5, "unit": "pH" },
    "holding_time_hours": 4.0,
    "max_holding_hours": 24.0
  },
  "engine_version": "2.0.0",
  "created_at": "2026-11-09T11:00:00.000000+00:00",
  "recorded_at": "2026-11-09T11:00:00.000000+00:00",
  "reviewer_state": "automated"
}
```

### 3.3 Response Schema (`POST /assistant/review-record`)
Returns the standard assessment wrapped with the model-facing explanation:
```json
{
  "assessment": { /* standard assessment object */ },
  "explanation": "Scientific Compliance Verification for EXP-XXXX ...\nVerdict: COMPLIANT (PASS) ...\nEvidence Breakdown: ...\nConclusion: ...",
  "confidence": 1.0,
  "verdict_match": true
}
```

---

## 4. Standard Reason Code Taxonomy

| Reason Code | Category | Severity | Description |
|---|---|---|---|
| `SOP_VERSION_INVALID` | Regulatory | Flagged | SOP version was not active or authorized on experiment run date. |
| `SOP_VERSION_CONFLICT` | Regulatory | Needs Review | Multiple conflicting SOP versions applicable or ambiguous date span. |
| `MISSING_SOP_EVIDENCE` | Data Integrity | Needs Review | Required SOP metadata or clause mapping omitted. |
| `CALIBRATION_EXPIRED` | Metrology | Flagged | Instrument calibration expired prior to experiment run date. |
| `CALIBRATION_NOT_YET_VALID`| Metrology | Flagged | Experiment run date precedes instrument calibration certification date. |
| `MISSING_INSTRUMENT_EVIDENCE`| Metrology | Needs Review | Instrument ID missing or calibration record unresolvable. |
| `LOT_EXPIRED` | Reagent | Flagged | Reagent lot expired before experiment execution date. |
| `LOT_NOT_YET_VALID` | Reagent | Flagged | Reagent lot qualification effective date is in the future. |
| `MISSING_REAGENT_EVIDENCE` | Reagent | Needs Review | Lot ID missing or unresolvable in lot catalog. |
| `HOLDING_TIME_EXCEEDED` | Physical Sample | Flagged | Elapsed time from sample collection to analysis exceeds maximum SOP limit. |
| `INVALID_TIMESTAMP_ORDER` | Physical Sample | Flagged | Analysis timestamp recorded prior to collection timestamp (chronological violation). |
| `MISSING_SAMPLE_EVIDENCE` | Physical Sample | Needs Review | Sample collection or analysis timestamp absent. |
| `MEASUREMENT_OUT_OF_RANGE` | Measurement | Flagged | Measurement interval $[v - u, v + u]$ lies strictly outside SOP specification limits. |
| `UNCERTAINTY_CROSSES_BOUNDARY`| Measurement | Needs Review | Measurement interval straddles the specification limit boundary (ambiguous compliance). |
| `FOREIGN_KEY_NOT_FOUND` | Data Integrity | Needs Review | Referenced SOP, Instrument, Lot, or Sample ID not found in laboratory catalogs. |
| `UNKNOWN_METHOD` | Methodology | Needs Review | Unrecognized or novel analytical method without registered standard procedure. |
| `ARITHMETIC_CONTRADICTION`| Analytical | Flagged | Explicit component mass/volume disagrees with reported concentration. |

---

## 5. HTTP Status Codes & Error Handling

- **`200 OK`**: Verification completed. Assessment returned (`checks_passed`, `flagged`, or `needs_review`).
- **`400 Bad Request`**: Request payload failed JSON schema validation (e.g., missing required fields, illegal types, negative uncertainty).
- **`422 Unprocessable Entity`**: Unparseable date formats or corrupted numeric data preventing rule evaluation.
- **`500 Internal Server Error`**: Unexpected system or storage failure.

---

## 6. Idempotency & Immutability Workflows

### Idempotency
- When an identical record (matching SHA-256 hash) is submitted again without changes, the API retrieves the existing active assessment from `ScientificMemory.get_active_assessment(record_id)` rather than re-creating duplicate ledger entries.
- If re-verification is explicitly forced (`force_reverify=true`), a new assessment is recorded linking to the previous assessment.

### Retrospective Audit / Correction Workflow (`supersedes_id`)
When an analyst corrects a typo, recalibrates equipment, or conducts an audit:
1. The original source record in `ScientificMemory` remains untouched.
2. The corrected record is submitted.
3. The API invokes `vault.verification.verify_record(corrected_record)`.
4. The memory engine creates a new assessment where `supersedes_id` points to the prior `assessment_id`.
5. Full audit history is queryable via `ScientificMemory.get_history(record_id)`.

---

## 7. Concrete End-to-End Examples

### Example 1: Compliant Record (`checks_passed`)
**Request:**
```http
POST /records/review HTTP/1.1
Content-Type: application/json

{
  "experiment_id": "EXP-0046",
  "sop_id": "SOP-001",
  "sop_version": "1.0",
  "clause_id": "CLAUSE-001",
  "run_date": "2025-01-15",
  "instrument_id": "INST-017",
  "lot_id": "LOT-026",
  "sample_id": "SMP-0001",
  "parameter": "pH Value",
  "measured_value": 7.58,
  "measurement_unit": "pH",
  "measurement_uncertainty": 0.05,
  "collection_timestamp": "2025-01-15T08:30:00Z",
  "analysis_timestamp": "2025-01-15T12:30:00Z"
}
```

**Response (HTTP 200 OK):**
```json
{
  "assessment_id": "ASM-1947BC42C631",
  "record_id": "EXP-0046",
  "supersedes_id": null,
  "status": "checks_passed",
  "verdict": "valid",
  "abstain": false,
  "original_verdict": null,
  "issues": [],
  "evidence": [
    {
      "rule_name": "sop_validation",
      "status": "pass",
      "reason": null,
      "details": "SOP version '1.0' is valid and authorized on 2025-01-15.",
      "evidence_refs": ["sop_id:SOP-001", "clause_id:CLAUSE-001"]
    },
    {
      "rule_name": "calibration_validation",
      "status": "pass",
      "reason": null,
      "details": "Instrument calibration is valid through 2026-07-11 (inclusive).",
      "evidence_refs": ["instrument_id:INST-017"]
    },
    {
      "rule_name": "lot_validation",
      "status": "pass",
      "reason": null,
      "details": "Reagent lot is valid through 2026-08-20 (inclusive).",
      "evidence_refs": ["lot_id:LOT-026"]
    },
    {
      "rule_name": "holding_time_validation",
      "status": "pass",
      "reason": null,
      "details": "Sample analyzed within holding time: 4.00 hours <= limit 24.00 hours.",
      "evidence_refs": ["sample_id:SMP-0001"]
    },
    {
      "rule_name": "measurement_validation",
      "status": "pass",
      "reason": null,
      "details": "Uncertainty interval [7.53, 7.63] pH is within or on the inclusive specification boundaries [6.5, 8.5] pH.",
      "evidence_refs": ["clause_id:CLAUSE-001"]
    }
  ],
  "derived": {
    "normalized_value": 7.58,
    "canonical_unit": "pH",
    "specification_limits": { "min": 6.5, "max": 8.5, "unit": "pH" },
    "holding_time_hours": 4.0,
    "max_holding_hours": 24.0,
    "instrument_status": "pass",
    "lot_status": "pass",
    "sop_status": "pass"
  },
  "engine_version": "2.0.0",
  "created_at": "2026-11-09T11:00:00.000000+00:00",
  "recorded_at": "2026-11-09T11:00:00.000000+00:00",
  "reviewer_state": "automated"
}
```

---

### Example 2: Defective Record (`flagged` — Expired Calibration & Lot)
**Request:**
```http
POST /records/review HTTP/1.1
Content-Type: application/json

{
  "experiment_id": "EXP-0001",
  "sop_id": "SOP-003",
  "sop_version": "1.0",
  "clause_id": "CLAUSE-014",
  "run_date": "2024-09-18",
  "instrument_id": "INST-005",
  "lot_id": "LOT-001",
  "sample_id": "SMP-0041",
  "parameter": "Lead Content",
  "measured_value": 0.0052,
  "measurement_unit": "mg/L",
  "measurement_uncertainty": 0.0012,
  "collection_timestamp": "2024-09-18T06:00:00Z",
  "analysis_timestamp": "2024-09-18T10:00:00Z"
}
```

**Response (HTTP 200 OK):**
```json
{
  "assessment_id": "ASM-428B85B06FA4",
  "record_id": "EXP-0001",
  "supersedes_id": null,
  "status": "flagged",
  "verdict": "invalid",
  "abstain": false,
  "original_verdict": null,
  "issues": [
    "CALIBRATION_NOT_YET_VALID",
    "LOT_EXPIRED"
  ],
  "evidence": [
    {
      "rule_name": "sop_validation",
      "status": "pass",
      "reason": null,
      "details": "SOP version '1.0' is valid and authorized on 2024-09-18.",
      "evidence_refs": ["sop_id:SOP-003", "clause_id:CLAUSE-014"]
    },
    {
      "rule_name": "calibration_validation",
      "status": "fail",
      "reason": "CALIBRATION_NOT_YET_VALID",
      "details": "Experiment run date (2024-09-18) precedes instrument calibration date (2024-11-05).",
      "evidence_refs": ["instrument_id:INST-005"]
    },
    {
      "rule_name": "lot_validation",
      "status": "fail",
      "reason": "LOT_EXPIRED",
      "details": "Reagent lot expired on 2024-09-08 (inclusive). Run date 2024-09-18 is 10 days overdue.",
      "evidence_refs": ["lot_id:LOT-001"]
    },
    {
      "rule_name": "holding_time_validation",
      "status": "pass",
      "reason": null,
      "details": "Sample analyzed within holding time: 4.00 hours <= limit 48.00 hours.",
      "evidence_refs": ["sample_id:SMP-0041"]
    },
    {
      "rule_name": "measurement_validation",
      "status": "pass",
      "reason": null,
      "details": "Uncertainty interval [0.0040, 0.0064] mg/L is within or on the inclusive specification boundaries [0.0005, 0.01] mg/L.",
      "evidence_refs": ["clause_id:CLAUSE-014"]
    }
  ],
  "derived": {
    "normalized_value": 0.0052,
    "canonical_unit": "mg/L",
    "holding_time_hours": 4.0,
    "max_holding_hours": 48.0,
    "instrument_status": "fail",
    "lot_status": "fail",
    "sop_status": "pass"
  },
  "engine_version": "2.0.0",
  "created_at": "2026-11-09T11:04:00.000000+00:00",
  "recorded_at": "2026-11-09T11:04:00.000000+00:00",
  "reviewer_state": "automated"
}
```

---

### Example 3: Ambiguity / Novel Method (`needs_review` — UNKNOWN_METHOD)
**Request:**
```http
POST /records/review HTTP/1.1
Content-Type: application/json

{
  "experiment_id": "EXP-9901",
  "sop_id": "SOP-999",
  "sop_version": "1.0",
  "clause_id": "CLAUSE-999",
  "method_id": "METH-NOVEL-SPECTRO-2026",
  "run_date": "2026-03-01",
  "instrument_id": "INST-001",
  "lot_id": "LOT-001",
  "sample_id": "SMP-0001",
  "parameter": "Trace Zinc",
  "measured_value": 1.45,
  "measurement_unit": "mg/L",
  "measurement_uncertainty": 0.05
}
```

**Response (HTTP 200 OK):**
```json
{
  "assessment_id": "ASM-884A911C2B01",
  "record_id": "EXP-9901",
  "supersedes_id": null,
  "status": "needs_review",
  "verdict": "unverified",
  "abstain": true,
  "original_verdict": null,
  "issues": [
    "UNKNOWN_METHOD",
    "FOREIGN_KEY_NOT_FOUND"
  ],
  "evidence": [
    {
      "rule_name": "method_adherence",
      "status": "needs_review",
      "reason": "UNKNOWN_METHOD",
      "details": "Method 'METH-NOVEL-SPECTRO-2026' is unregistered in standard method registry.",
      "evidence_refs": ["method_id:METH-NOVEL-SPECTRO-2026"]
    },
    {
      "rule_name": "sop_validation",
      "status": "needs_review",
      "reason": "FOREIGN_KEY_NOT_FOUND",
      "details": "SOP 'SOP-999' Clause 'CLAUSE-999' not found in SOP registry.",
      "evidence_refs": ["sop_id:SOP-999", "clause_id:CLAUSE-999"]
    }
  ],
  "derived": {
    "normalized_value": 1.45,
    "canonical_unit": "mg/L"
  },
  "engine_version": "2.0.0",
  "created_at": "2026-11-09T11:08:00.000000+00:00",
  "recorded_at": "2026-11-09T11:08:00.000000+00:00",
  "reviewer_state": "automated"
}
```

---

### Example 4: Retrospective Audit / Correction (`supersedes_id`)
**Scenario:** Analyst recalibrated instrument INST-005 retroactively, resolving `CALIBRATION_NOT_YET_VALID`.

**Request:**
```http
POST /records/review HTTP/1.1
Content-Type: application/json

{
  "experiment_id": "EXP-0001",
  "sop_id": "SOP-003",
  "sop_version": "1.0",
  "clause_id": "CLAUSE-014",
  "run_date": "2024-09-18",
  "instrument_id": "INST-005-RECAL",
  "lot_id": "LOT-026",
  "sample_id": "SMP-0041",
  "parameter": "Lead Content",
  "measured_value": 0.0052,
  "measurement_unit": "mg/L",
  "measurement_uncertainty": 0.0012,
  "collection_timestamp": "2024-09-18T06:00:00Z",
  "analysis_timestamp": "2024-09-18T10:00:00Z",
  "user_notes": "Retrospective re-evaluation with updated lot qualification and recalibrated instrument."
}
```

**Response (HTTP 200 OK):**
```json
{
  "assessment_id": "ASM-992F11D0AA32",
  "record_id": "EXP-0001",
  "supersedes_id": "ASM-428B85B06FA4",
  "status": "checks_passed",
  "verdict": "valid",
  "abstain": false,
  "original_verdict": "invalid",
  "issues": [],
  "evidence": [
    {
      "rule_name": "sop_validation",
      "status": "pass",
      "reason": null,
      "details": "SOP version '1.0' is valid and authorized on 2024-09-18.",
      "evidence_refs": ["sop_id:SOP-003", "clause_id:CLAUSE-014"]
    },
    {
      "rule_name": "calibration_validation",
      "status": "pass",
      "reason": null,
      "details": "Instrument calibration is valid through 2025-10-01 (inclusive).",
      "evidence_refs": ["instrument_id:INST-005-RECAL"]
    },
    {
      "rule_name": "lot_validation",
      "status": "pass",
      "reason": null,
      "details": "Reagent lot is valid through 2026-08-20 (inclusive).",
      "evidence_refs": ["lot_id:LOT-026"]
    },
    {
      "rule_name": "holding_time_validation",
      "status": "pass",
      "reason": null,
      "details": "Sample analyzed within holding time: 4.00 hours <= limit 48.00 hours.",
      "evidence_refs": ["sample_id:SMP-0041"]
    },
    {
      "rule_name": "measurement_validation",
      "status": "pass",
      "reason": null,
      "details": "Uncertainty interval [0.0040, 0.0064] mg/L is within or on the inclusive specification boundaries [0.0005, 0.01] mg/L.",
      "evidence_refs": ["clause_id:CLAUSE-014"]
    }
  ],
  "derived": {
    "normalized_value": 0.0052,
    "canonical_unit": "mg/L",
    "holding_time_hours": 4.0,
    "max_holding_hours": 48.0,
    "instrument_status": "pass",
    "lot_status": "pass",
    "sop_status": "pass"
  },
  "engine_version": "2.0.0",
  "created_at": "2026-11-09T11:15:00.000000+00:00",
  "recorded_at": "2026-11-09T11:15:00.000000+00:00",
  "reviewer_state": "human_override"
}
```

---

## 8. Thread Safety & Concurrency

The underlying `ScientificMemory` instance (`vault/memory.py`) utilizes reentrant locks (`threading.RLock()`) ensuring that:
- Concurrent ingestion requests cannot interleave or corrupt in-memory or persisted JSONL history.
- Read operations are safe and immediately reflect newly appended assessments.
- When deploying behind multi-worker WSGI/ASGI servers (e.g., Gunicorn or Uvicorn), workers can coordinate against a shared volume or SQLite/Postgres backend using identical JSON schema contracts.

