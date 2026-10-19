# Unreal Study — bộ tài liệu học Unreal Engine 5.8

Đã tách khỏi repo `mega_study_html` để giữ repo chính nhẹ. Site tĩnh, chạy được
trên **GitHub Pages** lẫn offline bằng server local.

## Chạy trên GitHub Pages

Repo này publish trực tiếp từ nhánh `main` (thư mục gốc):

1. Push repo lên GitHub.
2. Vào **Settings → Pages → Source: Deploy from a branch**, chọn branch `main`, thư mục `/ (root)`.
3. Truy cập `https://<user>.github.io/unreal-study/`.

Nội dung publish: `index.html` (trang chủ), khóa học, skill tree và 63 ảnh minh họa
(~33 MB) — tổng dung lượng nhỏ, đăng trong giây lát.

> ⚠️ **Docs mirror (~1,1 GB) không publish lên GitHub Pages** — Pages giới hạn cứng
> site tối đa 1 GB. Trên web, các link tới trang docs được JS tự động chuyển sang
> site chính thức [dev.epicgames.com](https://dev.epicgames.com/documentation/en-us/unreal-engine)
> (kèm `404.html` bắt link trực tiếp). Muốn dùng mirror offline, xem mục bên dưới.

## Chạy offline (có đầy đủ docs mirror)

```bash
cd D:\CODE\unreal-study
python serve.py            # mặc định 8766
```

| Nội dung | URL |
|---|---|
| 🏠 Trang chủ | http://127.0.0.1:8766/ |
| 🎓 Khóa học 24 chương (Starter → Advanced) | http://127.0.0.1:8766/khoa-hoc-unreal-engine.html |
| 🌳 Skill tree RPG (38 node, lưu tiến độ localStorage) | http://127.0.0.1:8766/unreal-skill-tree.html |
| 📚 Bản đối chiếu MD (Mermaid + bảng + checklist) | `unreal-skill-tree.md` |
| 📖 Docs mirror 3.644 trang | http://127.0.0.1:8766/unreal-engine-5.8-docs/site/ |

> Đừng dùng `python -m http.server` trực tiếp — trên Windows nó trả MIME sai cho
> `.woff2` làm font icon của docs mirror không load (serve.py đã xử lý).

Ở local, link docs trong khóa học/skill tree trỏ vào mirror; trên github.io cùng
link đó tự chuyển sang dev.epicgames.com (nhờ script chèn cuối 2 file HTML).

## Cấu trúc

```
├─ index.html                    # trang chủ (GitHub Pages root)
├─ khoa-hoc-unreal-engine.html   # khóa học tiếng Việt, 24 chương + quiz + flashcards
├─ unreal-skill-tree.html        # sơ đồ kỹ năng RPG: 7 nhánh × 8 tier, unlock theo tiền đề
├─ unreal-skill-tree.md          # bản MD để kiểm tra/enum; regen bằng scripts/export_skilltree_md.py
├─ images/                       # 63 ảnh minh họa của khóa học (lấy từ docs Epic)
├─ 404.html                      # bắt link docs mirror → chuyển sang dev.epicgames.com
├─ .nojekyll                     # tắt Jekyll của GitHub Pages
├─ serve.py                      # server local cho full mirror
└─ unreal-engine-5.8-docs/       # KHÔNG commit (xem .gitignore)
   ├─ site/                      # mirror 3.644 trang HTML + 12.077 ảnh (~1,1 GB)
   ├─ _raw/                      # JSON gốc đã crawl (65 MB)
   └─ scripts/                   # crawler, generator, pipeline; README chi tiết bên trong
```

`.gitignore` loại `site/` và `_raw/` khỏi git — nếu clone máy khác mà cần mirror,
chạy lại crawler trong `unreal-engine-5.8-docs/scripts/` (hướng dẫn trong README của scripts).

## Ghi chú kỹ thuật

- Ảnh của khóa học tham chiếu qua `images/` (tương đối) nên chạy được ở cả hai môi trường.
- Generator `scripts/build_course.py` dùng path `images/` mới trong `course_images.json`
  / `course_figures_used.json` — regenerate sẽ ra đúng path.
- `unreal-skill-tree.md` regen: `python unreal-engine-5.8-docs/scripts/export_skilltree_md.py`.
