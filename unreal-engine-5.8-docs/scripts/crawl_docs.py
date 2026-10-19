#!/usr/bin/env python3
"""Crawl all UE 5.8 document.json files into _raw/<slug>.json (resumable)."""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "_raw")
API = "https://dev.epicgames.com/community/api/documentation/document.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "application/json",
           "Referer": "https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-documentation"}


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


def fetch(slug, session, tries=5):
    path = os.path.join(RAW, slug + ".json")
    if os.path.exists(path) and os.path.getsize(path) > 2:
        return slug, "cached"
    for attempt in range(tries):
        try:
            r = session.get(API, params={
                "path": f"/documentation/unreal-engine/{slug}",
                "lang": "en-us",
            }, headers=HEADERS, timeout=30)
            if r.status_code == 200 and r.text.strip():
                data = r.json()
                if "blocks" in data or "redirect_url" in data:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False)
                    return slug, "ok"
                # unexpected shape -> save anyway for inspection
                with open(path + ".bad", "w", encoding="utf-8") as f:
                    f.write(r.text[:2000])
                return slug, "bad-shape"
            if r.status_code in (429, 503):
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code == 404:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"missing": True, "status": 404}, f)
                return slug, "404"
            time.sleep(1 + attempt)
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return slug, "failed"


def main():
    slugs = all_slugs()
    print(f"total pages: {len(slugs)}", flush=True)
    done = failed = 0
    t0 = time.time()
    session = requests.Session()
    session.headers.update(HEADERS)
    fails = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(fetch, s, session): s for s in slugs}
        for fut in as_completed(futs):
            slug, status = fut.result()
            if status in ("cached", "ok"):
                done += 1
            elif status in ("404", "bad-shape"):
                print(f"  {status}: {slug}", flush=True)
                done += 1
            else:
                failed += 1
                fails.append(slug)
            n = done + failed
            if n % 100 == 0:
                rate = n / max(time.time() - t0, 1)
                print(f"  {n}/{len(slugs)} done={done} failed={failed} "
                      f"({rate:.1f}/s eta {((len(slugs)-n)/max(rate,0.01))/60:.1f}m)", flush=True)
    with open(os.path.join(RAW, "_failed.json"), "w", encoding="utf-8") as f:
        json.dump(fails, f)
    print(f"FINISHED ok={done} failed={failed} in {(time.time()-t0)/60:.1f}m", flush=True)


if __name__ == "__main__":
    main()
