#!/usr/bin/env python3
"""Score aggregator: parses <<SCORES {...}>> blocks emitted by swarm agents.

Agents are instructed to end every report with a machine-readable line:
    <<SCORES {"ps": "26165", "role": "advocate", "feasibility": 8, ...}>>

Usage: python3 aggregate_scores.py <swarm_output.txt> [--phase NAME]
Prints a per-PS table (mean per axis across agents) sorted by composite.
Composite = feasibility + demo_wow + uniqueness + punch + win_prob + go_no_go - data_risk - severity
(only axes present are used; missing axes are skipped).
"""
import json, re, sys, collections

PATTERN = re.compile(r'<<SCORES\s*(\{.*?\})\s*>>', re.S)


def main():
    path = sys.argv[1]
    text = open(path, encoding='utf-8', errors='replace').read()
    blocks = []
    for m in PATTERN.finditer(text):
        try:
            blocks.append(json.loads(m.group(1)))
        except json.JSONDecodeError:
            pass

    if not blocks:
        print(f"No SCORES blocks found in {path}")
        sys.exit(1)

    by_ps = collections.defaultdict(list)
    for b in blocks:
        pid = str(b.get('ps', '?')).strip().upper()
        pid = pid.removeprefix('SIH')
        by_ps[pid].append(b)

    axes = sorted({k for b in blocks for k in b
                   if k not in ('ps', 'role', 'item') and isinstance(b[k], (int, float))})
    print(f"Parsed {len(blocks)} score blocks across {len(by_ps)} PS. Axes: {axes}\n")

    rows = []
    for ps, bs in by_ps.items():
        means = {}
        for a in axes:
            vals = [b[a] for b in bs if isinstance(b.get(a), (int, float))]
            if vals:
                means[a] = round(sum(vals) / len(vals), 2)
        composite = (means.get('feasibility', 0) + means.get('demo_wow', 0)
                     + means.get('uniqueness', 0) + means.get('punch', 0)
                     + means.get('win_prob', 0) + means.get('go_no_go', 0)
                     - means.get('data_risk', 0) - means.get('severity', 0))
        rows.append((ps, round(composite, 2), len(bs), means))

    rows.sort(key=lambda r: -r[1])
    hdr = f"{'PS':8} {'COMP':>6} {'N':>3} " + " ".join(f"{a[:8]:>9}" for a in axes)
    print(hdr)
    print('-' * len(hdr))
    for ps, comp, n, means in rows:
        print(f"{ps:8} {comp:6.2f} {n:3} " + " ".join(f"{means.get(a, 0):9.2f}" for a in axes))

    out = path.rsplit('.', 1)[0] + '.aggregated.json'
    with open(out, 'w') as f:
        json.dump({'blocks': blocks,
                   'summary': [{'ps': ps, 'composite': c, 'n_agents': n, 'means': m}
                               for ps, c, n, m in rows]}, f, indent=1)
    print(f"\nWrote {out}")


if __name__ == '__main__':
    main()
