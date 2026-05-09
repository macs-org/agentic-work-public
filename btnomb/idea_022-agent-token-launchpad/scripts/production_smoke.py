import json, sys, urllib.request
base=sys.argv[1].rstrip("/")
checks=[]
def get(p,h=None):
    req=urllib.request.Request(base+p, headers=h or {"User-Agent":"AgenticWorkSmoke/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        b=r.read(); checks.append({"path":p,"status":r.status,"bytes":len(b)})
get("/health"); get("/"); get("/pricing"); get("/tokens"); get("/openapi-agent.json"); get("/api/export", {"User-Agent":"AgenticWorkSmoke/1.0","X-PAYMENT":"demo"})
print(json.dumps({"base_url":base,"checks":checks}, indent=2))
