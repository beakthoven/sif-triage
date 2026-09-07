#!/usr/bin/env python3
"""Item builder: generates AgentSwarm items arrays from shortlisted PS data.

Usage:
  python3 build_items.py phase1 <shortlist.json> <out.json>
  python3 build_items.py phase2 <shortlist.json> <out.json>   # engineering, per-PS
Each item embeds PS data (truncated desc) + role assignment. The shared
context lives in the AgentSwarm prompt_template, not in items.
"""
import json, sys

ROLES_P1 = {
    'advocate': "ROLE: ADVOCATE for this PS. Steelman it ruthlessly: why it wins under the team's constraints, best architecture (1 para), the 90-second demo script for NON-technical judges, what data sources you'd use (verify 1-2 exist via web/gh if load-bearing), and how to beat teams building the same PS.",
    'prosecutor': "ROLE: PROSECUTOR against this PS. Destroy it: hunt kill-shots on data availability (verify claims via web/gh where load-bearing), hidden spec traps (read the description for vision/hard-research modules smuggled in), training feasibility, crowding (search GitHub for existing SIH-2026 repos on this PS ID), judge Q&A failures, demo fragility. Score each attack's severity /10.",
}


def ps_block(ps):
    desc = ps['desc'][:1400]
    return (f"CANDIDATE PS {ps['id']}: \"{ps['title']}\"\n"
            f"Org: {ps['org']} | Theme: {ps['theme']}\n"
            f"Dataset field: {ps['dataset'][:200] or '(none provided)'}\n"
            f"Description: {desc}")


def main():
    mode, shortlist_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    shortlist = json.load(open(shortlist_path))
    items = []
    if mode == 'phase1':
        for ps in shortlist:
            for role, instr in ROLES_P1.items():
                items.append(f"{instr}\n\n{ps_block(ps)}")
    elif mode == 'phase2':
        for ps in shortlist:
            items.append(ps_block(ps))
    json.dump(items, open(out_path, 'w'), indent=1, ensure_ascii=False)
    print(f"wrote {len(items)} items to {out_path}")


if __name__ == '__main__':
    main()
