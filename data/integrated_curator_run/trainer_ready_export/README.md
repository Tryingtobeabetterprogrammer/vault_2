---
tags:
- curatorkit
configs:
- config_name: sft_messages
  default: true
  description: curatorkit sft_messages export, sha256 d2d3e6cea87228eee789e3cf14ef2666e96610fe92da80fb3b6596761fbd5cfd
  data_files:
  - split: train
    path: sft_messages.jsonl
---

# Dataset Card: curatorkit_run

## Summary

- **Run timestamp**: 2026-11-09T08:57:54.842179Z
- **Wall clock time**: 24.3s
- **Pipeline config hash**: `f4a107085c67e3f6`

## Source Documents

  - Unknown

## Pipeline Stages

| Step | Input | Passed | Recovered | Rejected | Forward |
|------|-------|--------|-----------|----------|---------|
| JSONLReader | 720 | 720 | — | 0 | 720 |
| SchemaGate | 720 | 720 | 0 | 0 | 720 |
| ExactDeduplicator | 720 | 720 | — | — | 720 |
| MinHashDeduplicator | 720 | 358 | — | — | 358 |
| TextCleaner | 358 | 358 | — | — | 358 |
| MessagesExporter | — | 358 | — | — | 358 |

## Gate Pass Rates and Rejection Breakdown

- **JSONLReader**: 720/0 passed (N/A), 0 rejected
- **SchemaGate**: 720/720 passed (100.0%), 0 rejected


**Rejection reasons:**
  - None

## Deduplication

  - near_duplicates_removed: 362
  - surviving_count: 358

## Known Limitations

- MinHash threshold used: **0.9** — this is a starting point, not a universal answer. Adjust per domain (legal, medical, and other domain-specific corpora may need a lower threshold to avoid losing structurally similar but semantically valid examples).
- Table extraction requires `extract_tables: true` on the PDF reader and MinerU with GPU support. Disabled by default.
- Token counting uses a whitespace tokenizer by default. For exact LLM context window
  enforcement, enable `use_tiktoken: true` in the SchemaGate config.
- Both within-run (MinHash/Diversity) and cross-run (EmbeddingDeduplicator) deduplication
  are available. Cross-run dedup persists an embedding index across runs; use
  `embedding_reset_index: true` to start fresh.

## Reproduction

```bash
pip install curatorkit
curatorkit run pipeline.yaml --output-dir ./out/
```

## Tool Versions

- **curatorkit**: 0.1.21
- **python**: 3.11.9

## Configs

Load one with `datasets.load_dataset("<this folder or Hub repo>", "<config>")`.

| Config | Splits (rows) | Columns |
|--------|---------------|---------|
| `sft_messages` | train (358) | `messages`: list of {role, content}; role is system, user or assistant |
