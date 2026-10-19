#!/usr/bin/env python3
"""Gentle single-threaded crawler: ~1 req/s with jitter, long backoff on 429."""
import json
import os
import random
import sys
import time

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


def main():
    slugs = all_slugs()
    todo = []
    for s in slugs:
        p = os.path.join(RAW, s + ".json")
        if not os.path.exists(p) or os.path.getsize(p) < 3:
            todo.append(s)
    print(f"remaining: {len(todo)}/{len(slugs)}", flush=True)
    session = requests.Session()
    session.headers.update(HEADERS)
    ok = fail = 0
    t0 = time.time()
    for i, slug in enumerate(todo):
        path = os.path.join(RAW, slug + ".json")
        for attempt in range(30):
            try:
                r = session.get(API, params={
                    "path": f"/documentation/unreal-engine/{slug}",
                    "lang": "en-us",
                }, timeout=30)
                if r.status_code == 200 and r.text.strip():
                    try:
                        data = r.json()
                    except Exception:
                        time.sleep(2); continue
                    if "blocks" in data or "redirect_url" in data:
                        with open(path, "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False)
                        ok += 1
                        break
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump({"missing": True, "status": "bad-shape"}, f)
                    ok += 1
                    break
                if r.status_code in (429, 503):
                    # rate limited: long cooldown, keep retrying
                    if attempt % 5 == 0:
                        print(f"  429 at {slug} attempt {attempt}: sleeping 45s", flush=True)
                    time.sleep(45 + random.uniform(0, 15))
                    continue
                if r.status_code == 404:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump({"missing": True, "status": 404}, f)
                    ok += 1
                    break
                time.sleep(3)
            except Exception:
                time.sleep(5)
        else:
            fail += 1
            print(f"  FAILED after retries: {slug}", flush=True)
        if (i + 1) % 25 == 0:
            rate = (i + 1) / max(time.time() - t0, 1)
            eta = (len(todo) - i - 1) / max(rate, 0.01) / 60
            print(f"  {i+1}/{len(todo)} ok={ok} fail={fail} ({rate:.2f}/s eta {eta:.0f}m)", flush=True)
        time.sleep(random.uniform(0.55, 1.0))
    print(f"DONE ok={ok} fail={fail} in {(time.time()-t0)/60:.1f}m", flush=True)


if __name__ == "__main__":
    main()
