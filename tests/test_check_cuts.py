import json

from conftest import TICKS, run_script, write_json


def fcproj(sequences):
    """check_cuts.py が読む部分だけの .fcproj。sequences は {名前: [(クリップ名, 開始フレーム), ...]}"""
    tpf = TICKS // 30
    items = {}
    for i, (name, clips) in enumerate(sequences.items()):
        items[str(i)] = {"name": name, "kind": {"Sequence": {"video_tracks": [
            {"items": [{"name": n, "start": f * tpf} for n, f in clips], "transitions": []}]}}}
    return {"project": {"items": items}}


def test_cuts_one_frame_before_beat_pass(tmp_path, beats):
    write_json(tmp_path / "beats.json", beats)
    starts = [b["frame"] - 1 for b in beats["beats"][4:20:4]]
    write_json(tmp_path / "p.fcproj", fcproj({"MASTER": [(f"c{i}", f) for i, f in enumerate(starts)]}))
    r = run_script("check_cuts.py", tmp_path / "p.fcproj", "--beats", tmp_path / "beats.json")
    assert r.returncode == 0, r.stdout
    assert "NG 0" in r.stdout


def test_cut_off_the_beat_fails(tmp_path, beats):
    write_json(tmp_path / "beats.json", beats)
    starts = [b["frame"] - 1 for b in beats["beats"][4:20:4]]
    starts[2] += 3
    write_json(tmp_path / "p.fcproj", fcproj({"MASTER": [(f"c{i}", f) for i, f in enumerate(starts)]}))
    r = run_script("check_cuts.py", tmp_path / "p.fcproj", "--beats", tmp_path / "beats.json")
    assert r.returncode == 1
    assert "NG 1" in r.stdout


def test_nested_sections_use_origin_and_allow_two_frames(tmp_path, beats):
    write_json(tmp_path / "beats.json", beats)
    origin = 100
    tl = {"sections": [{"name": "S2", "origin": origin}]}
    write_json(tmp_path / "timeline.json", tl)
    frames = [b["frame"] for b in beats["beats"]]
    near = [f for f in frames if f > origin + 10][:4]
    ok = [("head", 0)] + [(f"c{i}", f - origin + d) for i, (f, d) in enumerate(zip(near, (-1, 0, 2, -2)))]
    write_json(tmp_path / "ok.fcproj", fcproj({"S2": ok}))
    r = run_script("check_cuts.py", tmp_path / "ok.fcproj", "--beats", tmp_path / "beats.json",
                   "--timeline", tmp_path / "timeline.json")
    assert r.returncode == 0, r.stdout
    assert "切り替え 4 か所" in r.stdout  # 区間の頭は数えない

    # 拍の間隔（約14フレーム）の中ほどまでずらすと NG
    bad = ok[:1] + [(n, f + (4 if n == "c1" else 0)) for n, f in ok[1:]]
    write_json(tmp_path / "bad.fcproj", fcproj({"S2": bad}))
    r = run_script("check_cuts.py", tmp_path / "bad.fcproj", "--beats", tmp_path / "beats.json",
                   "--timeline", tmp_path / "timeline.json")
    assert r.returncode == 1
