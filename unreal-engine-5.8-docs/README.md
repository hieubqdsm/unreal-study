# Unreal Engine 5.8 Documentation — Local Mirror

Bản mirror đầy đủ tài liệu **Unreal Engine 5.8** từ
[dev.epicgames.com](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-5-8-documentation)
chạy hoàn toàn offline: **3.644 trang**, **12.077 ảnh (nén WebP)**, CSS + font gốc của site.
Tổng dung lượng ~**1,1 GB**.

## Chạy local

```bash
cd game-dev/unreal-engine-5.8-docs
python serve.py          # mặc định cổng 8765
# mở http://127.0.0.1:8765/
```

Hoặc cổng khác: `python serve.py 9000`.

> Đừng dùng `python -m http.server` trực tiếp — trên Windows nó trả MIME sai cho
> `.woff2` khiến font icon không load (đó là lý do có `serve.py` riêng).

## Có gì

- `site/` — site tĩnh: mỗi trang một thư mục `<slug>/index.html`, trang chủ là
  `index.html` (mirror trang landing *Unreal Engine 5.8 Documentation*).
  - `assets/` — CSS gốc của Epic (`styles.css`), fonts (Inter, Roboto, Recursive
    Mono, EDS Icons, Material Symbols), JS tương tác tự viết (sidebar, filter,
  search, tabs, slider so sánh, slider chuỗi, copy code).
  - `images/` — toàn bộ ảnh (WebP nén: PNG → WebP q85 max 1600px; GIF động →
    WebP động max 960px; giữ nguyên bản gốc khi nén ra lớn hơn).
  - `assets/toc.html` — cây mục lục 3.644 mục dùng chung cho mọi trang (JS
    inject + tự đánh dấu trang hiện tại và mở chuỗi mục cha), giúp mỗi trang
    HTML chỉ còn ~18 KB thay vì nhúng nguyên cây.
  - `search-index.json` — chỉ mục tìm kiếm phía client.
- `_raw/` — dữ liệu gốc đã crawl: `toc.json` (cây mục lục) + `<slug>.json`
  (nội dung từng trang từ API `document.json` của Epic).
- `scripts/` — tooling:
  - `crawl_docs.py` / `crawl_gentle.py` — crawler (nhanh / nhẹ nhàng chống
    Cloudflare 429).
  - `collect_images.py`, `download_images.py`, `finalize.py` — thu thập và tải
    ảnh (CloudFront lane + resize-API lane), pipeline hoàn tất.
  - `generate_site.py` — dựng site tĩnh từ `_raw/` (renderer đầy đủ các loại
    block: markdown, callout, bảng, tabs OS, comparison/sequence slider,
    code snippet, video, attachment, document list…).
  - `convert_images.py` — nén ảnh sang WebP sau khi tải.
  - `check_links.py` — kiểm tra link chết + ảnh thiếu.
- `serve.py` — HTTP server có MIME đúng.

## Cách hoạt động / tái tạo

Site gốc là SPA (Angular) nên không mirror kiểu wget được. Pipeline:

1. `table_of_content.json` → cây 3.644 trang (phiên bản mặc định = 5.8).
2. Mỗi trang gọi `community/api/documentation/document.json?path=...` → JSON
   có cấu trúc block.
3. Generator dựng HTML tĩnh tái dùng CSS gốc + mô phỏng đúng DOM/class của từng
   loại block (so khớp với DOM thật đã chụp từ trang live).
4. Ảnh lấy bản gốc từ `d1iv7db44yhgxn.cloudfront.net/documentation/images/<uuid>/<file>`
   (ưu tiên), phần còn lại qua resize API của Epic.

Lưu ý Cloudflare: đừng crawl quá ~2 req/s — sẽ bị chặn IP khoảng 20 phút (429).

## Giới hạn đã biết

- Video (Kaltura) là iframe nhúng từ Epic — cần internet khi xem.
- Attachment (file zip mẫu) link thẳng tới CloudFront của Epic (không tải về).
- Python/Blueprint/C++ API Reference là ứng dụng riêng của Epic — các trang này
  chỉ là trang giới thiệu link ra ngoài.
- Thanh header trên cùng là bản đơn giản hóa (header thật của Epic là web
  component của unrealengine.com, phụ thuộc CDN riêng); mọi thứ khác (sidebar
  mục lục, nội dung, kiểu dáng) giữ đúng bản gốc.
