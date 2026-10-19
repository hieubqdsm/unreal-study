#!/usr/bin/env python3
"""Convert mirror images to WebP to shrink disk usage.
- PNG (static): resize to max 1600px wide, WebP q85; keep original if not smaller.
- PNG (animated/APNG) & GIF: animated WebP, max 960px wide, q75.
- JPG: left as-is (negligible).
Source file is deleted only after the .webp is written and verified.
"""
import json
import os
import sys
from multiprocessing import Pool

from PIL import Image

IMG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site", "images")
Image.MAX_IMAGE_PIXELS = 300_000_000


def convert(args):
    name, is_anim = args
    src = os.path.join(IMG, name)
    dst = os.path.join(IMG, name[:36] + ".webp")
    try:
        im = Image.open(src)
        if is_anim:
            frames = []
            durations = []
            idx = 0
            try:
                while True:
                    fr = im.convert("RGBA")
                    if fr.width > 960:
                        h = round(fr.height * 960 / fr.width)
                        fr = fr.resize((960, h), Image.LANCZOS)
                    frames.append(fr)
                    durations.append(im.info.get("duration", 80) or 80)
                    idx += 1
                    im.seek(idx)
            except EOFError:
                pass
            if not frames:
                return (name, "no-frames")
            loop = int(im.info.get("loop", 0))
            im.close()
            frames[0].save(dst, "WEBP", save_all=True, append_images=frames[1:],
                           duration=durations, loop=loop,
                           quality=75, method=4)
        else:
            if im.width > 1600:
                h = round(im.height * 1600 / im.width)
                im = im.resize((1600, h), Image.LANCZOS)
            im.save(dst, "WEBP", quality=85, method=4)
            im.close()
        # verify
        if not os.path.exists(dst) or os.path.getsize(dst) < 100:
            return (name, "bad-output")
        if os.path.getsize(dst) < os.path.getsize(src):
            os.remove(src)
            return (name, "ok")
        os.remove(dst)  # webp bigger -> keep original
        return (name, "kept-original")
    except Exception as e:
        for p in (dst,):
            if os.path.exists(p):
                os.remove(p)
        return (name, f"error: {str(e)[:60]}")


def main():
    files = [f for f in os.listdir(IMG) if f.endswith((".png", ".gif"))]
    jobs = []
    for f in files:
        # animated? cheap probe via extension first; APNG check needs open
        if f.endswith(".gif"):
            jobs.append((f, True))
        else:
            jobs.append((f, False))
    # probe APNG quickly in main process
    final_jobs = []
    for f, anim in jobs:
        if f.endswith(".png"):
            try:
                im = Image.open(os.path.join(IMG, f))
                n = getattr(im, "n_frames", 1)
                anim = n > 1
            except Exception:
                pass
        final_jobs.append((f, anim))
    print(f"to convert: {len(final_jobs)} (animated: {sum(1 for _, a in final_jobs if a)})", flush=True)
    stats = {}
    done = 0
    with Pool(processes=10) as pool:
        for name, res in pool.imap_unordered(convert, final_jobs, chunksize=8):
            stats[res.split(":")[0]] = stats.get(res.split(":")[0], 0) + 1
            if res.startswith("error"):
                print(f"  {res} :: {name}", flush=True)
            done += 1
            if done % 500 == 0:
                print(f"  {done}/{len(final_jobs)} {stats}", flush=True)
    print("DONE", stats, flush=True)


if __name__ == "__main__":
    main()
