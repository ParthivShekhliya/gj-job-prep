"""Builds exams.json from public Gujarat job RSS feeds (titles + links only). Python 3 standard library only."""
import json, re, html, time, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone

FEEDS = [
    "https://www.marugujarat.in/feed/",
    "https://www.marugujarat.in/category/gsssb/feed/",
    "https://www.marugujarat.in/category/gpsc/feed/",
    "https://www.marugujarat.in/category/getco/feed/",
]
PAGES = 5   # how many pages of each feed to read (each page = ~10 notices). Increase to go further back.
# EDIT HERE: add any exam/post name you want to be sure appears (one search per word)
SEARCH_TERMS = ["industry inspector", "industrial inspector", "wireless", "computer", "programmer", "engineer",
                "electrical", "civil", "mechanical", "technical", "inspector", "assistant", "clerk", "talati",
                "police", "teacher", "forest", "health worker", "GSSSB", "GPSC", "GPRB", "GETCO", "high court"]
SPECIAL = [(r"industr(y|ial) inspector", "cs,ec,el,me,oth")]   # posts open to non-civil engineers
def urls():
    for u in FEEDS:
        for p in range(1, PAGES + 1):
            yield u + ("&" if "?" in u else "?") + "paged=" + str(p)
    for t in SEARCH_TERMS:
        for p in (1, 2):
            yield "https://www.marugujarat.in/?s=" + urllib.parse.quote(t) + "&feed=rss2&paged=" + str(p)

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
    for rx, b in SPECIAL:
        if re.search(rx, title, re.I):
            branches = b.split(",")
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

# ---------- OFFICIAL SOURCE: OJAS portals (current + upcoming advertisements) ----------
OJAS_PAGES = ["https://ojas.gujarat.gov.in/", "https://gpsc-ojas.gujarat.gov.in/", "https://hc-ojas.gujarat.gov.in/"]
LAST = re.compile(r"^(.{4,300}?)\s*\(\s*(?:અંતિમ તારીખ|Last Date)\s*:?\s*(\d{1,2}-[A-Za-z]+-\d{4})\s*\)")

def to_text(h):
    h = re.sub(r"(?is)<(script|style).*?</\1>", "", h)
    h = re.sub(r"(?i)<br\s*/?>|</(p|li|tr|div|a|td|h\d)>", "\n", h)
    return html.unescape(re.sub(r"<[^>]+>", " ", h))

def gdate(d):
    for f in ("%d-%B-%Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(d, f).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return ""

def parse_ojas(h, src):
    t = to_text(h)
    cut = t.find("આવનાર જાહેરાત")            # section header: upcoming advertisements
    parts = [("now", t if cut < 0 else t[:cut])] + ([("soon", t[cut:])] if cut >= 0 else [])
    out = []
    for status, part in parts:
        for line in part.splitlines():
            m = LAST.search(re.sub(r"\s+", " ", line).strip())
            if not m:
                continue
            e = classify(m.group(1), "")
            e.update({"s": status, "fl": gdate(m.group(2)), "o": e["o"] if e["o"] != "Gujarat Govt" else "OJAS (official)",
                      "fs": "Official OJAS listing", "et": "Exam date: see notification", "l": src})
            out.append(e)
    return out

def ojas_all():
    out = []
    for u in OJAS_PAGES:
        try:
            h = fetch(u).decode("utf-8", "ignore")
        except Exception as ex:
            print("OJAS failed:", u, ex); continue
        out += parse_ojas(h, u)
        for href in re.findall(r"href=[\"']([^\"']+)[\"'][^>]*>\s*Show All", h, re.I)[:3]:
            try:
                out += parse_ojas(fetch(urllib.parse.urljoin(u, href)).decode("utf-8", "ignore"), u)
            except Exception as ex:
                print("Show All failed:", href, ex)
    print(len(out), "from OJAS")
    return out

def main():
    seen, exams = set(), []
    def add(e):
        k = re.sub(r"\W+", "", e["n"].lower())
        if k not in seen:
            seen.add(k); exams.append(e)
    for e in ojas_all():
        add(e)
    for u in urls():
        time.sleep(0.3)
        try:
            for e in parse(fetch(u)):
                add(e)
        except Exception as ex:
            print("feed failed:", u, ex)
    if not exams:
        raise SystemExit("no data fetched; keeping old exams.json")
    json.dump({"updated": datetime.now(timezone.utc).isoformat(), "exams": exams[:1500]},
              open("exams.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(exams), "exams written")

if __name__ == "__main__":
    main()
