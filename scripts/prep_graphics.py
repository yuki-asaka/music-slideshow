#!/usr/bin/env python3
"""グラフィックの素材を用意する。selection.csv のグリッドとコラージュの写真を、枠の形に切り抜いた縮小版にする。

グリッド: セル（画面 ÷ cols×rows）の2倍の大きさに、中央を切り抜いて縮小（work/graphics/grid/NN.jpg）。
  原寸の写真を48枚並べると EffectCraft の書き出しが 160秒以上かかるが、縮小版なら数秒で済む
コラージュ: 縦長の枠（632×画面の高さ）に合わせて中央を切り抜く（work/graphics/collage_<区間>/N.jpg）
生成画像: 画面の比率に合わせて切り、画面の大きさにする（assets/generated/G-*.jp*g → work/graphics/bg/G-*.jpg）
使い方: prep_graphics.py [--show data/show.json] [--selection data/selection.csv] [--out work/graphics]
"""
import argparse, csv, json
from pathlib import Path

from PIL import Image, ImageOps


def fit_crop(path, w, h):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    return ImageOps.fit(im, (w, h), Image.LANCZOS, centering=(0.5, 0.45))  # 顔は中央より少し上にあることが多い


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", default="data/show.json")
    ap.add_argument("--selection", default="data/selection.csv")
    ap.add_argument("--out", default="work/graphics")
    args = ap.parse_args()
    show = json.loads(Path(args.show).read_text())
    W, H = show["project"]["width"], show["project"]["height"]
    out = Path(args.out)
    rows = list(csv.DictReader(open(args.selection)))

    grid = [r for r in rows if r["kind"] == "grid"]
    gcfg = show.get("graphics", {}).get("grid")
    if gcfg:
        n = gcfg["cols"] * gcfg["rows"]
        if len(grid) != n:
            print(f"注意: グリッドの写真が {len(grid)} 枚（{gcfg['cols']}×{gcfg['rows']} = {n} 枚が必要）")
        tw, th = W // gcfg["cols"] * 2, H // gcfg["rows"] * 2
        (out / "grid").mkdir(parents=True, exist_ok=True)
        for k, r in enumerate(grid):
            fit_crop(r["file"], tw, th).save(out / "grid" / f"{k + 1:02d}.jpg", quality=90)

    for r in rows:
        if r["kind"] != "collage":
            continue
        d = out / f"collage_{r['section']}"
        d.mkdir(parents=True, exist_ok=True)
        for k, f in enumerate(r["file"].split("|")):
            fit_crop(f, 632, H).save(d / f"{k + 1}.jpg", quality=92)

    (out / "bg").mkdir(parents=True, exist_ok=True)
    gens = sorted(p for p in Path("assets/generated").glob("G-*") if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    for g in gens:
        fit_crop(g, W, H).save(out / "bg" / f"{g.stem}.jpg", quality=95)
    print(f"grid {len(grid)}, collages {sum(r['kind'] == 'collage' for r in rows)}, backgrounds {len(gens)}")


if __name__ == "__main__":
    main()
