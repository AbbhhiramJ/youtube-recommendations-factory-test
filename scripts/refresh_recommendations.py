import json
import re
import subprocess
import time
from pathlib import Path

QUERIES = [
    "artificial intelligence technology 2026",
    "programming python javascript 2026",
    "machine learning tutorial 2026",
    "science mathematics 2026",
    "productivity study skills 2026",
    "gaming technology 2026",
    "new music 2026",
]

REFRESH_FIX = r"""
(function(){
  const refreshButton=document.querySelector('#refresh');
  if(!refreshButton)return;
  refreshButton.onclick=()=>{
    const cards=[...document.querySelectorAll('#exploreGrid .card')];
    if(cards.length<2)return;
    for(let i=cards.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[cards[i],cards[j]]=[cards[j],cards[i]];}
    document.querySelector('#recommendations').innerHTML=cards.slice(0,6).map(c=>c.outerHTML).join('');
    refreshButton.textContent='Refreshed ✓';
    setTimeout(()=>refreshButton.textContent='Refresh recommendations ↻',1400);
  };
})();
"""

def search(query):
    cmd = [
        "yt-dlp", f"ytsearch10:{query}", "--flat-playlist",
        "--skip-download", "--print", "%(id)s\t%(title)s\t%(uploader)s",
        "--no-warnings",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[-500:])
    rows = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        video_id, title, channel = parts
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            continue
        rows.append({
            "id": video_id,
            "title": title.strip(),
            "channel": channel.strip() or "YouTube discovery",
            "category": "Discovery",
            "duration": "",
            "views": "Fresh result",
            "tags": re.findall(r"[a-z0-9+#.-]+", query.lower()),
        })
    return rows

items = []
for query in QUERIES:
    for attempt in range(2):
        try:
            items.extend(search(query))
            break
        except Exception as exc:
            print(f"Search failed ({query}, attempt {attempt + 1}): {exc}")
            time.sleep(2)

unique = []
seen = set()
for item in items:
    if item["id"] not in seen:
        seen.add(item["id"])
        unique.append(item)
items = unique[:60]

if len(items) < 10:
    raise SystemExit(f"Only {len(items)} usable YouTube results found; refusing to overwrite the app with a tiny feed.")

path = Path("app.js")
source = path.read_text(encoding="utf-8")
payload = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
replacement = f"const fallbackVideos={payload};let videos="
updated, count = re.subn(r"const fallbackVideos=.*?;let videos=", replacement, source, count=1, flags=re.S)
if count != 1:
    raise SystemExit("Could not locate fallbackVideos in app.js")
if "refreshButton.onclick=()=>{" not in updated:
    updated += "\n" + REFRESH_FIX + "\n"
path.write_text(updated, encoding="utf-8")

Path("recommendation-refresh-status.json").write_text(
    json.dumps({"items": len(items), "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=2),
    encoding="utf-8",
)
print(f"Updated {len(items)} recommendations")
