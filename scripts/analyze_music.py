#!/usr/bin/env python3
"""楽曲を解析して data/beats.json（拍・小節・区間の境界・最後の音・小節ごとの盛り上がり）を作る。

librosa の拍検出は曲全体に一度かけると途中で止まることがあり、拍の時刻も約23ミリ秒刻みに量子化される。
そこで曲を約40秒ごとの区間に分けて拍検出し、得られた拍の時刻に等間隔の格子（テンポ一定）を最小二乗で
当てはめ、その格子を拍の時刻とする。テンポが途中で変わる曲には使えない（残差が大きく出るので分かる）。

show.json の music（bpm_hint・downbeat_offset_beats・last_bar）と sections（区間の開始小節）を読む。
sections がまだ空なら、拍と小節だけを出す（区間は song_map.py の表を見て決め、もう一度実行する）。
使い方: analyze_music.py [--show data/show.json] [--audio 楽曲（既定は show.json の music.file）] [--out data/beats.json]
"""
import argparse, json, subprocess
from pathlib import Path

import librosa
import numpy as np

SEGMENT_SEC = 40
OVERLAP_SEC = 5  # 区間の前後に足す余白。拍検出は区間の端で不安定なので、余白で検出して区間の中の拍だけを使う


def detect_beats(y, sr, bpm):
    """約40秒ごとの区間に分けて拍を検出し、つなげる。区間どうしは重ならないので、同じ拍が二重に入らない。
    最後の区間が20秒未満になるときは、その前の区間に含める"""
    beats = []
    dur = len(y) / sr
    starts = list(np.arange(0, max(dur - 20, 1), SEGMENT_SEC))
    for i, st in enumerate(starts):
        en = starts[i + 1] if i + 1 < len(starts) else dur
        a, b = max(0.0, st - OVERLAP_SEC), min(dur, en + OVERLAP_SEC)
        _, bt = librosa.beat.beat_track(y=y[int(a * sr):int(b * sr)], sr=sr, start_bpm=bpm, units="time")
        bt = bt + a
        beats.append(bt[(bt >= st) & (bt < en)])
    return np.sort(np.concatenate(beats))


def best_period(beats, bpm):
    """bpm の前後 ±3% を 0.01 BPM 刻みで試し、格子に乗る拍がいちばん多い周期を選ぶ。
    librosa のテンポの推定は粗く（129.2 と 130 の差でも、曲の終わりには半小節ずれる）、そのまま当てはめると外れ値ばかりになる"""
    best = (0, 60 / bpm, beats.min())
    for b in np.arange(bpm * 0.97, bpm * 1.03, 0.01):
        p = 60 / b
        phase = np.angle(np.exp(2j * np.pi * beats / p).mean()) / (2 * np.pi) * p  # 拍の位相の平均
        resid = (beats - phase + p / 2) % p - p / 2
        n = int((np.abs(resid) < 0.05).sum())
        if n > best[0]:
            t0 = beats.min() + ((phase - beats.min() + p / 2) % p - p / 2)
            best = (n, p, t0)
    return best[1], best[2]


def fit_grid(beats, bpm):
    """拍の時刻に等間隔の格子を当てはめる。外れ値（半拍ずれなど）は除いて当てはめ直す。"""
    period, t0 = best_period(beats, bpm)
    for _ in range(3):
        k = np.round((beats - t0) / period)
        resid = beats - (t0 + k * period)
        keep = np.abs(resid) < 0.05
        period, t0 = np.polyfit(k[keep], beats[keep], 1)
    k = np.round((beats - t0) / period)
    resid = beats - (t0 + k * period)
    keep = np.abs(resid) < 0.05
    return period, t0, resid[keep], keep.mean()


def loudness(path):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    for line in reversed(out.splitlines()):
        if line.strip().startswith("I:"):
            return float(line.split()[1])
    return None


def music_end(y, sr):
    """音量が急に落ちる時刻（曲の実質的な終わり）を求める。"""
    rms = librosa.feature.rms(y=y, hop_length=256)[0]
    t = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=256)
    loud = rms > rms.max() * 0.25
    return float(t[np.where(loud)[0][-1]])


def bar_energy(y, sr, bars, bar_period):
    """小節ごとの音量（RMS）と高音域の量（4kHz 以上）。強く圧縮された曲は音量が平らなので、盛り上がりは高音域で見る"""
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    t = librosa.frames_to_time(np.arange(S.shape[1]), sr=sr, hop_length=512)
    rms = np.sqrt((S ** 2).mean(0))
    high = S[freqs >= 4000].mean(0)
    out = {}
    for n, b in bars.items():
        m = (t >= b["t"]) & (t < b["t"] + bar_period)
        if m.any():
            out[n] = (float(rms[m].mean()), float(high[m].mean()))
    rmax = max(v[0] for v in out.values()) or 1
    hmax = max(v[1] for v in out.values()) or 1
    return {str(n): {"rms": round(v[0] / rmax, 3), "high": round(v[1] / hmax, 3)} for n, v in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", default="data/show.json")
    ap.add_argument("--audio")
    ap.add_argument("--out", default="data/beats.json")
    args = ap.parse_args()
    show = json.loads(Path(args.show).read_text())
    m = show.get("music", {})
    fps = show.get("project", {}).get("fps", 30)
    audio = args.audio or m["file"]

    y, sr = librosa.load(audio, sr=22050, mono=True)
    duration = len(y) / sr
    bpm = m.get("bpm_hint") or float(np.atleast_1d(librosa.beat.beat_track(y=y, sr=sr)[0])[0])
    period, t0, resid, inlier = fit_grid(detect_beats(y, sr, bpm), bpm)
    # 小節の起点の補正（最初に検出した拍が1拍目でない場合に拍数でずらす。耳で確かめて show.json に書く）
    t0 += m.get("downbeat_offset_beats", 0) * period
    while t0 - period > 0:  # 格子を曲の頭まで延ばす（イントロの拍を落とさない）。ただし4拍単位で動かして小節をずらさない
        if t0 - 4 * period < 0:
            break
        t0 -= 4 * period
    beats = []
    k = 0
    while t0 + k * period < duration:
        t = t0 + k * period
        beats.append({"i": k, "t": round(t, 4), "frame": int(round(t * fps)), "bar": k // 4 + 1, "beat": k % 4 + 1})
        k += 1

    bars = {}
    for b in beats:
        if b["beat"] == 1:
            bars[b["bar"]] = {"t": b["t"], "frame": b["frame"]}
    bar_of = lambda n: bars[n]["t"] if n in bars else None
    end_t = music_end(y, sr)
    last_bar = m.get("last_bar") or max(n for n, b in bars.items() if b["t"] < end_t - 2 * period)

    sections = []
    secs = show.get("sections", [])
    for i, s in enumerate(secs):
        nxt = secs[i + 1]["start_bar"] if i + 1 < len(secs) else None
        sections.append({"name": s["name"], "start_bar": s["start_bar"], "end_bar": (nxt - 1) if nxt else last_bar,
                         "start": 0.0 if i == 0 else bar_of(s["start_bar"]),
                         "end": bar_of(nxt) if nxt else round(duration, 4)})

    out = {
        "source": Path(audio).name,
        "duration": round(duration, 4),
        "fps": fps,
        "tempo_bpm": round(60 / period, 3),
        "beat_period": round(period, 6),
        "bar_period": round(4 * period, 6),
        "first_beat": round(t0, 4),
        "grid_fit_residual_ms": {"median_abs": round(float(np.median(np.abs(resid))) * 1000, 1),
                                 "p95_abs": round(float(np.percentile(np.abs(resid), 95)) * 1000, 1),
                                 "inlier_ratio": round(float(inlier), 3)},
        "loudness_lufs": loudness(audio),
        "music_end": round(end_t, 3),
        "last_bar": last_bar,
        "sections": sections,
        "bars": {str(n): v for n, v in bars.items()},
        "bar_energy": bar_energy(y, sr, bars, 4 * period),
        "beats": beats,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    r = out["grid_fit_residual_ms"]
    print(f"tempo {out['tempo_bpm']} BPM, first beat {out['first_beat']}s, beats {len(beats)}, bars {len(bars)}, "
          f"fit residual median {r['median_abs']}ms p95 {r['p95_abs']}ms inlier {r['inlier_ratio']}, "
          f"music_end {out['music_end']}s (last bar {last_bar}), loudness {out['loudness_lufs']} LUFS")
    if r["p95_abs"] > 40 or r["inlier_ratio"] < 0.7:
        print("注意: 格子が合っていない。テンポが途中で変わる曲か、bpm_hint が倍・半分になっている")
    for s in sections:
        print(f"  {s['name']:4s} bar {s['start_bar']:3d}-{s['end_bar']:3d}  {s['start']:7.2f}-{s['end']:7.2f}s")


if __name__ == "__main__":
    main()
