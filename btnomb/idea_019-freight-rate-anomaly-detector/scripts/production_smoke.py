import json, sys, urllib.request
base = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else 'http://127.0.0.1:8000'
checks=[]
def get(path, headers=None):
    req=urllib.request.Request(base+path, headers=headers or {'User-Agent':'AgenticWorkSmoke/1.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        data=r.read().decode('utf-8', 'replace')
        checks.append({'path':path,'status':r.status,'bytes':len(data)})
        return data
get('/health')
get('/')
get('/pricing')
get('/anomalies')
get('/api/export', {'User-Agent':'AgenticWorkSmoke/1.0','X-PAYMENT':'demo-paid-token'})
print(json.dumps({'base_url': base, 'checks': checks}, indent=2))
