"""テストの共通部品。曲・写真・行事はすべて合成したもの（実案件の素材は使わない）。"""
import json, subprocess, sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

TICKS = 254016000000


def make_beats(bpm=130, bars=16, fps=30, first_beat=0.5):
    """analyze_music.py が書く beats.json と同じ形の、テンポ一定の拍"""
    period = 60 / bpm
    beats = []
    for k in range(bars * 4):
        t = first_beat + k * period
        beats.append({"i": k, "t": round(t, 4), "frame": int(round(t * fps)), "bar": k // 4 + 1, "beat": k % 4 + 1})
    return {"fps": fps, "tempo_bpm": bpm, "beat_period": period, "bar_period": 4 * period, "first_beat": first_beat,
            "duration": round(first_beat + bars * 4 * period, 4), "beats": beats}


def run_script(name, *args, cwd=None):
    return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)], cwd=cwd, capture_output=True, text=True)


@pytest.fixture
def beats():
    return make_beats()


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False))
    return path
