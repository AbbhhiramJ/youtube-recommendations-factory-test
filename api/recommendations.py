from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler

FALLBACK_QUERIES = [
    "artificial intelligence technology",
    "programming software engineering",
    "science mathematics learning",
    "productivity study skills",
    "gaming technology",
    "music new releases",
]

class SearchParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_result = False
        self.in_title = False
        self.href = ""
        self.title_parts = []
        self.results = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "")
        if tag == "a" and "result__a" in classes:
            self.in_result = True
            self.in_title = True
            self.href = attrs.get("href", "")
            self.title_parts = []

    def handle_data(self, data):
        if self.in_result and self.in_title:
            self.title_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.in_result:
            title = html.unescape(" ".join("".join(self.title_parts).split()))
            if title and self.href:
                self.results.append((title, self.href))
            self.in_result = False
            self.in_title = False


def clean_youtube_url(url: str) -> str | None:
    if url.startswith("//"):
        url = "https:" + url
    parsed = urllib.parse.urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = urllib.parse.parse_qs(parsed.query).get("uddg", [""])[0]
        url = urllib.parse.unquote(target)
        parsed = urllib.parse.urlparse(url)
    if parsed.netloc not in {"www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"}:
        return None
    if parsed.path.startswith("/watch"):
        video_id = urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
    elif parsed.netloc == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    else:
        video_id = parsed.path.split("/")[-1]
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id or ""):
        return None
    return f"https://www.youtube.com/watch?v={video_id}"


def search_youtube(query: str) -> list[dict]:
    search_url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({
        "q": f"site:youtube.com/watch {query} 2026"
    })
    request = urllib.request.Request(
        search_url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; watchlist-plus/1.0)",
            "Accept": "text/html",
        },
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        source = response.read().decode("utf-8", "ignore")
    parser = SearchParser()
    parser.feed(source)

    items = []
    for title, href in parser.results:
        url = clean_youtube_url(href)
        if not url:
            continue
        video_id = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("v", [""])[0]
        items.append({
            "id": video_id,
            "title": title.replace(" - YouTube", "").strip(),
            "channel": "YouTube discovery",
            "category": "Discovery",
            "duration": "",
            "views": "Fresh result",
            "tags": re.findall(r"[a-z0-9+#.-]+", query.lower()),
            "published": "",
            "url": url,
        })
    return items


def build_items(query: str) -> tuple[list[dict], list[str]]:
    queries = [query.strip()] if query.strip() else FALLBACK_QUERIES
    all_items = []
    failed = []
    for q in queries:
        try:
            all_items.extend(search_youtube(q))
        except Exception:
            failed.append(q)

    unique = []
    seen = set()
    for item in all_items:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        unique.append(item)

    return unique[:40], failed


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            query = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query
            ).get("q", [""])[0][:120]
            items, failed = build_items(query)
            body = json.dumps({
                "items": items,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "sources_ok": len(( [query] if query else FALLBACK_QUERIES )) - len(failed),
                "sources_failed": failed,
                "mode": "keyless-web-discovery",
            }, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
        except Exception as exc:
            body = json.dumps({"items": [], "error": str(exc)}).encode("utf-8")
            self.send_response(500)

        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
