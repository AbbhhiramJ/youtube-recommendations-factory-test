from __future__ import annotations

import json
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

CHANNELS = [
    ("UCYO_jab_esuFRV4b17AJtAw", "3Blue1Brown", "Technology", ["ai", "math", "learning"]),
    ("UC8butISFwT-Wl7EV0hUK0BQ", "freeCodeCamp.org", "Coding", ["coding", "python", "javascript", "learning"]),
    ("UCWv7vMbMWH4-V0ZXdmDpPBA", "Programming with Mosh", "Coding", ["coding", "python", "javascript", "learning"]),
    ("UCoOae5nYA7VqaXzerajD0lg", "Ali Abdaal", "Productivity", ["productivity", "learning"]),
    ("UCBJycsmduvYEL83R_U4JriQ", "Marques Brownlee", "Technology", ["technology", "gadgets", "ai"]),
]

ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"


def fetch_feed(channel_id: str, channel: str, category: str, tags: list[str]) -> list[dict]:
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    request = urllib.request.Request(url, headers={"User-Agent": "watchlist-plus/1.0"})
    with urllib.request.urlopen(request, timeout=5) as response:
        root = ET.fromstring(response.read())

    items = []
    for entry in root.findall(f"{ATOM}entry"):
        video_id = entry.findtext(f"{YT}videoId", default="")
        title = entry.findtext(f"{ATOM}title", default="")
        published = entry.findtext(f"{ATOM}published", default="")
        if not video_id or not title:
            continue
        items.append({
            "id": video_id,
            "title": title.strip(),
            "channel": channel,
            "category": category,
            "duration": "",
            "views": "New upload",
            "tags": tags,
            "published": published,
        })
    return items


def build_items(query: str) -> tuple[list[dict], list[str]]:
    all_items: list[dict] = []
    failed: list[str] = []
    for channel_id, channel, category, tags in CHANNELS:
        try:
            all_items.extend(fetch_feed(channel_id, channel, category, tags))
        except Exception:
            failed.append(channel)

    terms = re.findall(r"[a-z0-9+#.-]+", query.lower())
    if terms:
        all_items = [
            item for item in all_items
            if any(
                term in (
                    item["title"] + " " + item["channel"] + " " +
                    item["category"] + " " + " ".join(item["tags"])
                ).lower()
                for term in terms
            )
        ]

    all_items.sort(key=lambda item: item.get("published", ""), reverse=True)
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
            payload = {
                "items": items,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "sources_ok": len(CHANNELS) - len(failed),
                "sources_failed": failed,
                "mode": "public-youtube-rss",
            }
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
        except Exception as exc:
            body = json.dumps({"items": [], "error": str(exc)}).encode("utf-8")
            self.send_response(500)

        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
