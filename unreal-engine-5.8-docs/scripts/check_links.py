#!/usr/bin/env python3
"""Check generated site: dead internal links, missing images, page count."""
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")

pages = set()
for dirpath, dirnames, filenames in os.walk(SITE):
    for f in filenames:
        if f == "index.html":
            rel = os.path.relpath(dirpath, SITE).replace("\\", "/")
            pages.add("" if rel == "." else rel)

dead_links = Counter()
missing_imgs = Counter()
total_links = 0
total_imgs = 0
files = 0
for dirpath, _, filenames in os.walk(SITE):
    for f in filenames:
        if not f.endswith(".html"):
            continue
        files += 1
        fp = os.path.join(dirpath, f)
        cur = os.path.relpath(dirpath, SITE).replace("\\", "/")
        with open(fp, encoding="utf-8") as fh:
            html = fh.read()
        for m in re.finditer(r'href="(\.\./)?([a-z0-9-]+)/?"', html):
            total_links += 1
            target = m.group(2)
            if target not in pages:
                dead_links[target] += 1
        for m in re.finditer(r'src="\.\./images/([^"]+)"', html):
            total_imgs += 1
            if not os.path.exists(os.path.join(SITE, "images", m.group(1))):
                missing_imgs[m.group(1)] += 1

print(f"pages generated: {len(pages)} (html files: {files})")
print(f"internal links: {total_links}, dead: {sum(dead_links.values())} "
      f"({len(dead_links)} unique)")
for slug, c in dead_links.most_common(20):
    print(f"  {slug}: {c}")
print(f"local image refs: {total_imgs}, missing files: {sum(missing_imgs.values())} "
      f"({len(missing_imgs)} unique)")
for im, c in list(missing_imgs.items())[:10]:
    print(f"  {im}: {c}")
