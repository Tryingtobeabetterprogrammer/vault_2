# VAULT Architectural Decision Records (ADR)

## DEC-001: Schema Contracts Alignment
- **Status:** Proposed for Inter-Team Agreement
- **Date:** 2026-11-09
- **Author:** Vijay (Data & Evidence Lead)
- **Stakeholders:** Pawan (Harness/UI Lead), Model Lead
- **Context:** Pawan requires a stable REST API input and output structure for `POST /records/review` and `POST /assistant/review-record`. Model lead requires clean datasets without truth-label leakage.
- **Decision:**
  1. `contracts/record.schema.json` establishes the required fields for raw ingested laboratory experiments.
  2. `contracts/assessment.schema.json` defines the output format of `verify_record()`, distinguishing `status` (`checks_passed`, `flagged`, `needs_review`) from deterministic scientific verdicts (`valid`, `invalid`, `needs_review`).
  3. All ground truth verdicts are withheld from model-facing runtime and live assistant inputs.

## DEC-002: Immutability and Retrospective Invalidation
- **Status:** Approved
- **Date:** 2026-11-09
- **Decision:** Original ingested records and source payloads are strictly immutable with SHA-256 hashes recorded on intake. Retrospective audits (e.g. later calibration failure discoveries) create append-only assessment events referencing prior assessment IDs (`supersedes_id`) without overwriting historical records.

## DEC-003: Deterministic Rule Precedence and Abstention
- **Status:** Approved
- **Date:** 2026-11-09
- **Decision:**
  - All 5 rules pass -> `valid` (`abstain=false`, `status=checks_passed`).
  - At least one rule definite fail, zero review/ambiguity -> `invalid` (`abstain=false`, `status=flagged`).
  - Any unresolved review/ambiguity condition (missing evidence, boundary uncertainty crossing, unparseable timestamp, unsupported unit, foreign key not found) -> `needs_review` (`abstain=true`, `status=needs_review`), while preserving all concurrently detected definite failure codes.
