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

SEEDS = [
    {"id":"dQw4w9WgXcQ","title":"Never Gonna Give You Up","channel":"Rick Astley","category":"Music","duration":"3:33","views":"Classic","tags":["music"]},
    {"id":"kJQP7kiw5Fk","title":"Luis Fonsi - Despacito ft. Daddy Yankee","channel":"Luis Fonsi","category":"Music","duration":"4:42","views":"Classic","tags":["music","latin"]},
    {"id":"aqz-KE-bpKQ","title":"Gaming Technology Showcase","channel":"YouTube discovery","category":"Gaming","duration":"","views":"Discovery","tags":["gaming","technology"]},
    {"id":"jNQXAC9IVRw","title":"Me at the zoo","channel":"jawed","category":"Culture","duration":"0:19","views":"Classic","tags":["culture","youtube"]},
    {"id":"hY7m5jjJ9mM","title":"Cat Videos for When You Need a Break","channel":"The Pet Collective","category":"Relax","duration":"12:08","views":"Classic","tags":["relax","fun"]},
]

REFRESH_FIX = r"""(function(){
if(window.__recommendationRefreshFix)return;
window.__recommendationRefreshFix=true;
const originalRender=render;
function normalizeCategory(v){
 const text=((v.category||"")+" "+(v.title||"")+" "+(v.channel||"")+" "+((v.tags||[]).join(" "))).toLowerCase();
 if(/\b(music|song|album|concert|singer|dj)\b/.test(text))return "Music";
 if(/\b(python|javascript|programming|coding|developer|software|code|react|java)\b/.test(text))return "Coding";
 if(/\b(productivity|study|focus|habits|planning|notion|time management)\b/.test(text))return "Productivity";
 if(/\b(gaming|game|xbox|playstation|nintendo|steam|gpu)\b/.test(text))return "Gaming";
 if(/\b(culture|history|documentary|society|art|film)\b/.test(text))return "Culture";
 if(/\b(relax|calm|meditation|sleep|pets|fun)\b/.test(text))return "Relax";
 if(/\b(ai|artificial intelligence|machine learning|science|technology|tech|robot|quantum)\b/.test(text))return "Technology";
 return v.category||"Technology";
}
function normalizedRender(){
 if(Array.isArray(videos))videos.forEach(v=>v.category=normalizeCategory(v));
 const result=originalRender();
 const available=videos.filter(v=>!state.trash.includes(v.id)).length;
 if(available===0 && !window.__autoRefillPending && typeof loadRecommendations==="function"){
   window.__autoRefillPending=true;
   setTimeout(async()=>{
     try{await loadRecommendations();}
     finally{window.__autoRefillPending=false;}
   },120);
 }
 return result;
}
render=normalizedRender;
normalizedRender();
const refresh=document.querySelector('#refresh');
if(refresh){
 refresh.onclick=()=>{
   loadRecommendations();
 };
}
})();"""

def search(query):
    result = subprocess.run(
        ["yt-dlp", f"ytsearch10:{query}", "--flat-playlist", "--skip-download",
         "--print", "%(id)s\t%(title)s\t%(uploader)s", "--no-warnings"],
        capture_output=True, text=True, timeout=45
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[-500:])
    rows=[]
    for line in result.stdout.splitlines():
        parts=line.split("\t",2)
        if len(parts)==3 and re.fullmatch(r"[A-Za-z0-9_-]{11}",parts[0]):
            rows.append((parts[0],parts[1].strip(),parts[2].strip()))
    return rows

items=[]
for query,category in QUERY_CATEGORIES:
    for attempt in range(2):
        try:
            for video_id,title,channel in search(query):
                items.append({
                    "id":video_id,"title":title,
                    "channel":channel or "YouTube discovery",
                    "category":category,"duration":"",
                    "views":"Fresh result",
                    "tags":re.findall(r"[a-z0-9+#.-]+",query.lower())
                })
            break
        except Exception as exc:
            print(f"Search failed ({query}, attempt {attempt+1}): {exc}")
            time.sleep(2)

unique=[];seen=set()
for item in items:
    if item["id"] not in seen:
        seen.add(item["id"]);unique.append(item)

seed_ids={x["id"] for x in SEEDS}
unique=[x for x in unique if x["id"] not in seed_ids]
items=unique[:60-len(SEEDS)]+SEEDS

if len(items)<10:
    raise SystemExit(f"Only {len(items)} usable recommendations found")

path=Path("app.js")
source=path.read_text(encoding="utf-8")
payload=json.dumps(items,ensure_ascii=False,separators=(",",":"))
updated,count=re.subn(
    r"const fallbackVideos=.*?;let videos=",
    f"const fallbackVideos={payload};let videos=",
    source,count=1,flags=re.S
)
if count!=1:
    raise SystemExit("Could not locate fallbackVideos in app.js")

updated=updated.replace(
    "['All','Technology','Coding','Music','Productivity','Culture','Relax']",
    "['All','Technology','Coding','Music','Productivity','Culture','Gaming','Relax']"
)
updated=updated.replace(
    '["All","Technology","Coding","Music","Productivity","Culture","Relax"]',
    "['All','Technology','Coding','Music','Productivity','Culture','Gaming','Relax']"
)

if "window.__recommendationRefreshFix" not in updated:
    updated += "\n"+REFRESH_FIX+"\n"

path.write_text(updated,encoding="utf-8")

Path("recommendation-refresh-status.json").write_text(
    json.dumps({
        "items":len(items),
        "categories":{
            c:sum(1 for x in items if x["category"]==c)
            for _,c in QUERY_CATEGORIES
        },
        "updated":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
    },indent=2),
    encoding="utf-8"
)
print("Updated",len(items),"fallback recommendations with auto-refill hook")
