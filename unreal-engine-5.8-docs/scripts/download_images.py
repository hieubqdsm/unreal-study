#!/usr/bin/env python3
"""Download images.
mode=cf   : CloudFront originals for mapped images (concurrent, safe)
mode=api  : resize API for uuid-only images (gentle 1-thread, ~1 rps)
"""
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "_raw")
IMG = os.path.join(ROOT, "site", "images")
CF = "https://d1iv7db44yhgxn.cloudfront.net/documentation/images/{}/{}"
API_IMG = "https://dev.epicgames.com/community/api/documentation/image/{}?resizing_type=fit&width=1200&height=1200"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "image/avif,image/webp,image/png,image/*,*/*;q=0.8",
           "Referer": "https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-documentation",
           "Cookie": "visitor-uuid=8d067b67-cbc9-4ea7-8669-c51ba40fb271; _epicSID=78ed88418efc4625ae8447d2f11dc40b"}


def ext_for(ct, name):
    n = (name or "").lower()
    if n.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
        return ".jpg" if n.endswith((".jpg", ".jpeg")) else n[n.rfind("."):]
    ct = (ct or "").lower()
    if "png" in ct: return ".png"
    if "webp" in ct: return ".webp"
    if "gif" in ct: return ".gif"
    if "svg" in ct: return ".svg"
    return ".jpg"


def local_name(uuid, ext):
    return os.path.join(IMG, uuid + ext)


def dl_cf(entry):
    uuid, info = entry
    # prefer extension from file_name
    ext = ext_for(info.get("content_type"), info["file_name"])
    out = local_name(uuid, ext)
    if os.path.exists(out) and os.path.getsize(out) > 100:
        return "cached"
    # try both derived and .png fallback if 403 (name mismatch)
    for fn in [info["file_name"], info["file_name"].replace(" ", "-")]:
        url = CF.format(uuid, requests.utils.quote(fn))
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
            if r.status_code == 200 and len(r.content) > 100:
                ext2 = ext_for(r.headers.get("Content-Type"), fn)
                out = local_name(uuid, ext2)
                with open(out, "wb") as f:
                    f.write(r.content)
                return "ok"
        except Exception:
            pass
    return "fail:" + uuid


def run_cf():
    mapped = json.load(open(os.path.join(RAW, "images_mapped.json"), encoding="utf-8"))
    print(f"CloudFront images: {len(mapped)}", flush=True)
    done = fail = 0
    fails = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(dl_cf, e): e[0] for e in mapped.items()}
        for fut in as_completed(futs):
            st = fut.result()
            if st.startswith("fail"):
                fail += 1
                fails.append(st[5:])
            else:
                done += 1
            n = done + fail
            if n % 250 == 0:
                rate = n / max(time.time() - t0, 1)
                print(f"  {n}/{len(mapped)} fail={fail} ({rate:.1f}/s eta {(len(mapped)-n)/max(rate,.01)/60:.1f}m)", flush=True)
    with open(os.path.join(RAW, "_imgcf_failed.json"), "w") as f:
        json.dump(fails, f)
    print(f"CF DONE ok={done} fail={fail}", flush=True)


def run_api():
    uuids = json.load(open(os.path.join(RAW, "images_api_only.json"), encoding="utf-8"))
    # skip those already downloaded under any extension
    have = {f[:36] for f in os.listdir(IMG)} if os.path.isdir(IMG) else set()
    todo = [u for u in uuids if u not in have]
    print(f"API images: {len(todo)}/{len(uuids)}", flush=True)
    s = requests.Session(); s.headers.update(HEADERS)
    ok = 0
    for i, uuid in enumerate(todo):
        for attempt in range(40):
            try:
                r = s.get(API_IMG.format(uuid), timeout=60)
                if r.status_code == 200 and len(r.content) > 100:
                    ext = ext_for(r.headers.get("Content-Type"), "")
                    with open(local_name(uuid, ext), "wb") as f:
                        f.write(r.content)
                    ok += 1
                    break
                if r.status_code in (429, 503):
                    if attempt % 5 == 0:
                        print(f"  429 at {uuid} attempt {attempt}", flush=True)
                    time.sleep(45 + random.uniform(0, 15))
                else:
                    time.sleep(3)
            except Exception:
                time.sleep(5)
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(todo)}", flush=True)
        time.sleep(random.uniform(0.5, 0.9))
    print(f"API DONE ok={ok}/{len(todo)}", flush=True)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "cf"
    run_cf() if mode == "cf" else run_api()
