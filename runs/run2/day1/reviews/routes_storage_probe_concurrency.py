"""Concurrency probes for the routes/storage review (SEV1 finding 1).

Usage:
  SIF_DB_PATH=/tmp/sif-review/test.db SIF_MODEL_PATH=artifacts/models/masked-v1/sif_multitask_int8.onnx \
    SIF_EXPLAIN_LLM=0 .venv/bin/python -m uvicorn app.main:app --port 8191 &
  # seed 5050 rows: POST artifacts/demo/bulk_ingest_5k.csv to /api/ingest
  .venv/bin/python runs/run2/day1/reviews/routes_storage_probe_concurrency.py MODE
MODE: detector | readonly | pageload | pageload_writer
"""
import concurrent.futures as cf, collections, json, sys, threading, time
import urllib.error, urllib.request

BASE = "http://127.0.0.1:8191"
MODE = sys.argv[1] if len(sys.argv) > 1 else "detector"
stop = time.time() + 30
stats = collections.Counter()
lock = threading.Lock()

def bump(k):
    with lock: stats[k] += 1

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.loads(r.read())

truth = get("/api/reports/100")
TRUTH_SCORE = truth["prediction"]["sif_score"]
TRUTH_TEXT = truth["report"]["text"]

def reader_fixed():
    while time.time() < stop:
        try:
            d = get("/api/reports/100")
            if d["id"] != 100: bump("SILENT wrong id")
            if d["report"]["text"] != TRUTH_TEXT: bump("SILENT wrong text")
            if d["prediction"] is None: bump("SILENT prediction dropped")
            elif abs(d["prediction"]["sif_score"] - TRUTH_SCORE) > 1e-9: bump("SILENT wrong score")
            bump("ok")
        except urllib.error.HTTPError as e:
            bump(f"http {e.code}")
        except Exception as e:
            bump(f"err {type(e).__name__}")

def reader_density():
    while time.time() < stop:
        try:
            get("/api/density?by=site"); bump("density ok")
        except urllib.error.HTTPError as e:
            bump(f"density http {e.code}")
        except Exception as e:
            bump(f"density err {type(e).__name__}")

def reader_list():
    while time.time() < stop:
        try:
            get("/api/reports?limit=200"); bump("list ok")
        except urllib.error.HTTPError as e:
            bump(f"list http {e.code}")
        except Exception as e:
            bump(f"list err {type(e).__name__}")

def writer_explain_cache():
    n = 0
    while time.time() < stop:
        n += 1
        try:
            urllib.request.urlopen(urllib.request.Request(
                f"{BASE}/api/classify?explain=1&llm=0",
                data=json.dumps({"text": f"cache-write probe {n}: dropped object from derrick nearly hit roustabout on deck below."}).encode(),
                headers={"Content-Type": "application/json"}), timeout=60).read()
            bump("write ok")
        except Exception as e:
            bump(f"write err {type(e).__name__}")
        if MODE == "pageload_writer":
            time.sleep(0.25)

def page_load(i):
    try:
        with cf.ThreadPoolExecutor(max_workers=3) as ex:
            futs = [ex.submit(get, "/api/health"), ex.submit(get, "/api/reports?limit=50"), ex.submit(get, "/api/review")]
            for f in futs: f.result()
        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            futs = [ex.submit(get, "/api/health"), ex.submit(get, "/api/density?by=site")]
            for f in futs: f.result()
        get(f"/api/reports/{200 + (i % 50)}")
        bump("loads ok")
    except urllib.error.HTTPError as e:
        bump(f"load FAIL http {e.code}")
    except Exception as e:
        bump(f"load FAIL {type(e).__name__}")

if MODE == "detector":        # 3 fixed readers + 2 density + 2 cache-writers
    with cf.ThreadPoolExecutor(max_workers=7) as ex:
        futs = [ex.submit(reader_fixed) for _ in range(3)]
        futs += [ex.submit(reader_density) for _ in range(2)]
        futs += [ex.submit(writer_explain_cache) for _ in range(2)]
        for f in futs: f.result()
elif MODE == "readonly":      # 4 readers, ZERO writers
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(reader_fixed), ex.submit(reader_density), ex.submit(reader_density), ex.submit(reader_list)]
        for f in futs: f.result()
elif MODE == "pageload":      # sequential page loads, 3+2 internal parallelism
    i = 0
    while time.time() < stop:
        i += 1
        page_load(i)
elif MODE == "pageload_writer":  # page loads + one operator tab writing every 0.25s
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        wf = ex.submit(writer_explain_cache)
        futs, i = [], 0
        while time.time() < stop:
            i += 1
            futs.append(ex.submit(page_load, i))
            time.sleep(0.05)
        for f in futs: f.result()
        wf.result()

for k, v in stats.most_common():
    print(f"{v:6d}  {k}")
