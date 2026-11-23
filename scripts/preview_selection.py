#!/usr/bin/env python3
"""selection.csv を割り付けの順に並べた一覧画像を作る（区間・小節・ID・Ken Burns 付き）。

本編（写真・動画・コラージュ）は work/review/selection_preview_main_*.jpg、
グリッドの写真は work/review/selection_preview_grid.jpg に出す。動画は source_in の位置のコマを使う。
使い方: preview_selection.py [--selection data/selection.csv] [--out work/review]
"""
import argparse, csv, re, subprocess, tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CW, CH, LABEL_H, COLS = 320, 240, 44, 6
JP_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc"


def thumb(path, size=(CW - 6, CH - 6)):
    im = Image.open(path)
    im.draft("RGB", size)
    im = im.convert("RGB")
    im.thumbnail(size)
    return im


def video_frame(path, t):
    with tempfile.NamedTemporaryFile(suffix=".png") as f:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", path, "-frames:v", "1", "-update", "1", f.name],
                       check=True)
        return thumb(f.name)


def tiles_for(row):
    if row["kind"] == "video":
        t = float(re.search(r"source_in=([\d.]+)", row["note"]).group(1))
        return [video_frame(row["file"], t + 0.9)]
    if row["kind"] == "collage":
        ims = [thumb(p, ((CW - 6) // 3, CH - 6)) for p in row["file"].split("|")]
        canvas = Image.new("RGB", (CW - 6, CH - 6), "black")
        for k, im in enumerate(ims):
            canvas.paste(im, (k * (CW - 6) // 3, (CH - 6 - im.height) // 2))
        return [canvas]
    return [thumb(row["file"])]


def sheet(rows, title, path, font, small):
    n = len(rows)
    nrows = (n + COLS - 1) // COLS
    img = Image.new("RGB", (COLS * CW, 40 + nrows * (CH + LABEL_H)), (20, 20, 20))
    d = ImageDraw.Draw(img)
    d.text((8, 8), title, fill="white", font=font)
    for k, row in enumerate(rows):
        x, y = (k % COLS) * CW, 40 + (k // COLS) * (CH + LABEL_H)
        t = tiles_for(row)[0]
        img.paste(t, (x + (CW - t.width) // 2, y + (CH - t.height) // 2))
        head = f"{row['section']} 小節{row['bar']} ({row['bars']})  {row['kind']}"
        sub = f"{row['id'][:22]}  {row['kb']} {('punch@' + row['punch_in']) if row['punch_in'] else ''} {row['fix']}"
        d.text((x + 4, y + CH + 2), head, fill="yellow", font=small)
        d.text((x + 4, y + CH + 22), sub, fill=(200, 200, 200), font=small)
        if "要確認" in row["note"]:
            d.rectangle([x + 2, y + 2, x + CW - 3, y + CH - 3], outline="red", width=3)
    img.save(path, quality=88)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selection", default="data/selection.csv")
    ap.add_argument("--out", default="work/review")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(args.selection)))
    font = ImageFont.truetype(JP_FONT, 22)
    small = ImageFont.truetype(JP_FONT, 15)
    main_rows = [r for r in rows if r["kind"] != "grid"]
    per = COLS * 6
    for p in range(0, len(main_rows), per):
        part = main_rows[p:p + per]
        sheet(part, f"本編 {p + 1}〜{p + len(part)} / {len(main_rows)}（赤枠 = 要確認）",
              out / f"selection_preview_main_{p // per + 1}.jpg", font, small)
    grid = [r for r in rows if r["kind"] == "grid"]
    if grid:
        sheet(grid, f"グリッド {len(grid)}枚（小節{grid[0]['bar']}〜）", out / "selection_preview_grid.jpg", font, small)


if __name__ == "__main__":
    main()
