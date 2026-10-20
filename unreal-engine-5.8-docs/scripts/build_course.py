#!/usr/bin/env python3
"""Build game-dev/khoa-hoc-unreal-engine.html from course_src parts + course_images.json."""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(HERE, "course_src")
OUT = os.path.join(os.path.dirname(ROOT), "khoa-hoc-unreal-engine.html")  # game-dev/

html = ""
for p in ["part1.html", "part2.html", "part3.html"]:
    html += open(os.path.join(SRC, p), encoding="utf-8").read()

# ---- typo fixes ----
# Toàn bộ lỗi chính tả/ký tự lỗi đã được bake thẳng vào course_src (2026-10-19).
# Giữ list rỗng để còn chỗ vá nhanh lúc build nếu cần.
FIXES = [
]
for a, b in FIXES:
    if a in html:
        html = html.replace(a, b)
    else:
        print("fix not found (ok if fixed another way):", a[:40])

# ---- load titles + images ----
toc = json.load(open(os.path.join(ROOT, "_raw", "toc.json"), encoding="utf-8"))
titles = {}
def walk(es):
    for e in es:
        titles[e["slug"]] = e["title"]
        walk(e.get("sub_entries") or [])
walk(toc["entries"])

imgs = json.load(open(os.path.join(HERE, "course_images.json"), encoding="utf-8"))

# ---- link tokens ----
def link_repl(m):
    slug = m.group(1)
    t = titles.get(slug)
    if t:
        return f'<a class="inline" href="unreal-engine-5.8-docs/site/{slug}/">{t}</a>'
    print("!! missing link slug:", slug)
    return slug
html = re.sub(r"\{\{L:([a-z0-9/-]+)\}\}", link_repl, html)

# ---- image tokens ----
def img_repl(m):
    slug, idx, cap = m.group(1), int(m.group(2)), m.group(3)
    lst = imgs.get(slug) or []
    if idx >= len(lst):
        print(f"!! missing image {slug}:{idx} (has {len(lst)})")
        return ""
    im = lst[idx]
    src = im["f"]
    if not os.path.exists(os.path.join(os.path.dirname(ROOT), src)):
        print("!! image file missing on disk:", src)
    cap_esc = cap or im.get("c") or ""
    return (f'<figure class="fig"><img src="{src}" alt="{cap_esc}" loading="lazy">'
            f'<figcaption>{cap_esc}</figcaption></figure>')
html = re.sub(r"\{\{I:([a-z0-9/-]+):(\d+)(?:\|([^}]*))?\}\}", img_repl, html)

leftover = re.findall(r"\{\{[LI]:[^}]*\}\}", html)
if leftover:
    print("!! UNRESOLVED TOKENS:", leftover)

# ---- GitHub Pages shim: link docs mirror -> dev.epicgames.com khi chạy trên github.io ----
SHIM = """<script>
/* Chạy trên GitHub Pages: docs mirror không được publish (giới hạn 1 GB) —
   chuyển link tới trang docs sang site chính thức của Epic Developer Community.
   Ở local (serve.py) link giữ nguyên, trỏ vào bản mirror. */
(function () {
  if (!/(^|\\.)github\\.io$/.test(location.hostname)) return;
  var EPIC = "https://dev.epicgames.com/documentation/en-us/unreal-engine";
  var PRE = "unreal-engine-5.8-docs/site/";
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a[href^='" + PRE + "']");
    if (!a) return;
    var rest = a.getAttribute("href").slice(PRE.length).split("#")[0].split("?")[0].replace(/\\/+$/, "");
    if (!rest || rest.indexOf("images/") === 0) return;
    e.preventDefault();
    location.href = EPIC + "/" + rest;
  }, true);
})();
</script>
"""
html = html.replace("</body>", SHIM + "</body>")

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print(f"OK wrote {OUT} ({os.path.getsize(OUT)//1024} KB), figures resolved")
