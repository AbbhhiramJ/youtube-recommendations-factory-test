import json
import re
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

QUERIES = [
    "artificial intelligence technology",
    "programming python javascript",
    "machine learning tutorial",
    "science mathematics",
    "productivity study skills",
    "gaming technology",
    "new music",
]

class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.active = False
        self.href = ""
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "result__a" in attrs.get("class", ""):
            self.active = True
            self.href = attrs.get("href", "")
            self.parts = []

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.active:
            title = " ".join("".join(self.parts).split())
            if title and self.href:
                self.results.append((title, self.href))
            self.active = False

def youtube_url(href):
    if href.startswith("//"):
        href = "https:" + href
    parsed = urllib.parse.urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        href = urllib.parse.parse_qs(parsed.query).get("uddg", [""])[0]
        parsed = urllib.parse.urlparse(urllib.parse.unquote(href))
    if parsed.netloc not in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
        return None, None
    if parsed.netloc == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    else:
        video_id = urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id or ""):
        return None, None
    return f"https://www.youtube.com/watch?v={video_id}", video_id

def search(query):
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({
        "q": f"site:youtube.com/watch {query} 2026"
    })
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        html = response.read().decode("utf-8", "ignore")
    parser = Parser()
    parser.feed(html)
    out = []
    for title, href in parser.results:
        url, video_id = youtube_url(href)
        if url:
            out.append({
                "id": video_id,
                "title": title.replace(" - YouTube", "").strip(),
                "channel": "YouTube discovery",
                "category": "Discovery",
                "duration": "",
                "views": "Fresh result",
                "tags": re.findall(r"[a-z0-9+#.-]+", query.lower()),
            })
    return out

items = []
for query in QUERIES:
    for attempt in range(3):
        try:
            items.extend(search(query))
            break
        except Exception as exc:
            print(f"Search failed ({query}, attempt {attempt + 1}): {exc}")
            time.sleep(2 ** attempt)

unique = []
seen = set()
for item in items:
    if item["id"] not in seen:
        seen.add(item["id"])
        unique.append(item)
items = unique[:60]

path = Path("app.js")
source = path.read_text(encoding="utf-8")
payload = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
replacement = f"const fallbackVideos={payload};let videos="
updated, count = re.subn(r"const fallbackVideos=.*?;let videos=", replacement, source, count=1, flags=re.S)
if count != 1:
    raise SystemExit("Could not locate fallbackVideos in app.js")
path.write_text(updated, encoding="utf-8")
Path("recommendation-refresh-status.json").write_text(
    json.dumps({"items": len(items), "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=2),
    encoding="utf-8",
)
if len(items) < 10:
    raise SystemExit(f"Only {len(items)} usable YouTube results found; refusing to overwrite the app with a tiny feed.")
print(f"Updated {len(items)} recommendations")
