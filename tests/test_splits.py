"""Unit tests for VAULT synthetic dataset splits and leakage verification."""

import hashlib
import json
from pathlib import Path
import pytest

from data_engine.splits import generate_synthetic_splits


def compute_file_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


@pytest.fixture(scope="module")
def split_manifest(tmp_path_factory):
    out_dir = tmp_path_factory.mktemp("synthetic")
    return generate_synthetic_splits(output_dir=out_dir)


def test_split_manifest_record_counts(split_manifest):
    splits = split_manifest["splits"]
    train_count = splits["train"]["count"]
    dev_count = splits["dev"]["count"]
    test_count = splits["sealed_test"]["count"]

    assert split_manifest["total_experiments"] == 1200
    assert train_count + dev_count + test_count == 1200
    assert train_count > 0
    assert dev_count > 0
    assert test_count > 0


def test_zero_leakage_between_train_and_sealed_test(split_manifest):
    splits = split_manifest["splits"]
    train_ids = set(splits["train"]["experiment_ids"])
    dev_ids = set(splits["dev"]["experiment_ids"])
    test_ids = set(splits["sealed_test"]["experiment_ids"])

    # ID disjointness
    assert train_ids & test_ids == set()
    assert train_ids & dev_ids == set()
    assert dev_ids & test_ids == set()

    # SOP family disjointness
    train_sops = set(splits["train"]["sop_ids"])
    test_sops = set(splits["sealed_test"]["sop_ids"])
    dev_sops = set(splits["dev"]["sop_ids"])
    assert train_sops & test_sops == set()
    assert train_sops & dev_sops == set()
    assert dev_sops & test_sops == set()


def test_truth_ledger_withheld_from_records_jsonl():
    """Verify that records.jsonl does not contain ground-truth verdict labels."""
    records_path = Path("data/synthetic/records.jsonl")
    assert records_path.exists()

    forbidden_keys = {"final_verdict", "rule_results", "abstain", "failure_codes", "review_codes"}
    with open(records_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                for fk in forbidden_keys:
                    assert fk not in rec, f"Leaked ground-truth key '{fk}' found in records.jsonl"


def test_split_manifest_hashes_match_disk():
    """Verify that SHA-256 hashes recorded in split_manifest.json match files on disk."""
    manifest_path = Path("data/synthetic/split_manifest.json")
    assert manifest_path.exists()

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    records_path = Path("data/synthetic/records.jsonl")
    truth_path = Path("data/synthetic/truth_ledger.jsonl")

    assert compute_file_sha256(records_path) == manifest["file_hashes"]["records_jsonl"]
    assert compute_file_sha256(truth_path) == manifest["file_hashes"]["truth_ledger_jsonl"]

