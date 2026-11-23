import csv, json

import pytest
from PIL import Image

from build_timeline import CROP_MAX_ZOOM, LONG, PRE, SHORT, crop_to_view, kb_keys
from conftest import make_beats, run_script, write_json
from shake_steps import IN as SHAKE_IN, OUT as SHAKE_OUT

COLS = ["section", "bar", "bars", "kind", "id", "file", "kb", "punch_in", "fix", "note"]

# 架空の3区間・12小節: S1 カット / S2 区間ディゾルブで入る / S3 白フラッシュで入る
SHOW = {
    "project": {"name": "test", "width": 1920, "height": 1080, "fps": 30},
    "music": {"file": "assets/bpm/song.mp3", "gain_db": -1.0, "fade_in_sec": 0.5, "fade_out_sec": 0.3},
    "sections": [{"name": "S1", "start_bar": 1, "in": "cut"},
                 {"name": "S2", "start_bar": 5, "in": "dissolve"},
                 {"name": "S3", "start_bar": 9, "in": "flash"}],
    "chorus_bars": [9],
    "end_black_bar": 13,
    "cut_offset": -1,
    "transitions": {"flash": [9], "shake": [11], "dissolve_long": [6], "dissolve_short": [7]},
}
# (区間, 小節, 小節数)。S1 の4枚目だけ暗い写真にする
SLOTS = [("S1", 1, 1), ("S1", 2, 1), ("S1", 3, 1), ("S1", 4, 1),
         ("S2", 5, 1), ("S2", 6, 1), ("S2", 7, 1), ("S2", 8, 1),
         ("S3", 9, 2), ("S3", 11, 1), ("S3", 12, 1)]


def make_project(tmp_path, slots=SLOTS, show=SHOW):
    rows = []
    for i, (sec, bar, bars) in enumerate(slots):
        f = tmp_path / "work" / "photos" / f"p{i:02d}.jpg"
        f.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (400, 300), (40, 40, 40) if i == 3 else (140, 130, 120)).save(f)
        rows.append({"section": sec, "bar": bar, "bars": bars, "kind": "photo", "id": f"01-{i:03d}",
                     "file": str(f.relative_to(tmp_path)), "kb": "in", "punch_in": "", "fix": "", "note": ""})
    (tmp_path / "data").mkdir(exist_ok=True)
    with open(tmp_path / "data" / "selection.csv", "w", newline="") as fp:
        w = csv.DictWriter(fp, COLS)
        w.writeheader()
        w.writerows(rows)
    write_json(tmp_path / "data" / "show.json", show)
    write_json(tmp_path / "data" / "beats.json", make_beats(bars=14))


def build(tmp_path):
    r = run_script("build_timeline.py", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    return r.stdout, json.loads((tmp_path / "data" / "timeline.json").read_text())


@pytest.fixture
def timeline(tmp_path):
    make_project(tmp_path)
    out, tl = build(tmp_path)
    beats = json.loads((tmp_path / "data" / "beats.json").read_text())["beats"]
    frame = lambda bar: beats[round((bar - 1) * 4)]["frame"]
    clips = {c["bar"]: c for c in tl["clips"]}
    return out, tl, frame, clips


def test_no_problems(timeline):
    out, tl, _, clips = timeline
    assert "problems 0" in out
    assert len(clips) == len(SLOTS)
    assert tl["total_frames"] == round(make_beats(bars=14)["duration"] * 30)


def test_cut_lands_one_frame_before_beat(timeline):
    _, _, frame, clips = timeline
    for bar in (2, 3, 4, 8, 12):
        assert clips[bar]["in"]["type"] == "cut"
        assert clips[bar]["start"] == frame(bar) - 1


def test_dissolves_are_centred_on_beat(timeline):
    _, _, frame, clips = timeline
    assert clips[6]["in"] == {"type": "dissolve", "frames": LONG}
    assert clips[7]["in"] == {"type": "dissolve", "frames": SHORT}
    assert clips[6]["start"] == frame(6) and clips[7]["start"] == frame(7)


def test_section_dissolve_adds_handles(timeline):
    _, tl, frame, clips = timeline
    assert clips[5]["in"]["type"] == "section"
    assert clips[5]["start"] == frame(5) - PRE
    assert clips[4]["end"] == frame(5) + PRE  # 前の区間の最後の写真も延ばす
    s2 = next(s for s in tl["sections"] if s["name"] == "S2")
    assert s2["origin"] == frame(5) - PRE


def test_flash_peak_on_beat(timeline):
    _, tl, frame, clips = timeline
    assert clips[9]["in"]["type"] == "flash"
    assert clips[9]["start"] == frame(9) - 1
    flash = next(o for o in tl["overlays"] if o["name"] == "WHITE_FLASH")
    peak = max(flash["keys"]["opacity"], key=lambda kv: kv[1])
    assert peak[0] == frame(9)


def test_shake_cuts_on_beat_and_shakes_both_clips(timeline):
    _, _, frame, clips = timeline
    cut = frame(11)
    assert clips[11]["in"]["type"] == "shake"
    assert clips[11]["start"] == cut
    assert clips[9]["end"] == cut  # 前の写真もシェイクの拍ちょうどで終わる
    assert clips[9]["shake"] == ["out"] and clips[11]["shake"] == ["in"]
    assert [f for f, _ in clips[9]["keys"]["rotation"]] == [cut + d for d, *_ in SHAKE_OUT]
    assert [f for f, _ in clips[11]["keys"]["rotation"]] == [cut + d for d, *_ in SHAKE_IN]


def test_markers_and_end_black(timeline):
    _, tl, frame, _ = timeline
    names = [m["name"] for m in tl["markers"]]
    assert "サビの頭 小節9" in names
    black = next(o for o in tl["overlays"] if o["name"] == "END_BLACK")
    assert black["keys"]["opacity"][-1] == [frame(13) + 3, 100.0]


def test_dark_photo_gets_exposure_fix(timeline):
    _, _, _, clips = timeline
    assert clips[4]["lumetri"]["exposure"] > 0
    assert "lumetri" not in clips[2]


def test_gap_in_selection_is_reported(tmp_path):
    make_project(tmp_path, slots=[s for s in SLOTS if s[1] != 3])
    out, _ = build(tmp_path)
    assert "隙間・重なり（selection.csv）" in out
    assert "problems 0" not in out


def test_overlap_in_selection_is_reported(tmp_path):
    slots = [s if s[1] != 2 else ("S1", 2, 2) for s in SLOTS]
    make_project(tmp_path, slots=slots)
    out, _ = build(tmp_path)
    assert "隙間・重なり（selection.csv）" in out


def test_crop_zoom_is_capped_and_stays_inside_frame():
    v = crop_to_view((0.0, 0.0, 0.2, 0.2))  # 幅 0.2 → 5倍だが上限で止める
    assert v["zoom"] == CROP_MAX_ZOOM
    w, h = 1920 * v["zoom"], 1440 * v["zoom"]
    assert abs(v["x"] - 960) <= (w - 1920) / 2 and abs(v["y"] - 540) <= (h - 1080) / 2
    assert crop_to_view((0, 0, 1, 0.75))["zoom"] == 1.0


def test_ken_burns_zoom_is_gentle_and_capped():
    short = kb_keys("in", 0, 60)  # 2秒
    assert short["scale"][1][1] == pytest.approx(1.04)
    long = kb_keys("in", 0, 30 * 20)  # 20秒でも 10% まで
    assert long["scale"][1][1] == pytest.approx(1.10)
    pan = kb_keys("lr", 0, 90)
    assert pan["position"][0][1][0] > pan["position"][1][1][0]  # lr: 写真は右から左へ動く
