# FilmCraft・EffectCraft・PhotoCraft の注意点

slide-show2 の検証（T-1.x）と制作で分かったこと。新しい案件でも同じところでつまずくので、先に読んでおく。

## FilmCraft（filmcraft-cli run / MCP）

- **時間は ticks**（1秒 = 254016000000。30fps の1フレーム = 8467200000）。`frame` や `seconds` を受け付けるコマンドもある
- **`file.exportFrame` は `"sequence": <id>, "time": <ticks>` で指定する**。`frame` を渡すと無視されて黒いコマになる
- ヘッドレス（`filmcraft-cli run <jsonl>`）は1行1コマンド。結果は1行ずつ JSON で返る。前の段階の ID を次に渡すため、`apply_timeline.py` は3段階（作成・配置・効果）に分けて実行する
- `timeline.place {item, track, frame, duration:{frame}, insert:false}` でフレーム単位に置ける。静止画はヘッドレスでは原寸で置かれるので、`clip.fillFrame` で画面を埋める大きさにそろえ、その倍率を Ken Burns の基準にする
- キーフレーム: `effects.setParam` の `time` は**タイムライン上の時刻**、`effects.setInterpolation` の `keyframes[].time` は**クリップ内の時刻**（mediaTime）。取り違えると補間がかからない
- ディゾルブの重なりの後半はクリップの終わりの外になる。Ken Burns のキーフレームをディゾルブの終わりまで打たないと、そこで動きが止まる（キーフレームはクリップの外にも置ける）
- `sequence.applyVideoTransition {clip:<前のクリップ>, effect:"cross_dissolve", frames, edge:"out", align:"center"}` でカットを中央にしたディゾルブ
- **合成は線形光**。不透明度 85% の白は見た目で約95%の明るさになる（85% に見せたければ約60%）。Screen 合成の光漏れを暗い文字の上に重ねると、文字が明るく抜けてコントラストが 2:1 程度まで落ちる → 光漏れは文字の下に置く
- 標準の Earthquake トランジションは、前の写真しか揺れず、切り替えが2フレームのディゾルブになり、拍から約1.5フレーム遅れる → motion のキーフレームと Directional Blur で作る（`shake_steps.py` の表）
- 調整レイヤー（`file.newAdjustmentLayer`）に `lumetri`・`vignette`・`noise` をかけられる。書き出し時間は約2倍になる
- シーケンスのネスト: `timeline.place {item:<シーケンスの item>}` で中の効果ごと置ける。区間ごとのシーケンスをマスターに並べる
- 書き出し: `file.exportMedia`。H.264 High・VBR 2パス・20Mbps で全編3分なら約15分、ProRes 422 で約7分。**VBR の最大ビットレートは指定できない**（平均のみ）
- `filmcraft-cli run` が長くかかるときは、Bash の `run_in_background` で走らせ、終わりの通知を待つ（10分の制限に当たる）

## EffectCraft（MCP の run_script・command_batch）

- `run_script` は After Effects 形式の JavaScript（ExtendScript・ES3）。`let`・アロー関数・JSON は使わない
- **`$.evalFile` で読めるのは、スクリプト自身のフォルダか .ecproj のあるフォルダのファイルだけ**（それ以外は "scripts can only load files from their own or the project's folder"）。`graphics_plan.py` が `make_graphics.js` と設定を .ecproj のフォルダ（`project/`）にコピーするのはこのため
- 新しい案件では、最初に EffectCraft で空のプロジェクトを `project/graphics.ecproj` として保存してから `run_script` を使う
- フォント: `list_fonts` で PostScript 名を確かめる（ヒラギノ明朝 ProN W3/W6 = `HiraMinProN-W3/W6`、ヒラギノ丸ゴ ProN W4 = `HiraMaruProN-W4`）
- アルファ付きの書き出し: `renderQueue.setOutputModule {format:"prores", proresProfile:"4444", channels:"rgba", color:"straight"}` → `renderQueue.render {wait:true}`。FilmCraft に置くと透けて重なる
- キーフレームはフレームに丸められる（小節の頭との差は1フレーム未満）
- 原寸の写真を48枚並べると書き出しに160秒以上かかる。グリッドには縮小版（`prep_graphics.py`）を使う
- 書き出す前に `render_frame`（`inline:true`、`max_side:960`）で1コマ見て、文字の位置と読みやすさを確かめる
- 作り直したら `save_project` で .ecproj を保存する

## PhotoCraft

- 起動時の読み書き先（`--automation-read-root`）が別のフォルダに固定されていると、このプロジェクトの写真を開けない（`automation path rejected`）。**生徒の写真を別のフォルダにコピーしてまで使わない**。写真の補正は FilmCraft のクリップ上で行う

## 写真・動画の前処理

- HEIC は sips で JPG に変換する（`convert_photos.py`）。**sips の変換では HEIC の回転が画素に反映されず、EXIF の向きだけが残ることがある** → `fix_orientation.py` で画素を回転させる。縦向きの写真が横向きとして扱われる原因になる
- 同じ名前の HEIC と JPG があるので、元の拡張子を名前に残す（`IMG_3488_heic.jpg`）
- 動画は `list_clips.py` で解像度・fps・向き・長さを一覧にする。29.97fps 前後の素材は 30fps のシーケンスで問題なく使える
- 既存の編集版（`movies/full.mp4` など）は、写真の連続と文字の焼き込みでできていて、素材にならない

## 曲の解析（librosa）

- 曲全体に一度 `beat_track` をかけると途中で止まることがある（144.7秒で止まった例）。拍の時刻も約23ms 刻みに量子化される → 約40秒ごとに拍検出し、全体に等間隔の格子を当てはめる（`analyze_music.py`）
- 拍の間隔の中央値からテンポを出すと、量子化のせいで遅めに出る（130 → 129.2 BPM と誤った例。曲の終わりで半小節ずれる）
- librosa は小節の頭（ダウンビート）を判別しない。1拍目は耳で確かめる
- librosa は Python の仮想環境に入れておく（`python -m venv .venv && .venv/bin/pip install librosa`）。解析のスクリプトだけその Python で実行する
