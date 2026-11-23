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

## 注意

写真・曲などの素材はこのリポジトリに含みません。写真を外部サービスに送らない運用を前提にしています。
