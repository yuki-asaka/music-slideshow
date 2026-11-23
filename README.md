# music-slideshow

曲と写真から、拍に合わせたスライドショー動画を作る Claude Code のスキルです。
曲の解析（テンポ・小節・サビの位置）→ シナリオ設計 → 写真の選定 → 演出の選定 → タイムラインの自動生成 → FilmCraft・EffectCraft での組み立て → レビュー → 書き出しまでを、仕様書と承認ゲートを踏んで進めます。

## 使い方

`~/.claude/skills/music-slideshow` に置くと、Claude Code が「写真と曲でスライドショーを作りたい」といった依頼で読み込みます。流れは `SKILL.md`、詳細は `references/` を参照してください。

案件ごとの値は `data/show.json`（ひな形は `assets/show.example.json`、行事名などは架空の例）と `data/selection.csv` に書き、`scripts/` はそのまま使います。

## 必要なもの

- macOS（sips、ヒラギノフォント）、Python 3、Pillow、ffmpeg・ffprobe
- librosa（曲の解析）
- FilmCraft（`filmcraft-cli`）と EffectCraft の MCP

## ffmpeg・ffprobe の使いどころ

動画の書き出し・編集はすべて FilmCraft（`filmcraft-cli`）が行います。ffmpeg・ffprobe は計測と確認の補助にだけ使います。

| スクリプト | ツール | 用途 |
|---|---|---|
| `analyze_music.py` | ffmpeg（`ebur128` フィルタ） | 曲の音量（LUFS）を測る。この値から −14 LUFS 前後になるように音量の調整（`gain_db`）を決める |
| `export.py` | ffprobe | 書き出した動画の長さ・解像度・形式を確かめる |
| `export.py` | ffmpeg（`ebur128`） | 書き出した動画の音量とピークを測る |
| `list_clips.py` | ffprobe | 写真フォルダ内の動画の長さ・解像度を一覧にする |
| `preview_selection.py` | ffmpeg | 選定の一覧画像に使うため、動画から1コマ取り出す |

## テスト

`tests/` に pytest のテストがあります。曲・写真・行事はすべてテストの中で合成したもので、実案件の素材は使いません。GitHub Actions で push のたびに実行します。

```sh
pip install -r requirements-test.txt
pytest -q tests
```

| ファイル | 確かめること |
|---|---|
| `test_analyze_music.py` | 粗いテンポのヒントから正しいテンポを見つける、外れ値（半拍ずれ）を除いて格子を当てはめる、曲の終わりでも1フレーム以内。合成したクリック音で `analyze_music.py` を通しで動かし、`downbeat_offset_beats` で小節の頭が合うこと（ffmpeg が必要） |
| `test_build_timeline.py` | 架空の3区間・12小節で、カットが拍の1フレーム前、ディゾルブの中央・白フラッシュの頂点・シェイクが拍ちょうど、区間ディゾルブのハンドル、暗い写真の露出補正、selection.csv の隙間・重なりの検出、切り出しの倍率の上限、Ken Burns の動き |
| `test_shake_steps.py` | シェイクのキーフレームの時刻と値、前後が静止していること |
| `test_check_cuts.py` | 拍に合ったカットは通り、ずれたカットは終了コード 1 になること（マスターと区間シーケンスの両方） |

FilmCraft・EffectCraft を動かす部分（`apply_timeline.py`・`make_graphics.js`・`export.py`・`graphics_plan.py` の出力を使った書き出し）はテストできません。実案件では `check_cuts.py` とフレームの一覧（`export.py frames`）で確かめます。

## 注意

写真・曲などの素材はこのリポジトリに含みません。写真を外部サービスに送らない運用を前提にしています。
