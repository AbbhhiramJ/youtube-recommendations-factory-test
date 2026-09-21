from __future__ import annotations

import json
import random
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

CLIENT_VERSION = "2.20260114.08.00"
BASE_URL = "https://www.youtube.com/youtubei/v1/search?prettyPrint=false"

QUERY_BANK = {
    "Technology": [
        "technology 2026", "artificial intelligence 2026", "AI news 2026",
        "machine learning 2026", "future technology 2026", "robotics 2026",
        "space technology 2026", "new gadgets 2026",
    ],
    "Coding": [
        "programming 2026", "Python 2026", "JavaScript 2026",
        "software engineering 2026", "web development 2026",
        "AI coding 2026", "open source 2026", "developer tools 2026",
    ],
    "Music": [
        "new music 2026", "new songs 2026", "music releases 2026",
        "live music 2026", "music discovery 2026",
    ],
    "Productivity": [
        "productivity 2026", "study skills 2026", "focus techniques 2026",
        "student productivity 2026", "time management 2026",
    ],
    "Culture": [
        "culture 2026", "history documentary 2026", "art 2026",
        "documentary 2026", "society 2026", "film culture 2026",
    ],
    "Gaming": [
        "gaming 2026", "new games 2026", "gaming technology 2026",
        "PC gaming 2026", "console gaming 2026", "game development 2026",
    ],
    "Relax": [
        "relaxing videos", "calm music", "nature relaxing 2026",
        "funny animals", "ambient 2026", "sleep sounds",
    ],
}

def text_of(value: object) -> str:
    if isinstance(value, dict):
        if isinstance(value.get("simpleText"), str):
            return value["simpleText"]
        runs = value.get("runs")
        if isinstance(runs, list):
            return "".join(
                run.get("text", "") for run in runs if isinstance(run, dict)
            )
    return ""

def walk_video_renderers(node: object):
    if isinstance(node, dict):
        renderer = node.get("videoRenderer")
        if isinstance(renderer, dict) and renderer.get("videoId"):
            yield renderer
        for value in node.values():
            yield from walk_video_renderers(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_video_renderers(value)

def find_continuation(node: object) -> str | None:
    if isinstance(node, dict):
        command = node.get("continuationCommand")
        if isinstance(command, dict) and command.get("token"):
            return command["token"]
        endpoint = node.get("continuationEndpoint")
        if isinstance(endpoint, dict):
            command = endpoint.get("continuationCommand")
            if isinstance(command, dict) and command.get("token"):
                return command["token"]
        for value in node.values():
            token = find_continuation(value)
            if token:
                return token
    elif isinstance(node, list):
        for value in node:
            token = find_continuation(value)
            if token:
                return token
    return None

def youtube_search(query: str, continuation: str | None = None) -> tuple[list[dict], str | None]:
    body = {
        "context": {
            "client": {
                "clientName": "WEB",
                "clientVersion": CLIENT_VERSION,
                "hl": "en",
                "gl": "IN",
            }
        }
    }
    if continuation:
        body["continuation"] = continuation
    else:
        body["query"] = query

    request = urllib.request.Request(
        BASE_URL,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0 Safari/537.36"
            ),
            "X-YouTube-Client-Name": "1",
            "X-YouTube-Client-Version": CLIENT_VERSION,
            "Origin": "https://www.youtube.com",
            "Referer": "https://www.youtube.com/",
            "Accept-Language": "en-IN,en;q=0.9",
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8", "ignore"))

    items = []
    seen = set()
    for renderer in walk_video_renderers(data):
        video_id = renderer.get("videoId")
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", str(video_id)):
            continue
        if video_id in seen:
            continue
        seen.add(video_id)
        title = text_of(renderer.get("title")) or "Untitled video"
        channel = text_of(renderer.get("ownerText")) or "YouTube"
        duration = text_of(renderer.get("lengthText"))
        views = text_of(renderer.get("viewCountText"))
        published = text_of(renderer.get("publishedTimeText"))
        thumbnail = (
            renderer.get("thumbnail", {})
            .get("thumbnails", [{}])[-1]
            .get("url", f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg")
        )
        items.append({
            "id": video_id,
            "title": title,
            "channel": channel,
            "category": "Discovery",
            "duration": duration,
            "views": views or "Fresh result",
            "tags": re.findall(r"[a-z0-9+#.-]+", query.lower()),
            "published": published,
            "thumbnail": thumbnail,
            "url": f"https://www.youtube.com/watch?v={video_id}",
        })
    return items, find_continuation(data)

def category_from_query(query: str) -> str:
    q = query.lower()
    for category, terms in QUERY_BANK.items():
        if any(term.lower().replace(" 2026", "") in q for term in terms):
            return category
    return "Discovery"

def build_items(query: str) -> tuple[list[dict], list[str]]:
    if query.strip():
        selected = [query.strip()[:120]]
    else:
        categories = list(QUERY_BANK)
        random.shuffle(categories)
        selected = [random.choice(QUERY_BANK[c]) for c in categories[:4]]

    all_items = []
    failed = []
    used_queries = set()

    for selected_query in selected:
        if selected_query in used_queries:
            continue
        used_queries.add(selected_query)
        try:
            page_one, continuation = youtube_search(selected_query)
            page_items = page_one

            # Pull one additional live continuation page. This makes each refresh
            # explore beyond the first search page instead of recycling a local pool.
            if continuation and len(page_items) < 30:
                page_two, _ = youtube_search(selected_query, continuation)
                page_items.extend(page_two)

            category = category_from_query(selected_query)
            for item in page_items:
                item["category"] = category
            all_items.extend(page_items)
        except Exception as exc:
            failed.append(f"{selected_query}: {type(exc).__name__}")

    unique = []
    seen = set()
    random.shuffle(all_items)
    for item in all_items:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        unique.append(item)

    return unique[:60], failed

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            query = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query
            ).get("q", [""])[0]
            items, failed = build_items(query)
            body = json.dumps({
                "items": items,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "sources_ok": max(0, 4 - len(failed)) if not query else int(not failed),
                "sources_failed": failed,
                "mode": "live-youtube-innertube-discovery",
                "source": "youtube-search",
            }, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
        except Exception as exc:
            body = json.dumps({
                "items": [],
                "error": f"live YouTube discovery failed: {type(exc).__name__}",
            }).encode("utf-8")
            self.send_response(500)

        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
