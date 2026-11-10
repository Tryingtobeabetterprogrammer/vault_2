#!/usr/bin/env python3
"""VAULT V2 Simulator CLI Driver.

Generates 1,200 synthetic laboratory experiments across 14 scenario families
and outputs datasets to data/raw_v2/.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Ensure repository root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from synth.generate_v2 import generate_all_v2


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate VAULT V2 synthetic laboratory datasets.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic generation (default: 42)")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory (default: data/raw_v2)")
    parser.add_argument("--config", type=str, default="config/simulator_config_v2.json", help="V2 config path")

    args = parser.parse_args()

    print(f"=== VAULT V2 Laboratory Data Simulator ===")
    print(f"Seed: {args.seed}")
    print(f"Config: {args.config}")

    out_dir = args.output_dir or os.path.join(REPO_ROOT, "data", "raw_v2")
    print(f"Target Directory: {out_dir}\n")

    metadata = generate_all_v2(seed=args.seed, output_dir=out_dir)

    print("Generation complete!")
    print(f"Counts: {metadata.get('counts')}")
    print("\nScenario Distribution:")
    for fam, cnt in sorted(metadata.get("scenario_family_distribution", {}).items()):
        print(f"  {fam:<45}: {cnt}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

