#!/usr/bin/env python3
"""写真（HEIC/JPG）を JPG・長辺3840px に変換して work/photos/<行事の key>/ に置く。元の写真は変更しない（macOS の sips を使う）。

行事の対応は show.json の photos.events（folder = 元のフォルダ名、key = 番号_英字名）。key の頭2文字が写真 ID の頭になる（08-171）。
同じ名前の HEIC と JPG が衝突しないよう、元の拡張子を名前に残す（IMG_3488_heic.jpg）。変換済みのファイルは飛ばす。
使い方: convert_photos.py [--show data/show.json] [--jobs 8]
出力: work/photos/、data/photos.csv（event,src,dst）、work/convert_failed.txt
"""
import argparse, csv, json, subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

EXTS = {".jpg", ".jpeg", ".heic"}


def convert(job):
    src, dst = job
    if dst.exists() and dst.stat().st_size > 0:
        return None
    r = subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "92", "-Z", "3840", str(src), "--out", str(dst)],
                       capture_output=True)
    return None if r.returncode == 0 else str(src)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", default="data/show.json")
    ap.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args()
    cfg = json.loads(Path(args.show).read_text())["photos"]
    root = Path(cfg["source_root"]).expanduser()
    dst_root = Path("work/photos")
    rows, jobs = [], []
    for ev in cfg["events"]:
        src_dir = root / ev["folder"]
        if not src_dir.is_dir():
            print(f"見つからない: {src_dir}")
            continue
        (dst_root / ev["key"]).mkdir(parents=True, exist_ok=True)
        for src in sorted(p for p in src_dir.iterdir() if p.is_file() and p.suffix.lower() in EXTS):
            dst = dst_root / ev["key"] / f"{src.stem}_{src.suffix.lower()[1:]}.jpg"
            rows.append({"event": ev["key"], "src": str(src), "dst": str(dst)})
            jobs.append((src, dst))
    with ThreadPoolExecutor(args.jobs) as ex:
        failed = [f for f in ex.map(convert, jobs) if f]
    Path("data").mkdir(exist_ok=True)
    with open("data/photos.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["event", "src", "dst"])
        w.writeheader()
        w.writerows(rows)
    Path("work/convert_failed.txt").write_text("\n".join(failed) + ("\n" if failed else ""))
    print(f"元の写真: {len(rows)}  失敗: {len(failed)}")
    for ev in cfg["events"]:
        print(f"  {ev['key']}: {sum(r['event'] == ev['key'] for r in rows)}")


if __name__ == "__main__":
    main()
