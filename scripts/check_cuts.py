#!/usr/bin/env python3
"""保存したプロジェクト（.fcproj）のカットとトランジションが拍からどれだけずれているかを調べる。

カット（クリップの頭）は、拍の cut_offset フレーム前（既定 -1）にあるべき。
トランジションは中央が拍の上にあるべき（中央揃え。奇数フレームは半フレームの差を許す）。
使い方: check_cuts.py <project.fcproj> [--sequence 名前] [--tracks V1,V2] [--beats data/beats.json]
        [--cut-offset -1] [--tolerance 0]
        check_cuts.py <project.fcproj> --timeline data/timeline.json
          区間シーケンスのクリップを、timeline.json の原点でマスターの時刻に直して調べる。
          切り替えが拍から ±2 フレーム以内か（受け入れ基準2）を見る。シェイクは拍ちょうど、カットは cut_offset
ずれが許容を超えるカットがあれば終了コード 1。
"""
import argparse, json, sys
from pathlib import Path

TICKS = 254016000000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--sequence")
    ap.add_argument("--tracks", default="V1")
    ap.add_argument("--beats", default="data/beats.json")
    ap.add_argument("--cut-offset", type=int, default=-1)
    ap.add_argument("--tolerance", type=int, default=0)
    ap.add_argument("--timeline")
    args = ap.parse_args()
    if args.timeline:
        sys.exit(check_nested(args))

    info = json.loads(Path(args.beats).read_text())
    fps = info["fps"]
    beat_frames = [b["frame"] for b in info["beats"]]
    beat_label = {b["frame"]: f"{b['bar']}.{b['beat']}" for b in info["beats"]}
    tpf = TICKS // fps

    items = json.loads(Path(args.project).read_text())["project"]["items"]
    seqs = [v for v in items.values() if "Sequence" in v["kind"]]
    seq = next((s for s in seqs if s["name"] == args.sequence), None) if args.sequence else seqs[0]
    if seq is None:
        sys.exit(f"シーケンスが見つからない: {args.sequence}")
    tracks = seq["kind"]["Sequence"]["video_tracks"]
    wanted = {f"V{i + 1}" for i in range(len(tracks))} if args.tracks == "all" else set(args.tracks.split(","))

    def nearest(frame):
        return min(beat_frames, key=lambda b: abs(b - frame))

    bad = 0
    for i, tr in enumerate(tracks):
        name = f"V{i + 1}"
        if name not in wanted:
            continue
        for c in sorted(tr["items"], key=lambda c: c["start"]):
            f = c["start"] / tpf
            b = nearest(f + -args.cut_offset)
            diff = f - b
            ok = abs(diff - args.cut_offset) <= args.tolerance
            bad += not ok
            print(f"{name} cut   {c['name'][:28]:28s} frame {f:7.1f}  beat {beat_label[b]:>6s} ({b})  "
                  f"diff {diff:+.1f}  {'OK' if ok else 'NG'}")
        for t in tr.get("transitions", []):
            center = (t["start"] + t["duration"] / 2) / tpf
            b = nearest(center)
            diff = center - b
            ok = abs(diff) <= max(args.tolerance, 0.5) + 1  # カットを -1 に置いた分の差を許す
            bad += not ok
            print(f"{name} trans {t['effect']['effect'][:28]:28s} center {center:6.1f}  beat {beat_label[b]:>6s} ({b})  "
                  f"diff {diff:+.1f}  {t['duration'] / tpf:.0f}f  {'OK' if ok else 'NG'}")
    print(f"NG {bad}")
    sys.exit(1 if bad else 0)


def check_nested(args):
    info = json.loads(Path(args.beats).read_text())
    beat_frames = [b["frame"] for b in info["beats"]]
    tl = json.loads(Path(args.timeline).read_text())
    origin = {s["name"]: s["origin"] for s in tl["sections"]}
    tpf = TICKS // info["fps"]
    items = json.loads(Path(args.project).read_text())["project"]["items"]
    bad = total = 0
    worst = 0
    for v in items.values():
        if "Sequence" not in v["kind"] or v["name"] not in origin:
            continue
        for c in v["kind"]["Sequence"]["video_tracks"][0]["items"]:
            f = c["start"] / tpf + origin[v["name"]]
            if f <= origin[v["name"]] + 0.5:
                continue  # 区間の頭（マスターのつなぎで決まる）
            b = min(beat_frames, key=lambda x: abs(x - f))
            d = f - b
            total += 1
            worst = max(worst, abs(d))
            if abs(d) > 2:
                bad += 1
                print(f"NG {v['name']} {c['name'][:24]} frame {f:.0f} beat {b} diff {d:+.0f}")
    print(f"切り替え {total} か所、拍からの最大のずれ {worst:.0f} フレーム、±2 を超えたもの {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    main()
