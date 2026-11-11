import json, urllib.request, os, ssl, time
def post(body, tries=5):
    for k in range(tries):
        try:
            rq=urllib.request.Request('https://api.hyperliquid.xyz/info',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','User-Agent':'research-client'})
            return json.loads(urllib.request.urlopen(rq,timeout=40).read())
        except Exception as e:
            err=e; time.sleep(1.5*(k+1))
    raise err
