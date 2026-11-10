"""Comprehensive test suite for VAULT V2 Synthetic Data Generator."""

import json
import os
import random
import tempfile
import pytest

from synth import generate_v2
from synth.generate_v2 import (
    generate_all_v2,
    generate_sops_v2,
    generate_instruments_v2,
    generate_lots_v2,
    generate_samples_v2,
    generate_experiments_v2,
)


@pytest.fixture(scope="module")
def v2_generated_data():
    """Generate in-memory datasets once for the test module."""
    rng = random.Random(42)
    sops = generate_sops_v2()
    instruments = generate_instruments_v2(rng)
    lots = generate_lots_v2(rng)
    samples = generate_samples_v2(rng)
    experiments = generate_experiments_v2(sops, instruments, lots, samples, rng, total_experiments=1200)
    return {
        "sops": sops,
        "instruments": instruments,
        "lots": lots,
        "samples": samples,
        "experiments": experiments,
    }


def test_experiment_count_is_exactly_1200(v2_generated_data):
    exps = v2_generated_data["experiments"]
    assert len(exps) == 1200


def test_experiment_ids_are_unique(v2_generated_data):
    exps = v2_generated_data["experiments"]
    eids = [e["experiment_id"] for e in exps]
    assert len(eids) == len(set(eids))
    assert eids[0] == "EXP-0001"
    assert eids[-1] == "EXP-1200"


def test_no_verdict_fields_assigned_by_simulator(v2_generated_data):
    exps = v2_generated_data["experiments"]
    for e in exps:
        assert "verdict" not in e, f"Found premature verdict in raw experiment: {e['experiment_id']}"
        assert "status" not in e
        assert "reason_codes" not in e


def test_all_14_scenario_families_present_and_count_matches(v2_generated_data):
    exps = v2_generated_data["experiments"]
    fam_counts = {}
    for e in exps:
        fam = e.get("scenario_family")
        fam_counts[fam] = fam_counts.get(fam, 0) + 1

    expected_counts = {
        "Nominal valid": 520,
        "Unit conversion valid": 120,
        "Timezone valid": 80,
        "Calibration expiry invalid": 45,
        "Lot expiry invalid": 45,
        "Holding time exceeded invalid": 45,
        "Measurement out of range invalid": 45,
        "Timestamp inversion invalid": 25,
        "Compound dual failure invalid": 35,
        "SOP overlap conflict review": 40,
        "Measurement boundary uncertainty review": 70,
        "Missing evidence review": 55,
        "Broken foreign key review": 35,
        "Compound failure with review": 40,
    }

    assert fam_counts == expected_counts
    assert sum(fam_counts.values()) == 1200


def test_sop_overlap_scenarios_fall_strictly_in_sop3_overlap_window(v2_generated_data):
    exps = v2_generated_data["experiments"]
    overlap_exps = [e for e in exps if e.get("scenario_family") == "SOP overlap conflict review"]
    assert len(overlap_exps) == 40
    for e in overlap_exps:
        assert e["sop_id"] == "SOP-003"
        assert e["sop_version"] is None  # Omitted version triggers conflict
        run_d = e["run_date"]
        # Window: 2025-05-15 to 2025-05-31
        assert "2025-05-15" <= run_d <= "2025-05-31", f"Run date {run_d} outside overlap window!"


def test_guarded_uncertainty_in_nominal_valid_experiments(v2_generated_data):
    exps = v2_generated_data["experiments"]
    # Map (clause_id, sop_version) to clause
    sops_map = {(c["clause_id"], c["sop_version"]): c for c in v2_generated_data["sops"]}
    nom_valid = [e for e in exps if e.get("scenario_family") == "Nominal valid"]
    assert len(nom_valid) == 520

    for e in nom_valid:
        cid = e["clause_id"]
        ver = e["sop_version"]
        c = sops_map[(cid, ver)]
        s_min = float(c["minimum_value"])
        s_max = float(c["maximum_value"])
        val = float(e["measured_value"])
        unc = float(e["measurement_uncertainty"])

        # Guarded margin: interval [val - unc, val + unc] must be strictly inside [s_min, s_max]
        lower_bound = val - unc
        upper_bound = val + unc
        assert lower_bound >= s_min, f"{e['experiment_id']} lower bound {lower_bound} below s_min {s_min}"
        assert upper_bound <= s_max, f"{e['experiment_id']} upper bound {upper_bound} above s_max {s_max}"


def test_timestamp_inversion_scenarios_have_negative_delta(v2_generated_data):
    from datetime import datetime, timezone
    import zoneinfo
    exps = v2_generated_data["experiments"]
    inv_exps = [e for e in exps if e.get("scenario_family") == "Timestamp inversion invalid"]
    assert len(inv_exps) == 25
    for e in inv_exps:
        site_tz = e.get("site_timezone", "UTC")
        col_dt = datetime.fromisoformat(e["collected_at"].replace("Z", "+00:00"))
        if col_dt.tzinfo is None:
            col_dt = col_dt.replace(tzinfo=zoneinfo.ZoneInfo(site_tz) if site_tz else timezone.utc)
        ana_dt = datetime.fromisoformat(e["analyzed_at"].replace("Z", "+00:00"))
        if ana_dt.tzinfo is None:
            ana_dt = ana_dt.replace(tzinfo=zoneinfo.ZoneInfo(site_tz) if site_tz else timezone.utc)
        assert ana_dt.astimezone(timezone.utc) < col_dt.astimezone(timezone.utc), (
            f"Expected inversion, but analyzed ({ana_dt}) >= collected ({col_dt})"
        )


def test_broken_foreign_key_scenarios(v2_generated_data):
    exps = v2_generated_data["experiments"]
    broken_exps = [e for e in exps if e.get("scenario_family") == "Broken foreign key review"]
    assert len(broken_exps) == 35

    broken_inst = [e for e in broken_exps if e["instrument_id"] == "INST-999"]
    broken_lot = [e for e in broken_exps if e["lot_id"] == "LOT-999"]
    broken_sample = [e for e in broken_exps if e["sample_id"] == "SMP-9999"]
    broken_clause = [e for e in broken_exps if e["clause_id"] == "CLAUSE-999"]

    assert len(broken_inst) > 0
    assert len(broken_lot) > 0
    assert len(broken_sample) > 0
    assert len(broken_clause) > 0


def test_site_id_and_site_timezone_populated(v2_generated_data):
    exps = v2_generated_data["experiments"]
    for e in exps:
        assert "site_id" in e and e["site_id"] in ("SITE-BOS", "SITE-BER", "SITE-SFO", "SITE-LON")
        assert "site_timezone" in e and e["site_timezone"] in (
            "America/New_York", "Europe/Berlin", "America/Los_Angeles", "Europe/London"
        )


def test_reproducibility_with_seed_42():
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        meta1 = generate_all_v2(seed=42, output_dir=d1)
        meta2 = generate_all_v2(seed=42, output_dir=d2)

        # Check content match for all output files
        for fname in ["sops_v2.jsonl", "instruments_v2.jsonl", "lots_v2.jsonl", "samples_v2.jsonl", "experiments_v2.jsonl", "runs_v2.csv"]:
            p1 = os.path.join(d1, fname)
            p2 = os.path.join(d2, fname)
            with open(p1, "rb") as f1, open(p2, "rb") as f2:
                assert f1.read() == f2.read(), f"File {fname} content differed between runs with seed 42!"

