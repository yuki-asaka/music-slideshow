#!/usr/bin/env python3
"""FilmCraft のプロジェクトから、動画（レビュー版・上映版・マスター）か、確認用のフレームの一覧を書き出す（filmcraft-cli run）。

  export.py video review  output/review_v1.mp4    720p・8Mbps（焼き込みありで組んだプロジェクトから）
  export.py video screen  output/xxx.mp4          1080p・H.264 High・VBR 2パス 20Mbps・AAC
  export.py video master  output/xxx_master.mov   ProRes 422・PCM
  export.py frames 14.5,46.5,72.5 work/review/v5_sheet.jpg   小節.拍（.5 = 3拍目）のコマを並べた一覧
書き出したら、長さ・形式・音量（ebur128）を表示する。上映版の全編は 15分ほどかかるので、Bash の run_in_background で走らせる。
マスターシーケンスの item は work/timeline/ids.json（apply_timeline.py が書く）から読む。
使い方: export.py video <review|screen|master> <出力> [--project project/slideshow.fcproj]
        export.py frames <小節の一覧> <一覧の画像> [--project ...] [--beats data/beats.json]
"""
import argparse, json, subprocess, sys
from pathlib import Path

TICKS = 254016000000
PRESETS = {
    "review": {"format": "h264", "width": 1280, "height": 720, "bitrateMode": "vbr1Pass", "bitrateKbps": 8000,
               "audio": True, "audioCodec": "aac"},
    "screen": {"format": "h264", "h264Profile": "high", "width": 1920, "height": 1080, "fps": 30, "bitrateMode": "vbr2Pass",
               "bitrateKbps": 20000, "audio": True, "audioCodec": "aac"},
    "master": {"format": "prores", "proresProfile": "standard", "width": 1920, "height": 1080, "fps": 30, "audio": True,
               "audioCodec": "pcm"},
}


def run(lines, name):
    path = Path("work/timeline") / f"{name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(l, ensure_ascii=False) for l in lines) + "\n")
    p = subprocess.run(["filmcraft-cli", "run", str(path)], capture_output=True, text=True)
    res = [json.loads(l) for l in p.stdout.splitlines() if l.startswith("{")]
    bad = [r for r in res if not r.get("ok")]
    if p.returncode or bad or len(res) != len(lines):
        print(p.stdout[-2000:], p.stderr[-2000:], file=sys.stderr)
        sys.exit(f"{name}: 失敗")
    return res


def opener(project):
    seq = json.loads(Path("work/timeline/ids.json").read_text())["sequences"]["MASTER"]
    return seq, [{"id": "file.open", "params": {"path": str(Path(project).resolve())}}]


def video(args):
    seq, lines = opener(args.project)
    out = str(Path(args.out).resolve())
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    p = {"path": out, **PRESETS[args.kind], "range": "entire", "sequence": seq, "wait": True}
    if args.kind == "screen" and args.width:
        p.update(width=args.width, height=args.height)
    lines += [{"id": "sequence.open", "params": {"item": seq}}, {"id": "file.exportMedia", "params": p}]
    run(lines, f"export_{args.kind}")
    subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                    "stream=codec_name,profile,width,height,r_frame_rate,bit_rate,sample_rate:format=duration,size",
                    "-of", "compact", out])
    e = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", out, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr.splitlines()
    print("\n".join(l.strip() for l in e if l.strip().startswith(("I:", "Peak:"))))


def frames(args):
    from PIL import Image, ImageDraw, ImageFont
    seq, lines = opener(args.project)
    info = json.loads(Path(args.beats).read_text())
    bars = [float(x) for x in args.bars.split(",")]
    tpf = TICKS // info["fps"]
    tmp = Path("work/review/_frames")
    tmp.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, b in enumerate(bars):
        k = (b - 1) * 4  # 拍の番号（小数は拍の途中）
        f = info["beats"][int(k)]["frame"] + round((k - int(k)) * info["beat_period"] * info["fps"])
        p = tmp / f"{i:03d}.png"
        paths.append(p)
        # time は ticks で渡す（frame を渡すと無視されて黒いコマになる）
        lines.append({"id": "file.exportFrame", "params": {"path": str(p.resolve()), "format": "png", "sequence": seq,
                                                           "time": f * tpf}})
    run(lines, "export_frames")
    cols, w, h = 4, 480, 270
    sheet = Image.new("RGB", (cols * w, (h + 26) * ((len(paths) + cols - 1) // cols)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 18)
    except OSError:
        font = ImageFont.load_default()
    for i, (p, b) in enumerate(zip(paths, bars)):
        x, y = (i % cols) * w, (i // cols) * (h + 26)
        sheet.paste(Image.open(p).convert("RGB").resize((w, h)), (x, y))
        d.text((x + 4, y + h + 3), f"bar {b:g}", fill=(255, 220, 0), font=font)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out, quality=85)
    print(f"{args.out}（{len(paths)} コマ。1コマずつは {tmp}/）")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("video")
    v.add_argument("kind", choices=list(PRESETS))
    v.add_argument("out")
    v.add_argument("--project", default="project/slideshow.fcproj")
    v.add_argument("--width", type=int)
    v.add_argument("--height", type=int)
    f = sub.add_parser("frames")
    f.add_argument("bars")
    f.add_argument("out")
    f.add_argument("--project", default="project/slideshow.fcproj")
    f.add_argument("--beats", default="data/beats.json")
    args = ap.parse_args()
    video(args) if args.cmd == "video" else frames(args)


if __name__ == "__main__":
    main()
