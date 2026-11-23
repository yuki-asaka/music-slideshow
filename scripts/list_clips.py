#!/usr/bin/env python3
"""動画素材の解像度・フレームレート・向き・長さを data/clips.csv に一覧にする。

show.json の photos.source_root の下を探す。photos.exclude_videos に書いたファイル名（既存の編集版など）は除く。
編集済みのスライドショー（文字の焼き込み・写真の連続）は素材にならないので、一覧を見て人が除く。
使い方: list_clips.py [--show data/show.json]
"""
import argparse, csv, json, subprocess
from pathlib import Path


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
                         capture_output=True, text=True, check=True).stdout
    info = json.loads(out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    num, den = map(int, v.get("avg_frame_rate", "0/1").split("/"))
    fps = num / den if den else 0
    rot = 0
    for sd in v.get("side_data_list", []):
        rot = int(sd.get("rotation", rot))
    rot = int(v.get("tags", {}).get("rotate", rot))
    w, h = v["width"], v["height"]
    if abs(rot) in (90, 270):
        w, h = h, w
    has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    return dict(width=w, height=h, fps=round(fps, 3), rotation=rot,
                orientation="portrait" if h > w else "landscape",
                duration=round(float(info["format"]["duration"]), 2), audio=has_audio)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", default="data/show.json")
    args = ap.parse_args()
    cfg = json.loads(Path(args.show).read_text())["photos"]
    root = Path(cfg["source_root"]).expanduser()
    exclude = set(cfg.get("exclude_videos", []))
    rows = []
    for p in sorted(root.rglob("*")):
        if p.suffix.lower() in (".mp4", ".mov", ".m4v") and p.name not in exclude:
            r = probe(p)
            r["src"] = str(p)
            r["folder"] = p.parent.name
            r["slow_ok"] = r["fps"] >= 59  # スピードランプは 60fps 以上の素材だけ
            rows.append(r)
    fields = ["folder", "src", "width", "height", "fps", "rotation", "orientation", "duration", "audio", "slow_ok"]
    Path("data").mkdir(exist_ok=True)
    with open("data/clips.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows({k: r[k] for k in fields} for r in rows)
    print(f"{len(rows)} clips -> data/clips.csv")


if __name__ == "__main__":
    main()
