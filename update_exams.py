"""Builds exams.json from public Gujarat job RSS feeds (titles + links only). Python 3 standard library only."""
import json, re, html, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone

FEEDS = [
    "https://www.marugujarat.in/feed/",
    "https://www.marugujarat.in/category/gsssb/feed/",
    "https://www.marugujarat.in/category/gpsc/feed/",
    "https://www.marugujarat.in/category/getco/feed/",
]
BOARDS = [("GSSSB", "GSSSB"), ("GPSC", "GPSC"), ("GPRB", "GPRB"), ("LRD", "GPRB"), ("PSI", "GPRB"),
          ("GETCO", "GETCO"), ("GUVNL", "GUVNL group"), ("MGVCL", "GUVNL group"), ("DGVCL", "GUVNL group"),
          ("UGVCL", "GUVNL group"), ("PGVCL", "GUVNL group"), ("High Court", "Gujarat High Court"),
          ("GSRTC", "GSRTC"), ("Talati", "GPSSB"), ("TET", "SEB"), ("TAT", "SEB"), ("Anganwadi", "WCD Gujarat")]
BRANCH = {"cs": r"computer|\bIT\b|programmer|system analyst|software|wireless|technical operator",
          "ec": r"electronic|communication|wireless|telecom",
          "el": r"electrical|vidyut|lineman|junior engineer|\bJE\b",
          "ci": r"civil|work assistant|draftsman",
          "me": r"mechanic|helper"}

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 GJPrepFeed"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()

def iso(d):
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", d or "")
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else ""

def classify(title, desc):
    t = title + " " + desc
    board = next((b for k, b in BOARDS if re.search(r"\b" + re.escape(k) + r"\b", t, re.I)), "Gujarat Govt")
    branches = [k for k, rx in BRANCH.items() if re.search(rx, title, re.I)]
    low = title.lower()
    status = "old" if re.search(r"result|answer key|selection list|merit list|final list", low) else "now"
    last = re.search(r"last date[^0-9]{0,25}(\d{1,2}[/-]\d{1,2}[/-]\d{4})", desc, re.I)
    posts = re.search(r"([\d,]{1,6})\s*posts", t, re.I)
    return {"n": re.sub(r"\s*[-|–]\s*MaruGujarat.*$", "", html.unescape(title)).strip(),
            "o": board, "s": status, "b": ",".join(branches) or "any",
            "p": posts.group(1).replace(",", "") if posts else "",
            "fl": iso(last.group(1)) if last else "",
            "fs": "Auto-detected from public feed – verify on OJAS", "ed": "", "et": "",
            "sy": "See official notification", "l": ""}

def parse(xml_bytes):
    out = []
    for it in ET.fromstring(xml_bytes).iter("item"):
        title = (it.findtext("title") or "").strip()
        desc = re.sub(r"<[^>]+>", " ", html.unescape(it.findtext("description") or ""))
        if not title:
            continue
        e = classify(title, desc)
        e["l"] = (it.findtext("link") or "").strip()
        e["et"] = "Posted " + (it.findtext("pubDate") or "")[:16]
        out.append(e)
    return out

def main():
    seen, exams = set(), []
    for u in FEEDS:
        try:
            for e in parse(fetch(u)):
                k = re.sub(r"\W+", "", e["n"].lower())
                if k not in seen:
                    seen.add(k); exams.append(e)
        except Exception as ex:
            print("feed failed:", u, ex)
    if not exams:
        raise SystemExit("no data fetched; keeping old exams.json")
    json.dump({"updated": datetime.now(timezone.utc).isoformat(), "exams": exams[:400]},
              open("exams.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(exams), "exams written")

if __name__ == "__main__":
    main()
