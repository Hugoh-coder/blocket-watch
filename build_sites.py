#!/usr/bin/env python3
"""Build the browsable web pages from watch.py JSON snapshots into docs/ (GitHub Pages).

  uv run watch.py --json      > std.json
  uv run watch.py xl61 --json > xl61.json
  python3 build_sites.py       # writes docs/index.html, docs/cyklar.html, docs/cyklar-xl.html

Facebook items come from watch.py itself when APIFY_TOKEN is set (see the Action), so
there's nothing to hand-edit here anymore."""
import datetime
import html as html_mod
import json
import pathlib
import re

HERE = pathlib.Path(__file__).parent
DOCS = HERE / "docs"
UPDATED = datetime.date.today().strftime("%-d %B %Y")


def load(name):
    p = HERE / name
    return json.loads(p.read_text())["items"] if p.exists() else []


def clean_xl(items):
    # drop cm-labelled bikes below 59 (e.g. "60 real 58" quirk that trips the cm regex)
    out = []
    for it in items:
        m = re.match(r"(\d{2})\s*cm", it.get("size", ""))
        if m and int(m.group(1)) < 59:
            continue
        out.append(it)
    return out


def dedupe(items):
    # same exact title across sources = one bike cross-posted; keep cheapest, note the other
    by_title = {}
    for it in items:
        k = it["title"].strip().lower()
        if k in by_title:
            keep, drop = sorted([by_title[k], it], key=lambda x: x["price"])
            if drop["src"] != keep["src"]:
                keep["note"] = f"Finns även på {drop['src']}"
            by_title[k] = keep
        else:
            by_title[k] = it
    return list(by_title.values())


def js(s):
    return json.dumps(s, ensure_ascii=False)


def build(items, out_name, title, size_line, dad_note=""):
    items = dedupe(items)
    items.sort(key=lambda x: (x["brand"], x["price"]))
    rows = "\n".join(
        "    {{ brand:{brand}, title:{title}, price:{price}, size:{size}, loc:{loc}, "
        "src:{src}, url:{url}{note} }},".format(
            brand=js(it["brand"]), title=js(it["title"]), price=it["price"],
            size=js(it.get("size", "")), loc=js(it["loc"]), src=js(it["src"]), url=js(it["url"]),
            note=(", note:" + js(it["note"])) if it.get("note") else "")
        for it in items)
    page = (PAGE_TPL.replace("__TITLE__", html_mod.escape(title))
            .replace("__SIZELINE__", html_mod.escape(size_line))
            .replace("__COUNT__", str(len(items)))
            .replace("__UPDATED__", UPDATED)
            .replace("__DADNOTE__", dad_note)
            .replace("__ROWS__", rows))
    (DOCS / out_name).write_text(page)
    print(f"wrote docs/{out_name}: {len(items)} bikes")


STYLE = r"""<style>
  :root {
    --bg:#f5f3ee; --surface:#fffefb; --ink:#23272b; --ink-soft:#5b6167; --line:#e0dcd2;
    --accent:#0e9b8a; --accent-ink:#fff; --chip:#e7f3f1; --chip-ink:#0c6d61;
    --shadow:0 1px 2px rgba(30,30,30,.05), 0 6px 16px rgba(30,30,30,.06);
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#14171a; --surface:#1d2125; --ink:#eef0f2; --ink-soft:#a2abb2; --line:#30363c;
      --accent:#3fd0bd; --accent-ink:#0c1214; --chip:#17342f; --chip-ink:#6fe0d0;
      --shadow:0 1px 2px rgba(0,0,0,.3), 0 6px 18px rgba(0,0,0,.35); }
  }
  :root[data-theme="light"] { --bg:#f5f3ee; --surface:#fffefb; --ink:#23272b; --ink-soft:#5b6167;
    --line:#e0dcd2; --accent:#0e9b8a; --accent-ink:#fff; --chip:#e7f3f1; --chip-ink:#0c6d61;
    --shadow:0 1px 2px rgba(30,30,30,.05), 0 6px 16px rgba(30,30,30,.06); }
  :root[data-theme="dark"] { --bg:#14171a; --surface:#1d2125; --ink:#eef0f2; --ink-soft:#a2abb2;
    --line:#30363c; --accent:#3fd0bd; --accent-ink:#0c1214; --chip:#17342f; --chip-ink:#6fe0d0;
    --shadow:0 1px 2px rgba(0,0,0,.3), 0 6px 18px rgba(0,0,0,.35); }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
    font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; line-height:1.5;
    -webkit-font-smoothing:antialiased; }
  .wrap { max-width:940px; margin:0 auto; padding:0 18px; }
  header { position:sticky; top:0; z-index:10;
    background:color-mix(in srgb, var(--bg) 88%, transparent); backdrop-filter:blur(8px);
    border-bottom:1px solid var(--line); }
  .head-inner { padding:18px 18px 14px; max-width:940px; margin:0 auto; }
  h1 { margin:0; font-size:1.5rem; font-weight:800; letter-spacing:-.02em; text-wrap:balance; }
  .sub { margin:3px 0 0; color:var(--ink-soft); font-size:.9rem; }
  .sub b { color:var(--ink); font-variant-numeric:tabular-nums; }
  .dad { margin:11px 0 0; padding:9px 13px; background:var(--chip); color:var(--chip-ink);
    border-radius:9px; font-size:.85rem; }
  .back { display:inline-block; margin:0 0 2px; color:var(--accent); text-decoration:none;
    font-size:.82rem; font-weight:600; }
  .controls { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-top:13px; }
  .filters { display:flex; flex-wrap:wrap; gap:6px; }
  button.f, button.sort { font:inherit; font-size:.85rem; font-weight:600; padding:6px 13px;
    border-radius:999px; border:1px solid var(--line); background:var(--surface);
    color:var(--ink-soft); cursor:pointer; transition:background .15s,color .15s,border-color .15s; }
  button.f:hover, button.sort:hover { border-color:var(--accent); color:var(--ink); }
  button.f.on { background:var(--accent); color:var(--accent-ink); border-color:var(--accent); }
  .sort { margin-left:auto; }
  button.f:focus-visible, button.sort:focus-visible, a.card:focus-visible, a.big:focus-visible {
    outline:2px solid var(--accent); outline-offset:2px; }
  main { padding:20px 0 60px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(270px,1fr)); gap:14px; }
  a.card { display:flex; flex-direction:column; gap:9px; background:var(--surface);
    border:1px solid var(--line); border-radius:14px; padding:15px 16px 16px;
    text-decoration:none; color:inherit; box-shadow:var(--shadow);
    transition:transform .12s,border-color .12s; }
  a.card:hover { transform:translateY(-2px); border-color:var(--accent); }
  .card-top { display:flex; justify-content:space-between; align-items:baseline; gap:10px; }
  .brand { font-size:.7rem; font-weight:700; text-transform:uppercase; letter-spacing:.07em;
    color:var(--chip-ink); background:var(--chip); padding:3px 9px; border-radius:6px; white-space:nowrap; }
  .price { font-size:1.28rem; font-weight:800; letter-spacing:-.01em;
    font-variant-numeric:tabular-nums; white-space:nowrap; }
  .title { font-size:.98rem; font-weight:600; line-height:1.35; }
  .meta { display:flex; flex-wrap:wrap; gap:6px 12px; color:var(--ink-soft); font-size:.82rem; margin-top:2px; }
  .meta .loc::before { content:"📍 "; }
  .size { color:var(--ink); font-weight:600; }
  .note { font-size:.76rem; color:var(--ink-soft); font-style:italic; }
  .row-bottom { display:flex; justify-content:space-between; align-items:center; margin-top:auto; padding-top:5px; }
  .src { font-size:.74rem; color:var(--ink-soft); }
  .go { font-size:.85rem; font-weight:700; color:var(--accent); }
  .empty { text-align:center; color:var(--ink-soft); padding:50px 20px; font-size:.95rem; }
  footer { border-top:1px solid var(--line); padding:22px 0 40px; color:var(--ink-soft); font-size:.8rem; }
  footer p { margin:0 0 7px; }
  footer b { color:var(--ink); }
  .choose { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:16px; margin-top:26px; }
  a.big { display:block; background:var(--surface); border:1px solid var(--line); border-radius:16px;
    padding:24px; text-decoration:none; color:inherit; box-shadow:var(--shadow);
    transition:transform .12s,border-color .12s; }
  a.big:hover { transform:translateY(-2px); border-color:var(--accent); }
  a.big .em { font-size:2rem; }
  a.big h2 { margin:8px 0 4px; font-size:1.2rem; }
  a.big p { margin:0; color:var(--ink-soft); font-size:.9rem; }
</style>"""

PAGE_TPL = "<title>__TITLE__</title>\n" + STYLE + r"""
<header><div class="head-inner">
  <a class="back" href="./">← Alla listor</a>
  <h1>__TITLE__ 🚲</h1>
  <p class="sub"><b id="count">__COUNT__</b> begagnade landsvägscyklar i hela Sverige · Trek · Specialized · Canyon · Bianchi · __SIZELINE__ · 10 000–25 000 kr</p>
  __DADNOTE__
  <div class="controls">
    <div class="filters" id="filters"></div>
    <button class="sort" id="sortBtn">Pris: lägst först ↑</button>
  </div>
</div></header>
<main><div class="wrap">
  <div class="grid" id="grid"></div>
  <div class="empty" id="empty" hidden>Inga cyklar för det här märket i prisklassen just nu.</div>
</div></main>
<footer><div class="wrap">
  <p>Uppdaterad <b>__UPDATED__</b>. Uppdateras automatiskt varje morgon. Klicka på en cykel för att öppna annonsen.</p>
  <p>Källor: Blocket, Happyride, Sportson Begagnat och Facebook Marketplace. Priser och tillgänglighet kan ändras — annonsen gäller.</p>
</div></footer>
<script>
  const bikes = [
__ROWS__
  ];
  const brands = ["Alla", "Trek", "Specialized", "Canyon", "Bianchi"];
  let activeBrand = "Alla", sortAsc = true;
  const filtersEl = document.getElementById("filters");
  brands.forEach(b => {
    const btn = document.createElement("button");
    btn.className = "f" + (b === "Alla" ? " on" : "");
    btn.textContent = b;
    btn.onclick = () => { activeBrand = b;
      document.querySelectorAll("button.f").forEach(x => x.classList.toggle("on", x.textContent === b));
      render(); };
    filtersEl.appendChild(btn);
  });
  const sortBtn = document.getElementById("sortBtn");
  sortBtn.onclick = () => { sortAsc = !sortAsc;
    sortBtn.textContent = sortAsc ? "Pris: lägst först ↑" : "Pris: högst först ↓"; render(); };
  const kr = n => n.toLocaleString("sv-SE") + " kr";
  function render() {
    const grid = document.getElementById("grid"), empty = document.getElementById("empty");
    let list = bikes.filter(b => activeBrand === "Alla" || b.brand === activeBrand);
    list.sort((a, b) => sortAsc ? a.price - b.price : b.price - a.price);
    document.getElementById("count").textContent = list.length;
    grid.innerHTML = ""; empty.hidden = list.length > 0;
    for (const b of list) {
      const a = document.createElement("a");
      a.className = "card"; a.href = b.url; a.target = "_blank"; a.rel = "noopener";
      a.innerHTML = `
        <div class="card-top"><span class="brand">${b.brand}</span><span class="price">${kr(b.price)}</span></div>
        <div class="title">${b.title}</div>
        <div class="meta">${b.size ? `<span class="size">Storlek ${b.size}</span>` : ``}<span class="loc">${b.loc}</span></div>
        ${b.note ? `<div class="note">${b.note}</div>` : ``}
        <div class="row-bottom"><span class="src">${b.src}</span><span class="go">Visa annons →</span></div>`;
      grid.appendChild(a);
    }
  }
  render();
</script>
"""

INDEX_TPL = "<title>Racercyklar till salu</title>\n" + STYLE + r"""
<header><div class="head-inner">
  <h1>Racercyklar till salu 🚲</h1>
  <p class="sub">Begagnade landsvägscyklar i hela Sverige · Trek · Specialized · Canyon · Bianchi · 10 000–25 000 kr · uppdateras varje morgon</p>
</div></header>
<main><div class="wrap">
  <div class="choose">
    <a class="big" href="cyklar.html">
      <div class="em">🚲</div><h2>Min storlek</h2>
      <p>Storlek L / XL / 58 cm — <b id="a">__CA__</b> cyklar</p>
    </a>
    <a class="big" href="cyklar-xl.html">
      <div class="em">👴</div><h2>Pappas storlek</h2>
      <p>Storlek XL / 61 cm — <b id="b">__CB__</b> cyklar</p>
    </a>
  </div>
</div></main>
<footer><div class="wrap"><p>Uppdaterad <b>__UPDATED__</b>. Källor: Blocket, Happyride, Sportson, Facebook Marketplace.</p></div></footer>
"""

DOCS.mkdir(exist_ok=True)

std = load("std.json")
build(std, "cyklar.html", "Racercyklar till salu", "storlek L / XL / 58 cm")

xl = clean_xl(load("xl61.json"))
dad = ('<p class="dad">👴 Pappas storlek: XL / 61 cm. Det här är en smal nisch — '
       'få cyklar av just dessa märken finns i den storleken och prisklassen just nu.</p>')
build(xl, "cyklar-xl.html", "Racercyklar XL / 61 cm", "storlek XL / 60–62 cm", dad_note=dad)

count_a = len(dedupe(std))
count_b = len(dedupe(clean_xl(load("xl61.json"))))
(DOCS / "index.html").write_text(
    INDEX_TPL.replace("__CA__", str(count_a)).replace("__CB__", str(count_b)).replace("__UPDATED__", UPDATED))
print(f"wrote docs/index.html")
