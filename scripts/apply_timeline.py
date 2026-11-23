#!/usr/bin/env python3
"""data/timeline.json から FilmCraft のプロジェクト（project/slideshow.fcproj）を組み立てる。

filmcraft-cli run（ヘッドレス）で、次の3段階を順に実行する。各段階の結果（JSON 行）から ID を読み、次の段階に渡す。
  1. 新しいプロジェクト、区間シーケンス（timeline.json の sections）とマスター、素材の読み込み、カラーマット、調整レイヤー
  2. クリップの配置（区間シーケンスの V1/V2、マスターの V1〜V7 と A1）、動画の画面合わせ（fillFrame）
  3. 効果: Ken Burns・シェイク・パンチインのキーフレーム、補正、ディゾルブ、合成モード、調整レイヤーの効果、マーカー
使い方: apply_timeline.py [--timeline data/timeline.json] [--project project/slideshow.fcproj] [--keep] [--no-burnin]
  --keep で各段階の .jsonl を work/timeline/ に残す
  プロジェクトのルート（data/ と work/ があるフォルダ）で実行する。相対パスはそこから解決する
"""
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path.cwd()
TICKS = 254016000000
FPS = 30
TPF = TICKS // FPS
SECTIONS = []
FIXED_EFFECT = {"motion": 0, "opacity": 1}  # どのビデオクリップにも最初からある効果の番号


def ticks(frame):
    return int(round(frame)) * TPF


def run(steps, name, keep):
    path = ROOT / "work" / "timeline" / f"{name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(s, ensure_ascii=False) for s in steps) + "\n")
    p = subprocess.run(["filmcraft-cli", "run", str(path)], capture_output=True, text=True)
    results = [json.loads(l) for l in p.stdout.splitlines() if l.startswith("{")]
    failed = [r for r in results if not r.get("ok")]
    if p.returncode or failed or len(results) != len(steps):
        for r in failed[:10]:
            print("NG", r, file=sys.stderr)
        print(p.stderr[-2000:], file=sys.stderr)
        sys.exit(f"{name}: {len(results)}/{len(steps)} 行、失敗 {len(failed)}")
    if not keep:
        path.unlink()
    print(f"{name}: {len(steps)} commands ok")
    return [r.get("result") for r in results]


def abspath(p):
    return str(ROOT / p) if not p.startswith("/") else p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeline", default="data/timeline.json")
    ap.add_argument("--project", default="project/slideshow.fcproj")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--no-burnin", action="store_true", help="レビュー用の焼き込み（V8）を置かない")
    args = ap.parse_args()
    global FPS, TPF, SECTIONS
    tl = json.loads((ROOT / args.timeline).read_text())
    FPS = tl["fps"]
    TPF = TICKS // FPS
    SECTIONS = [s["name"] for s in tl["sections"]]
    width, height = tl.get("width", 1920), tl.get("height", 1080)
    if args.no_burnin:
        tl["overlays"] = [o for o in tl["overlays"] if not o.get("review_only")]
    proj = str(ROOT / args.project)
    total = tl["total_frames"]
    sec = {s["name"]: s for s in tl["sections"]}
    clips, overlays, adjust = tl["clips"], tl["overlays"], tl["adjust"]

    # ---- 1. プロジェクト・シーケンス・素材 ----
    files = []
    for c in clips:
        files.append(abspath(c["file"]))
    for o in overlays:
        if "file" in o:
            files.append(abspath(o["file"]))
    files.append(abspath(tl["audio"]["file"]))
    files = list(dict.fromkeys(files))
    steps = [{"id": "file.newProject", "params": {"name": "slideshow"}}]
    for n in SECTIONS:
        steps.append({"id": "file.newSequence", "params": {"name": n, "width": width, "height": height, "fps": FPS, "video": 2, "audio": 1}})
    steps.append({"id": "file.newSequence", "params": {"name": "MASTER", "width": width, "height": height, "fps": FPS, "video": 8, "audio": 1}})
    steps.append({"id": "file.import", "params": {"paths": files}})
    mattes = [o for o in overlays if "matte" in o]
    for o in mattes:
        steps.append({"id": "file.newColorMatte", "params": {"color": o["matte"], "seconds": 10}})
    for a in adjust:
        steps.append({"id": "file.newAdjustmentLayer", "params": {"seconds": total / FPS + 1}})
    steps.append({"id": "file.saveAs", "params": {"path": proj}})
    res = run(steps, "1_create", args.keep)
    seq_id = {n: res[1 + i]["sequence"] for i, n in enumerate(SECTIONS + ["MASTER"])}
    item_of = dict(zip(files, res[1 + len(SECTIONS) + 1]["items"]))
    k = 1 + len(SECTIONS) + 2
    matte_item = {o["name"]: res[k + i]["item"] for i, o in enumerate(mattes)}
    k += len(mattes)
    adjust_item = {a["name"]: res[k + i]["item"] for i, a in enumerate(adjust)}

    # ---- 2. 配置 ----
    steps = [{"id": "file.open", "params": {"path": proj}}]
    placed = []  # (kind, ref) を steps と同じ順に記録し、結果からクリップ ID を取る
    for n in SECTIONS:
        s = sec[n]
        steps.append({"id": "sequence.open", "params": {"item": seq_id[n]}})
        placed.append(None)
        for c in [c for c in clips if c["section"] == n]:
            local = c["start"] - s["origin"]
            p = {"item": item_of[abspath(c["file"])], "track": c["track"], "frame": local,
                 "duration": {"frame": c["end"] - c["start"]}, "insert": False, "audio": False}
            if c["kind"] == "video":
                p["sourceIn"] = {"seconds": c["source_in"]}
            steps.append({"id": "timeline.place", "params": p})
            placed.append(("clip", c))
            # 静止画もヘッドレスでは原寸で置かれるので、すべて画面を埋める大きさにそろえ、その倍率を Ken Burns の基準にする
            if c.get("role") != "portrait_fg":
                steps.append({"id": "clip.fillFrame", "params": {}})
                placed.append(("fill", c))
    # マスター: 区間のネスト
    steps.append({"id": "sequence.open", "params": {"item": seq_id["MASTER"]}})
    placed.append(None)
    for i, n in enumerate(SECTIONS):
        s = sec[n]
        start, end = s["start"], s["end"]
        if s["in"] == "under_grid":
            start = s["origin"]
        if i + 1 < len(SECTIONS) and sec[SECTIONS[i + 1]]["in"] == "under_grid":
            end = sec[SECTIONS[i + 1]]["origin"]
        steps.append({"id": "timeline.place", "params": {"item": seq_id[n], "track": "V1", "frame": start,
                                                          "duration": {"frame": end - start},
                                                          "sourceIn": {"frame": start - s["origin"]},
                                                          "insert": False, "audio": False}})
        placed.append(("nest", n))
    for o in overlays:
        item = item_of[abspath(o["file"])] if "file" in o else matte_item[o["name"]]
        p = {"item": item, "track": o["track"], "frame": o["start"], "duration": {"frame": o["end"] - o["start"]},
             "insert": False, "audio": False}
        if "file" in o:
            p["sourceIn"] = {"frame": o["source_in"]}
        steps.append({"id": "timeline.place", "params": p})
        placed.append(("overlay", o))
    for a in adjust:
        steps.append({"id": "timeline.place", "params": {"item": adjust_item[a["name"]], "track": a["track"], "frame": a["start"],
                                                          "duration": {"frame": a["end"] - a["start"]}, "insert": False}})
        placed.append(("adjust", a))
    steps.append({"id": "timeline.place", "params": {"item": item_of[abspath(tl["audio"]["file"])], "track": "A1", "frame": 0,
                                                      "insert": False}})
    placed.append(("audio", None))
    steps.append({"id": "file.save", "params": {}})
    placed.append(None)
    res = run(steps, "2_place", args.keep)
    clip_id, base = {}, {}
    last = None
    for (r, pl) in zip(res[1:], placed):
        if pl is None:
            continue
        kind, ref = pl
        key = (kind, id(ref)) if isinstance(ref, dict) else (kind, ref)
        if kind == "fill":
            base[id(ref)] = r["clips"][0]["scale"]
        else:
            clip_id[key] = r["clips"][0]

    # ---- 3. 効果 ----
    steps = [{"id": "file.open", "params": {"path": proj}}]

    def keyframes(cid, effect, param, keys, origin, start, src_ticks=0, scale=None, fmt=None):
        out, refs = [], []
        for f, v in keys:
            val = v
            if scale is not None:
                val = round(v * scale, 3)
            if fmt == "pos":
                val = [round(v[0], 1), round(v[1], 1)]
            out.append({"id": "effects.setParam", "params": {"clip": cid, "effect": effect, "param": param, "value": val,
                                                              "time": ticks(f - origin), "keyframe": True}})
            refs.append({"clip": cid, "effect": effect if isinstance(effect, int) else FIXED_EFFECT[effect], "param": param,
                         "time": ticks(f - start) + src_ticks})
        out.append({"id": "effects.setInterpolation", "params": {"keyframes": refs, "interpolation": "linear"}})
        return out

    for n in SECTIONS:
        s = sec[n]
        steps.append({"id": "sequence.open", "params": {"item": seq_id[n]}})
        sc = [c for c in clips if c["section"] == n]
        for c in sc:
            cid = clip_id[("clip", id(c))]
            b = base.get(id(c), 100.0)
            if c.get("role") == "portrait_fg":
                b = 1080 / 1440 * 100  # 縦向き 1080×1440 を高さに合わせる
            src = int(round(c["source_in"] * TICKS)) if c["kind"] == "video" else 0
            idx = 3
            fx = {}
            if "blur_length" in c["keys"]:
                steps.append({"id": "effects.apply", "params": {"clips": [cid], "effect": "directional_blur"}})
                fx["blur"] = idx
                idx += 1
            if c.get("lumetri"):
                steps.append({"id": "effects.apply", "params": {"clips": [cid], "effect": "lumetri"}})
                for param, v in c["lumetri"].items():
                    steps.append({"id": "effects.setParam", "params": {"clip": cid, "effect": idx, "param": param, "value": v}})
                idx += 1
            if c.get("role") == "portrait_bg":
                steps.append({"id": "effects.apply", "params": {"clips": [cid], "effect": "gaussian_blur"}})
                steps.append({"id": "effects.setParam", "params": {"clip": cid, "effect": idx, "param": "blurriness", "value": 80}})
                steps.append({"id": "effects.setParam", "params": {"clip": cid, "effect": idx, "param": "repeat_edge", "value": True}})
                idx += 1
            o = s["origin"]
            for param, keys in c["keys"].items():
                if param == "scale":
                    steps += keyframes(cid, "motion", "scale", keys, o, c["start"], src, scale=b)
                elif param == "position":
                    steps += keyframes(cid, "motion", "position", keys, o, c["start"], src, fmt="pos")
                elif param == "rotation":
                    steps += keyframes(cid, "motion", "rotation", keys, o, c["start"], src)
                elif param == "opacity":
                    steps += keyframes(cid, "opacity", "opacity", keys, o, c["start"], src)
                elif param == "blur_length":
                    steps += keyframes(cid, fx["blur"], "length", keys, o, c["start"], src)
                elif param == "blur_direction":
                    steps += keyframes(cid, fx["blur"], "direction", keys, o, c["start"], src)
        # 区間の中のディゾルブ（入ってくるクリップの前のクリップにかける）
        v1 = sorted([c for c in sc if c["track"] == "V1" and c.get("role") != "portrait_bg"], key=lambda c: c["start"])
        for a, bclip in zip(v1, v1[1:]):
            if bclip["in"]["type"] == "dissolve" and a["end"] == bclip["start"]:
                steps.append({"id": "sequence.applyVideoTransition", "params": {
                    "clip": clip_id[("clip", id(a))], "effect": "cross_dissolve", "frames": bclip["in"]["frames"],
                    "edge": "out", "align": "center"}})
    # マスター
    steps.append({"id": "sequence.open", "params": {"item": seq_id["MASTER"]}})
    for i, n in enumerate(SECTIONS[:-1]):
        if sec[SECTIONS[i + 1]]["in"] == "dissolve":
            steps.append({"id": "sequence.applyVideoTransition", "params": {
                "clip": clip_id[("nest", n)], "effect": "cross_dissolve", "frames": 28, "edge": "out", "align": "center"}})
    for o in overlays:
        cid = clip_id[("overlay", id(o))]
        if o.get("blend"):
            steps.append({"id": "effects.setParam", "params": {"clip": cid, "effect": "opacity", "param": "blend", "value": o["blend"]}})
        for param, keys in o.get("keys", {}).items():
            src = ticks(o.get("source_in", 0))
            steps += keyframes(cid, "opacity", "opacity", keys, 0, o["start"], src)
    for a in adjust:
        cid = clip_id[("adjust", id(a))]
        idx = 3
        for eff, params in a["effects"].items():
            steps.append({"id": "effects.apply", "params": {"clips": [cid], "effect": eff}})
            for p, v in params.items():
                steps.append({"id": "effects.setParam", "params": {"clip": cid, "effect": idx, "param": p, "value": v}})
            idx += 1
        for param, keys in a.get("keys", {}).items():
            steps += keyframes(cid, "opacity", "opacity", keys, 0, a["start"])
    aid = clip_id[("audio", None)]
    steps += keyframes(aid, 0, "level", tl["audio"]["keys"], 0, 0)
    for m in tl["markers"]:
        steps.append({"id": "markers.add", "params": {"target": "program", "time": ticks(m["frame"]), "name": m["name"],
                                                       "color": m["color"]}})
    steps.append({"id": "file.save", "params": {}})
    run(steps, "3_effects", args.keep)
    (ROOT / "work" / "timeline").mkdir(parents=True, exist_ok=True)
    (ROOT / "work" / "timeline" / "ids.json").write_text(json.dumps({"sequences": seq_id}, indent=1))
    print("project:", proj, "master sequence item:", seq_id["MASTER"])


if __name__ == "__main__":
    main()
