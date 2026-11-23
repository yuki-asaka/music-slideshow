#!/usr/bin/env python3
"""show.json の graphics と beats.json から、EffectCraft 用の設定 project/graphics_plan.js と、書き出しの手順 work/graphics/render_steps.json を作る。

EffectCraft の run_script は、スクリプト自身のフォルダか .ecproj のあるフォルダのファイルしか $.evalFile できない。
そこで設定（graphics_plan.js: var PLAN = {...}）と make_graphics.js（スキルからコピー）を .ecproj のフォルダ（既定 project/）に置く。
render_steps.json は MCP の command_batch にそのまま渡す steps で、
buildAll() がレンダーキューに積む順番（タイトル → 章 → コラージュ → グリッド → 光漏れ → 焼き込み）に合わせてある。
文字を含むコンポは ProRes 4444 の RGBA（straight）、グリッドと光漏れは RGB で書き出す。
使い方: graphics_plan.py [--show data/show.json] [--beats data/beats.json] [--only CH7,CH8,GRID]
  --only を付けたら、run_script でも buildAll(["CH7","CH8","GRID"]) と同じ名前を渡す（順番がずれないように）
"""
import argparse, json, shutil
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", default="data/show.json")
    ap.add_argument("--beats", default="data/beats.json")
    ap.add_argument("--only")
    ap.add_argument("--ecproj-dir", default="project", help="EffectCraft のプロジェクト（.ecproj）を置くフォルダ")
    args = ap.parse_args()
    show = json.loads(Path(args.show).read_text())
    info = json.loads(Path(args.beats).read_text())
    g = show.get("graphics", {})
    root = str(Path.cwd())
    plan = {
        "root": root, "width": show["project"]["width"], "height": show["project"]["height"], "fps": show["project"]["fps"],
        "bar_period": info["bar_period"], "first_beat": info["first_beat"], "duration": round(info["duration"], 3),
        "fonts": g.get("fonts", {"title": "HiraMinProN-W6", "chapter": "HiraMaruProN-W4"}),
        "title_ink": g.get("title_ink", [78, 42, 26]), "title_glow": g.get("title_glow", [255, 246, 232]),
        "titles": g.get("titles", []), "chapters": g.get("chapters", []), "collages": g.get("collages", []),
        "leaks": g.get("leaks", []), "grid": g.get("grid"),
        "sections": [[s["start_bar"], s["name"]] for s in show["sections"]],
    }
    out = Path("work/graphics")
    out.mkdir(parents=True, exist_ok=True)
    ec = Path(args.ecproj_dir)
    ec.mkdir(parents=True, exist_ok=True)
    (ec / "graphics_plan.js").write_text("var PLAN = " + json.dumps(plan, ensure_ascii=False, indent=1) + ";\n")
    shutil.copy(Path(__file__).resolve().parent / "make_graphics.js", ec / "make_graphics.js")

    order = [(t["name"], "rgba") for t in plan["titles"]] + [(c["name"], "rgba") for c in plan["chapters"]]
    order += [(c["name"], "rgba") for c in plan["collages"]]
    if plan["grid"]:
        order.append(("GRID", "rgb"))
    order += [(l["name"], "rgb") for l in plan["leaks"]]
    order.append(("BURNIN", "rgba"))
    if args.only:
        want = args.only.split(",")
        order = [o for o in order if o[0] in want]
    steps = []
    for i, (name, ch) in enumerate(order):
        p = {"index": i + 1, "format": "prores", "proresProfile": "4444", "channels": ch, "audio": "off",
             "output": f"{root}/work/graphics/{name}.mov"}
        if ch == "rgba":
            p["color"] = "straight"
        steps.append({"id": "renderQueue.setOutputModule", "params": p})
    steps.append({"id": "renderQueue.render", "params": {"wait": True}})
    (out / "render_steps.json").write_text(json.dumps(steps, ensure_ascii=False, indent=1))
    names = [o[0] for o in order]
    print(f"{ec}/graphics_plan.js, {ec}/make_graphics.js, work/graphics/render_steps.json（{len(names)} コンポ: {', '.join(names)}）")
    print("run_script のコード:")
    print(f'  $.evalFile(new File("{ec.resolve()}/graphics_plan.js"));')
    print(f'  $.evalFile(new File("{ec.resolve()}/make_graphics.js"));')
    print(f"  buildAll({json.dumps(names, ensure_ascii=False) if args.only else ''});")


if __name__ == "__main__":
    main()
