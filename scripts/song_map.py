#!/usr/bin/env python3
"""シナリオを考えるための「曲の地図」を出す。小節ごとの時刻、盛り上がり（音量・高音域）、キメの候補、決めた区間を1行ずつ並べる。

区間（Aメロ・サビなど）の境目は、高音域の量が段で変わる小節と、find_hits.py の change（曲調の切り替わり）が重なるところが候補。
強く圧縮された曲は音量（rms）がほぼ平らなので、盛り上がりは高音域（high）で見る。最後は必ず人の耳で確かめる。
使い方: song_map.py [--beats data/beats.json] [--hits data/hits.json] [--out work/song_map.md]
"""
import argparse, json
from pathlib import Path


def bar(v, width=20):
    n = int(round(v * width))
    return "█" * n + "·" * (width - n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beats", default="data/beats.json")
    ap.add_argument("--hits", default="data/hits.json")
    ap.add_argument("--out", default="work/song_map.md")
    args = ap.parse_args()
    info = json.loads(Path(args.beats).read_text())
    hits = json.loads(Path(args.hits).read_text())["hits"] if Path(args.hits).exists() else []
    by_bar = {}
    for h in hits:
        by_bar.setdefault(h["bar"], []).append(f"{h['kind']}{'' if h['beat'] == 1 else '@' + str(h['beat'])}")
    sec_at = {s["start_bar"]: s["name"] for s in info.get("sections", [])}
    lines = [f"# 曲の地図 — {info['source']}", "",
             f"テンポ {info['tempo_bpm']} BPM、1小節 {info['bar_period']:.3f}秒（{info['bar_period'] * info['fps']:.1f}フレーム）、"
             f"最初の拍 {info['first_beat']}秒、音が切れる {info['music_end']}秒（小節{info['last_bar']}の終わり）、{info['loudness_lufs']} LUFS", "",
             "| 小節 | 時刻 | 区間 | 高音域 | 音量 | キメの候補 |", "|---:|---:|---|---|---|---|"]
    prev = None
    for n in sorted(int(k) for k in info["bars"]):
        if n > info["last_bar"] + 1:
            break
        t = info["bars"][str(n)]["t"]
        e = info.get("bar_energy", {}).get(str(n), {"rms": 0, "high": 0})
        step = ""
        if prev is not None and abs(e["high"] - prev) >= 0.15:
            step = " ▲" if e["high"] > prev else " ▼"
        prev = e["high"]
        lines.append(f"| {n} | {int(t // 60)}:{t % 60:04.1f} | {sec_at.get(n, '')} | `{bar(e['high'])}`{step} | `{bar(e['rms'], 10)}` | "
                     f"{' '.join(by_bar.get(n, []))} |")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:4]))
    print(f"-> {args.out}（{len(lines) - 6} 小節）")


if __name__ == "__main__":
    main()
