import json,urllib.request,urllib.error,time
U='https://api.hyperliquid.xyz/info'; EX='https://rpc.hyperliquid.xyz/explorer'
def post(b,url=U,retries=6):
    data=json.dumps(b).encode()
    for i in range(retries):
        try:
            rq=urllib.request.Request(url,data=data,headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(rq,timeout=40) as r: return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code==429: time.sleep(5+5*i); continue
            if e.code in (500,502,503,504): time.sleep(2+2*i); continue
            raise
        except Exception as e:
            time.sleep(2+2*i)
    return None
