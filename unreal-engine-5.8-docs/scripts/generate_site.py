#!/usr/bin/env python3
"""Generate static local site from _raw/*.json (UE 5.8 docs mirror)."""
import html as html_mod
import json
import os
import re
import shutil
import sys
from urllib.parse import urlparse, parse_qs, unquote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "_raw")
SITE = os.path.join(ROOT, "site")

# ---------------------------------------------------------------- load data
with open(os.path.join(RAW, "toc.json"), encoding="utf-8") as f:
    TOC = json.load(f)

# slug -> info (title, parents list of entries, children)
PAGES = {}          # slug -> {title, parent_slugs:[...], entry}
ORDER = []          # depth-first slug order


def build_pages():
    def walk(entries, parents):
        for e in entries:
            slug = e["slug"]
            PAGES[slug] = {"title": e["title"], "parents": parents,
                           "children": e.get("sub_entries") or []}
            ORDER.append(slug)
            walk(e.get("sub_entries") or [], parents + [e])
    walk(TOC["entries"], [])


build_pages()

# uuid -> local image filename
IMGMAP = {}
imgdir = os.path.join(SITE, "images")
if os.path.isdir(imgdir):
    for f in os.listdir(imgdir):
        IMGMAP[f[:36]] = f

DOCS = {}  # slug -> doc json


def load_docs():
    for slug in ORDER:
        p = os.path.join(RAW, slug + ".json")
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    DOCS[slug] = json.load(f)
            except Exception:
                pass


load_docs()

# ---------------------------------------------------------------- helpers
UA_DEV = "https://dev.epicgames.com"


def img_local(uuid):
    fn = IMGMAP.get(uuid)
    if fn:
        return "../images/" + fn
    return None


def img_src(uuid, params="resizing_type=fit"):
    """Local path if downloaded, otherwise the online resize API url."""
    if not uuid:
        return None
    loc = img_local(uuid)
    if loc:
        return loc
    return f"{UA_DEV}/community/api/documentation/image/{uuid}?{params}"


def rewrite_html(s):
    """Rewrite links + image urls inside a content html fragment."""
    if not s:
        return s

    def img_repl(m):
        uuid = m.group(1)
        loc = img_local(uuid)
        return loc if loc else m.group(0)

    # images: full api urls with params
    s = re.sub(
        r"https://dev\.epicgames\.com/community/api/documentation/image/([a-f0-9-]{36})(\?[^\"'\s)]*)?",
        img_repl, s)
    # links
    def link_repl(m):
        url = m.group(1)
        if url.startswith("/documentation/unreal-engine/"):
            url = UA_DEV + url
        if url.startswith(UA_DEV + "/documentation/unreal-engine/"):
            rest = url[len(UA_DEV + "/documentation/unreal-engine/"):]
            rest = rest.split("?")[0].split("#")
            slug = rest[0].strip("/")
            anchor = rest[1] if len(rest) > 1 else ""
            if slug in PAGES:
                return ("../" + slug + "/" + ("#" + anchor if anchor else ""))
        return m.group(0)
    s = re.sub(r'href="([^"]+)"', lambda m: 'href="' + link_repl(m) + '"', s)
    # protocol-relative or root-relative already handled above
    return s


def esc(s):
    return html_mod.escape(s or "", quote=True)


def slugify_header(text, anchor):
    if anchor and anchor.get("name"):
        return anchor["name"]
    t = re.sub(r"<[^>]+>", "", text or "").strip().lower()
    t = re.sub(r"[^a-z0-9\s-]", "", t)
    t = re.sub(r"[\s-]+", "", t)
    return t


def inline_html(content):
    """Paragraph/header content is already HTML-escaped text with inline tags."""
    return content or ""


# ---------------------------------------------------------------- blocks
def render_blocks(blocks, depth=0) -> str:
    out = []
    for b in blocks or []:
        if not isinstance(b, dict):
            continue
        if (b.get("settings") or {}).get("is_hidden"):
            continue
        t = b.get("type")
        r = BLOCK_RENDERERS.get(t)
        if r:
            out.append(r(b))
        else:
            out.append(f"<!-- unknown block type: {esc(t)} -->")
    return "\n".join(out)


def r_paragraph(b):
    return f"<p>{inline_html(b.get('content'))}</p>"


def r_header(b):
    lvl = b.get("level") or 2
    lvl = min(max(int(lvl), 1), 6)
    hid = slugify_header(b.get("content", ""), (b.get("settings") or {}).get("anchor"))
    return f"<h{lvl} id=\"{esc(hid)}\"> {inline_html(b.get('content'))} </h{lvl}>"


def r_markdown(b):
    return rewrite_html(b.get("content_html") or "")


def r_enhanced_list(b):
    style = b.get("style") or "unordered"
    tag = "ul"
    inner = []
    for i, cell in enumerate(b.get("items") or []):
        inner.append("<li>" + render_blocks(cell) + "</li>")
    if style == "ordered":
        tag = "ol"
        return f"<ol>{''.join(inner)}</ol>"
    return f"<ul>{''.join(inner)}</ul>"


def img_tag_for(im, extra_cls="", alt=None):
    uuid = (im or {}).get("storage_key")
    loc = img_local(uuid) if uuid else None
    if not loc:
        return ""
    w = im.get("width") or ""
    h = im.get("height") or ""
    a = esc(alt if alt is not None else (im.get("file_name") or ""))
    return (f'<img class="figure-img img-fluid {extra_cls}" src="{loc}" '
            f'alt="{a}" width="{w}" height="{h}" loading="lazy">')


def r_image(b):
    im = b.get("image") or {}
    uuid = im.get("storage_key")
    loc = img_src(uuid) if uuid else None
    if not loc:
        return ""
    w = b.get("width") or im.get("width") or ""
    h = im.get("height") or ""
    cap = (b.get("caption") or "").strip()
    alt = esc(b.get("alt_text") or cap or (im.get("file_name") or ""))
    img = (f'<img class="figure-img img-fluid" src="{loc}" alt="{alt}" '
           f'width="{w}" height="{h}" loading="lazy">')
    fig = f'<a href="{loc}" target="_blank">{img}</a>'
    if cap:
        fig += f'<figcaption class="figure-caption">{inline_html(cap)}</figcaption>'
    return (f'<block-image class="block-image"><div class="block-image">'
            f'<figure class="figure">{fig}</figure></div></block-image>')


CALLOUT_ICON = {
    "info": "icon-info-circle-filled",
    "note": "icon-info-circle-filled",
    "warning": "icon-exclamation-triangle-filled",
    "alert": "icon-exclamation-triangle-filled",
    "tip": "icon-lightbulb-on-filled",
}


def r_callout(b):
    ct = b.get("callout_type") or "info"
    cls = {"note": "is-info", "info": "is-info", "warning": "is-warning",
           "alert": "is-alert", "tip": "is-tip"}.get(ct, "is-info")
    icon = CALLOUT_ICON.get(ct, CALLOUT_ICON["info"])
    body = render_blocks(b.get("blocks"))
    return (f'<block-callout class="block-callout {cls}">'
            f'<div class="block-callout-inner">'
            f'<span class="eds-icon block-callout-icon {icon} text-body-secondary"></span>'
            f'<span class="block-callout-content">{body}</span></div></block-callout>')


def r_video(b):
    vid = b.get("video_id")
    if not vid:
        return ""
    return (f'<block-video class="block-video">'
            f'<electra-player class="d-block ratio ratio-16x9">'
            f'<iframe src="{UA_DEV}/community/api/cms/videos/{esc(vid)}/embed.html" '
            f'allow="autoplay; fullscreen; encrypted-media" allowfullscreen '
            f'title="Epic video player"></iframe></electra-player></block-video>')


def r_code_snippet(b):
    st = (b.get("snippet_type") or "text").lower()
    label = {"blueprint": "Blueprint", "cpp": "C++", "c++": "C++",
             "python": "Python", "text": "Text", "ini": "INI",
             "cpp_header": "C++ Header", "cpp_source": "C++ Source"}.get(st, st.title())
    code = b.get("code_preview") or b.get("code") or ""
    title = (b.get("title") or "").strip()
    title_html = f'<div class="block-code-snippet-header-title">{esc(title)}</div>' if title else ""
    code_html = esc(html_mod.unescape(code))
    lang = {"cpp": "cpp", "c++": "cpp", "python": "python"}.get(st, "text")
    return (f'<block-code-snippet class="block-code-snippet">'
            f'<header class="block-code-snippet-header">'
            f'<div class="block-code-snippet-header-type"> {esc(label)} </div>{title_html}'
            f'<button type="button" class="btn btn-sm ue-copy-btn" data-copy>Copy</button></header>'
            f'<div class="code"><pre class="pre-block"><code class="language-{lang} hljs">{code_html}</code></pre></div>'
            f'</block-code-snippet>')


def _table_cell_html(cell_blocks):
    if not cell_blocks:
        return ""
    return render_blocks(cell_blocks)


def r_enhanced_table(b):
    rows = b.get("rows") or []
    widths = b.get("widths")
    ncols = max((len(r) for r in rows), default=0)
    colgroup = ""
    if widths:
        cols = "".join(f'<col style="width:{esc(w)}">' for w in widths)
        colgroup = f"<colgroup>{cols}</colgroup>"
    thead_rows = []
    body_rows = list(rows)
    if rows and any(c and c[0].get("type") == "enhanced_table_header" for c in rows[0] if c):
        head = body_rows.pop(0)
        ths = "".join(
            "<th> " + (c[0].get("content") or "") + " </th>" if c and c[0].get("type") == "enhanced_table_header"
            else "<th></th>"
            for c in head)
        thead_rows.append(f"<tr>{ths}</tr>")
    else:
        thead_rows.append("<tr>" + "<th></th>" * ncols + "</tr>")
    trs = []
    for r in body_rows:
        tds = "".join(f"<td>{_table_cell_html(c)}</td>" for c in r)
        trs.append(f"<tr>{tds}</tr>")
    return (f'<div class="table-responsive"><table class="table" style="--columns-count: {ncols};">'
            f"{colgroup}<thead>{''.join(thead_rows)}</thead><tbody>{''.join(trs)}</tbody></table></div>")


SWITCH_LABELS = {"windows": "Windows", "linux": "Linux", "macos": "macOS",
                 "mac": "macOS", "operating_system": "Operating System"}
SWITCH_ICONS = {"windows": "icon-windows", "linux": "icon-linux-tux",
                "macos": "icon-apple", "mac": "icon-apple"}


def r_switch(b):
    sb = b.get("switchable_blocks") or {}
    stype = (b.get("switch_type") or "").lower()
    panes = []
    tabs = []
    keys = list(sb.keys())
    for i, k in enumerate(keys):
        label = SWITCH_LABELS.get(k, k.replace("_", " ").title())
        icon = SWITCH_ICONS.get(k, "")
        active = " is-active" if i == 0 else ""
        hidden = "" if i == 0 else " visually-hidden"
        icon_html = f'<i class="block-switch-option-icon eds-icon {icon}"></i>' if icon else ""
        tabs.append(f'<button type="button" class="btn btn-sm ue-switch-tab{active}" '
                    f'data-switch-key="{esc(k)}">{esc(label)}</button>')
        panes.append(f'<block-switch-view class="block-switch-view ue-switch-pane{active}" '
                     f'data-switch-key="{esc(k)}">{icon_html}{render_blocks(sb[k])}</block-switch-view>')
    label = SWITCH_LABELS.get(stype, "Options")
    return (f'<div class="ue-switch"><div class="ue-switch-bar">'
            f'<span class="form-label mb-0 fs-sm">{esc(label)}</span>'
            f'<div class="ue-switch-tabs">{"".join(tabs)}</div></div>'
            f'{"".join(panes)}</div>')


def r_comparison_slider(b):
    l, rft = b.get("image_left") or {}, b.get("image_right") or {}
    ll = img_src(l.get("storage_key"), "resizing_type=fit&width=1920&height=1080")
    rl = img_src(rft.get("storage_key"), "resizing_type=fit&width=1920&height=1080")
    if not ll or not rl:
        return ""
    capl, capr = esc(b.get("caption_left") or ""), esc(b.get("caption_right") or "")
    return (f'<div class="block-comparison-slider ue-comparison">'
            f'<div class="img-before"><img src="{ll}" alt="{capl}"></div>'
            f'<div class="img-after" style="clip-path: inset(0 0 0 50%);"><img src="{rl}" alt="{capr}"></div>'
            f'<input type="range" min="0" max="100" value="50" class="slider" aria-label="Comparison slider">'
            f'<span class="ue-comp-label ue-comp-label-l">{capl}</span>'
            f'<span class="ue-comp-label ue-comp-label-r">{capr}</span>'
            f'</div>')


def r_sequence_slider(b):
    ims = b.get("images") or []
    imgs = []
    for i, im in enumerate(ims):
        meta = im.get("image") or im
        loc = img_src(meta.get("storage_key") or im.get("storage_key"), "resizing_type=fit&width=1920&height=1080")
        if not loc:
            continue
        hidden = "" if i == 0 else " visually-hidden"
        imgs.append(f'<img loading="lazy" class="img img-fluid item-{i+1}{hidden}" src="{loc}" '
                    f'alt="{esc(b.get("caption") or "")}">')
    if not imgs:
        return ""
    cap = esc(b.get("caption") or "")
    return (f'<block-slider-sequence class="block-slider-sequence ue-sequence">'
            f'<div class="img-list">{"".join(imgs)}</div>'
            f'<input type="range" min="1" max="{len(imgs)}" value="1" class="slider" aria-label="Sequence slider">'
            f'<div class="caption">{cap}</div></block-slider-sequence>')


def r_document_list(b):
    items = b.get("items") or []
    grouped = (b.get("list_type") or "") == "grouped"
    cls = "block-document-list is-grouped" if grouped else "block-document-list"
    lis = []
    for it in items:
        url = it.get("document_url") or ""
        m = re.search(r"/documentation/unreal-engine/([a-z0-9-]+)", url)
        href = f"../{m.group(1)}/" if m and m.group(1) in PAGES else url
        thumb_uuid = it.get("thumbnail_storage_key")
        tloc = img_src(thumb_uuid, "resizing_type=fit&width=640&height=640")
        thumb = (f'<img loading="lazy" width="{"640" if grouped else "120"}" height="{"640" if grouped else "92"}" class="thumbnail" src="{tloc}" alt="{esc(it.get("title"))}">'
                 if tloc else "")
        lis.append(
            f'<li block-dir-item=""><a class="document-list-card" href="{href}">'
            f'<div class="thumbnail-container">{thumb}</div>'
            f'<div class="document-list-card-content"><h3 class="document-list-card-title">'
            f'{esc(it.get("title"))}</h3>'
            f'<p class="document-list-card-description">{esc(it.get("description") or "")}</p>'
            f'</div></a></li>')
    return (f'<ul block-document-list="" class="{cls}">{"".join(lis)}</ul>')


def r_attachment(b):
    a = b.get("attachment") or {}
    url = a.get("original_url") or ""
    cap = b.get("caption") or a.get("file_name") or "Download"
    return (f'<block-attachment><a class="btn btn-secondary text-white mb-3" href="{esc(url)}">'
            f'{esc(cap)}<span class="fs-md"><i class="eds-icon icon-arrow-down-circle-filled icon-pad-left"></i></span>'
            f'</a></block-attachment>')


def r_include(b):
    return render_blocks(b.get("blocks"))


BLOCK_RENDERERS = {
    "paragraph": r_paragraph,
    "header": r_header,
    "markdown": r_markdown,
    "enhanced_list": r_enhanced_list,
    "image": r_image,
    "callout": r_callout,
    "video": r_video,
    "code_snippet": r_code_snippet,
    "enhanced_table": r_enhanced_table,
    "switch": r_switch,
    "comparison_slider": r_comparison_slider,
    "sequence_slider": r_sequence_slider,
    "document_list": r_document_list,
    "attachment": r_attachment,
    "include": r_include,
    "enhanced_table_header": lambda b: inline_html(b.get("content")),
    "divider": lambda b: "<hr>",
    "link_group": lambda b: f'<div class="block-link-group">{render_blocks(b.get("blocks"))}</div>',
}


def r_external_video(b):
    url = b.get("url") or b.get("original_url") or ""
    if not url:
        return ""
    cap = esc(b.get("caption") or "")
    return (f'<block-external-video class="block-external-video">'
            f'<div class="ratio ratio-16x9"><iframe src="{esc(url)}" '
            f'allow="autoplay; fullscreen; encrypted-media" allowfullscreen '
            f'title="{cap}"></iframe></div>'
            + (f'<div class="caption">{cap}</div>' if cap else "")
            + '</block-external-video>')


def r_glossary(b):
    tags = b.get("tags") or []
    return ('<div class="block-glossary-nav">'
            + "".join(f'<span class="label">{esc(t)}</span>' for t in tags)
            + '</div>')


BLOCK_RENDERERS["external_video"] = r_external_video
BLOCK_RENDERERS["glossary"] = r_glossary


# ---------------------------------------------------------------- sidebar
def render_toc_shared():
    """Shared sidebar tree: every entry is a link, every branch collapsed.
    ue-local.js injects this into each page, marks the active entry and
    expands its ancestor chain."""
    def item(e, is_root=False):
        slug = e["slug"]
        children = e.get("sub_entries") or []
        cls = "contents-table-el is-root-entry" if is_root else "contents-table-el"
        if children:
            btn = ('<button type="button" class="btn btn-expander" aria-label="Expand">'
                   '<i class="eds-icon icon-chevron-right icon-expander text-secondary"></i></button>')
            a = f'<a class="contents-table-link is-parent" data-slug="{esc(slug)}" href="../{slug}/">{esc(e["title"])}</a>'
            sub = ('<ul class="contents-table-list">' +
                   "".join(item(c) for c in children) + "</ul>")
            return (f'<li class="contents-table-item ue-collapsed"><div class="{cls}">{btn}{a}</div>{sub}</li>')
        btn = '<button type="button" class="btn btn-expander" aria-hidden="true" tabindex="-1"></button>'
        a = f'<a class="contents-table-link" data-slug="{esc(slug)}" href="../{slug}/">{esc(e["title"])}</a>'
        return f'<li class="contents-table-item"><div class="{cls}">{btn}{a}</div></li>'

    root = TOC["entries"][0]
    return ('<nav><ul class="contents-table">' + item(root, is_root=True) + "</ul></nav>")


# ---------------------------------------------------------------- page
TEMPLATE = """<!DOCTYPE html>
<html lang="en-US">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, minimum-scale=1">
<title>__TITLE__ | Unreal Engine 5.8 Documentation</title>
<link rel="preload" href="../assets/inter-regular.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="../assets/styles.css">
<link rel="stylesheet" href="../assets/fonts.css">
<link rel="stylesheet" href="../assets/ue-local.css">
<script defer src="../assets/ue-local.js"></script>
</head>
<body class="theme-unreal-engine">
<div class="app-root">
<header class="site-header d-print-none ue-top-header">
  <div class="ue-top-header-inner">
    <button type="button" class="btn ue-burger d-lg-none" aria-label="Open table of contents"><i class="eds-icon icon-three-lines-horizontal"></i></button>
    <a class="ue-brand" href="../unreal-engine-5-8-documentation/">
      <span class="ue-brand-badge">UE</span>
      <span class="ue-brand-text">Unreal Engine <b>5.8</b> Documentation</span>
    </a>
    <div class="ue-search-box">
      <i class="eds-icon icon-magnifying-glass"></i>
      <input type="search" id="ue-search-input" class="form-control" placeholder="Search pages…" autocomplete="off">
      <div id="ue-search-results" class="ue-search-results visually-hidden"></div>
    </div>
    <a class="ue-live-link d-none d-sm-inline-flex" href="https://dev.epicgames.com/documentation/en-us/unreal-engine/__SLUG__" target="_blank" rel="noopener">View online<i class="eds-icon icon-arrow-up-right-from-square icon-pad-left"></i></a>
  </div>
</header>
<div class="site-container">
  <site-nav class="site-nav d-print-none">
    <div class="document-table-of-content-block has-background">
      <div class="contents-versions dropdown">
        <button type="button" aria-expanded="false" class="btn btn-outline is-menu-expander w-100 justify-content-between ue-version-btn">
          <span><span>Unreal Engine&nbsp;5.8</span></span><i class="eds-icon icon-chevron-down"></i>
        </button>
      </div>
      <div class="toc-form-block">
        <form novalidate class="search-field" onsubmit="return false">
          <i class="eds-icon icon-three-lines-horizontal-decrease icon-pad-left"></i>
          <input type="search" name="query" class="form-control ue-toc-filter" placeholder="Filter by title" aria-label="Filter by title">
        </form>
      </div>
      <div class="documents-tree" id="ue-documents-tree"></div>
    </div>
  </site-nav>
  <main class="page-content">
    <header class="section-page-header">
      <div class="row d-flex justify-content-between">
        <div class="col col-sm-10">
          <nav><ol class="breadcrumb is-shrinkable">__BREADCRUMB__
          </ol></nav>
        </div>
      </div>
      <h1>__H1__</h1>
      __DESC__
    </header>
    <div class="row">
      <div class="col-lg-9 print-w-100">
        __BANNER__
        <article>
          <div document-content-blocks-renderer="" class="d-block">
            <div id="content-blocks-renderer" class="content-blocks-renderer">
              <blocks-renderer id="blocks-renderer">__CONTENT__
              </blocks-renderer>
            </div>
          </div>
        </article>
        __RELATED__
        <div class="ue-prevnext d-print-none">__PREVNEXT__</div>
      </div>
      <div class="col-lg-3 d-none d-lg-block d-print-none">
        <content-sidebar class="sidebar-sticky has-top-offset">
          <content-nav class="content-nav">
            <header class="content-nav-header"><div class="title">On this page</div></header>
            <ul class="list">__ONTHISPAGE__
            </ul>
          </content-nav>
        </content-sidebar>
      </div>
    </div>
  </main>
</div>
<footer class="ue-footer d-print-none">
  <div class="ue-footer-inner">
    <span>Unreal Engine 5.8 Documentation — local mirror</span>
    <span class="ue-footer-src">Source: <a href="https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-documentation" target="_blank" rel="noopener">dev.epicgames.com</a> · © Epic Games</span>
  </div>
</footer>
</div>
<script>window.UE_PAGE={slug:"__SLUG__"};</script>
</body>
</html>
"""

LANDING_EXTRA_CSS = '<link rel="stylesheet" href="assets/styles.css">'  # unused


def breadcrumb_html(slug):
    info = PAGES.get(slug)
    out = ['<li class="breadcrumb-item is-root"><span class="icon-pad-right">'
           '<img alt="Epic Games" width="20" height="20" class="align-middle" src="../assets/logo-epic.svg"></span>'
           '<a href="../unreal-engine-5-8-documentation/">Developer</a></li>']
    if info:
        chain = info["parents"][1:] if info["parents"] else []
        shown = chain
        if len(chain) > 1:
            shown = chain[-1:]
            out.append('<li class="breadcrumb-item is-expander">'
                       '<button type="button" class="btn btn-breadcrumb ue-crumb-expand" title="Expand breadcrumbs">'
                       '<i class="eds-icon icon-ellipsis-horizontal"></i></button>'
                       f'<span class="visually-hidden ue-crumb-hidden">'
                       + "".join(f'<li class="breadcrumb-item"><a href="../{p["slug"]}/">{esc(p["title"])}</a></li>' for p in chain[:-1])
                       + '</span></li>')
        for p in shown:
            out.append(f'<li class="breadcrumb-item"><a href="../{p["slug"]}/">{esc(p["title"])}</a></li>')
        out.append(f'<li class="breadcrumb-item active" aria-current="page"><span class="text-truncate">{esc(info["title"])}</span></li>')
    return "\n".join(out)


def onthispage_html(content_html):
    out = []
    for m in re.finditer(r'<(h[23]) id="([^"]+)">(.*?)</\1>', content_html):
        lvl = 1 if m.group(1) == "h2" else 2
        text = html_mod.unescape(re.sub(r"<[^>]+>", "", m.group(3))).replace(" ", " ").strip()
        out.append(f'<li class="list-item is-level-{lvl}"><a class="list-link" href="#{m.group(2)}"> {esc(text)} </a></li>')
    return "\n".join(out)


def related_html(doc):
    rd = doc.get("related_documents") or []
    if not rd:
        return ""
    lis = []
    for it in rd[:12]:
        slug = it.get("slug")
        href = f"../{slug}/" if slug in PAGES else "#"
        tmb = (it.get("thumbnail_image") or {}).get("storage_key")
        tloc = img_src(tmb, "resizing_type=fit&width=640&height=640") if tmb else None
        img = f'<img width="80" height="46" loading="lazy" class="img" src="{tloc}" alt="">' if tloc else ""
        lis.append(f'<li><a class="ue-related-link" href="{href}">{img}<span>{esc(it.get("title"))}</span></a></li>')
    return ('<content-nav class="content-nav"><header class="content-nav-header">'
            '<div class="title">Related documents</div></header>'
            f'<ul class="list">{"".join(lis)}</ul></content-nav>')


def prevnext_html(slug):
    i = ORDER.index(slug) if slug in ORDER else -1
    prev = ORDER[i - 1] if i > 0 else None
    nxt = ORDER[i + 1] if 0 <= i < len(ORDER) - 1 else None
    out = []
    if prev:
        out.append(f'<a class="btn btn-outline ue-prevnext-btn" href="../{prev}/">'
                   f'<i class="eds-icon icon-arrow-left icon-pad-right"></i>'
                   f'<span class="text-truncate">{esc(PAGES[prev]["title"])}</span></a>')
    out.append('<span class="flex-fill"></span>')
    if nxt:
        out.append(f'<a class="btn btn-outline ue-prevnext-btn" href="../{nxt}/">'
                   f'<span class="text-truncate">{esc(PAGES[nxt]["title"])}</span>'
                   f'<i class="eds-icon icon-arrow-right icon-pad-left"></i></a>')
    return "".join(out)


def banner_html(doc):
    b = doc.get("banner_image")
    if not b:
        return ""
    loc = img_src(b.get("storage_key"), "resizing_type=fill&width=1920&height=335")
    if not loc:
        return ""
    return (f'<div class="b-img"><img class="img-fluid" alt="{esc(doc.get("title"))}" '
            f'width="{b.get("width") or 1920}" height="{b.get("height") or 335}" '
            f'loading="lazy" src="{loc}"></div>')


def generate_page(slug):
    doc = DOCS.get(slug)
    if doc is None:
        return None
    if "redirect_url" in doc:
        content = ('<block-callout class="block-callout is-info"><div class="block-callout-inner">'
                   '<span class="eds-icon block-callout-icon icon-info-circle-filled text-body-secondary"></span>'
                   '<span class="block-callout-content"><p>This page redirects to '
                   f'<a href="{esc(doc["redirect_url"])}" target="_blank" rel="noopener">{esc(doc["redirect_url"])}</a></p>'
                   '</span></div></block-callout>')
        title = PAGES.get(slug, {}).get("title", slug)
    else:
        content = render_blocks(doc.get("blocks"))
        title = doc.get("title") or PAGES.get(slug, {}).get("title", slug)

    page = TEMPLATE
    desc = (doc.get("description") or "").strip() if isinstance(doc, dict) else ""
    desc_html = f'<p class="text-secondary mb-0">{esc(desc)}</p>' if desc else ""
    page = page.replace("__TITLE__", esc(title))
    page = page.replace("__H1__", esc(title))
    page = page.replace("__DESC__", desc_html)
    page = page.replace("__SLUG__", esc(slug))
    page = page.replace("__BREADCRUMB__", breadcrumb_html(slug))
    page = page.replace("__BANNER__", banner_html(doc) if isinstance(doc, dict) else "")
    page = page.replace("__CONTENT__", content)
    page = page.replace("__ONTHISPAGE__", onthispage_html(content))
    page = page.replace("__RELATED__", related_html(doc) if isinstance(doc, dict) else "")
    page = page.replace("__PREVNEXT__", prevnext_html(slug))
    return page


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    os.makedirs(os.path.join(SITE, "assets"), exist_ok=True)
    with open(os.path.join(SITE, "assets", "toc.html"), "w", encoding="utf-8") as f:
        f.write(render_toc_shared())
    count = 0
    search_index = []
    for slug in ORDER:
        if slug not in DOCS:
            continue
        page = generate_page(slug)
        if page is None:
            continue
        if slug == "unreal-engine-5-8-documentation":
            # site root: all refs are relative to site root -> strip ../
            page = page.replace('="../', '="')
            page = page.replace(
                'window.UE_PAGE={slug:"unreal-engine-5-8-documentation"}',
                'window.UE_PAGE={slug:"unreal-engine-5-8-documentation",root:true}')
            with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as f:
                f.write(page)
            # also keep its own directory so sidebar links work uniformly
            d = os.path.join(SITE, slug)
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
                f.write(page)
            search_index.append({"s": slug, "t": PAGES[slug]["title"], "b": ""})
            count += 1
            continue
        d = os.path.join(SITE, slug)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(page)
        info = PAGES.get(slug) or {}
        bc = " > ".join(esc(p["title"]) for p in info.get("parents", [])[1:])
        search_index.append({"s": slug, "t": info.get("title", slug), "b": bc})
        count += 1
        if limit and count >= limit:
            break
    with open(os.path.join(SITE, "search-index.json"), "w", encoding="utf-8") as f:
        json.dump(search_index, f, ensure_ascii=False)
    print(f"generated {count} pages; search index {len(search_index)}")


if __name__ == "__main__":
    main()
