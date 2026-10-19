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
FIXES = [
    ("kéo thá", "kéo thả"),
    ("công nghệ标志", "công nghệ biểu tượng"),
    ("ting cài với C++", "tương thích với C++"),
    ("đổi pitch/g因子", "đổi pitch/giá trị"),
    ("nảybounce", "nảy (bounce)"),
    ("vfd tay lên tường", "ví dụ tay đặt lên tường"),
    ("hiện/hện menu", "hiện/ẩn menu"),
    ("Pakks", "Paks"),
    ("exe Mage Movie Render Queue", "Movie Render Queue (MRQ)"),
    ("Ba macro靈 hồn", "Ba macro linh hồn"),
    ("Ba macro灵 hồn", "Ba macro linh hồn"),
    ("cho物 liệu", "cho vật liệu"),
    ("Materia同 Landscape/Spline/Decal?", "Material domain khác: Landscape/Spline/Decal?"),
    ("Data Layer思路 pattern", "Data Layer pattern"),
    ("Thương ngườiBanNgày", "ThươngNhânBanNgày"),
    ("kiểm chứng", "kiểm chứng"),
    ("Bay camera验证", "Bay camera kiểm chứng"),
    ("bay camera验证", "bay camera kiểm chứng"),
    ("đ tán lá thật", "tán lá thật"),
    ("hàng tỷ tri vẫn", "hàng tỷ tam giác vẫn"),
    ("mechan ic", "mechanic"),
    ("Event Tick = reo ruỗi", "Event Tick = gánh nặng"),
    ("GPU RTX/giờ ko chuyên", "GPU RTX hoặc GPU không chuyên"),
    ("phối duet", "phối hợp"),
    ("gọi DestroyActor +.Broadcast delegates", "gọi DestroyActor và broadcast delegate"),
    ("even procedural animation runtime", "thậm chí procedural animation runtime"),
    ("marketplace/Compose nhớ format này", "marketplace theo format này"),
    ('<td><th switch giữa các tool: Select, Landscape, Foliage, Mesh Paint…</td>',
     '<td>Switch giữa các tool: Select, Landscape, Foliage, Mesh Paint…</td>'),
    ('<p>Mode <span class="term-en">Foliage</p> (Shift+3)',
     '<p>Mode <span class="term-en">Foliage</span> (Shift+3)'),
    ('Niagara — Visual Effects</span></h2>', 'Niagara — Visual Effects</h2>'),
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

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print(f"OK wrote {OUT} ({os.path.getsize(OUT)//1024} KB), figures resolved")
