#!/usr/bin/env python3
"""変換済みの JPG（work/photos）で、EXIF の向き（Orientation）が 1 以外のものを画素ごと回転させ、向きの情報を 1 にする。

sips の変換では HEIC の回転が画素に反映されず、EXIF の向きだけが残ることがある。
読み込むアプリによって向きが変わらないよう、ここでそろえる。修正したファイルを data/orientation_fixed.txt に書く。
使い方: fix_orientation.py [work/photos]
"""
import sys
from pathlib import Path

from PIL import Image, ImageOps


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "work/photos")
    fixed = []
    for p in sorted(root.rglob("*.jpg")):
        im = Image.open(p)
        o = im.getexif().get(274, 1)
        if o == 1:
            continue
        exif = im.getexif()
        im = ImageOps.exif_transpose(im)
        exif[274] = 1
        im.save(p, quality=92, exif=exif.tobytes())
        fixed.append(f"{p}\t{o}")
    Path("data/orientation_fixed.txt").write_text("\n".join(fixed) + "\n")
    print(f"fixed {len(fixed)}")


if __name__ == "__main__":
    main()
