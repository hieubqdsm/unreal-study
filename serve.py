#!/usr/bin/env python3
"""Local server cho toàn bộ unreal-study (course + skill tree + docs mirror) với MIME đúng.

Usage:  python serve.py [port]     (mặc định 8766)
"""
import http.server
import os
import socketserver
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
ROOT = os.path.dirname(os.path.abspath(__file__))

EXT = {
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".zip": "application/zip",
}


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kw):
        super().__init__(*args, directory=ROOT, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def guess_type(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in EXT:
            return EXT[ext]
        return super().guess_type(path)


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with Server(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Serving {ROOT}")
        print(f"Course     : http://127.0.0.1:{PORT}/khoa-hoc-unreal-engine.html")
        print(f"Skill tree : http://127.0.0.1:{PORT}/unreal-skill-tree.html")
        print(f"Docs mirror: http://127.0.0.1:{PORT}/unreal-engine-5.8-docs/site/")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
