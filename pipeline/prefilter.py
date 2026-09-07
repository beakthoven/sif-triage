#!/usr/bin/env python3
"""Phase 0: deterministic pre-filter of SIH software problem statements.

Reads the raw CSV, applies hard exclusions (vision/image-AI, generic student
innovation, proprietary-tool-locked, infeasible-illegal), then heuristic
scoring (research-depth penalties, buildability rewards) and emits a ranked
list. Deterministic and transparent — the agent phases do the real judging;
this just keeps them from wasting attention on obvious misfits.

Usage: python3 prefilter.py <raw_csv> <out_dir> [--top N]
"""
import csv, json, re, sys, os

VISION = re.compile(r'\b(image|imagery|vision|cctv|video analytics|satellite imag|camera|drone imag|facial|face recogn|lidar|sonar|radar imag|thermal imag|photo|retinopathy|super resolution|3d model generation|visual perception|optical|ohrc|hyperspectral|ocr)\b', re.I)
PROPRIETARY = re.compile(r'\b(autodesk|revit|forma site)\b', re.I)
INFEASIBLE = re.compile(r'\bdark web\b|de-anonymization', re.I)
RESEARCH = re.compile(r'\bquantum|nwp|numerical weather|downscal|nowcast|wrf|hydrodynamic|signal parameter|\.iq\b|gpu-accelerated|solver|dead reckoning|seismic|electronic warfare|sea-ice|iceberg|subsurface ocean|sonar|digital twin|edge-ai|autonomous|ulpin|3d\b', re.I)
NICHE_DATA = re.compile(r'antarctic|polar|manganese|geological|bitcoin|cryptocurrenc|unidirectional|iq files|wav files|burn-in|space|chandrayaan', re.I)
REWARD = re.compile(r'\bchatbot|assistant|conversational|rag|dashboard|portal|platform|recommend|match|analytics|workflow|verif|monitor|forecast|detect|classif|multilingual|voice|crowdsourc|marketplace|management system|compliance|audit|traceab|anomal|fraud|search|document|grievance|scheme|skill|learning|translation', re.I)
GENERIC_CRUD = re.compile(r'^\s*(a digital platform|portal for|integrated .* (portal|platform)|web-based .* platform)\b', re.I)


def main():
    raw_csv, out_dir = sys.argv[1], sys.argv[2]
    top_n = int(sys.argv[sys.argv.index('--top') + 1]) if '--top' in sys.argv else 24
    rows = list(csv.DictReader(open(raw_csv, encoding='utf-8')))
    soft = [r for r in rows if r['category'].strip().lower() == 'software']

    survivors, excluded = [], []
    for r in soft:
        text = (r['problem statement title'] + ' ' + r['description']).strip()
        pid = r['problem statement id'].strip()
        if r['problem statement title'].strip().lower() == 'student innovation':
            excluded.append((pid, 'student-innovation-generic')); continue
        if VISION.search(text):
            excluded.append((pid, 'vision/image-ai')); continue
        if PROPRIETARY.search(text):
            excluded.append((pid, 'proprietary-tool-locked')); continue
        if INFEASIBLE.search(text):
            excluded.append((pid, 'infeasible-illegal')); continue

        score = 0.0
        score -= 3.0 * len(RESEARCH.findall(text))
        score -= 2.0 * len(NICHE_DATA.findall(text))
        score += min(6.0, 0.75 * len(REWARD.findall(text)))
        if r['dataset link'].strip():
            score += 2.0
        if GENERIC_CRUD.search(r['problem statement title']):
            score -= 1.0
        survivors.append({
            'id': pid,
            'title': r['problem statement title'].strip(),
            'org': r['organization'].strip(),
            'dept': r['department'].strip(),
            'theme': r['theme'].strip(),
            'dataset': r['dataset link'].strip(),
            'desc': re.sub(r'\s+', ' ', r['description']).strip(),
            'heuristic': round(score, 2),
        })

    survivors.sort(key=lambda x: -x['heuristic'])
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'phase0_ranked.json'), 'w') as f:
        json.dump(survivors, f, indent=1, ensure_ascii=False)
    with open(os.path.join(out_dir, 'phase0_excluded.json'), 'w') as f:
        json.dump(excluded, f, indent=1)
    with open(os.path.join(out_dir, 'phase0_shortlist.json'), 'w') as f:
        json.dump(survivors[:top_n], f, indent=1, ensure_ascii=False)

    print(f"software={len(soft)} survivors={len(survivors)} excluded={len(excluded)}")
    print(f"--- TOP {top_n} ---")
    for i, s in enumerate(survivors[:top_n], 1):
        print(f"{i:2}. [{s['heuristic']:6.2f}] {s['id']} | {s['title'][:90]}")
    print(f"--- NEXT 10 (bench) ---")
    for i, s in enumerate(survivors[top_n:top_n + 10], top_n + 1):
        print(f"{i:2}. [{s['heuristic']:6.2f}] {s['id']} | {s['title'][:90]}")


if __name__ == '__main__':
    main()
