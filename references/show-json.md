# data/show.json と data/selection.csv の書き方

曲と案件に固有の値は、すべてこの2つのファイルに書く。スクリプトの中には書かない。
ひな形は `assets/show.example.json`（slide-show2 で実際に使った値。130BPM・109小節・8行事）。

## show.json

小節番号はすべて `data/beats.json` の小節（1始まり）。半小節は `.5`。

| キー | 意味 | 決める時期 |
|---|---|---|
| `project` | `width`・`height`・`fps`（既定 1920×1080・30） | 最初 |
| `photos.source_root` | 写真のフォルダ（`~` 可） | 最初 |
| `photos.events[]` | 行事ごとに `key`（`01_start` のように番号_英字。頭2文字が写真 ID の頭）、`folder`（元のフォルダ名）、`date`・`title`（章タイトルの文字の候補） | 最初。行事を足したら末尾に足す（既存の key の番号は変えない） |
| `photos.exclude_videos` | 動画の一覧から外すファイル名（既存の編集版など） | 最初 |
| `music.file` | 曲のパス | 最初 |
| `music.bpm_hint` | テンポの目安。空なら自動推定。倍・半分に推定されたら書く | 解析のとき |
| `music.downbeat_offset_beats` | 最初に検出した拍が1拍目でないときに、何拍ずらすか | 耳で確かめてから |
| `music.last_bar` | 音が切れる小節の、1つ前の小節（最後に音がある小節） | 解析のとき |
| `music.gain_db`・`fade_in_sec`・`fade_out_sec` | 音量の調整（−14 LUFS に合わせる）と頭・終わりのフェード | 解析のとき |
| `sections[]` | 区間。`name`（S1…）、`start_bar`、`in`（前の区間からの入り方: `cut`・`dissolve`・`flash`・`shake`・`under_grid`）、`label`（Aメロなど） | 曲の構成を耳で確かめてから |
| `chorus_bars` | サビの頭の小節（文字を置かない場所。マーカーも打つ） | 同上 |
| `end_black_bar` | 音が切れる小節（この頭で黒へ6フレームでフェード） | 同上 |
| `cut_offset` | カットを拍の何フレーム前に置くか（既定 −1） | 試写で 0〜−2 を調整 |
| `transitions.flash` | 白フラッシュで入る小節（サビ1の頭など） | シナリオ |
| `transitions.shake` | シェイクで入る小節（全編で8回程度まで） | シナリオ |
| `transitions.dissolve_long`・`dissolve_short` | その小節から始まるクリップを、2拍（28f）／半拍（7f）のディゾルブで入れる。ここにない小節はカット | シナリオ |
| `backgrounds[]` | V1 に置く生成画像。`id`・`section`・`bar`・`bars`・`file`。`start_at_zero`（0フレームから）、`fade_in_bars: [a, b]`（小節 a→b で黒から浮かぶ） | シナリオ |
| `kb_overrides[]` | その小節の写真の動きを直接指定する。`scale: [始, 終]`・`position: [[x,y],[x,y]]`。`start_early: true` はグリッドの下で14フレーム早く始める（グリッドが溶けて次の写真が現れる） | マッチディゾルブなど |
| `graphics.fonts` | `title`（明朝など）・`chapter`（丸ゴシックなど）。EffectCraft の `list_fonts` で確かめた PostScript 名 | 演出 |
| `graphics.title_ink`・`title_glow` | 生成画像の上の文字の色とにじみの色（0〜255 の RGB） | 演出・レビュー |
| `graphics.titles[]` | 明朝の文字。`name`・`text`・`bar`・`bars`・`reveal_bars`（出そろうまで）・`pos` | シナリオ |
| `graphics.chapters[]` | 章タイトル。`name`・`date`・`event`・`bar`（2小節出る） | シナリオ |
| `graphics.collages[]` | 3分割コラージュ。`name`・`section`・`bar`（2小節。selection.csv にも同じ小節の `collage` 行を書く） | シナリオ |
| `graphics.leaks[]` | 光漏れ。`name`・`bar`（2小節）・`colors`（0〜1 の RGB を2つ）・`from_x`・`to_x`・`y` | 演出 |
| `graphics.grid` | グリッド。`start_bar`・`done_bar`（この頭で最後の1枚）・`end_bar`・`cols`・`rows`・`background` | シナリオ |
| `looks.sections[]` | 区間ごとのルック（調整レイヤー V5）。`from_bar`・`to_bar`（null で最後まで）・`fade_bars`・`lumetri` | 演出 |
| `looks.global` | 全体のルック（V6）。`lumetri`・`vignette` | 演出 |
| `looks.grain` | フィルムグレインの量（V7、2〜3） | 演出 |

## selection.csv

1行が1スロット。`build_timeline.py` が、隙間・重なり・長さ0を検査する（`problems 0` になるまで直す）。

| 列 | 意味 | 例 |
|---|---|---|
| `section` | 区間 | `S5` |
| `bar` | 開始小節（半小節は .5） | `78.5` |
| `bars` | 長さ（小節） | `0.5` |
| `kind` | `photo` / `video` / `collage` / `grid` | |
| `id` | 写真 ID。動画はファイル名。コラージュは `|` でつなぐ | `08-140` |
| `file` | 変換済みの写真のパス（`data/photo_stats.csv` から ID で引く）。動画は元のファイルの絶対パス | |
| `kb` | Ken Burns: `in`（寄る）/ `out`（引く）/ `lr`・`rl`（横に流す） | `in` |
| `punch_in` | その小節の何拍目でパンチイン（1.15倍）するか。空なら無し | `3` |
| `fix` | `crop=x0,y0,x1,y1`（写真に対する割合で切り出す）。複数は `;` で区切る | `crop=0.00,0.00,1.00,0.75` |
| `role` | 何の場面か（人が読む説明。レビューで話すときに使う） | `章8 国際交流` |
| `note` | 動画は `source_in=53.9s`（切り出しの開始）。縦向きの動画は `縦向き` と書く（背景にぼかしを敷く）。前景の倍率は `data/clips.csv`（`list_clips.py`）の幅・高さから出す | |

決まりごと:

- 生成画像（`show.json` の `backgrounds`）とグリッドの小節には行を書かない。その前後の行とは隙間なくつながるようにする
- グリッドは `kind=grid` を `cols × rows` 行。並び順がタイルの番号（登場の順番）。`bar` と `bars` はグリッドの範囲を書いておく（表示用）
- 写真 ID を `photos.csv` の行の順番から引かない（ID とずれる）。必ず `photo_stats.csv` の `id` 列で引く
- `crop` の倍率は `1 / (x1 − x0)`（上限 2.4倍）。`crop=0,0,1,0.75` のように横幅いっぱいで上下だけ指定すると、倍率1のまま上寄せ・下寄せになる（顔が写真の端にある写真に使う）
- CSV を書き換えるときは Python の csv モジュールを使う（`fix` 列のカンマを含む値が引用符で囲まれるため、sed では壊れる）
