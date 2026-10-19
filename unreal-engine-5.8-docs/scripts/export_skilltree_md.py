#!/usr/bin/env python3
"""Export unreal-skill-tree.md (Mermaid + tables + checklist) from skilltree_data.json dumped from the HTML."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, 'skilltree_data.json'), encoding='utf-8'))
nodes, lanes = d['nodes'], d['lanes']
by_id = {n['id']: n for n in nodes}
LV = lambda t: 'Starter' if t <= 3 else ('Intermediate' if t <= 5 else 'Advanced')
OUT = os.path.join(os.path.dirname(HERE), '..', 'unreal-skill-tree.md')

def mid(s):
    return s.replace('"', "'")

out = []
out.append('# Unreal Engine 5.8 — Skill Tree (bản đối chiếu MD)')
out.append('')
out.append('Sơ đồ kỹ năng dạng RPG: **trục dọc = 7 nhánh chuyên môn**, **trục ngang = 8 tier** '
           '(Tier 1–3 Starter · Tier 4–5 Intermediate · Tier 6–8 Advanced). '
           'File này đối chiếu với `unreal-skill-tree.html` — xuất trực tiếp từ cùng dữ liệu trong HTML.')
out.append('')
out.append(f'**Tổng quan:** {len(nodes)} kỹ năng · {len(lanes)} nhánh · 8 tier · '
           f'{sum(1 for n in nodes if n.get("cap"))} node capstone ★')
out.append('')

# ---- mermaid ----
out.append('## Sơ đồ Mermaid (render trên GitHub)')
out.append('')
out.append('```mermaid')
out.append('graph TD')
for l in lanes:
    out.append(f'  subgraph L{l["id"]}["{l["ico"]} {l["name"]}"]')
    out.append('    direction TB')
    for n in sorted([x for x in nodes if x['lane'] == l['id']], key=lambda x: (x['t'], x['id'])):
        nm = mid(n['nm']) + (' ★' if n.get('cap') else '')
        out.append(f'    {n["id"]}["{nm}<br/><small>T{n["t"]} · {LV(n["t"])}</small>"]')
    out.append('  end')
out.append('')
for n in nodes:
    for r in n.get('req', []):
        out.append(f'  {r} --> {n["id"]}')
out.append('```')
out.append('')
out.append('> Ghi chú: mỗi subgraph là một nhánh, ô liệt kê theo tier; mũi tên `A --> B` = học B cần biết A trước. '
           'Mermaid tự xếp layout nên **hình khác HTML** (HTML là lưới lane × tier) — hãy so **nhóm nhánh + quan hệ mũi tên**, không so vị trí ô.')
out.append('')

# ---- per-lane tables ----
out.append('## Chi tiết từng nhánh')
for l in lanes:
    ln = sorted([n for n in nodes if n['lane'] == l['id']], key=lambda x: (x['t'], x['id']))
    out.append('')
    out.append(f'### {l["ico"]} {l["name"]} ({len(ln)} kỹ năng)')
    out.append('')
    out.append('| Tier | Cấp | Kỹ năng | Thuật ngữ EN | Yêu cầu trước | Khóa học | Docs mirror |')
    out.append('|---|---|---|---|---|---|---|')
    for n in ln:
        req = '—' if not n.get('req') else ', '.join(f'`{by_id[r]["nm"]}`' for r in n['req'])
        nm = ('★ ' if n.get('cap') else '') + n['nm']
        docs = '<br/>'.join(f'[{x}](unreal-engine-5.8-docs/site/{x}/)' for x in n['refs'].get('docs', []))
        out.append(f'| T{n["t"]} | {LV(n["t"])} | **{nm}** | {n["en"]} | {req} | '
                   f'[Ch.{n["refs"]["ch"]}](khoa-hoc-unreal-engine.html#ch{n["refs"]["ch"]}) | {docs} |')

# ---- checklist theo tier ----
out.append('')
out.append('## Checklist tiến độ (theo tier)')
out.append('')
out.append('Tick dần khi học — dùng song song với vòng % trong trang HTML (tiến độ HTML lưu riêng ở localStorage).')
out.append('')
for t in sorted({n['t'] for n in nodes}):
    out.append(f'**Tier {t} — {LV(t)}**')
    out.append('')
    for l in lanes:
        for n in sorted([x for x in nodes if x['lane'] == l['id'] and x['t'] == t], key=lambda x: x['id']):
            out.append(f'- [ ] {l["ico"]} {n["nm"]} — {n["en"]}' + (' ★ CAPSTONE' if n.get('cap') else ''))
    out.append('')

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('wrote', os.path.abspath(OUT), len('\n'.join(out)) // 1024, 'KB')
