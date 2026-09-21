import json
import re
import subprocess
import time
from pathlib import Path

QUERY_CATEGORIES = [
    ("artificial intelligence technology 2026", "Technology"),
    ("programming python javascript 2026", "Coding"),
    ("machine learning tutorial 2026", "Technology"),
    ("science mathematics 2026", "Technology"),
    ("productivity study skills 2026", "Productivity"),
    ("gaming technology 2026", "Gaming"),
    ("new music 2026", "Music"),
    ("culture documentary 2026", "Culture"),
]

REFRESH_FIX = r"""
(function(){
  if(window.__recommendationRefreshFix)return;
  window.__recommendationRefreshFix=true;
  const originalRender=render;
  function normalizeCategory(v){
    const text=((v.category||"")+" "+(v.title||"")+" "+(v.channel||"")+" "+((v.tags||[]).join(" "))).toLowerCase();
    if(text.match(/\b(music|song|album|concert|singer|dj)\b/))return "Music";
    if(text.match(/\b(python|javascript|programming|coding|developer|software|code|react|java)\b/))return "Coding";
    if(text.match(/\b(productivity|study|focus|habits|planning|notion|time management)\b/))return "Productivity";
    if(text.match(/\b(gaming|game|xbox|playstation|nintendo|steam|gpu)\b/))return "Gaming";
    if(text.match(/\b(culture|history|documentary|society|art|film)\b/))return "Culture";
    if(text.match(/\b(ai|artificial intelligence|machine learning|science|technology|tech|robot|quantum)\b/))return "Technology";
    return v.category || "Technology";
  }
  function normalizedRender(){
    if(Array.isArray(videos))videos.forEach(v=>{v.category=normalizeCategory(v);});
    return originalRender();
  }
  render=normalizedRender;
  normalizedRender();
  const refresh=document.querySelector('#refresh');
  if(refresh){
    refresh.onclick=()=>{
      const pool=videos.filter(v=>!state.trash.includes(v.id));
      for(let i=pool.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[pool[i],pool[j]]=[pool[j],pool[i]];}
      const originalVideos=videos;
      videos=pool.concat(videos.filter(v=>state.trash.includes(v.id)));
      normalizedRender();
      videos=originalVideos;
      refresh.textContent='Refreshed ✓';
      setTimeout(()=>refresh.textContent='Refresh recommendations ↻',1400);
    };
  }
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
        rows.append((video_id, title.strip(), channel.strip()))
    return rows

items = []
for query, category in QUERY_CATEGORIES:
    for attempt in range(2):
        try:
            for video_id, title, channel in search(query):
                items.append({
                    "id": video_id,
                    "title": title,
                    "channel": channel or "YouTube discovery",
                    "category": category,
                    "duration": "",
                    "views": "Fresh result",
                    "tags": re.findall(r"[a-z0-9+#.-]+", query.lower()),
                })
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
if "window.__recommendationRefreshFix" not in updated:
    updated += "\n" + REFRESH_FIX + "\n"
path.write_text(updated, encoding="utf-8")

Path("recommendation-refresh-status.json").write_text(
    json.dumps({
        "items": len(items),
        "categories": {c: sum(1 for x in items if x["category"] == c) for _, c in QUERY_CATEGORIES},
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }, indent=2),
    encoding="utf-8",
)
print(f"Updated {len(items)} recommendations with category metadata")
