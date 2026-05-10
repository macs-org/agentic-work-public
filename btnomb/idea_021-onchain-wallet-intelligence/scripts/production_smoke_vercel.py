import json, sys, urllib.request
base=sys.argv[1].rstrip('/')
checks=[]
def get(path, headers=None):
    req=urllib.request.Request(base+path, headers=headers or {'User-Agent':'AgenticWorkSmoke/1.0'})
    with urllib.request.urlopen(req, timeout=40) as r:
        b=r.read(); checks.append({'path':path,'status':r.status,'bytes':len(b)}); return b
for p in ['/health','/']:
    get(p)
print(json.dumps({'base_url':base,'checks':checks}, indent=2))
