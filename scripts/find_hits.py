#!/usr/bin/env python3
"""キメの候補を data/hits.json に出す。依頼者が耳で確かめて status を confirmed / rejected にする。

候補の種類
  accent : 打楽器の立ち上がりが特に強い拍（フィルの頭、強いアタック）
  stop   : 打楽器が急に止まる拍（ブレイク、音が抜ける瞬間）
  change : 曲調が切り替わる小節の頭（区間の境界の候補）
使い方: find_hits.py <楽曲> [--beats data/beats.json] [--out data/hits.json]
"""
import argparse, json
from pathlib import Path

import librosa
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--beats", default="data/beats.json")
    ap.add_argument("--out", default="data/hits.json")
    args = ap.parse_args()

    info = json.loads(Path(args.beats).read_text())
    beats = [b for b in info["beats"] if b["t"] < info["music_end"]]
    y, sr = librosa.load(args.audio, sr=22050, mono=True)
    _, perc = librosa.effects.hpss(y)
    hop = 256
    env = librosa.onset.onset_strength(y=perc, sr=sr, hop_length=hop)
    rms = librosa.feature.rms(y=perc, hop_length=hop)[0]
    t = librosa.frames_to_time(np.arange(len(env)), sr=sr, hop_length=hop)

    def window(arr, a, b):
        m = (t >= a) & (t < b)
        return arr[m] if m.any() else np.array([0.0])

    period = info["beat_period"]
    strength = np.array([window(env, b["t"] - 0.03, b["t"] + 0.05).max() for b in beats])
    energy = np.array([window(rms, b["t"], b["t"] + period).mean() for b in beats])

    hits = []
    accent_th = np.percentile(strength, 97)
    for b, s in zip(beats, strength):
        if s >= accent_th:
            hits.append({**b, "kind": "accent", "score": round(float(s / accent_th), 2)})
    for i in range(4, len(beats)):
        before = energy[i - 4:i].mean()
        if before > 0 and energy[i] < before * 0.45:
            hits.append({**beats[i], "kind": "stop", "score": round(float(1 - energy[i] / before), 2)})

    # 小節ごとの音色の変化（MFCC とクロマ）から、曲調の切り替わりを拾う
    mf = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
    ch = librosa.feature.chroma_cqt(y=y, sr=sr)
    tf = librosa.frames_to_time(np.arange(mf.shape[1]), sr=sr)
    bar_nums = sorted(int(n) for n in info["bars"] if info["bars"][n]["t"] < info["music_end"])
    feats = []
    for n in bar_nums:
        a = info["bars"][str(n)]["t"]
        m = (tf >= a) & (tf < a + info["bar_period"])
        feats.append(np.r_[mf[:, m].mean(1), ch[:, m].mean(1) * 20])
    F = np.array(feats)
    F = (F - F.mean(0)) / (F.std(0) + 1e-9)
    D = np.corrcoef(F)
    k = 4
    nov = np.zeros(len(D))
    for i in range(k, len(D) - k):
        nov[i] = D[i - k:i, i - k:i].mean() + D[i:i + k, i:i + k].mean() - 2 * D[i - k:i, i:i + k].mean()
    th = np.percentile(nov[k:-k], 85)
    for i in range(1, len(nov) - 1):
        if nov[i] >= th and nov[i] >= nov[i - 1] and nov[i] >= nov[i + 1]:
            bar = info["bars"][str(bar_nums[i])]
            hits.append({"t": bar["t"], "frame": bar["frame"], "bar": bar_nums[i], "beat": 1,
                         "kind": "change", "score": round(float(nov[i]), 2)})

    hits.sort(key=lambda h: h["t"])
    for h in hits:
        h["status"] = "candidate"  # 耳で確かめて confirmed / rejected にする
        h["time"] = f"{int(h['t'] // 60)}:{h['t'] % 60:04.1f}"
        h.pop("i", None)
    Path(args.out).write_text(json.dumps({"source": info["source"], "hits": hits}, ensure_ascii=False, indent=1))
    for h in hits:
        print(f"{h['time']:>7s}  bar {h['bar']:3d}.{h['beat']}  {h['kind']:6s}  {h['score']}")


if __name__ == "__main__":
    main()
