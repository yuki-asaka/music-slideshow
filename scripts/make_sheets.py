#!/usr/bin/env python3
"""行事ごとのコンタクトシート（1枚48コマ、番号とファイル名付き）と、写真ごとの指標を作る。

指標（data/photo_stats.csv）
  sharp  : ラプラシアンの分散（縮小画像）。小さいほどブレ・ピンぼけの疑い
  bright : 平均の明るさ（0〜255）
  orient : landscape / portrait
  group  : 似た写真のグループ番号（撮影順に隣り合う写真の dHash の差で区切る）
コマの番号（例 04-123）は、シートの読み取りと selection.csv での指示に使う。
使い方: make_sheets.py [--manifest data/photos.csv] [--out work/sheets] [--stats data/photo_stats.csv]
"""
import argparse, csv
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageStat

COLS, ROWS, CW, CH = 8, 6, 240, 180
LABEL_H = 20
DUP_BITS = 10  # dHash（64ビット）の差がこれ以下なら似た写真とみなす


def load_small(path, size=(320, 240)):
    im = Image.open(path)
    im.draft("RGB", size)
    im = im.convert("RGB")
    im.thumbnail(size)
    return im


def dhash(im):
    g = im.convert("L").resize((9, 8), Image.BILINEAR)
    px = g.tobytes()
    bits = 0
    for r in range(8):
        for c in range(8):
            bits = bits << 1 | (px[r * 9 + c] > px[r * 9 + c + 1])
    return bits


def sharpness(im):
    g = im.convert("L").filter(ImageFilter.FIND_EDGES)
    return ImageStat.Stat(g).var[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="data/photos.csv")
    ap.add_argument("--out", default="work/sheets")
    ap.add_argument("--stats", default="data/photo_stats.csv")
    args = ap.parse_args()

    by_event = defaultdict(list)
    with open(args.manifest) as f:
        for row in csv.DictReader(f):
            by_event[row["event"]].append(row["dst"])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 13)

    stats = []
    for event in sorted(by_event):
        files = sorted(by_event[event], key=lambda p: Path(p).name)
        prefix = event[:2]
        prev_hash, group = None, 0
        for n0 in range(0, len(files), COLS * ROWS):
            sheet = Image.new("RGB", (COLS * CW, ROWS * (CH + LABEL_H)), "black")
            d = ImageDraw.Draw(sheet)
            for k, path in enumerate(files[n0:n0 + COLS * ROWS]):
                n = n0 + k + 1
                im = load_small(path)
                h = dhash(im)
                if prev_hash is None or bin(h ^ prev_hash).count("1") > DUP_BITS:
                    group += 1
                prev_hash = h
                stats.append({"id": f"{prefix}-{n:03d}", "event": event, "file": path,
                              "sharp": round(sharpness(im), 1),
                              "bright": round(ImageStat.Stat(im.convert("L")).mean[0], 1),
                              "orient": "portrait" if im.height > im.width else "landscape",
                              "group": f"{prefix}g{group:03d}"})
                t = im.copy()
                t.thumbnail((CW - 4, CH - 4))
                x, y = (k % COLS) * CW, (k // COLS) * (CH + LABEL_H)
                sheet.paste(t, (x + (CW - t.width) // 2, y + (CH - t.height) // 2))
                d.text((x + 3, y + CH + 2), f"{prefix}-{n:03d} {Path(path).stem[:16]}", fill="yellow", font=font)
            sheet.save(out / f"{event}_{n0 // (COLS * ROWS) + 1:02d}.jpg", quality=88)
        print(f"{event}: {len(files)} photos, {group} groups")

    with open(args.stats, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(stats[0]))
        w.writeheader()
        w.writerows(stats)


if __name__ == "__main__":
    main()
