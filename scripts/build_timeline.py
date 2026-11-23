#!/usr/bin/env python3
"""data/show.json・data/selection.csv・data/beats.json・data/hits.json から data/timeline.json を作る。

フレームはすべてマスターシーケンスの絶対フレーム。区間シーケンスに置くときは apply_timeline.py が
区間の原点（origin）を引く。区間シーケンスは、区間の前後に PRE フレームずつ余分に絵を持つ
（マスターで区間どうしをディゾルブでつなぐときのハンドル）。

切り替えの種類（show.json の transitions と sections[].in）
  cut      : 拍の cut_offset フレーム前で切る
  dissolve : 拍を中央にクロスディゾルブ（dissolve_long 28 / dissolve_short 7 フレーム）
  shake    : 拍ちょうどで切り、前後をキーフレームで揺らす（shake_steps.py の値）
  flash    : 拍の1フレーム前で切り、白の頂点を拍に置く
使い方: build_timeline.py [--show data/show.json] [--selection data/selection.csv] [--out data/timeline.json]
"""
import argparse, csv, json, math, sys
from pathlib import Path

from PIL import Image, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shake_steps import IN as SHAKE_IN, OUT as SHAKE_OUT

LONG, SHORT = 28, 7
PRE = 14
ZOOM_PER_SEC, ZOOM_MAX = 0.02, 0.10
PAN_SCALE, PAN_PX_PER_SEC = 1.08, 40
PUNCH = 1.15
TONE_EV_MIN, TONE_EV_MAX = 0.3, 0.7  # 露出の補正: 中央値から 0.3 段以上外れたら、差の 7 割を戻す（最大 0.7 段）
TONE_WARM_MIN, TONE_TEMP_MAX = 25, 15  # 色み（R−B）が 25 以上外れたら色温度で寄せる（最大 ±15）
CROP_MAX_ZOOM = 2.4  # 3840px の写真を 2.4倍に寄せると、元の画素の 1.2倍（わずかにぼける程度）
W, H = 1920, 1080
FPS = 30


class Grid:
    def __init__(self, beats):
        self.beats = beats

    def frame(self, bar):
        k = round((bar - 1) * 4)
        return self.beats[k]["frame"]


def kb_keys(kb, f0, f1, crop=None):
    """Ken Burns のキーフレーム。f0〜f1 は見えている範囲（ディゾルブの重なりを含む）。値は基準（画面を埋める大きさ）に対する倍率と位置"""
    dur = (f1 - f0) / FPS
    z = min(ZOOM_PER_SEC * dur, ZOOM_MAX)
    cx, cy, k = W / 2, H / 2, 1.0
    if crop:
        k, cx, cy = crop["zoom"], crop["x"], crop["y"]
    if kb == "in":
        return {"scale": [(f0, k), (f1, k * (1 + z))], "position": [(f0, [cx, cy]), (f1, [cx, cy])]}
    if kb == "out":
        return {"scale": [(f0, k * (1 + z)), (f1, k)], "position": [(f0, [cx, cy]), (f1, [cx, cy])]}
    room = (W * PAN_SCALE * k - W) / 2 * 0.9
    d = min(PAN_PX_PER_SEC * dur, room) / 2
    sign = 1 if kb == "lr" else -1  # lr: 画面が左から右へ流れる（写真は右から左へ動く）
    return {"scale": [(f0, PAN_SCALE * k), (f1, PAN_SCALE * k)],
            "position": [(f0, [cx + sign * d, cy]), (f1, [cx - sign * d, cy])]}


def value_at(keys, f):
    for (a, va), (b, vb) in zip(keys, keys[1:]):
        if a <= f <= b:
            u = (f - a) / (b - a) if b > a else 0
            if isinstance(va, list):
                return [x + (y - x) * u for x, y in zip(va, vb)]
            return va + (vb - va) * u
    return keys[0][1] if f < keys[0][0] else keys[-1][1]


def add_shake(clip, cut, rows, side):
    """shake_steps.py の表（フレームのずれ, x, y, 回転, 拡大の上乗せ%, ブラー, 向き）を Ken Burns の値に重ねる"""
    for d, x, y, rot, ds, blur, ang in rows:
        f = cut + d
        base_s = value_at(clip["keys"]["scale"], f)
        base_p = value_at(clip["keys"]["position"], f)
        clip["keys"]["scale"].append((f, base_s * (1 + ds / 100)))
        clip["keys"]["position"].append((f, [base_p[0] + x * base_s, base_p[1] + y * base_s]))
        clip["keys"].setdefault("rotation", []).append((f, rot))
        clip["keys"].setdefault("blur_length", []).append((f, blur))
        clip["keys"].setdefault("blur_direction", []).append((f, ang))
    clip["shake"] = clip.get("shake", []) + [side]


def parse_crop(fix):
    for part in fix.split(";"):
        if part.startswith("crop="):
            x0, y0, x1, y1 = map(float, part[5:].split(","))
            return x0, y0, x1, y1
    return None


def crop_to_view(c):
    """切り出し範囲（写真に対する割合）から、倍率と位置を出す。4:3 の写真は倍率1で画面の横幅を埋める"""
    x0, y0, x1, y1 = c
    k = max(min(1 / (x1 - x0), CROP_MAX_ZOOM), 1.0)
    cxn, cyn = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = W * k, W * 3 / 4 * k
    px = W / 2 + (0.5 - cxn) * w
    py = H / 2 + (0.5 - cyn) * h
    # 画面の端が見えないように抑える
    mx, my = (w - W) / 2, (h - H) / 2
    px = min(max(px, W / 2 - mx), W / 2 + mx)
    py = min(max(py, H / 2 - my), H / 2 + my)
    return {"zoom": round(k, 4), "x": round(px, 1), "y": round(py, 1)}


def tone(path):
    im = Image.open(path)
    im.draft("RGB", (320, 240))
    st = ImageStat.Stat(im.convert("RGB").resize((160, 120)))
    r, g_, b = st.mean
    return 0.2126 * r + 0.7152 * g_ + 0.0722 * b, r - b


def match_tone(clips, sections):
    photos = [c for c in clips if c["kind"] == "photo"]
    for c in photos:
        c["tone"] = tone(c["file"])
    for n in sections:
        sc = [c for c in photos if c["section"] == n]
        if len(sc) < 3:
            continue
        ys = sorted(c["tone"][0] for c in sc)
        ws = sorted(c["tone"][1] for c in sc)
        ym, wm = ys[len(ys) // 2], ws[len(ws) // 2]
        for c in sc:
            y, w = c["tone"]
            ev = math.log2(ym / max(y, 1))
            fix = {}
            if abs(ev) > TONE_EV_MIN:
                fix["exposure"] = round(max(-TONE_EV_MAX, min(TONE_EV_MAX, ev * 0.7)), 2)
            dw = wm - w
            if abs(dw) > TONE_WARM_MIN:
                fix["temperature"] = round(max(-TONE_TEMP_MAX, min(TONE_TEMP_MAX, dw * 0.25)), 1)
            if fix:
                c["lumetri"] = fix
        for c in sc:
            c.pop("tone", None)


def main():
    global W, H, FPS
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", default="data/show.json")
    ap.add_argument("--selection", default="data/selection.csv")
    ap.add_argument("--beats", default="data/beats.json")
    ap.add_argument("--hits", default="data/hits.json")
    ap.add_argument("--out", default="data/timeline.json")
    args = ap.parse_args()
    show = json.loads(Path(args.show).read_text())
    W, H, FPS = show["project"]["width"], show["project"]["height"], show["project"]["fps"]
    info = json.loads(Path(args.beats).read_text())
    g = Grid(info["beats"])
    rows = list(csv.DictReader(open(args.selection)))
    total = round(info["duration"] * FPS)
    cut_offset = show.get("cut_offset", -1)
    handle = int(round(info["bar_period"] * FPS))  # EffectCraft のコンポの前の余白（1小節）
    gfx_cfg = show.get("graphics", {})

    SECTIONS = [s["name"] for s in show["sections"]]
    boundary = {s["name"]: s["in"] for s in show["sections"]}
    sec_bar = {s["name"]: s["start_bar"] for s in show["sections"]}
    sec_start = {n: (0 if i == 0 else g.frame(sec_bar[n])) for i, n in enumerate(SECTIONS)}
    sec_end = {n: (sec_start[SECTIONS[i + 1]] if i + 1 < len(SECTIONS) else total) for i, n in enumerate(SECTIONS)}

    tr = show.get("transitions", {})
    shake_bars = set(tr.get("shake", []))
    flash_bars = set(tr.get("flash", []))
    in_transition = {}
    for b in tr.get("dissolve_long", []):
        in_transition[b] = ("dissolve", LONG)
    for b in tr.get("dissolve_short", []):
        in_transition[b] = ("dissolve", SHORT)
    overrides = {o["bar"]: o for o in show.get("kb_overrides", [])}

    # V1 のスロット（写真・動画）。生成画像の背景も V1 に置く
    slots = []
    for bg in show.get("backgrounds", []):
        slots.append({"section": bg["section"], "bar": bg["bar"], "bars": bg["bars"], "kind": "image", "id": bg["id"],
                      "file": bg["file"], "kb": "in", "punch_in": "", "fix": "", "note": "", "_bg": bg})
    for r in rows:
        if r["kind"] in ("photo", "video"):
            slots.append({**r, "bar": float(r["bar"]), "bars": float(r["bars"])})
    slots.sort(key=lambda s: s["bar"])
    clips = []
    for s in slots:
        b0 = s["bar"]
        trans = ("shake", 0) if b0 in shake_bars else in_transition.get(b0, ("cut", 0))
        if b0 in flash_bars:
            trans = ("flash", 0)
        f = g.frame(b0)
        start = f + cut_offset if trans[0] in ("cut", "flash") else f
        c = {"section": s["section"], "bar": b0, "bars": s["bars"], "kind": s["kind"], "id": s["id"],
             "file": s["file"], "kb": s["kb"], "punch_in": s["punch_in"], "fix": s["fix"], "note": s.get("note", ""),
             "start": start, "in": {"type": trans[0], "frames": trans[1]}, "track": "V1",
             "source_in": float(s["note"].split("source_in=")[1].split("s")[0]) if s["kind"] == "video" else 0.0,
             "portrait": "縦向き" in s.get("note", "")}
        if "_bg" in s:
            c["_bg"] = s["_bg"]
        clips.append(c)
    # 終わりは次のクリップの始まり。コラージュ・グリッドの区間は V2 が覆うので V1 は空ける
    covers = [(g.frame(c["bar"]) - 1, g.frame(c["bar"] + 2)) for c in gfx_cfg.get("collages", [])]
    grid = gfx_cfg.get("grid")
    if grid:
        covers.append((g.frame(grid["start_bar"]) - 1, g.frame(grid["end_bar"]) - PRE))
    for k, c in enumerate(clips):
        nxt = clips[k + 1]["start"] if k + 1 < len(clips) else total
        own_end = g.frame(c["bar"] + c["bars"]) + (cut_offset if c["bar"] + c["bars"] not in shake_bars else 0)
        end = nxt
        for a, b in covers:
            if c["start"] < a <= nxt:
                end = a
        bg = c.get("_bg")
        if bg and bg.get("start_at_zero"):
            end = g.frame(c["bar"] + c["bars"])
            c["start"] = 0
        c["end"] = min(end, max(own_end, end)) if c["kind"] != "image" else end
    # グリッドの下で始まるクリップ（グリッドが溶けて見える）
    for c in clips:
        o = overrides.get(c["bar"])
        if o and o.get("start_early"):
            c["start"] = g.frame(c["bar"]) - PRE
            c["in"] = {"type": "cut", "frames": 0}

    # 区間どうしをディゾルブでつなぐところは、区間シーケンスの中で前後に PRE フレームずつ絵を延ばす
    for n in SECTIONS:
        sc = [c for c in clips if c["section"] == n]
        if boundary.get(n) == "dissolve":
            sc[0]["start"] = sec_start[n] - PRE
            sc[0]["in"] = {"type": "section", "frames": LONG}
        i = SECTIONS.index(n)
        if i + 1 < len(SECTIONS) and boundary.get(SECTIONS[i + 1]) == "dissolve":
            sc[-1]["end"] = sec_end[n] + PRE

    # Ken Burns（見えている範囲 = ディゾルブの半分を前後に足す）
    for k, c in enumerate(clips):
        half_in = c["in"]["frames"] // 2 + 1 if c["in"]["type"] == "dissolve" else 0
        nxt = clips[k + 1] if k + 1 < len(clips) else None
        half_out = nxt["in"]["frames"] // 2 + 1 if nxt and nxt["in"]["type"] == "dissolve" and nxt["start"] == c["end"] else 0
        vis0, vis1 = c["start"] - half_in, c["end"] + half_out
        crop = None
        cr = parse_crop(c["fix"])
        if cr:
            crop = crop_to_view(cr)
            c["crop"] = crop
        if c["kind"] == "video":
            c["keys"] = {"scale": [(vis0, 1.0), (vis1, 1.0)], "position": [(vis0, [W / 2, H / 2]), (vis1, [W / 2, H / 2])]}
        else:
            c["keys"] = kb_keys(c["kb"] or "in", vis0, vis1, crop)
        o = overrides.get(c["bar"])
        if o and "scale" in o:  # マッチディゾルブなど、動きを直接指定する
            pos = o.get("position", [[W / 2, H / 2], [W / 2, H / 2]])
            c["keys"] = {"scale": [(vis0, o["scale"][0]), (vis1, o["scale"][1])],
                         "position": [(vis0, list(pos[0])), (vis1, list(pos[1]))]}
        c["visible"] = [vis0, vis1]
        if c["punch_in"]:
            fp = g.frame(c["bar"] + (int(c["punch_in"]) - 1) / 4)
            s0 = value_at(c["keys"]["scale"], fp - 1)
            s1 = value_at(c["keys"]["scale"], vis1)
            c["keys"]["scale"] = [kv for kv in c["keys"]["scale"] if kv[0] < fp - 1] + [(fp - 1, s0), (fp, s0 * PUNCH), (vis1, s1 * PUNCH)]
            c["punch_frame"] = fp
        bg = c.get("_bg")
        if bg and bg.get("fade_in_bars"):
            a, b = bg["fade_in_bars"]
            c["keys"]["opacity"] = [(g.frame(a), 0.0), (g.frame(b), 100.0)]
    # 区間の中で明るさ（Y の平均）と色み（R−B）が大きく外れた写真だけを、区間の中央値に寄せる
    match_tone(clips, SECTIONS)

    # シェイク
    for k, c in enumerate(clips):
        if c["in"]["type"] != "shake":
            continue
        cut = c["start"]
        prev = clips[k - 1] if k else None
        if prev and prev["end"] == cut:
            add_shake(prev, cut, SHAKE_OUT, "out")
        add_shake(c, cut, SHAKE_IN, "in")
    for c in clips:
        for p in c["keys"]:
            c["keys"][p] = sorted({f: v for f, v in c["keys"][p]}.items())
        c.pop("note", None)
        c.pop("_bg", None)

    # 縦向きの動画の背景（ぼかし）
    extra = []
    for c in clips:
        if c["portrait"]:
            bg = {**c, "track": "V1", "role": "portrait_bg", "keys": {"scale": [(c["visible"][0], 1.0), (c["visible"][1], 1.0)],
                  "position": [(c["visible"][0], [W / 2, H / 2]), (c["visible"][1], [W / 2, H / 2])]}}
            c["track"] = "V2"
            c["role"] = "portrait_fg"
            extra.append(bg)
    clips += extra

    # マスターの上のトラック（EffectCraft の .mov、白フラッシュ、光漏れ、黒）
    def gfx(name, track, bar0, bar1, start_off=0, extra_opts=None):
        d = {"track": track, "file": f"work/graphics/{name}.mov", "name": name, "start": g.frame(bar0) + start_off,
             "end": g.frame(bar1) + start_off, "source_in": handle}
        d.update(extra_opts or {})
        return d
    overlays = [gfx(t["name"], "V3", t["bar"], t["bar"] + t["bars"]) for t in gfx_cfg.get("titles", [])]
    overlays += [gfx(c["name"], "V3", c["bar"], c["bar"] + 2) for c in gfx_cfg.get("chapters", [])]
    for c in gfx_cfg.get("collages", []):
        o = gfx(c["name"], "V2", c["bar"], c["bar"] + 2, cut_offset)
        o["end"] = g.frame(c["bar"] + 2)
        o["source_in"] = handle - 1
        overlays.append(o)
    # 光漏れは文字の下（V2）に置く。上に重ねると、暗い色の文字が Screen で明るく抜けて読めなくなる
    overlays += [gfx(l["name"], "V2", l["bar"], l["bar"] + 2, 0, {"blend": "Screen"}) for l in gfx_cfg.get("leaks", [])]
    overlays.sort(key=lambda o: (o["track"] != "V3", o["track"], o["start"]))
    if grid:
        gstart = g.frame(grid["start_bar"]) - 1
        done = int(round((1 + grid["done_bar"] - grid["start_bar"]) * info["bar_period"] * FPS))  # GRID.mov で最後の1枚が入るフレーム
        fe = g.frame(grid["end_bar"])
        overlays.append({"track": "V2", "file": "work/graphics/GRID.mov", "name": "GRID", "start": gstart,
                         "end": fe + PRE, "source_in": gstart - (g.frame(grid["done_bar"]) - done),
                         "keys": {"opacity": [(fe - PRE, 100.0), (fe + PRE, 0.0)]}})
    # V8: レビュー用の焼き込み。本番の書き出しでは apply_timeline.py --no-burnin で外す
    overlays.append({"track": "V8", "file": "work/graphics/BURNIN.mov", "name": "BURNIN", "start": 0, "end": total,
                     "source_in": 0, "review_only": True})
    for b in sorted(flash_bars):
        f = g.frame(b)
        overlays.append({"track": "V4", "matte": "#ffffff", "name": f"WHITE_FLASH_{b}" if len(flash_bars) > 1 else "WHITE_FLASH",
                         "start": f - 4, "end": f + 9, "keys": {"opacity": [(f - 4, 0.0), (f, 60.0), (f + 8, 0.0)]}})
    fend = g.frame(show["end_black_bar"]) if show.get("end_black_bar") else total - 6
    overlays.append({"track": "V4", "matte": "#000000", "name": "END_BLACK", "start": fend - 3, "end": total,
                     "keys": {"opacity": [(fend - 3, 0.0), (fend + 3, 100.0)]}})

    # 調整レイヤー（V5: 区間ごと、V6: 全体のルックとビネット、V7: グレイン）
    looks = show.get("looks", {})
    adjust = []
    for lk in looks.get("sections", []):
        a, fb = lk["from_bar"], lk.get("fade_bars", 1)
        keys = [(g.frame(a), 0.0), (g.frame(a + fb), 100.0)]
        end = total
        if lk.get("to_bar"):
            z = lk["to_bar"]
            end = g.frame(z)
            keys += [(g.frame(z - fb), 100.0), (g.frame(z), 0.0)]
        adjust.append({"track": "V5", "name": lk["name"], "start": g.frame(a), "end": end,
                       "effects": {"lumetri": lk["lumetri"]}, "keys": {"opacity": keys}})
    if looks.get("global"):
        adjust.append({"track": "V6", "name": "LOOK_ALL", "start": 0, "end": total, "effects": looks["global"]})
    if looks.get("grain"):
        adjust.append({"track": "V7", "name": "GRAIN", "start": 0, "end": total, "effects": {"noise": {"amount": looks["grain"]}}})

    hits = json.loads(Path(args.hits).read_text())["hits"] if Path(args.hits).exists() else []
    markers = [{"frame": sec_start[n], "name": f"{n} 小節{sec_bar[n]}", "color": "blue"} for n in SECTIONS]
    markers += [{"frame": g.frame(b), "name": f"サビの頭 小節{b}", "color": "red"} for b in show.get("chorus_bars", [])]
    if grid:
        markers.append({"frame": g.frame(grid["done_bar"]), "name": f"グリッド完成 小節{grid['done_bar']}", "color": "green"})
    if show.get("end_black_bar"):
        markers.append({"frame": fend, "name": f"音が切れる 小節{show['end_black_bar']}", "color": "green"})
    markers += [{"frame": h["frame"], "name": f"キメ {h['kind']} 小節{h['bar']}.{h['beat']}", "color": "yellow"}
                for h in hits if h["status"] == "confirmed"]

    sections = []
    for n in SECTIONS:
        origin = max(0, sec_start[n] - PRE)
        sections.append({"name": n, "start": sec_start[n], "end": sec_end[n], "origin": origin, "in": boundary.get(n, "cut")})
    m = show["music"]
    gain = m.get("gain_db", 0.0)
    fi, fo = round(m.get("fade_in_sec", 0.5) * FPS), round(m.get("fade_out_sec", 0.3) * FPS)
    out = {"fps": FPS, "width": W, "height": H, "total_frames": total, "cut_offset": cut_offset, "pre": PRE,
           "sections": sections, "clips": clips, "overlays": overlays, "adjust": adjust, "markers": markers,
           "audio": {"file": m["file"], "gain_db": gain,
                     "keys": [(0, -60.0), (fi, gain), (total - fo, gain), (total, -60.0)]}}
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1))

    # 検査: 重なり、長さ0、スロットの隙間
    bad = 0
    for n in SECTIONS:
        v1 = sorted([c for c in clips if c["section"] == n and c["track"] == "V1" and c.get("role") != "portrait_bg"],
                    key=lambda c: c["start"])
        for a, b in zip(v1, v1[1:]):
            if a["end"] > b["start"]:
                print("重なり", a["id"], b["id"], a["end"], b["start"])
                bad += 1
    for c in clips:
        if c["end"] <= c["start"]:
            print("長さ0", c["id"])
            bad += 1
    seq = sorted([(float(r["bar"]), float(r["bars"]), r["id"]) for r in rows if r["kind"] != "grid"])
    seq += [(bg["bar"], bg["bars"], bg["id"]) for bg in show.get("backgrounds", [])]
    if grid:
        seq.append((grid["start_bar"], grid["end_bar"] - grid["start_bar"], "GRID"))
    seq.sort()
    for (b0, n0, i0), (b1, _, i1) in zip(seq, seq[1:]):
        if abs(b0 + n0 - b1) > 1e-6:
            print(f"隙間・重なり（selection.csv）: {i0} 小節{b0}+{n0} → {i1} 小節{b1}")
            bad += 1
    print(f"clips {len(clips)} overlays {len(overlays)} adjust {len(adjust)} markers {len(markers)} problems {bad}")
    for s in sections:
        print(f"  {s['name']:4s} {s['start']:5d}-{s['end']:5d} origin {s['origin']} in={s['in']}")


if __name__ == "__main__":
    main()
