---
name: music-slideshow
description: 曲と写真（行事・旅行・卒業・謝恩会・結婚式など）から、拍に合わせたスライドショー動画を FilmCraft・EffectCraft で作る一連の流れ。曲の解析（テンポ・小節・サビの位置）→ 内容に合ったシナリオ設計 → 写真の選定 → 演出の選定（Ken Burns・ディゾルブ・白フラッシュ・シェイク・章タイトル・コラージュ・グリッド）→ タイムラインの自動生成と組み立て → レビュー → 書き出しまで、仕様書と承認ゲートを踏んで進める。「写真と曲でスライドショーを作りたい」「思い出のムービー」「卒業ムービー」「振り返り動画」「音ハメ」「BGM に合わせて写真を切り替えたい」と言われたら、ツール名が出ていなくても使う。既存のスライドショーに行事を足す・曲を替える・写真を差し替えるときにも使う。
---

# 曲と写真のスライドショー

曲の構成（溜めて放つ）と写真の物語（時系列・行事の盛り上がり・人）を重ね、切り替えを拍に合わせた動画を作る。
曲や案件に固有の値は `data/show.json` と `data/selection.csv` に書き、スクリプトは書き換えずに使う。

このスキルのフォルダを `SKILL_DIR` と書く（`~/.claude/skills/music-slideshow`）。スクリプトは `SKILL_DIR/scripts/`。

## 大事にすること

- **依頼者の思い出の動画である**。物語の軸・コピー・先生の名前・曲の構成は、推測で決めずに確かめる。段階ごとに文書を出して承認を得てから進む（`references/process.md`）
- **写真は外部に出さない**。生徒・家族の写真を画像生成 AI などの外部サービスに送らない。生成画像（背景）は人物を含めずに作る
- **拍は実測の格子だけを正とする**。カットは拍の1フレーム前、白フラッシュの頂点とシェイクは拍ちょうど。受け入れの目安は「切り替えの 90% 以上が ±2 フレーム以内」（実績は 100% が ±1 フレーム）
- **写真に語らせる**。文字は最小限、サビの頭に文字を置かない、強い演出は回数を絞る
- **作り直せる形で残す**。手で FilmCraft を触らず、`show.json`・`selection.csv` を直してスクリプトで組み直す

## 前提

- macOS（写真の変換に sips、フォントにヒラギノ）、Python 3 と Pillow、ffmpeg・ffprobe
- librosa（曲の解析だけ。仮想環境に入れて、その Python で `analyze_music.py`・`find_hits.py` を実行する）
- `filmcraft-cli`（ヘッドレスの FilmCraft）と EffectCraft の MCP（`run_script`・`command_batch`・`render_frame`・`save_project`）
- 作業はプロジェクトのルート（`data/`・`work/`・`project/`・`specs/`・`output/` を置くフォルダ）で行う。スクリプトは相対パスをそこから解決する

```
assets/          曲（assets/bpm/）、生成画像（assets/generated/G-01.jpg …）
data/            show.json, selection.csv, beats.json, hits.json, photos.csv, photo_stats.csv, clips.csv, timeline.json
project/         slideshow.fcproj（FilmCraft）, graphics.ecproj（EffectCraft）, make_graphics.js と graphics_plan.js（コピー）
work/            photos/（変換済み）, sheets/, graphics/（.mov と素材）, timeline/, review/, song_map.md
specs/           requirements.md, design.md, task.md, review-log.md, acceptance.md
output/          review_vN.mp4, preview_1080p.mp4, 納品物
```

## 流れ

### 0. 準備（聞き取りの前にできること）

1. 素材を見る: 写真のフォルダ（行事ごとの枚数）、動画、曲。`SKILL_DIR/assets/show.example.json` を `data/show.json` にコピーし、`project`・`photos`・`music.file` を書く（ほかの項目は後で）
2. 写真: `convert_photos.py` → `fix_orientation.py work/photos` → `make_sheets.py`。動画: `list_clips.py`
3. 曲: `analyze_music.py`（`sections` は空のまま）→ `find_hits.py "<曲>"` → `song_map.py`
4. ここで分かったこと（テンポ・長さ・推定した構成・行事ごとの枚数・使える動画）を、聞き取りの材料にする

### 1. 要求（G1）

目的・視聴者・上映環境・必ず入れる人と場面・文字にしてよい言葉・続編の有無・プライバシーの範囲・コミットの要否を聞き、`specs/requirements.md` に書く。聞きたいことは「質問 / 当方の仮定」の表で一度に出す。

### 2. 設計（G2）— ここがスキルの中心

`references/scenario-design.md` を読んでから進める。

1. 曲の構成を推定し（`work/song_map.md`）、**依頼者に耳で確かめてもらう**（最初の拍が1拍目か、区間の境目、Bメロの頭）。`show.json` の `sections`・`chorus_bars`・`end_black_bar`・`music` を書き、`analyze_music.py` をもう一度実行する
2. 物語の軸（曲のテーマと写真の内容が重なる言葉）を決める
3. 区間に役割を割り当て、テンポの階段を作り、小節単位で割り付ける
4. 演出を選ぶ（`references/effects-catalog.md`）。どこで・なぜ使うかを書く
5. 文字のコピー案、生成画像のプロンプト（人物なし・画風をそろえる）を書く
6. `specs/design.md` にまとめる（ひな形は `references/process.md`）。小節単位の表は、そのまま `show.json` と `selection.csv` に写せる粒度にする

新しい演出やツールの使い方を試すときは、実装の前に小さく検証する（`references/tool-notes.md` に既知の落とし穴）。

### 3. 選定（G4）

`references/photo-selection.md` を読む。コンタクトシートを Read で見て、`data/selection.csv` を書く（列は `references/show-json.md`）。ID からファイルは `photo_stats.csv` で引く。`preview_selection.py` で一覧画像を作って依頼者に確認してもらう。

### 4. 実装

```sh
python3 SKILL_DIR/scripts/prep_graphics.py            # グリッド・コラージュ・生成画像の素材
python3 SKILL_DIR/scripts/graphics_plan.py            # project/graphics_plan.js, project/make_graphics.js, work/graphics/render_steps.json
```

EffectCraft（最初の1回は空のプロジェクトを `project/graphics.ecproj` として保存しておく）:
1. `run_script` に `graphics_plan.py` が表示したコード（`$.evalFile` ×2 と `buildAll()`）を渡す
2. `render_frame` で章タイトルと文字を1コマずつ見る
3. `command_batch` に `work/graphics/render_steps.json` の中身を steps として渡して書き出す → `save_project`

一部だけ作り直すときは `graphics_plan.py --only CH7,CH8,GRID` とし、`buildAll(["CH7","CH8","GRID"])` に同じ名前を渡す。

```sh
python3 SKILL_DIR/scripts/build_timeline.py           # data/timeline.json（problems 0 になるまで selection.csv を直す）
python3 SKILL_DIR/scripts/apply_timeline.py           # project/slideshow.fcproj（焼き込みあり）
python3 SKILL_DIR/scripts/check_cuts.py project/slideshow.fcproj --timeline data/timeline.json
python3 SKILL_DIR/scripts/export.py frames 12,27,46.5,60 work/review/v1_sheet.jpg   # 気になる小節を Read で見る
python3 SKILL_DIR/scripts/export.py video review output/review_v1.mp4               # run_in_background で
```

### 5. レビュー（G5）

`references/process.md` の「レビューの回し方」。依頼者に出す前に、拍のずれ・フレームの一覧・長さ・音量を自分で確かめる。指摘は review-log.md に記録し、原因を確かめてから直す。似た箇所も確かめて報告する。最後に `apply_timeline.py --no-burnin` → `export.py video screen output/preview_1080p.mp4` で試写版を出す。

### 6. 納品（G6）

`export.py video screen` と `export.py video master` で書き出し、長さ・形式・音量を確かめ、受け入れ基準を `specs/acceptance.md` に1項目ずつ書く。

## スクリプト一覧

| スクリプト | 入力 → 出力 |
|---|---|
| `convert_photos.py` | show.json の photos → `work/photos/`・`data/photos.csv` |
| `fix_orientation.py` | `work/photos/` の EXIF の向きを画素に反映 |
| `make_sheets.py` | → `work/sheets/`・`data/photo_stats.csv`（ID・ブレ・明るさ・向き・似た写真のグループ） |
| `list_clips.py` | → `data/clips.csv` |
| `analyze_music.py` | 曲・show.json → `data/beats.json`（拍・小節・区間・小節ごとの盛り上がり） |
| `find_hits.py` | 曲 → `data/hits.json`（キメの候補。耳で confirmed にする） |
| `song_map.py` | → `work/song_map.md`（シナリオ用の曲の地図） |
| `preview_selection.py` | selection.csv → `work/review/selection_preview_*.jpg` |
| `prep_graphics.py` | → `work/graphics/grid/`・`collage_*/`・`bg/` |
| `graphics_plan.py` | show.json・beats.json → EffectCraft の設定と書き出しの手順 |
| `make_graphics.js` | EffectCraft のコンポを作る関数（graphics_plan.py がコピーする） |
| `build_timeline.py` | show.json・selection.csv・beats.json → `data/timeline.json` |
| `apply_timeline.py` | timeline.json → `project/slideshow.fcproj`（`--no-burnin` で上映用） |
| `check_cuts.py` | 拍とのずれの検査 |
| `export.py` | 動画（review / screen / master）とフレームの一覧 |
| `shake_steps.py` | シェイクの揺れの表（build_timeline.py が使う） |

## 参考資料（必要なときに読む）

- `references/scenario-design.md` — 曲の地図の作り方、区間の役割、テンポの階段、文字、集合写真、行事の追加（設計の前に必ず）
- `references/effects-catalog.md` — 演出ごとの使いどころ・値・実装場所、トラック構成
- `references/show-json.md` — show.json と selection.csv の全項目
- `references/photo-selection.md` — 選定の基準、16:9 の切り出し、プライバシー
- `references/tool-notes.md` — FilmCraft・EffectCraft・librosa の落とし穴（実装・書き出しでつまずいたら）
- `references/process.md` — 段階と承認ゲート、文書のひな形、レビューと試写
- `assets/show.example.json` — 実績のある設定（130BPM・109小節・8行事・3分21秒）
