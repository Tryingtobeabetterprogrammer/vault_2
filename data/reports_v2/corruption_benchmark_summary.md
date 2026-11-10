# VAULT V4 Corruption Benchmark Report

**Total Records Evaluated:** 144
**Coverage:** 100.0%

## 1. System Comparison

| Metric | CuratorKIT Baseline Hygiene | VAULT Evidence Gate |
|---|---|---|
| Precision | 0.00% | 100.00% |
| Recall | 0.00% | 100.00% |
| False Positive Rate | 0.00% | 0.00% |
| Accuracy | 34.72% | 100.00% |

## 2. Injected Corruption Detection Rate

| Corruption Type | Injected Count | Detected by VAULT | Detected by CuratorKIT |
|---|---|---|---|
| `wrong_arithmetic` | 10 | 10 (100%) | 0 (0%) |
| `missing_context` | 10 | 10 (100%) | 0 (0%) |
| `wrong_sop_version` | 10 | 10 (100%) | 0 (0%) |
| `false_verdict` | 10 | 10 (100%) | 0 (0%) |
| `unsupported_claim` | 10 | 10 (100%) | 0 (0%) |

## 3. Scenario Family Breakdown (All 14 Families)

| Scenario Family | Total | Defective | Detected by VAULT | Detection Rate |
|---|---|---|---|---|
| Nominal valid | 72 | 31 | 31 | 100% |
| Timezone valid | 11 | 7 | 7 | 100% |
| Unit conversion valid | 17 | 12 | 12 | 100% |
| Broken foreign key review | 4 | 4 | 4 | 100% |
| Calibration expiry invalid | 4 | 4 | 4 | 100% |
| Compound dual failure invalid | 4 | 4 | 4 | 100% |
| Compound failure with review | 4 | 4 | 4 | 100% |
| Holding time exceeded invalid | 4 | 4 | 4 | 100% |
| Lot expiry invalid | 4 | 4 | 4 | 100% |
| Measurement boundary uncertainty review | 4 | 4 | 4 | 100% |
| Measurement out of range invalid | 4 | 4 | 4 | 100% |
| Missing evidence review | 4 | 4 | 4 | 100% |
| SOP overlap conflict review | 4 | 4 | 4 | 100% |
| Timestamp inversion invalid | 4 | 4 | 4 | 100% |
