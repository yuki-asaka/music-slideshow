import json

from conftest import run_script
from shake_steps import IN, OUT, TPF, steps_for


def test_out_rows_end_before_cut_and_in_rows_start_on_cut():
    # 前のクリップはカットの前だけ、次のクリップはカットのフレームから揺れる
    assert all(d < 0 for d, *_ in OUT)
    assert IN[0][0] == 0
    # 揺れの前後は静止（位置・回転・拡大・ブラーがすべて 0）
    assert OUT[0][1:] == (0, 0, 0.0, 0, 0, 0)
    assert IN[-1][1:] == (0, 0, 0.0, 0, 0, 0)


def test_steps_for_keyframes_times_and_values():
    steps = steps_for(12, IN, 76, 100, 3)
    assert len(steps) == len(IN) * 5  # position・rotation・scale・length・direction
    times = sorted({s["params"]["time"] for s in steps})
    assert times == [(76 + d) * TPF for d, *_ in IN]
    first = [s["params"] for s in steps if s["params"]["time"] == 76 * TPF]
    pos = next(p["value"] for p in first if p["param"] == "position")
    assert pos == [960 + IN[0][1], 540 + IN[0][2]]
    blur = [p for p in first if p["effect"] == 3]
    assert {p["param"] for p in blur} == {"length", "direction"}
    assert all(s["params"]["clip"] == 12 and s["params"]["keyframe"] for s in steps)


def test_cli_outputs_steps_for_both_clips():
    r = run_script("shake_steps.py", "--out-clip", 11, "--in-clip", 12, "--cut-frame", 76)
    assert r.returncode == 0, r.stderr
    steps = json.loads(r.stdout)
    assert {s["params"]["clip"] for s in steps} == {11, 12}
    assert len(steps) == (len(OUT) + len(IN)) * 5
