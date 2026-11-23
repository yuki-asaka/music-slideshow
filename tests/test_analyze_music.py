import json, shutil

import numpy as np
import pytest

librosa = pytest.importorskip("librosa")
sf = pytest.importorskip("soundfile")

import analyze_music
from analyze_music import OVERLAP_SEC, SEGMENT_SEC, best_period, detect_beats, fit_grid
from conftest import run_script, write_json


def jittered_beats(bpm, first, n, jitter_ms=10, seed=0):
    """検出した拍に見立てた時刻: 等間隔に揺らぎ（±10ms）と librosa の約23msの量子化、半拍ずれの外れ値を混ぜる"""
    rng = np.random.default_rng(seed)
    t = first + np.arange(n) * 60 / bpm + rng.uniform(-jitter_ms, jitter_ms, n) / 1000
    t = np.round(t / 0.0232) * 0.0232
    t[::17] += 30 / bpm  # 半拍ずれ
    return t


@pytest.mark.parametrize("bpm", [96.0, 130.0, 145.9])
def test_tempo_recovered_from_rough_hint(bpm):
    beats = jittered_beats(bpm, 0.37, 400)
    hint = bpm * 0.985  # librosa のテンポ推定くらいの粗さ（130 → 128）
    period, _ = best_period(beats, hint)
    assert 60 / period == pytest.approx(bpm, abs=0.1)  # 粗い探索（±50ms に乗る拍の数で選ぶ）
    period, *_ = fit_grid(beats, hint)
    assert 60 / period == pytest.approx(bpm, abs=0.01)  # 最小二乗で詰めたあと


def test_fit_grid_drops_outliers_and_locks_phase():
    bpm, first = 130.0, 0.37
    beats = jittered_beats(bpm, first, 400)
    period, t0, resid, inlier = fit_grid(beats, bpm)
    assert 60 / period == pytest.approx(bpm, abs=0.01)
    k = round((t0 - first) / period)
    assert t0 - k * period == pytest.approx(first, abs=0.005)
    assert inlier > 0.9  # 半拍ずれ（1/17）は外れ値として落ちる
    # 曲の終わり（400拍目）でも格子のずれが1フレーム（33ms）未満
    end = first + 399 * 60 / bpm
    assert abs((t0 + round((end - t0) / period) * period) - end) < 1 / 30


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg が必要（音量の計測）")
def test_cli_on_click_track(tmp_path):
    bpm, first, sec, sr = 130.0, 0.5, 60, 22050
    period = 60 / bpm
    times = first + np.arange(int((sec - first - 1) / period)) * period
    y = librosa.clicks(times=times, sr=sr, length=sec * sr, click_freq=1500)
    y += librosa.clicks(times=times[::4], sr=sr, length=sec * sr, click_freq=800)  # 1拍目を強く
    sf.write(tmp_path / "click.wav", y * 0.5, sr)

    def analyze(offset):
        write_json(tmp_path / "show.json", {"project": {"fps": 30},
                                            "music": {"file": "click.wav", "bpm_hint": 130, "downbeat_offset_beats": offset}})
        r = run_script("analyze_music.py", "--show", "show.json", "--out", "beats.json", cwd=tmp_path)
        assert r.returncode == 0, r.stderr
        return json.loads((tmp_path / "beats.json").read_text())

    info = analyze(0)
    assert info["tempo_bpm"] == pytest.approx(bpm, abs=0.05)
    assert info["grid_fit_residual_ms"]["p95_abs"] < 40
    # 格子の拍が、最初の拍より後のクリックすべてから1フレーム以内
    grid = np.array([b["t"] for b in info["beats"]])
    for t in times[times >= info["first_beat"] - 0.05]:
        assert np.abs(grid - t).min() < 1 / 30
    assert set(info["bar_energy"]) == set(info["bars"])

    # 最初に検出した拍が1拍目でないときは downbeat_offset_beats でずらす（耳で確かめる手順）。
    # 小節1の頭が強いクリック（4拍ごと）に乗ること
    k = int(round((info["first_beat"] - first) / period)) % 4
    info = analyze((4 - k) % 4)
    bar1 = info["bars"]["1"]["t"]
    assert np.abs(times[::4] - bar1).min() < 1 / 30


def test_detect_beats_uses_bounded_segments_without_duplicates(monkeypatch):
    """各区間は前後の余白を含めて区切られ、拍は区間の境目で二重にならない（librosa の拍検出は差し替える）"""
    sr, bpm, dur = 1000, 120.0, 200.0
    period = 60 / bpm
    truth = np.arange(0, dur, period)
    lengths = []

    def fake_beat_track(y, sr, start_bpm, units):
        # y の値は曲の頭からの秒（下で作る）。切り出した範囲の本当の拍を、区間の頭からの秒で返す
        lengths.append(len(y) / sr)
        a, b = y[0], y[-1] + 1 / sr
        return start_bpm, truth[(truth >= a) & (truth < b)] - a

    monkeypatch.setattr(analyze_music.librosa.beat, "beat_track", fake_beat_track)
    beats = detect_beats(np.arange(int(dur * sr)) / sr, sr, bpm)
    assert len(lengths) == len(np.arange(0, dur - 20, SEGMENT_SEC))
    assert max(lengths) < SEGMENT_SEC + 20 + 2 * OVERLAP_SEC  # 最後の区間（20秒未満の残りを含む）でも曲の最後までにはならない
    assert np.all(np.diff(beats) > period / 2)  # 二重の拍がない
    assert len(beats) == len(truth)  # 拍を落としてもいない


def test_detect_beats_on_long_click_track_has_no_duplicates():
    # 130秒なら3区間（0・40・80秒から）。以前は各区間を曲の最後まで解析していたので、後半の拍が二重・三重に入っていた
    bpm, first, sec, sr = 130.0, 0.5, 130, 22050
    period = 60 / bpm
    times = first + np.arange(int((sec - first - 1) / period)) * period
    y = librosa.clicks(times=times, sr=sr, length=sec * sr, click_freq=1500)
    beats = detect_beats(y, sr, bpm)
    assert np.all(np.diff(beats) > period / 2)
    assert len(beats) <= len(times)
    assert len(beats) >= len(times) * 0.9
