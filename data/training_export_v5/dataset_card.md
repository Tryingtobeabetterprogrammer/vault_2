# VAULT V5 — Scientific Training Dataset Card

## Overview
- **Dataset Version:** 1.0.0
- **Model Target:** Cohere Tiny Aya Global Fine-Tuning
- **Total Source Records:** 1200
- **Scientifically Verified Candidates:** 720 (100% checks_passed)
- **Quarantined Records:** 480 (Definite violations & ambiguities)
- **Deduplication Strategy:** CuratorKIT ExactDeduplicator (SHA-256)
- **Export Format:** ChatML `messages`

## Curation & Verification Pipeline
1. **VAULT Evidence Gate:** All records verified by 5 deterministic rules. Only `checks_passed` records qualify.
2. **Evidence Synthesis:** Assistant responses explain SOP currency, calibration, lot validity, holding times, and measurement uncertainty.
3. **CuratorKIT Hygiene:** Schema validation, exact deduplication, and text cleaning via official CuratorKIT v0.1.21.
4. **Truth Isolation:** Zero ground-truth leakage; truth ledger never enters model-facing pipeline.
