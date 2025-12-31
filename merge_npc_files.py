#!/usr/bin/env python3
"""
Merge multiple NPC profile JSON files into a single npc_truth.json file.

Usage:
    python merge_npc_files.py npc_batch1.json npc_batch2.json npc_batch3.json npc_batch4.json
"""

import json
import sys
import os
from pathlib import Path


def merge_npc_files(input_files, output_file):
    """
    Merge multiple NPC JSON files into one.

    Args:
        input_files: List of input JSON file paths
        output_file: Output file path for merged result
    """
    merged_npcs = []

    for input_file in input_files:
        print(f"Reading {input_file}...")
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # Handle both array format and object format
                if isinstance(data, list):
                    merged_npcs.extend(data)
                    count = len(data)
                elif isinstance(data, dict):
                    # If it's a dict, check if there's a key containing the NPC list
                    if 'npcs' in data:
                        merged_npcs.extend(data['npcs'])
                        count = len(data['npcs'])
                    else:
                        # Dict with NPC IDs as keys - extract the values (NPC objects)
                        npc_objects = list(data.values())
                        merged_npcs.extend(npc_objects)
                        count = len(npc_objects)
                else:
                    count = 0

            print(f"  Added {count} NPC(s)")
        except Exception as e:
            print(f"Error reading {input_file}: {e}")
            sys.exit(1)

    # Create output directory if it doesn't exist
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write merged data
    print(f"\nWriting {len(merged_npcs)} NPCs to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged_npcs, f, indent=2, ensure_ascii=False)

    print(f"✓ Successfully created {output_file}")
    print(f"  Total NPCs: {len(merged_npcs)}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python merge_npc_files.py <input_file1> <input_file2> ...")
        print("\nExample:")
        print("  python merge_npc_files.py npc_batch1.json npc_batch2.json npc_batch3.json npc_batch4.json")
        sys.exit(1)

    input_files = sys.argv[1:]
    output_file = "scenarios/lepto_maharlika/data/npc_truth.json"

    # Verify all input files exist
    for input_file in input_files:
        if not os.path.exists(input_file):
            print(f"Error: Input file '{input_file}' not found")
            sys.exit(1)

    merge_npc_files(input_files, output_file)


if __name__ == "__main__":
    main()
