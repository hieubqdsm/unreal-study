#!/usr/bin/env python3
"""Post-crawl pipeline: images (CloudFront + variants + API fallback) then generate site."""
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "_raw")
IMG = os.path.join(ROOT, "site", "images")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
      "Referer": "https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-documentation",
      "Cookie": "visitor-uuid=8d067b67-cbc9-4ea7-8669-c51ba40fb271; _epicSID=78ed88418efc4625ae8447d2f11dc40b"}
CF = "https://d1iv7db44yhgxn.cloudfront.net/documentation/images/{}/{}"
API_IMG = "https://dev.epicgames.com/community/api/documentation/image/{}?resizing_type=fit&width=1200&height=1200"


def ext_of(ct, name):
    n = (name or "").lower()
    for e in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'):
        if n.endswith(e):
            return '.jpg' if e in ('.jpg', '.jpeg') else e
    ct = (ct or '').lower()
    if 'png' in ct: return '.png'
    if 'webp' in ct: return '.webp'
    if 'gif' in ct: return '.gif'
    if 'svg' in ct: return '.svg'
    return '.jpg'


def have():
    return {f[:36] for f in os.listdir(IMG)} if os.path.isdir(IMG) else set()


def variants(fn):
    dbl = re.sub(r'(\.\w{3,4})\1$', r'\1', fn)
    return [fn, fn.lower(), dbl, dbl.lower(),
            fn.replace(' ', '-'), fn.replace(' ', '-').lower()]


def cf_download(entry):
    uuid, info = entry
    for v in variants(info["file_name"]):
        try:
            r = requests.get(CF.format(uuid, requests.utils.quote(v)), headers=UA, timeout=90)
        except Exception:
            continue
        if r.status_code == 200 and len(r.content) > 100:
            with open(os.path.join(IMG, uuid + ext_of(r.headers.get('Content-Type'), v)), 'wb') as f:
                f.write(r.content)
            return uuid
    return None


def stage_cf():
    mapped = json.load(open(os.path.join(RAW, "images_mapped.json"), encoding="utf-8"))
    h = have()
    todo = {u: i for u, i in mapped.items() if u not in h}
    print(f"[cf] todo {len(todo)}/{len(mapped)}", flush=True)
    fails = []
    done = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(cf_download, e): e[0] for e in todo.items()}
        for fut in as_completed(futs):
            if fut.result():
                done += 1
            else:
                fails.append(futs[fut])
            n = done + len(fails)
            if n % 300 == 0:
                rate = n / max(time.time() - t0, 1)
                print(f"  [cf] {n}/{len(todo)} fail={len(fails)} ({rate:.1f}/s)", flush=True)
    print(f"[cf] done ok={done} fail={len(fails)}", flush=True)
    return fails


def api_download(uuid, s):
    for attempt in range(60):
        try:
            r = s.get(API_IMG.format(uuid), timeout=60)
            if r.status_code == 200 and len(r.content) > 100:
                with open(os.path.join(IMG, uuid + ext_of(r.headers.get('Content-Type'), '')), 'wb') as f:
                    f.write(r.content)
                return True
            if r.status_code in (429, 503):
                if attempt % 6 == 0:
                    print(f"  [api] 429 {uuid[:8]} attempt {attempt}", flush=True)
                time.sleep(40)
            else:
                time.sleep(2)
        except Exception:
            time.sleep(4)
    return False


def stage_api(uuids):
    h = have()
    todo = [u for u in uuids if u not in h]
    print(f"[api] todo {len(todo)}", flush=True)
    s = requests.Session()
    s.headers.update(UA)
    ok = 0
    for i, u in enumerate(todo):
        if api_download(u, s):
            ok += 1
        else:
            print(f"  [api] FAILED {u}", flush=True)
        if (i + 1) % 100 == 0:
            print(f"  [api] {i+1}/{len(todo)}", flush=True)
        time.sleep(0.55)
    print(f"[api] done ok={ok}/{len(todo)}", flush=True)


def main():
    print("== collect refs ==", flush=True)
    subprocess.run([sys.executable, os.path.join(HERE, "collect_images.py")], check=True)
    print("== cloudfront ==", flush=True)
    fails = stage_cf()
    if fails:
        print(f"retrying {len(fails)} via api lane", flush=True)
    print("== api lane (mapped fails + api-only) ==", flush=True)
    api_only = json.load(open(os.path.join(RAW, "images_api_only.json"), encoding="utf-8"))
    stage_api(fails + api_only)
    print("== generate site ==", flush=True)
    subprocess.run([sys.executable, os.path.join(HERE, "generate_site.py")], check=True)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
