# Cross-process: a harness-style SECOND process writes precomputed rows to the
# same DB file while the live server is under read+explain load. WAL mode.
import concurrent.futures as cf, json, multiprocessing as mp, time, urllib.request, urllib.error, collections

DB = "/tmp/sif-review/test.db"
BASE = "http://127.0.0.1:8191"

def harness_writer(q):
    import sqlite3
    conn = sqlite3.connect(DB)  # default timeout=5.0s busy handler
    conn.execute("PRAGMA journal_mode=WAL")
    ok = locked = other = 0
    for i in range(300):
        try:
            with conn:
                conn.execute("INSERT OR REPLACE INTO precomputed (key, payload, created_at) VALUES (?, ?, datetime('now'))",
                             (f"harness:{i%50}", json.dumps({"i": i})))
            ok += 1
        except sqlite3.OperationalError as e:
            if "locked" in str(e): locked += 1
            else: other += 1
        except Exception:
            other += 1
    q.put((ok, locked, other))

def server_reader(stats, lock, stop):
    while time.time() < stop:
        try:
            urllib.request.urlopen(BASE+"/api/density?by=activity", timeout=60).read()
            with lock: stats["density ok"] += 1
        except urllib.error.HTTPError as e:
            with lock: stats[f"density http {e.code}"] += 1
        except Exception as e:
            with lock: stats[f"density err {type(e).__name__}"] += 1

def server_explainer(stats, lock, stop):
    n = 0
    while time.time() < stop:
        n += 1
        try:
            urllib.request.urlopen(urllib.request.Request(
                f"{BASE}/api/classify?explain=1&llm=0",
                data=json.dumps({"text": f"crossproc probe {n}: dropped hammer from mast platform during rig move, landed 2m from floorman."}).encode(),
                headers={"Content-Type": "application/json"}), timeout=60).read()
            with lock: stats["explain ok"] += 1
        except urllib.error.HTTPError as e:
            with lock: stats[f"explain http {e.code}"] += 1
        except Exception as e:
            with lock: stats[f"explain err {type(e).__name__}"] += 1

if __name__ == "__main__":
    import threading
    q = mp.Queue()
    p = mp.Process(target=harness_writer, args=(q,))
    stats = collections.Counter()
    lock = threading.Lock()
    stop = time.time() + 30
    p.start()
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(server_reader, stats, lock, stop) for _ in range(2)]
        futs += [ex.submit(server_explainer, stats, lock, stop) for _ in range(2)]
        for f in futs: f.result()
    p.join()
    ok, locked, other = q.get()
    print(f"harness writer: ok={ok} locked={locked} other={other}")
    for k, v in stats.most_common(): print(f"{v:6d}  {k}")
