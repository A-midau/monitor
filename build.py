"""Reads sources.json, picks the best items, writes index.html."""
import json, re, time, html, datetime as dt, urllib.request
import feedparser

cfg = json.load(open("sources.json", encoding="utf-8"))
S = cfg["settings"]
UA = "Mozilla/5.0 (personal-digest)"
now = time.time()
cutoff = now - S["hours"] * 3600
errors = []

def yt_feed(handle):
    req = urllib.request.Request(f"https://www.youtube.com/{handle}",
        headers={"User-Agent": UA, "Cookie": "CONSENT=YES+1"})
    page = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
    m = re.search(r'"channelId":"(UC[\w-]{22})"', page) or re.search(r'channel_id=(UC[\w-]{22})', page)
    if not m: raise ValueError("channel id not found")
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={m.group(1)}"

candidates = []
for src in cfg["sources"]:
    try:
        url = src.get("url") or yt_feed(src["youtube"])
        d = feedparser.parse(url, agent=UA)
        if not d.entries:
            errors.append(f"{src['name']}: no entries"); continue
        picked = 0
        for rank, e in enumerate(d.entries):
            t = e.get("published_parsed") or e.get("updated_parsed")
            ts = time.mktime(t) if t else now
            if ts < cutoff: continue
            age_h = (now - ts) / 3600
            # priority dominates, then freshness, then position in ranked feeds
            score = src.get("priority", 1) * 10 - age_h / 6 - (rank * 1.5 if src.get("ranked") else 0)
            vid = e.get("yt_videoid")
            candidates.append(dict(src=src["name"], type=src["type"], title=e.get("title", "(no title)").strip(),
                link=e.get("link", "#"), ts=ts, score=score,
                thumb=f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg" if vid else ""))
    except Exception as ex:
        errors.append(f"{src['name']}: {str(ex)[:60]}")

candidates.sort(key=lambda c: c["score"], reverse=True)
chosen, per, seen = [], {}, set()
for c in candidates:
    key = re.sub(r"\W+", "", c["title"].lower())
    if key in seen or per.get(c["src"], 0) >= S["per_source_cap"]: continue
    seen.add(key); per[c["src"]] = per.get(c["src"], 0) + 1; chosen.append(c)
    if len(chosen) >= S["max_items"]: break
chosen.sort(key=lambda c: c["ts"], reverse=True)

LABEL = {"model": "Model", "tool": "Tool", "video": "Video", "discussion": "Discussion"}
rows = ""
for c in chosen:
    th = f'<img src="{html.escape(c["thumb"])}" alt="" loading="lazy">' if c["thumb"] else ""
    rows += (f'<a class="item" href="{html.escape(c["link"])}" target="_blank" rel="noopener" '
             f'data-type="{c["type"]}" data-ts="{int(c["ts"]*1000)}">{th}<div class="body">'
             f'<div class="meta"><span class="tag {c["type"]}">{LABEL.get(c["type"], c["type"])}</span>'
             f'<span>{html.escape(c["src"])}</span><span class="when"></span></div>'
             f'<div class="title">{html.escape(c["title"])}</div></div><i class="dot"></i></a>')
if not rows: rows = '<p class="empty">Nothing new right now.</p>'
updated = int(now * 1000)
err = f'<p class="issues">Sources with issues: {html.escape("; ".join(errors))}</p>' if errors else ""

page = open("template.html", encoding="utf-8").read()
page = page.replace("{{ROWS}}", rows).replace("{{UPDATED}}", str(updated)).replace("{{ERRORS}}", err)
open("index.html", "w", encoding="utf-8").write(page)
print(f"Built index.html with {len(chosen)} items, {len(errors)} source issues")
