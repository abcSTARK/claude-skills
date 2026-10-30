#!/usr/bin/env python3
"""
Scan a directory tree and report groups of byte-identical files.

Two-stage filter for speed on large trees: group by file size first
(cheap), only hash files that share a size with at least one other file.
Within a size group, hash with SHA-256 and report groups with >1 member
as confirmed exact duplicates.

This script only reports — it never deletes. Deciding which copy to keep
(and whether near-duplicates with different content are really the same
thing) is a judgment call for the agent/user, not this script.

Usage:
    python3 find_duplicates.py <root-dir> [--json]
"""

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict


def iter_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip common noise that's never worth hashing
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", ".Trash")]
        for name in filenames:
            if name in (".DS_Store",):
                continue
            yield os.path.join(dirpath, name)


def sha256_of(path, chunk_size=1024 * 1024):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def find_duplicate_groups(root):
    by_size = defaultdict(list)
    for path in iter_files(root):
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        by_size[size].append(path)

    duplicate_groups = []
    for size, paths in by_size.items():
        if len(paths) < 2 or size == 0:
            continue
        by_hash = defaultdict(list)
        for path in paths:
            try:
                digest = sha256_of(path)
            except OSError:
                continue
            by_hash[digest].append(path)
        for digest, group in by_hash.items():
            if len(group) > 1:
                duplicate_groups.append({
                    "sha256": digest,
                    "size_bytes": size,
                    "files": sorted(group),
                })

    duplicate_groups.sort(key=lambda g: -g["size_bytes"])
    return duplicate_groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", help="Directory to scan")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    args = parser.parse_args()

    if not os.path.isdir(args.root):
        print(f"Not a directory: {args.root}", file=sys.stderr)
        sys.exit(1)

    groups = find_duplicate_groups(args.root)

    if args.json:
        print(json.dumps(groups, indent=2))
        return

    if not groups:
        print("No exact duplicates found.")
        return

    total_reclaimable = sum(g["size_bytes"] * (len(g["files"]) - 1) for g in groups)
    print(f"Found {len(groups)} group(s) of exact duplicates "
          f"({total_reclaimable / 1_048_576:.1f} MB reclaimable if one copy is kept per group):\n")
    for g in groups:
        print(f"[{g['size_bytes'] / 1024:.1f} KB each, sha256={g['sha256'][:12]}...]")
        for f in g["files"]:
            print(f"  {f}")
        print()


if __name__ == "__main__":
    main()
