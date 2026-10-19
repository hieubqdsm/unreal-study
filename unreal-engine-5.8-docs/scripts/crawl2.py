#!/usr/bin/env python3
"""Two-worker gentle crawler (~1.4 rps total, shared 429 cooldown)."""
import json
import os
import random
import threading
import time
from queue import Queue

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "_raw")
API = "https://dev.epicgames.com/community/api/documentation/document.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-documentation",
    "Cookie": "visitor-uuid=8d067b67-cbc9-4ea7-8669-c51ba40fb271; _epicSID=78ed88418efc4625ae8447d2f11dc40b",
}

lock = threading.Lock()
stats = {"ok": 0, "fail": 0, "n": 0}
fails = []
COOLDOWN = threading.Event()  # set while cooling down


def all_slugs():
    with open(os.path.join(RAW, "toc.json"), encoding="utf-8") as f:
        toc = json.load(f)
    slugs = []

    def walk(entries):
        for e in entries:
            slugs.append(e["slug"])
            walk(e.get("sub_entries") or [])
    walk(toc["entries"])
    return slugs


def worker(q, wid):
    session = requests.Session()
    session.headers.update(HEADERS)
    while True:
        try:
            slug = q.get_nowait()
        except Exception:
            return
        path = os.path.join(RAW, slug + ".json")
        ok = False
        for attempt in range(12):
            if COOLDOWN.is_set():
                time.sleep(10)
                continue
            try:
                r = session.get(API, params={"path": f"/documentation/unreal-engine/{slug}", "lang": "en-us"}, timeout=60, allow_redirects=False)
                if r.status_code in (301, 302, 303, 307, 308):
                    loc = r.headers.get("Location", "")
                    data = None
                    try:
                        data = r.json()
                    except Exception:
                        pass
                    payload = data if isinstance(data, dict) and "redirect_url" in data else {"redirect_url": loc}
                    d_ = os.path.dirname(path)
                    if d_:
                        os.makedirs(d_, exist_ok=True)
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(payload, f, ensure_ascii=False)
                    ok = True
                    break
                if r.status_code == 200 and r.text.strip():
                    try:
                        data = r.json()
                    except Exception:
                        time.sleep(2); continue
                    if "blocks" in data or "redirect_url" in data:
                        d_ = os.path.dirname(path)
                        if d_:
                            os.makedirs(d_, exist_ok=True)
                        with open(path, "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False)
                        ok = True
                        break
                    d_ = os.path.dirname(path)
                    if d_:
                        os.makedirs(d_, exist_ok=True)
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump({"missing": True, "status": "bad-shape"}, f)
                    ok = True
                    break
                if r.status_code in (429, 503):
                    COOLDOWN.set()
                    print(f"  [w{wid}] 429 on {slug}: global cooldown 60s", flush=True)
                    time.sleep(60)
                    COOLDOWN.clear()
                    continue
                if r.status_code == 404:
                    d_ = os.path.dirname(path)
                    if d_:
                        os.makedirs(d_, exist_ok=True)
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump({"missing": True, "status": 404}, f)
                    ok = True
                    break
                time.sleep(3)
            except Exception:
                time.sleep(4)
        with lock:
            stats["n"] += 1
            if ok:
                stats["ok"] += 1
            else:
                stats["fail"] += 1
                fails.append(slug)
                print(f"  FAILED: {slug}", flush=True)
            n = stats["n"]
            if n % 50 == 0:
                print(f"  {n} done ok={stats['ok']} fail={stats['fail']}", flush=True)
        q.task_done()
        time.sleep(random.uniform(1.2, 1.8))


def main():
    slugs = all_slugs()
    todo = [s for s in slugs
            if not os.path.exists(os.path.join(RAW, s + ".json"))]
    print(f"remaining {len(todo)}/{len(slugs)}", flush=True)
    q = Queue()
    for s in todo:
        q.put(s)
    t0 = time.time()
    threads = [threading.Thread(target=worker, args=(q, i), daemon=True) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with open(os.path.join(RAW, "_failed.json"), "w", encoding="utf-8") as f:
        json.dump(fails, f)
    rate = stats["n"] / max(time.time() - t0, 1)
    print(f"DONE ok={stats['ok']} fail={stats['fail']} rate={rate:.2f}/s", flush=True)


if __name__ == "__main__":
    main()
