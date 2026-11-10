"""VAULT Dataset Split and Leakage Verification Engine.

Partitions synthetic Scintest laboratory records into group/family-separated
train, dev, and sealed-test splits with strict zero-leakage guarantees.
Exports:
- data/synthetic/records.jsonl
- data/synthetic/truth_ledger.jsonl
- data/synthetic/split_manifest.json
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

SIMULATOR_VERSION = "2.0.0"
SIMULATOR_SEED = 42

# SOP Cluster Allocations ensuring family and clause separation
TRAIN_SOPS = {"SOP-001", "SOP-002", "SOP-003", "SOP-004"}
DEV_SOPS = {"SOP-005", "SOP-006"}
TEST_SOPS = {"SOP-007", "SOP-008"}


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def generate_synthetic_splits(
    raw_experiments_path: Path = Path("data/raw_v2/experiments_v2.jsonl"),
    ground_truth_ledger_path: Path = Path("data/ground_truth_v2/ground_truth_ledger_v2.jsonl"),
    output_dir: Path = Path("data/synthetic"),
) -> Dict[str, Any]:
    """Partition experiments and truth ledger into group-separated splits and export artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Read raw experiments
    raw_records: List[Dict[str, Any]] = []
    with open(raw_experiments_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                raw_records.append(json.loads(line))

    # 2. Read truth ledger
    truth_records: Dict[str, Dict[str, Any]] = {}
    with open(ground_truth_ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                truth_records[item["experiment_id"]] = item

    # 3. Partition by SOP group to prevent clause and family leakage
    train_ids: List[str] = []
    dev_ids: List[str] = []
    test_ids: List[str] = []

    train_clauses: Set[str] = set()
    dev_clauses: Set[str] = set()
    test_clauses: Set[str] = set()

    missing_sop_count = 0
    for rec in raw_records:
        eid = rec["experiment_id"]
        sop = rec.get("sop_id")
        cid = rec.get("clause_id")

        if sop in TRAIN_SOPS:
            train_ids.append(eid)
            if cid and cid != "CLAUSE-999":
                train_clauses.add(cid)
        elif sop in DEV_SOPS:
            dev_ids.append(eid)
            if cid and cid != "CLAUSE-999":
                dev_clauses.add(cid)
        elif sop in TEST_SOPS:
            test_ids.append(eid)
            if cid and cid != "CLAUSE-999":
                test_clauses.add(cid)
        else:
            # Missing SOP evidence records (split deterministically)
            missing_sop_count += 1
            if missing_sop_count <= 9:
                train_ids.append(eid)
            elif missing_sop_count <= 11:
                dev_ids.append(eid)
            else:
                test_ids.append(eid)

    # 4. Perform strict leakage checks
    train_set = set(train_ids)
    dev_set = set(dev_ids)
    test_set = set(test_ids)

    # Record ID disjointness
    shared_train_test = train_set & test_set
    shared_train_dev = train_set & dev_set
    shared_dev_test = dev_set & test_set

    # SOP Clause disjointness between Train and Sealed Test
    shared_clauses_train_test = train_clauses & test_clauses
    shared_clauses_dev_test = dev_clauses & test_clauses

    leakage_passed = (
        len(shared_train_test) == 0
        and len(shared_train_dev) == 0
        and len(shared_dev_test) == 0
        and len(shared_clauses_train_test) == 0
        and len(shared_clauses_dev_test) == 0
    )

    if not leakage_passed:
        raise ValueError(
            f"Split leakage check failed: shared_records={len(shared_train_test)}, shared_clauses={len(shared_clauses_train_test)}"
        )

    # 5. Export records.jsonl (withheld from ground truth labels)
    records_out = output_dir / "records.jsonl"
    with open(records_out, "w", encoding="utf-8") as f:
        for rec in raw_records:
            f.write(json.dumps(rec) + "\n")

    # 6. Export truth_ledger.jsonl (authoritative ground truth, withheld from inference)
    truth_out = output_dir / "truth_ledger.jsonl"
    with open(truth_out, "w", encoding="utf-8") as f:
        for rec in raw_records:
            t_rec = truth_records[rec["experiment_id"]]
            f.write(json.dumps(t_rec) + "\n")

    # Compute verdict distribution per split
    def get_verdict_dist(ids: List[str]) -> Dict[str, int]:
        dist = {"valid": 0, "invalid": 0, "needs_review": 0}
        for eid in ids:
            v = truth_records[eid]["final_verdict"]
            dist[v] = dist.get(v, 0) + 1
        return dist

    train_verdicts = get_verdict_dist(train_ids)
    dev_verdicts = get_verdict_dist(dev_ids)
    test_verdicts = get_verdict_dist(test_ids)

    # 7. Export split_manifest.json
    records_hash = compute_file_sha256(records_out)
    truth_hash = compute_file_sha256(truth_out)

    manifest_data = {
        "simulator_version": SIMULATOR_VERSION,
        "seed": SIMULATOR_SEED,
        "total_experiments": len(raw_records),
        "split_strategy": "group_family_separated_sop_clusters",
        "file_hashes": {
            "records_jsonl": records_hash,
            "truth_ledger_jsonl": truth_hash,
        },
        "leakage_verification": {
            "shared_train_test_record_ids": len(shared_train_test),
            "shared_train_dev_record_ids": len(shared_train_dev),
            "shared_dev_test_record_ids": len(shared_dev_test),
            "shared_train_test_clauses": len(shared_clauses_train_test),
            "shared_dev_test_clauses": len(shared_clauses_dev_test),
            "status": "PASS",
        },
        "splits": {
            "train": {
                "count": len(train_ids),
                "sop_ids": sorted(list(TRAIN_SOPS)),
                "clauses_count": len(train_clauses),
                "verdict_distribution": train_verdicts,
                "experiment_ids": train_ids,
            },
            "dev": {
                "count": len(dev_ids),
                "sop_ids": sorted(list(DEV_SOPS)),
                "clauses_count": len(dev_clauses),
                "verdict_distribution": dev_verdicts,
                "experiment_ids": dev_ids,
            },
            "sealed_test": {
                "count": len(test_ids),
                "sop_ids": sorted(list(TEST_SOPS)),
                "clauses_count": len(test_clauses),
                "verdict_distribution": test_verdicts,
                "experiment_ids": test_ids,
            },
        },
    }

    manifest_out = output_dir / "split_manifest.json"
    with open(manifest_out, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    manifest_hash = compute_file_sha256(manifest_out)
    manifest_data["file_hashes"]["split_manifest_json"] = manifest_hash

    return manifest_data
