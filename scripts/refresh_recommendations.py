import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

CHANNELS = [
    ("UCYO_jab_esuFRV4b17AJtAw", "3Blue1Brown", "Technology", ["ai", "math", "learning"]),
    ("UC8butISFwT-Wl7EV0hUK0BQ", "freeCodeCamp.org", "Coding", ["coding", "python", "javascript", "learning"]),
    ("UCWv7vMbMWH4-V0ZXdmDpPBA", "Programming with Mosh", "Coding", ["coding", "python", "javascript", "learning"]),
    ("UCoOae5nYA7VqaXzerajD0lg", "Ali Abdaal", "Productivity", ["productivity", "learning"]),
    ("UCBJycsmduvYEL83R_U4JriQ", "Marques Brownlee", "Technology", ["technology", "gadgets", "ai"]),
]

ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"

def fetch(channel_id, channel, category, tags):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 watchlist-refresh/1.0"})
            with urllib.request.urlopen(req, timeout=20) as response:
                root = ET.fromstring(response.read())
            rows = []
            for entry in root.findall(f"{ATOM}entry"):
                video_id = entry.findtext(f"{YT}videoId", "")
                title = entry.findtext(f"{ATOM}title", "")
                published = entry.findtext(f"{ATOM}published", "")
                if video_id and title:
                    rows.append({
                        "id": video_id,
                        "title": title.strip(),
                        "channel": channel,
                        "category": category,
                        "duration": "",
                        "views": "Fresh upload",
                        "tags": tags,
                        "published": published,
                    })
            return rows
        except Exception as exc:
            last = exc
            time.sleep(2 ** attempt)
    print(f"Feed failed for {channel}: {last}")
    return []

items = []
for args in CHANNELS:
    items.extend(fetch(*args))

items.sort(key=lambda x: x.get("published", ""), reverse=True)
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
print(f"Updated {len(items)} recommendations")
