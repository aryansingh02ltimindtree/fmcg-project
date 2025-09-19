#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Oversample a target task (default: ytd_summary) in an instruction-tuning JSONL.
Works with the NLG files we created (each line has "instruction", "output"),
where the source JSON is embedded after 'JSON:' inside "instruction".

Usage:
  python oversample_ytd.py --in data/nlg_insights_train_48m6.jsonl \
                           --out data/nlg_insights_train_48m6_ytd3x.jsonl \
                           --factor 3 \
                           --task ytd_summary
"""

import argparse, json, sys, collections

def extract_task(row):
    """Extract the 'task' field from the embedded JSON in 'instruction'."""
    instr = row.get("instruction", "")
    if "JSON:" not in instr:
        return ""
    try:
        jtxt = instr.split("JSON:", 1)[1].strip()
        j = json.loads(jtxt)
        return (j.get("task") or "").lower()
    except Exception:
        return ""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input train JSONL")
    ap.add_argument("--out", dest="out", required=True, help="Output oversampled train JSONL")
    ap.add_argument("--factor", type=int, default=3, help="Duplication factor for the target task (default: 3)")
    ap.add_argument("--task", default="ytd_summary", help="Task name to oversample (default: ytd_summary)")
    args = ap.parse_args()

    in_path, out_path = args.inp, args.out
    target_task = args.task.lower()
    k = max(1, args.factor)

    counts_before = collections.Counter()
    total_in = 0
    kept = 0

    with open(in_path, "r", encoding="utf-8") as f, open(out_path, "w", encoding="utf-8") as w:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            total_in += 1
            t = extract_task(row)
            counts_before[t] += 1

            # duplicate target task by factor k, others once
            dup = k if t == target_task else 1
            for _ in range(dup):
                w.write(json.dumps(row, ensure_ascii=False) + "\n")
                kept += 1

    # Simple report
    print("Input file:", in_path)
    print("Total rows (in):", total_in)
    print("Counts by task (in):", dict(counts_before))
    print(f"\nOversampled task='{target_task}' by factor={k}")
    print("Output file:", out_path)
    print("Total rows (out):", kept)

if __name__ == "__main__":
    main()
