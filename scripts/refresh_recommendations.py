from pathlib import Path
p=Path("scripts/refresh_recommendations.py")
s=p.read_text(encoding="utf-8")
s=s.replace(
'''    {"id":"aqz-KE-bpKQ","title":"Gaming Technology Showcase","channel":"YouTube discovery","category":"Gaming","duration":"","views":"Discovery","tags":["gaming","technology"]},
]''',
'''    {"id":"aqz-KE-bpKQ","title":"Gaming Technology Showcase","channel":"YouTube discovery","category":"Gaming","duration":"","views":"Discovery","tags":["gaming","technology"]},
    {"id":"jNQXAC9IVRw","title":"Me at the zoo","channel":"jawed","category":"Culture","duration":"0:19","views":"Classic","tags":["culture","youtube"]},
    {"id":"hY7m5jjJ9mM","title":"Cat Videos for When You Need a Break","channel":"The Pet Collective","category":"Relax","duration":"12:08","views":"Classic","tags":["relax","fun"]},
]''')
p.write_text(s,encoding="utf-8")
print("Added Culture and Relax seeds")
