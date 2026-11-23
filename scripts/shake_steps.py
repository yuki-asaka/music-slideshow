#!/usr/bin/env python3
"""シェイクトランジションを作る FilmCraft のコマンド列（command_batch の steps）を出す。

FilmCraft 標準の Earthquake トランジションは前の写真しか揺れず、切り替えがディゾルブになり、
拍から約1.5フレーム遅れる。そこで motion のキーフレームと
Directional Blur（各クリップの effect 3 に事前に適用）で作る。
前のクリップはカットの直前3フレーム、次のクリップはカットから4フレーム揺らし、揺れは段階的に弱める。
build_timeline.py は IN / OUT の表だけを使う。単独で使うときは:
使い方: shake_steps.py --out-clip 11 --in-clip 12 --cut-frame 76 [--base-scale 100] [--blur-effect 3]
"""
import argparse, json

TPF = 254016000000 // 30
# (フレームのずれ, x, y, 回転, 拡大の上乗せ, ブラーの長さ, ブラーの向き)  0 がカットのフレーム
OUT = [(-4, 0, 0, 0.0, 0, 0, 0), (-3, 40, -10, 1.5, 4, 30, 0), (-2, -35, 15, -2.0, 6, 45, 160), (-1, 30, -5, 2.0, 8, 40, 10)]
IN = [(0, -40, 10, -2.0, 8, 45, 170), (1, 25, -5, 1.5, 6, 30, 10), (2, -15, 5, -0.8, 3, 15, 170), (3, 5, 0, 0.3, 1, 5, 0),
      (4, 0, 0, 0.0, 0, 0, 0)]


def steps_for(clip, rows, cut, base_scale, blur_effect):
    out = []
    for d, x, y, rot, ds, blur, ang in rows:
        t = (cut + d) * TPF
        for param, value in (("position", [960 + x, 540 + y]), ("rotation", rot), ("scale", base_scale + ds)):
            out.append({"id": "effects.setParam", "params": {"clip": clip, "effect": "motion", "param": param,
                                                             "value": value, "time": t, "keyframe": True}})
        for param, value in (("length", blur), ("direction", ang)):
            out.append({"id": "effects.setParam", "params": {"clip": clip, "effect": blur_effect, "param": param,
                                                             "value": value, "time": t, "keyframe": True}})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-clip", type=int, required=True)
    ap.add_argument("--in-clip", type=int, required=True)
    ap.add_argument("--cut-frame", type=int, required=True)
    ap.add_argument("--base-scale", type=float, default=100)
    ap.add_argument("--blur-effect", type=int, default=3)
    a = ap.parse_args()
    steps = steps_for(a.out_clip, OUT, a.cut_frame, a.base_scale, a.blur_effect)
    steps += steps_for(a.in_clip, IN, a.cut_frame, a.base_scale, a.blur_effect)
    print(json.dumps(steps))


if __name__ == "__main__":
    main()
