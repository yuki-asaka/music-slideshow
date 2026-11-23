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

## 注意

写真・曲などの素材はこのリポジトリに含みません。写真を外部サービスに送らない運用を前提にしています。
