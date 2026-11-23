// EffectCraft のコンポ（タイトル・章タイトル・コラージュ・グリッド・光漏れ・焼き込み）を作る。
// graphics_plan.py が、このファイルと設定 graphics_plan.js（var PLAN = {...}）を .ecproj のフォルダ（既定 project/）にコピーする。
// run_script は .ecproj のフォルダのファイルしか読めないので、そのコピーを読む:
//   $.evalFile(new File("<ルート>/project/graphics_plan.js"));
//   $.evalFile(new File("<ルート>/project/make_graphics.js"));
//   buildAll();   // 全部。レンダーキューにも積む。名前の一覧を返す
// どのコンポも前後に1小節の余白（ハンドル）を付ける。内容は HANDLE 秒から始まる（FilmCraft 側は source_in = 1小節で合わせる）。
// 素材は prep_graphics.py が work/graphics/ に用意したもの。ExtendScript（ES3）なので let・アロー関数・JSON は使わない。

var ROOT = PLAN.root + "/";
var W = PLAN.width, H = PLAN.height, FPS = PLAN.fps;
var BAR = PLAN.bar_period, BEAT = BAR / 4, HANDLE = BAR;
var MINCHO = PLAN.fonts.title, MARU = PLAN.fonts.chapter;
var TITLE_INK = [PLAN.title_ink[0] / 255, PLAN.title_ink[1] / 255, PLAN.title_ink[2] / 255];
var TITLE_GLOW = [PLAN.title_glow[0] / 255, PLAN.title_glow[1] / 255, PLAN.title_glow[2] / 255];

function newComp(name, contentBars) {
  for (var i = app.project.numItems; i >= 1; i--) {
    if (app.project.item(i).name === name) app.project.item(i).remove();
  }
  return app.project.items.addComp(name, W, H, 1, contentBars * BAR + 2 * HANDLE, FPS);
}

function importImage(path) {
  return app.project.importFile(new ImportOptions(new File(path.charAt(0) === "/" ? path : ROOT + path)));
}

function addText(comp, str, font, size, pos, justify) {
  var L = comp.layers.addText(str);
  var st = L.property("ADBE Text Properties").property("ADBE Text Document");
  var td = st.value;
  td.font = font;
  td.fontSize = size;
  td.fillColor = [1, 1, 1];
  td.justification = justify || ParagraphJustification.CENTER_JUSTIFY;
  st.setValue(td);
  L.property("ADBE Transform Group").property("ADBE Position").setValue(pos);
  // ぼかした弱い影（黒 40%）
  var ds = L.Effects.addProperty("ADBE Drop Shadow");
  ds.property(2).setValue(40);
  ds.property(4).setValue(3);
  ds.property(5).setValue(12);
  return L;
}

// 1文字ずつ、ぼかしが取れながら少し下から浮かび上がる（revealSec で出そろう）
function revealByChar(L, t0, revealSec) {
  var an = L.property("ADBE Text Properties").property("ADBE Text Animators").addProperty("ADBE Text Animator");
  var ap = an.property("ADBE Text Animator Properties");
  ap.addProperty("ADBE Text Opacity").setValue(0);
  ap.addProperty("ADBE Text Position 3D").setValue([0, 28, 0]);
  ap.addProperty("ADBE Text Blur").setValue([12, 12]);
  var sel = an.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
  sel.property(4).property(5).setValue(2);
  var off = sel.property("ADBE Text Percent Offset");
  off.setValueAtTime(t0, -100);
  off.setValueAtTime(t0 + revealSec, 100);
}

function fade(layer, tIn, inSec, tOut, outSec, peak) {
  var op = layer.property("ADBE Transform Group").property("ADBE Opacity");
  op.setValueAtTime(tIn, 0);
  op.setValueAtTime(tIn + inSec, peak);
  op.setValueAtTime(tOut - outSec, peak);
  op.setValueAtTime(tOut, 0);
}

// 生成画像（明るい背景）の上の明朝の文字。白い文字＋黒い帯はデザインとして浮くので、
// 暗い暖色（TITLE_INK）の文字を直接のせ、背景の濃いところでも沈まないよう明るいにじみ（TITLE_GLOW）を薄く敷く
function titleComp(name, str, bars, revealBars, pos) {
  var c = newComp(name, bars);
  var t0 = HANDLE, t1 = HANDLE + bars * BAR;
  var L = addText(c, str, MINCHO, 72, [pos[0], pos[1] + 26]);
  var st = L.property("ADBE Text Properties").property("ADBE Text Document");
  var td = st.value;
  td.fillColor = TITLE_INK;
  st.setValue(td);
  var ds = L.Effects.property(1);
  ds.property(1).setValue(TITLE_GLOW);
  ds.property(2).setValue(85);
  ds.property(4).setValue(0);
  ds.property(5).setValue(22);
  revealByChar(L, t0, revealBars * BAR);
  fade(L, t0, 0.01, t1, BEAT, 100);
  // 出そろったあとも止まって見えないよう、ごくゆっくり寄る
  var sc = L.property("ADBE Transform Group").property("ADBE Scale");
  sc.setValueAtTime(t0, [100, 100]);
  sc.setValueAtTime(t1, [103, 103]);
  return c;
}

// 章タイトルカード。帯は画面下から 1/4、日付 120px・行事名 56px、2小節。文字は少し横に流れながらイーズでフェード
function chapterComp(name, date, event) {
  var c = newComp(name, 2);
  var t0 = HANDLE, t1 = HANDLE + 2 * BAR;
  var band = c.layers.addSolid([0, 0, 0], "band", W, 220, 1);
  band.property("ADBE Transform Group").property("ADBE Position").setValue([W / 2, 810]);
  fade(band, t0, BEAT * 1.5, t1, BEAT * 1.5, 40);
  var d = addText(c, date, MARU, 120, [190, 852], ParagraphJustification.LEFT_JUSTIFY);
  var e = addText(c, event, MARU, 56, [190 + date.length * 70 + 60, 838], ParagraphJustification.LEFT_JUSTIFY);
  var parts = [[d, 0], [e, BEAT * 0.5]];
  for (var i = 0; i < parts.length; i++) {
    var L = parts[i][0], dt = parts[i][1];
    var p = L.property("ADBE Transform Group").property("ADBE Position");
    var v = p.value;
    p.setValueAtTime(t0 + dt, [v[0] - 20, v[1]]);
    p.setValueAtTime(t1, [v[0] + 20, v[1]]);
    var op = L.property("ADBE Transform Group").property("ADBE Opacity");
    op.setValueAtTime(t0 + dt, 0);
    op.setValueAtTime(t0 + dt + BEAT * 2, 100);
    op.setValueAtTime(t1 - BEAT * 2, 100);
    op.setValueAtTime(t1, 0);
    for (var k = 1; k <= op.numKeys; k++) op.setInterpolationTypeAtKey(k, KeyframeInterpolationType.BEZIER);
    op.setTemporalEaseAtKey(2, [new KeyframeEase(0, 75)], [new KeyframeEase(0, 75)]);
    op.setTemporalEaseAtKey(3, [new KeyframeEase(0, 75)], [new KeyframeEase(0, 75)]);
  }
  return c;
}

// 3分割コラージュ。縦長 632px の3枚を、半拍ずつずらして下から入れる
function collageComp(name, dir) {
  var c = newComp(name, 2);
  var t0 = HANDLE;
  for (var i = 0; i < 3; i++) {
    var L = c.layers.add(importImage(dir + "/" + (i + 1) + ".jpg"));
    var x = 316 + i * 644;
    var tr = L.property("ADBE Transform Group");
    var t = t0 + i * BEAT / 2;
    tr.property("ADBE Position").setValueAtTime(t, [x, H / 2 + 60]);
    tr.property("ADBE Position").setValueAtTime(t + 0.2, [x, H / 2]);
    tr.property("ADBE Opacity").setValueAtTime(t, 0);
    tr.property("ADBE Opacity").setValueAtTime(t + 0.2, 100);
    tr.property("ADBE Scale").setValueAtTime(t, [100, 100]);
    tr.property("ADBE Scale").setValueAtTime(t0 + 2 * BAR + HANDLE, [104, 104]);
  }
  return c;
}

// グリッド。(done_bar - start_bar) 小節かけて加速しながら置き、done_bar の頭で最後の1枚が入って完成、end_bar まで引いて見せる
function gridComp(name) {
  var G = PLAN.grid;
  var buildBars = G.done_bar - G.start_bar, allBars = G.end_bar - G.start_bar;
  var c = newComp(name, allBars);
  var t0 = HANDLE, tDone = HANDLE + buildBars * BAR;
  c.layers.add(importImage(G.background));
  var cam = c.layers.addNull();
  cam.property("ADBE Transform Group").property("ADBE Position").setValue([W / 2, H / 2]);
  cam.property("ADBE Transform Group").property("ADBE Scale").setValueAtTime(t0, [110, 110]);
  cam.property("ADBE Transform Group").property("ADBE Scale").setValueAtTime(tDone, [106, 106]);
  cam.property("ADBE Transform Group").property("ADBE Scale").setValueAtTime(tDone + BAR, [100, 100]);
  var cols = G.cols, rows = G.rows, n = cols * rows, cw = W / cols, ch = H / rows, gap = 6;
  // セルの順番を決まった方法でかき混ぜる（毎回同じ並びになる）
  var order = [];
  for (var k = 0; k < n; k++) order.push(k);
  for (var k = n - 1; k > 0; k--) {
    var j = (k * 7919 + 13) % (k + 1), tmp = order[k];
    order[k] = order[j];
    order[j] = tmp;
  }
  for (var k = 0; k < n; k++) {
    var m = k + 1, cell = order[k];
    var L = c.layers.add(importImage("work/graphics/grid/" + (m < 10 ? "0" : "") + m + ".jpg"));
    L.parent = cam;
    var s = (cw - gap) / (cw * 2) * 100;  // タイルはセルの2倍の大きさで用意してある
    var tr = L.property("ADBE Transform Group");
    // 最後の1枚が done_bar の頭に入る。前半はゆっくり、後半は速く
    var t = t0 + buildBars * BAR * Math.pow(m / n, 0.55);
    t = Math.round(t * FPS) / FPS;
    // 親（cam）の原点が画面の中央なので、セルの中心から画面の中央を引く
    tr.property("ADBE Position").setValue([(cell % cols) * cw + cw / 2 - W / 2, Math.floor(cell / cols) * ch + ch / 2 - H / 2]);
    tr.property("ADBE Scale").setValueAtTime(t - 0.2, [s * 1.5, s * 1.5]);
    tr.property("ADBE Scale").setValueAtTime(t, [s, s]);
    tr.property("ADBE Opacity").setValueAtTime(t - 0.2, 0);
    tr.property("ADBE Opacity").setValueAtTime(t, 100);
    L.inPoint = t - 0.2;
  }
  return c;
}

// 光漏れ。暖色の平面をぼかして横に流す（外部素材なし）。FilmCraft でスクリーン合成する
function leakComp(name, colors, fromX, toX, seedY) {
  var c = newComp(name, 2);
  var t0 = HANDLE, t1 = HANDLE + 2 * BAR;
  for (var j = 0; j < colors.length; j++) {
    var S = c.layers.addSolid(colors[j], "leak" + j, 1100, 900, 1);
    S.Effects.addProperty("ADBE Gaussian Blur 2").property(1).setValue(260);
    var p = S.property("ADBE Transform Group").property("ADBE Position");
    p.setValueAtTime(t0, [fromX + j * 300, seedY + j * 250]);
    p.setValueAtTime(t1, [toX - j * 200, seedY + 100 + j * 150]);
    fade(S, t0, BAR * 0.6, t1, BAR * 0.6, 70 - j * 20);
  }
  return c;
}

// レビュー用の焼き込み（V8）。タイムコード・小節.拍・区間名を式で計算する（beats.json の格子）
function burninComp(name) {
  for (var i = app.project.numItems; i >= 1; i--) if (app.project.item(i).name === name) app.project.item(i).remove();
  var c = app.project.items.addComp(name, W, H, 1, PLAN.duration, FPS);
  var bg = c.layers.addSolid([0, 0, 0], "bg", 760, 60, 1);
  bg.property("ADBE Transform Group").property("ADBE Position").setValue([420, H - 63]);
  bg.property("ADBE Transform Group").property("ADBE Opacity").setValue(50);
  var L = c.layers.addText("x");
  var st = L.property("ADBE Text Properties").property("ADBE Text Document");
  var td = st.value; td.font = "Menlo"; td.fontSize = 40; td.fillColor = [1, 1, 0];
  td.justification = ParagraphJustification.LEFT_JUSTIFY; st.setValue(td);
  L.property("ADBE Transform Group").property("ADBE Position").setValue([60, H - 50]);
  var S = [];
  for (var i = 0; i < PLAN.sections.length; i++) S.push("[" + PLAN.sections[i][0] + ", '" + PLAN.sections[i][1] + "']");
  st.expression = "var t0=" + PLAN.first_beat + ", bp=" + PLAN.bar_period + "; var b=Math.floor((time-t0)/bp)+1; var be=Math.floor((time-t0)/(bp/4))%4+1;" +
    "var S=[" + S.join(", ") + "]; var s=''; for(var i=0;i<S.length;i++){ if(b>=S[i][0]) s=S[i][1]; }" +
    "var f=Math.round(time*" + FPS + "); function p(n){return (n<10?'0':'')+n;}" +
    "p(Math.floor(f/" + (FPS * 60) + "))+':'+p(Math.floor(f/" + FPS + ")%60)+':'+p(f%" + FPS + ")+'   bar '+(time<t0?'-':b+'.'+be)+'   '+s;";
  return c;
}

// only: 作るコンポの名前の配列（省略すると全部）。作ったコンポをレンダーキューに積み、名前を "," でつないで返す。
// レンダーキューの順番は graphics_plan.py が書いた render_steps.json と同じになる（同じ only を渡すこと）
function buildAll(only) {
  var want = {};
  if (only) for (var i = 0; i < only.length; i++) want[only[i]] = true;
  var ok = function (n) { return !only || want[n]; };
  var made = [];
  for (var i = 0; i < PLAN.titles.length; i++) {
    var t = PLAN.titles[i];
    if (ok(t.name)) made.push(titleComp(t.name, t.text, t.bars, t.reveal_bars, t.pos));
  }
  for (var i = 0; i < PLAN.chapters.length; i++) {
    var ch = PLAN.chapters[i];
    if (ok(ch.name)) made.push(chapterComp(ch.name, ch.date, ch.event));
  }
  for (var i = 0; i < PLAN.collages.length; i++) {
    var co = PLAN.collages[i];
    if (ok(co.name)) made.push(collageComp(co.name, "work/graphics/collage_" + co.section));
  }
  if (PLAN.grid && ok("GRID")) made.push(gridComp("GRID"));
  for (var i = 0; i < PLAN.leaks.length; i++) {
    var lk = PLAN.leaks[i];
    if (ok(lk.name)) made.push(leakComp(lk.name, lk.colors, lk.from_x, lk.to_x, lk.y));
  }
  if (ok("BURNIN")) made.push(burninComp("BURNIN"));
  while (app.project.renderQueue.numItems > 0) app.project.renderQueue.item(1).remove();
  var names = [];
  for (var i = 0; i < made.length; i++) {
    app.project.renderQueue.items.add(made[i]);
    names.push(made[i].name);
  }
  return names.join(",");
}
