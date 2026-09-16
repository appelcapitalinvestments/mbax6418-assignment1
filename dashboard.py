"""
MBAX 6418 - Assignment 1, Steps 3, 4 and 7
Generate a single self-contained HTML dashboard from a saved results file.

Nothing here computes a metric. Every number rendered is read from the JSON
that `score3.py` wrote, which is what makes Step 7's instruction checkable:
"Check the numbers on the page against the numbers you saved earlier - in the
browser, not just by eye."

Design decisions and why
------------------------
Sentiment is polarity data, so its three classes use a **diverging** encoding:
blue for POSITIVE, neutral gray for NEUTRAL, red for NEGATIVE. Not an arbitrary
categorical set. All three clear 3:1 contrast against both the light and dark
chart surfaces.

The LLM-versus-word-list comparison is two series, so it takes the first two
categorical slots (blue, orange), which validate on all pairs in both modes.

Emotion distribution on its own is a single series, so it uses one hue rather
than a different color per bar. Coloring one series by category is decoration,
not encoding.

Dark mode is a selected set of steps for the dark surface, not an inverted
copy of the light one.

Run:  python dashboard.py                                  # newest results file
      python dashboard.py results/step6_balanced50.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
RESULTS_DIR = HERE / "results"
OUTPUT = HERE / "dashboard.html"

CLASSES = ("POSITIVE", "NEUTRAL", "NEGATIVE")


def _short(path: Path) -> str:
    """Path relative to this file's folder when it sits under it, else absolute."""
    try:
        return str(path.resolve().relative_to(HERE.resolve()))
    except ValueError:
        return str(path)


def newest_results() -> Path:
    candidates = sorted(RESULTS_DIR.glob("step6_*.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        candidates = sorted(RESULTS_DIR.glob("step2_*.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise SystemExit(
            "No results file found in results/. Run `python score3.py` first."
        )
    return candidates[-1]


_BR = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]{1,40}>")
_ENTITY = {"&amp;": "&", "&quot;": '"', "&#34;": '"', "&apos;": "'", "&#39;": "'",
           "&lt;": "<", "&gt;": ">", "&nbsp;": " "}


def clean_review_text(s: str) -> str:
    """Amazon review bodies carry raw HTML - mostly <br /> where the reviewer
    pressed return, plus the occasional entity. The page escapes everything it
    prints, so left alone these render as literal '<br />' in the middle of a
    sentence. Turn the breaks into spaces and drop the rest before escaping."""
    s = _BR.sub(" ", s or "")
    s = _TAG.sub("", s)
    for entity, char in _ENTITY.items():
        s = s.replace(entity, char)
    return " ".join(s.split())


def build(payload: dict) -> str:
    run = payload["run"]
    m = payload["metrics"]
    rows = payload["rows"]

    classes = [c for c in CLASSES if c in m["per_class"]]
    emotion = m.get("emotion") or {}

    # Only what the page needs, so the embedded blob stays small and readable.
    table_rows = [
        {
            "i": r.get("row_index"),
            "rating": int(r["rating"]),
            "truth": r.get("truth"),
            "pred": r.get("prediction"),
            "conf": r.get("confidence"),
            "ok": r.get("correct"),
            "llm": r.get("llm_emotion"),
            "nrc": r.get("nrc_emotion"),
            "title": clean_review_text(r.get("title"))[:160],
            "text": clean_review_text(r.get("text"))[:600],
        }
        for r in rows
    ]

    data = {
        "run": run,
        "metrics": m,
        "rows": table_rows,
        "classes": classes,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    return _TEMPLATE.replace("__DATA__", json.dumps(data))


_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Review Sentiment Classifier - MBAX 6418 Assignment 1</title>
<style>
:root{
  color-scheme: light;
  --plane:#f9f9f7; --surface:#fcfcfb;
  --ink:#0b0b0b; --ink-2:#52514e; --ink-muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --ring:rgba(11,11,11,0.10);
  --pos:#2a78d6; --neu:#898781; --neg:#e34948;
  --s1:#2a78d6; --s2:#eb6834;
  --seq-100:#cde2fb; --seq-250:#86b6ef; --seq-400:#3987e5; --seq-550:#1c5cab; --seq-700:#0d366b;
  --good:#0ca30c; --critical:#d03b3b;
}
@media (prefers-color-scheme: dark){
  :root:where(:not([data-theme="light"])){
    color-scheme: dark;
    --plane:#0d0d0d; --surface:#1a1a19;
    --ink:#ffffff; --ink-2:#c3c2b7; --ink-muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,0.10);
    --pos:#3987e5; --neu:#898781; --neg:#e66767;
    --s1:#3987e5; --s2:#d95926;
    --good:#0ca30c; --critical:#d03b3b;
  }
}
:root[data-theme="dark"]{
  color-scheme: dark;
  --plane:#0d0d0d; --surface:#1a1a19;
  --ink:#ffffff; --ink-2:#c3c2b7; --ink-muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,0.10);
  --pos:#3987e5; --neu:#898781; --neg:#e66767;
  --s1:#3987e5; --s2:#d95926;
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--plane); color:var(--ink);
  font:14px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1180px; margin:0 auto; padding:40px 20px 72px}
header{margin-bottom:28px}
h1{font-size:26px; font-weight:640; letter-spacing:-0.015em; margin:0 0 6px}
.sub{color:var(--ink-2); font-size:13.5px; margin:0}
.meta{margin-top:14px; display:flex; flex-wrap:wrap; gap:6px}
.chip{
  font:11.5px/1 ui-monospace,SFMono-Regular,Menlo,monospace;
  color:var(--ink-2); background:var(--surface);
  border:1px solid var(--ring); border-radius:999px; padding:6px 10px;
}
.controls{display:flex; gap:8px; align-items:center; margin-top:16px; flex-wrap:wrap}
button{
  font:inherit; font-size:13px; color:var(--ink-2); cursor:pointer;
  background:var(--surface); border:1px solid var(--ring);
  border-radius:8px; padding:7px 13px;
}
button:hover{color:var(--ink)}
button[aria-pressed="true"]{color:var(--ink); border-color:var(--axis); font-weight:560}
section{
  background:var(--surface); border:1px solid var(--ring); border-radius:12px;
  padding:24px; margin-bottom:20px;
}
h2{font-size:15px; font-weight:620; margin:0 0 4px; letter-spacing:-0.005em}
.note{color:var(--ink-2); font-size:12.5px; margin:0 0 20px; max-width:74ch}
.tiles{display:grid; grid-template-columns:repeat(auto-fit,minmax(168px,1fr)); gap:16px}
.tile{padding:2px 0}
.tile .k{font-size:11.5px; color:var(--ink-muted); text-transform:uppercase; letter-spacing:.055em}
.tile .v{font-size:31px; font-weight:640; letter-spacing:-0.02em; margin-top:5px; font-variant-numeric:tabular-nums}
.tile .d{font-size:12px; color:var(--ink-2); margin-top:3px}
.bars{display:flex; flex-direction:column; gap:13px}
.bar-row{display:grid; grid-template-columns:106px 1fr 92px; align-items:center; gap:12px}
.bar-lab{font-size:12.5px; color:var(--ink-2); display:flex; align-items:center; gap:7px}
.dot{width:9px; height:9px; border-radius:2px; flex:none}
.track{height:15px; background:var(--grid); border-radius:4px; position:relative}
.fill{height:100%; border-radius:4px 0 0 4px; position:relative}
.fill.full{border-radius:4px}
.bar-val{font-size:12.5px; color:var(--ink-2); text-align:right; font-variant-numeric:tabular-nums}
.grouped{display:flex; flex-direction:column; gap:9px}
.g-row{display:grid; grid-template-columns:104px 1fr 74px; align-items:center; gap:12px}
.g-val{font-size:12px; color:var(--ink-2); text-align:right; font-variant-numeric:tabular-nums}
.g-stack{display:flex; flex-direction:column; gap:3px}
/* A zero value must draw nothing. min-width on every bar turns a real zero
   into a visible tick, which is the mirror image of the collapsed-bar bug the
   assignment warns about: the reader sees a mark where there is no data. */
.g-bar{height:11px; border-radius:3px}
.g-bar[data-n="0"]{display:none}
.legend{display:flex; gap:16px; margin-bottom:16px; flex-wrap:wrap}
.legend span{display:flex; align-items:center; gap:7px; font-size:12.5px; color:var(--ink-2)}
table.cm{border-collapse:separate; border-spacing:2px; margin-top:4px}
table.cm th{font-size:11.5px; font-weight:520; color:var(--ink-muted); padding:5px 9px; text-align:center}
table.cm th.rh{text-align:right}
table.cm td{
  padding:14px 18px; text-align:center; border-radius:5px;
  font-variant-numeric:tabular-nums; font-size:15px; font-weight:560;
  min-width:74px;
}
.cm-note{font-size:12px; color:var(--ink-muted); margin-top:12px}
.filters{display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:16px}
.count{font-size:12.5px; color:var(--ink-2); margin-left:auto; font-variant-numeric:tabular-nums}
.scroller{overflow-x:auto; -webkit-overflow-scrolling:touch}
/* 150 rows would make the page 14,000px tall, so the table scrolls in place. */
.scroller.tall{max-height:min(620px,72vh); overflow-y:auto}
table.rev{width:100%; min-width:760px; border-collapse:collapse; font-size:12.5px}
table.rev th{
  text-align:left; font-weight:560; font-size:11.5px; color:var(--ink-muted);
  text-transform:uppercase; letter-spacing:.05em;
  padding:8px 10px; border-bottom:1px solid var(--axis); white-space:nowrap;
  position:sticky; top:0; background:var(--surface); z-index:2;
}
table.rev td{padding:9px 10px; border-bottom:1px solid var(--grid); vertical-align:top}
table.rev tr:hover td{background:var(--plane)}
.tag{
  display:inline-flex; align-items:center; gap:5px;
  font-size:11.5px; white-space:nowrap;
}
.mono{font:11.5px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace; color:var(--ink-2)}
.rt{max-width:420px; color:var(--ink-2)}
/* "agreed"/"differed" are words, not colors - no green/red pair to fail CVD. */
.ok-y{color:var(--ink-muted)}
.ok-n{color:var(--ink); font-weight:600}
.ok-e{color:var(--ink-muted); font-style:italic}
.tt{
  position:fixed; pointer-events:none; opacity:0; transition:opacity .1s;
  background:var(--surface); border:1px solid var(--axis); border-radius:7px;
  padding:8px 11px; font-size:12px; color:var(--ink); z-index:50;
  box-shadow:0 4px 14px rgba(0,0,0,.13); max-width:280px;
}
.hoverable{cursor:default}
.tblview{display:none; margin-top:18px}
.tblview.on{display:block}
table.plain{border-collapse:collapse; font-size:12.5px}
table.plain th,table.plain td{padding:5px 14px 5px 0; text-align:left}
table.plain th{color:var(--ink-muted); font-weight:520; font-size:11.5px}
footer{color:var(--ink-muted); font-size:12px; margin-top:32px; line-height:1.7}
@media (max-width:640px){
  .bar-row{grid-template-columns:92px 1fr 76px}
  .g-row{grid-template-columns:88px 1fr}
  .wrap{padding:24px 14px 48px}
}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Review Sentiment &amp; Emotion Classifier</h1>
    <p class="sub">Amazon Reviews &rsquo;23 &middot; Gift Cards &middot; MBAX 6418 Assignment 1</p>
    <div class="meta" id="meta"></div>
    <div class="controls">
      <button id="theme" type="button">Toggle theme</button>
      <button id="tables" type="button" aria-pressed="false">Show data tables</button>
    </div>
  </header>

  <section>
    <h2>Headline</h2>
    <p class="note" id="headnote"></p>
    <div class="tiles" id="tiles"></div>
  </section>

  <section>
    <h2>Accuracy by class</h2>
    <p class="note">How often the model agreed with the star rating, within each true class. A balanced sample means each bar rests on a similar number of reviews, so the three are comparable to each other.</p>
    <div class="bars" id="perclass"></div>
    <div class="tblview" id="perclass-t"></div>
  </section>

  <section>
    <h2>Where the mistakes go</h2>
    <p class="note">Rows are the star rating&rsquo;s answer, columns are the model&rsquo;s. Anything off the diagonal is a disagreement. Cell shading is a single-hue ramp, so darker means more reviews.</p>
    <div class="scroller" id="confusion"></div>
    <p class="cm-note" id="cmnote"></p>
    <div class="tblview" id="confusion-t"></div>
  </section>

  <section>
    <h2>What the sample looks like</h2>
    <p class="note">Star ratings present in this run. Balanced sampling is the reason this is not the near-vertical 5-star spike the raw file produces.</p>
    <div class="bars" id="stars"></div>
    <div class="tblview" id="stars-t"></div>
  </section>

  <section id="emosec">
    <h2>Two readings of emotion</h2>
    <p class="note" id="emonote"></p>
    <div class="legend">
      <span><i class="dot" style="background:var(--s1)"></i>Predicted by the model</span>
      <span><i class="dot" style="background:var(--s2)"></i>Derived from the NRC word list</span>
    </div>
    <div class="grouped" id="emotions"></div>
    <div class="tblview" id="emotions-t"></div>
  </section>

  <section>
    <h2>Reviews</h2>
    <p class="note">Filter to a subset and the count updates live. Every row here is in the saved results file.</p>
    <div class="filters">
      <button data-f="all" aria-pressed="true" type="button">All</button>
      <button data-f="ok" aria-pressed="false" type="button">Agreed</button>
      <button data-f="miss" aria-pressed="false" type="button">Disagreed</button>
      <button data-f="err" aria-pressed="false" type="button">Failed</button>
      <button data-f="POSITIVE" aria-pressed="false" type="button">True positive</button>
      <button data-f="NEUTRAL" aria-pressed="false" type="button">True neutral</button>
      <button data-f="NEGATIVE" aria-pressed="false" type="button">True negative</button>
      <span class="count" id="count"></span>
    </div>
    <div class="scroller tall">
      <table class="rev">
        <thead><tr>
          <th>Row</th><th>Stars</th><th>Rating says</th><th>Model says</th>
          <th>Conf</th><th>Model emotion</th><th>Word list</th><th>Review</th>
        </tr></thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
  </section>

  <footer id="foot"></footer>
</div>
<div class="tt" id="tt"></div>

<script>
const DATA = __DATA__;
const $ = s => document.querySelector(s);
const CLR = {POSITIVE:'var(--pos)', NEUTRAL:'var(--neu)', NEGATIVE:'var(--neg)'};
const pct = v => v==null ? ' - ' : (v*100).toFixed(1)+'%';

/* ---------- tooltip ---------- */
const tt = $('#tt');
function bindTip(el, html){
  el.classList.add('hoverable');
  el.addEventListener('mousemove', e => {
    tt.innerHTML = html;
    tt.style.opacity = 1;
    const pad = 14;
    let x = e.clientX + pad, y = e.clientY + pad;
    const r = tt.getBoundingClientRect();
    if (x + r.width > innerWidth - 8) x = e.clientX - r.width - pad;
    if (y + r.height > innerHeight - 8) y = e.clientY - r.height - pad;
    tt.style.left = x+'px'; tt.style.top = y+'px';
  });
  el.addEventListener('mouseleave', () => tt.style.opacity = 0);
}

/* ---------- header ---------- */
const run = DATA.run, M = DATA.metrics;
$('#meta').innerHTML = [
  run.model, run.endpoint,
  run.sampling, run.seed!=null ? 'seed '+run.seed : null,
  'run '+String(run.timestamp_utc).replace('T',' ').replace('+00:00',' UTC')
].filter(Boolean).map(t => `<span class="chip">${t}</span>`).join('');

/* ---------- headline tiles ---------- */
const margin = (M.agreement_with_rating!=null && M.majority_class_baseline!=null)
  ? M.agreement_with_rating - M.majority_class_baseline : null;

$('#headnote').textContent =
  'Agreement is how often the model matched the answer derived from the star rating. '
  + 'The baseline is what a model would score by always guessing the most common class. '
  + 'The gap between them is the part the model actually earned.';

$('#tiles').innerHTML = [
  {k:'Agreement', v:pct(M.agreement_with_rating), d:M.n_scored+' reviews scored'},
  {k:'Majority baseline', v:pct(M.majority_class_baseline), d:'always guess the biggest class'},
  {k:'Margin over baseline', v:(margin==null?' - ':(margin>=0?'+':'−')+Math.abs(margin*100).toFixed(1)+' pts'),
   d:'what the model earned'},
  {k:'Unusable replies', v:String(M.n_failed), d:'excluded from accuracy'},
].map(t => `<div class="tile"><div class="k">${t.k}</div>
   <div class="v">${t.v}</div><div class="d">${t.d}</div></div>`).join('');

/* ---------- per-class accuracy ---------- */
const pcRows = DATA.classes.map(c => ({c, ...M.per_class[c]}));
$('#perclass').innerHTML = pcRows.map(r => `
  <div class="bar-row">
    <div class="bar-lab"><i class="dot" style="background:${CLR[r.c]}"></i>${r.c}</div>
    <div class="track"><div class="fill" data-c="${r.c}"
        style="width:${(r.accuracy||0)*100}%; background:${CLR[r.c]}"></div></div>
    <div class="bar-val">${pct(r.accuracy)} <span style="color:var(--ink-muted)">(${r.correct}/${r.n})</span></div>
  </div>`).join('');
pcRows.forEach(r => {
  const el = document.querySelector(`.fill[data-c="${r.c}"]`);
  if (el) bindTip(el, `<b>${r.c}</b><br>${r.correct} of ${r.n} matched the rating<br>${pct(r.accuracy)} accuracy`);
});
$('#perclass-t').innerHTML = '<table class="plain"><tr><th>Class</th><th>Correct</th><th>Total</th><th>Accuracy</th></tr>'
  + pcRows.map(r=>`<tr><td>${r.c}</td><td>${r.correct}</td><td>${r.n}</td><td>${pct(r.accuracy)}</td></tr>`).join('')
  + '</table>';

/* ---------- confusion matrix ---------- */
const CM = M.confusion_truth_by_prediction;
const cmMax = Math.max(...DATA.classes.flatMap(t => DATA.classes.map(p => CM[t][p])), 1);
/* The sequential ramp is the same in both themes - a magnitude ramp should not
   flip meaning when the page does - so the text on it is pinned to a fixed ink,
   never the theme-aware --ink token. White only from step 3 up: white on
   #3987e5 is 3.64:1, under AA for text this size, while #0b0b0b on it is 5.4:1. */
const SEQ = ['#cde2fb','#86b6ef','#3987e5','#1c5cab','#0d366b'];
function cell(n){
  if(!n) return {bg:'var(--grid)', fg:'var(--ink-muted)'};
  const i = Math.min(SEQ.length-1, Math.floor((n/cmMax)*(SEQ.length-0.001)));
  return {bg:SEQ[i], fg:i>=3?'#ffffff':'#0b0b0b'};
}
$('#confusion').innerHTML = '<table class="cm"><tr><th></th>'
  + DATA.classes.map(p=>`<th>${p}</th>`).join('') + '</tr>'
  + DATA.classes.map(t => '<tr><th class="rh">'+t+'</th>'
      + DATA.classes.map(p => {
          const n = CM[t][p], s = cell(n);
          return `<td data-t="${t}" data-p="${p}" style="background:${s.bg};color:${s.fg}">${n}</td>`;
        }).join('')
    + '</tr>').join('') + '</table>';
document.querySelectorAll('table.cm td').forEach(td=>{
  const t=td.dataset.t, p=td.dataset.p, n=CM[t][p];
  const tot = DATA.classes.reduce((s,x)=>s+CM[t][x],0);
  bindTip(td, `Rating said <b>${t}</b><br>Model said <b>${p}</b><br>${n} review${n===1?'':'s'}`
    + (tot?`<br>${((n/tot)*100).toFixed(0)}% of true ${t}`:''));
});
if (CM.NEUTRAL){
  const tot = DATA.classes.reduce((s,x)=>s+CM.NEUTRAL[x],0);
  if (tot) $('#cmnote').textContent =
    `Of the ${tot} three-star reviews, the model called `
    + DATA.classes.map(p=>`${CM.NEUTRAL[p]} ${p.toLowerCase()}`).join(', ') + '.';
}
$('#confusion-t').innerHTML = '<table class="plain"><tr><th>Rating says</th><th>Model says</th><th>Count</th></tr>'
  + DATA.classes.flatMap(t=>DATA.classes.map(p=>`<tr><td>${t}</td><td>${p}</td><td>${CM[t][p]}</td></tr>`)).join('')
  + '</table>';

/* ---------- star distribution ---------- */
const stars = M.rating_distribution || {};
// JSON object keys that look like integers come back in ascending order no
// matter what order they were written in, so the 5-to-1 order is restored here.
const starRows = Object.entries(stars).sort((a,b) => Number(b[0]) - Number(a[0]));
const sMax = Math.max(...Object.values(stars), 1);
const total = Object.values(stars).reduce((a,b)=>a+b,0);
$('#stars').innerHTML = starRows.map(([s,n]) => `
  <div class="bar-row">
    <div class="bar-lab">${s} star${s==='1'?'':'s'}</div>
    <div class="track"><div class="fill" data-s="${s}"
        style="width:${(n/sMax)*100}%; background:var(--seq-400)"></div></div>
    <div class="bar-val">${n} <span style="color:var(--ink-muted)">(${((n/total)*100).toFixed(0)}%)</span></div>
  </div>`).join('');
starRows.forEach(([s,n])=>{
  const el=document.querySelector(`.fill[data-s="${s}"]`);
  if(el) bindTip(el, `<b>${s} star</b><br>${n} of ${total} reviews`);
});
$('#stars-t').innerHTML = '<table class="plain"><tr><th>Stars</th><th>Count</th></tr>'
  + starRows.map(([s,n])=>`<tr><td>${s}</td><td>${n}</td></tr>`).join('') + '</table>';

/* ---------- emotion comparison ---------- */
const E = M.emotion;
if (!E || !E.n_comparable){ $('#emosec').style.display='none'; }
else {
  $('#emonote').textContent =
    `The model named an emotion and a word list derived one independently, with no model call. `
    + `They agreed on ${E.n_agree} of ${E.n_comparable} reviews where both produced an answer (${pct(E.agreement_rate)}). `
    + `The word list gave no answer on ${E.nrc_no_answer} reviews, either because no listed word appeared or because the top score was a tie.`;
  const keys = [...new Set([...Object.keys(E.llm_distribution||{}), ...Object.keys(E.nrc_distribution||{})])].sort();
  const eMax = Math.max(1, ...keys.map(k => Math.max(E.llm_distribution[k]||0, E.nrc_distribution[k]||0)));
  $('#emotions').innerHTML =
    '<div class="g-row"><div></div><div></div>'
    + '<div class="g-val" style="color:var(--ink-muted);font-size:11px">model / list</div></div>'
    + keys.map(k => {
    const a = E.llm_distribution[k]||0, b = E.nrc_distribution[k]||0;
    return `<div class="g-row">
      <div class="bar-lab">${k}</div>
      <div class="g-stack">
        <div class="g-bar" data-e="${k}" data-w="llm" data-n="${a}" style="width:${Math.max(a?2:0,(a/eMax)*100)}%;background:var(--s1)"></div>
        <div class="g-bar" data-e="${k}" data-w="nrc" data-n="${b}" style="width:${Math.max(b?2:0,(b/eMax)*100)}%;background:var(--s2)"></div>
      </div>
      <div class="g-val">${a} <span style="color:var(--ink-muted)">/</span> ${b}</div>
    </div>`;
  }).join('');
  document.querySelectorAll('.g-bar').forEach(el=>{
    const k=el.dataset.e, w=el.dataset.w;
    const n = (w==='llm'?E.llm_distribution:E.nrc_distribution)[k]||0;
    bindTip(el, `<b>${k}</b><br>${w==='llm'?'Model':'Word list'}: ${n} review${n===1?'':'s'}`);
  });
  $('#emotions-t').innerHTML = '<table class="plain"><tr><th>Emotion</th><th>Model</th><th>Word list</th></tr>'
    + keys.map(k=>`<tr><td>${k}</td><td>${E.llm_distribution[k]||0}</td><td>${E.nrc_distribution[k]||0}</td></tr>`).join('')
    + '</table>';
}

/* ---------- review table with live filtering ---------- */
let filter = 'all';
const esc = s => String(s??'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function matches(r){
  if (filter==='all') return true;
  if (filter==='ok') return r.ok===true;
  if (filter==='miss') return r.ok===false;
  if (filter==='err') return r.ok===null;
  return r.truth===filter;
}
function render(){
  const shown = DATA.rows.filter(matches);
  $('#count').textContent = `${shown.length} of ${DATA.rows.length} reviews`;
  $('#tbody').innerHTML = shown.map(r => {
    const mark = r.ok===true ? '<span class="ok-y">agreed</span>'
               : r.ok===false ? '<span class="ok-n">differed</span>'
               : '<span class="ok-e">no reply</span>';
    return `<tr>
      <td class="mono">${r.i}</td>
      <td class="mono">${r.rating}</td>
      <td><span class="tag"><i class="dot" style="background:${CLR[r.truth]||'var(--neu)'}"></i>${esc(r.truth)}</span></td>
      <td><span class="tag"><i class="dot" style="background:${CLR[r.pred]||'var(--grid)'}"></i>${esc(r.pred??' - ')}</span> ${mark}</td>
      <td class="mono">${r.conf==null?' - ':r.conf.toFixed(2)}</td>
      <td class="mono">${esc(r.llm??' - ')}</td>
      <td class="mono">${esc(r.nrc??' - ')}</td>
      <td class="rt"><b style="color:var(--ink)">${esc(r.title)}</b><br>${esc(r.text)}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="8" style="color:var(--ink-muted);padding:20px 10px">No reviews match this filter.</td></tr>';
}
document.querySelectorAll('.filters button').forEach(b => {
  b.addEventListener('click', () => {
    filter = b.dataset.f;
    document.querySelectorAll('.filters button')
      .forEach(x => x.setAttribute('aria-pressed', String(x===b)));
    render();
  });
});
render();

/* ---------- controls ---------- */
$('#theme').addEventListener('click', () => {
  const cur = document.documentElement.getAttribute('data-theme');
  const next = cur === 'dark' ? 'light' : cur === 'light' ? 'dark'
    : (matchMedia('(prefers-color-scheme: dark)').matches ? 'light' : 'dark');
  document.documentElement.setAttribute('data-theme', next);
});
$('#tables').addEventListener('click', e => {
  const on = e.currentTarget.getAttribute('aria-pressed') !== 'true';
  e.currentTarget.setAttribute('aria-pressed', String(on));
  e.currentTarget.textContent = on ? 'Hide data tables' : 'Show data tables';
  document.querySelectorAll('.tblview').forEach(t => t.classList.toggle('on', on));
});

$('#foot').innerHTML =
  'Data: Amazon Reviews &rsquo;23, Gift Cards category, McAuley Lab, UC San Diego -  '
  + '<span class="mono">amazon-reviews-2023.github.io</span><br>'
  + 'Emotion word list: NRC Word-Emotion Association Lexicon (Mohammad &amp; Turney), used under its '
  + 'non-commercial research terms and not redistributed with this project.<br>'
  + 'Every figure on this page is read from the saved results file, not recomputed here. '
  + 'Page generated ' + String(DATA.generated_utc).replace('T',' ').replace('+00:00',' UTC') + '.';
</script>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", nargs="?", help="path to a results JSON file")
    args = parser.parse_args()

    path = (Path(args.results) if args.results else newest_results()).resolve()
    payload = json.loads(path.read_text())

    OUTPUT.write_text(build(payload))

    m = payload["metrics"]
    print(f"Read    {_short(path)}")
    print(f"Wrote   {_short(OUTPUT)}  ({OUTPUT.stat().st_size / 1024:.0f} KB)")
    print("\nFigures embedded, for checking against the page in the browser:")
    print(f"  agreement            {m['agreement_with_rating']:.4f}  -> {m['agreement_with_rating']*100:.1f}%")
    print(f"  majority baseline    {m['majority_class_baseline']:.4f}  -> {m['majority_class_baseline']*100:.1f}%")
    print(f"  scored / failed      {m['n_scored']} / {m['n_failed']}")
    for c, s in m["per_class"].items():
        if s["n"]:
            print(f"  {c:<9} accuracy  {s['correct']}/{s['n']} = {s['accuracy']*100:.1f}%")
    print("\nOpen it with:  open dashboard.html")


if __name__ == "__main__":
    main()
