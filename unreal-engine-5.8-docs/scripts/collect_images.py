#!/usr/bin/env python3
"""Collect all image references from crawled docs.
- storage_key + file_name -> CloudFront originals (fast lane)
- uuid-only (markdown html refs) -> resize API (gentle lane, written to list)
Outputs: _raw/images_mapped.json  {uuid: {file_name, content_type}}
         _raw/images_api_only.json [uuid, ...]
"""
import json
import glob
import os
import re
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "_raw")

mapped = {}
api_only = collections.Counter()


def note_image(im):
    if not isinstance(im, dict):
        return
    key = im.get("storage_key")
    if not key:
        return
    fn = im.get("file_name")
    if fn:
        mapped[key] = {"file_name": fn, "content_type": im.get("content_type", "")}
    else:
        api_only[key] += 1


def scan_block(b):
    if not isinstance(b, dict):
        return
    note_image(b.get("image"))
    note_image(b.get("banner_image"))
    note_image(b.get("thumbnail_image"))
    note_image(b.get("image_left"))
    note_image(b.get("image_right"))
    for c in b.get("cases") or []:
        scan_block(c)
    for it in b.get("items") or []:
        if isinstance(it, dict):
            note_image(it.get("image"))
            key = it.get("thumbnail_storage_key")
            if key:
                api_only[key] += 1
        elif isinstance(it, list):
            for cell in it:
                scan_block(cell) if isinstance(cell, dict) else None
    for im in b.get("images") or []:
        note_image(im)
    for row in b.get("rows") or []:
        if isinstance(row, list):
            for cell in row:
                if isinstance(cell, list):
                    for cb in cell:
                        scan_block(cb)
    for sub in b.get("blocks") or []:
        scan_block(sub)
    sb = b.get("switchable_blocks")
    if isinstance(sb, dict):
        for v in sb.values():
            if isinstance(v, list):
                for sub in v:
                    scan_block(sub)


for fp in glob.glob(os.path.join(RAW, "**", "*.json"), recursive=True):
    base = os.path.basename(fp)
    if base.startswith("_"):
        continue
    try:
        d = json.load(open(fp, encoding="utf-8"))
    except Exception:
        continue
    if not isinstance(d, dict):
        continue
    for fld in ("banner_image", "thumbnail_image"):
        v = d.get(fld)
        if isinstance(v, dict):
            note_image(v)
        elif isinstance(v, list):
            for x in v:
                note_image(x)
    for fld in ("related_documents", "prereq_documents"):
        for rd in d.get(fld) or []:
            if isinstance(rd, dict):
                note_image(rd.get("thumbnail_image"))
                for b in rd.get("blocks") or []:
                    scan_block(b)
    for b in d.get("blocks", []):
        scan_block(b)
        html = b.get("content_html", "") or ""
        for u in re.findall(r"documentation/image/([a-f0-9-]{36})", html):
            api_only[u] += 1

# api_only minus mapped
api_only = {u: c for u, c in api_only.items() if u not in mapped}
with open(os.path.join(RAW, "images_mapped.json"), "w", encoding="utf-8") as f:
    json.dump(mapped, f, ensure_ascii=False, indent=0)
with open(os.path.join(RAW, "images_api_only.json"), "w", encoding="utf-8") as f:
    json.dump(sorted(api_only), f, ensure_ascii=False, indent=0)
print(f"mapped(CloudFront): {len(mapped)}  api_only: {len(api_only)}")
