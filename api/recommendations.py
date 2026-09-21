from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

app = FastAPI()

# Public YouTube channel feeds. RSS/Atom is used deliberately so the app
# can discover fresh uploads without a YouTube Data API key.
CHANNELS = [
    ("UCYO_jab_esuFRV4b17AJtAw", "3Blue1Brown", "Technology", ["ai", "math", "learning"]),
    ("UC8butISFwT-Wl7EV0hUK0BQ", "freeCodeCamp.org", "Coding", ["coding", "python", "javascript", "learning"]),
    ("UCWv7vMbMWH4-V0ZXdmDpPBA", "Programming with Mosh", "Coding", ["coding", "python", "javascript", "learning"]),
    ("UCoOae5nYA7VqaXzerajD0lg", "Ali Abdaal", "Productivity", ["productivity", "learning"]),
    ("UCBJycsmduvYEL83R_U4JriQ", "Marques Brownlee", "Technology", ["technology", "gadgets", "ai"]),
]

NS = {"yt": "http://www.youtube.com/xml/schemas/2015", "media": "http://search.yahoo.com/mrss/"}


def _feed(channel_id: str, channel: str, category: str, tags: list[str]) -> list[dict]:
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "watchlist-plus/1.0 (+https://youtube.com/)"},
    )
    with urllib.request.urlopen(request, timeout=7) as response:
        root = ET.fromstring(response.read())

    items = []
    for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
        video_id = entry.findtext("yt:videoId", default="", namespaces=NS)
        title = entry.findtext("{http://www.w3.org/2005/Atom}title", default="")
        published = entry.findtext("{http://www.w3.org/2005/Atom}published", default="")
        link = ""
        for node in entry.findall("{http://www.w3.org/2005/Atom}link"):
            if node.attrib.get("rel") == "alternate":
                link = node.attrib.get("href", "")
                break
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
            "url": link or f"https://www.youtube.com/watch?v={video_id}",
        })
    return items


@app.get("/api/recommendations")
def recommendations(q: str = Query(default="", max_length=120)) -> JSONResponse:
    all_items: list[dict] = []
    errors = []
    for channel_id, channel, category, tags in CHANNELS:
        try:
            all_items.extend(_feed(channel_id, channel, category, tags))
        except Exception as exc:
            errors.append(channel)
    needle = q.strip().lower()
    if needle:
        terms = re.findall(r"[a-z0-9+#.-]+", needle)
        all_items = [
            item for item in all_items
            if any(
                term in (item["title"] + " " + item["channel"] + " " + item["category"] + " " + " ".join(item["tags"])).lower()
                for term in terms
            )
        ]
    all_items.sort(key=lambda x: x.get("published", ""), reverse=True)
    seen = set()
    unique = []
    for item in all_items:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        unique.append(item)
    return JSONResponse({
        "items": unique[:40],
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sources_ok": len(CHANNELS) - len(errors),
        "sources_failed": errors,
        "mode": "public-youtube-rss",
    })
