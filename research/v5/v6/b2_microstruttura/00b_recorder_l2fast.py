"""Secondo recorder: Hyperliquid l2Book 'fast' (5 livelli, ~2 aggiornamenti/s) per BTC, ETH, SOL -> data_cache/v6_live/hl_l2f_*.jsonl.gz"""
import asyncio, json, time, gzip, os, websockets
OUT = "/home/user/GERVA-Capital/data_cache/v6_live"; ROT = 300
class W:
    def __init__(s, name): s.name = name; s.f = None; s.slot = None; s.lf = 0
    def write(s, row):
        now = time.time(); slot = int(now // ROT)
        if slot != s.slot:
            if s.f: s.f.close()
            s.f = gzip.open(f"{OUT}/{s.name}_{time.strftime('%Y%m%d_%H%M%S', time.gmtime(now))}.jsonl.gz", "at", compresslevel=5); s.slot = slot
        s.f.write(json.dumps(row, separators=(",", ":")) + "\n")
        if now - s.lf > 15: s.f.flush(); s.lf = now
async def main():
    w = W("hl_l2f")
    while True:
        try:
            async with websockets.connect("wss://api.hyperliquid.xyz/ws", open_timeout=20, max_size=2**24) as ws:
                for c in ("BTC", "ETH", "SOL"):
                    await ws.send(json.dumps({"method": "subscribe", "subscription": {"type": "l2Book", "coin": c, "fast": True}}))
                last = time.time()
                while True:
                    m = json.loads(await asyncio.wait_for(ws.recv(), 30)); t = time.time_ns()
                    if time.time() - last > 25: await ws.send(json.dumps({"method": "ping"})); last = time.time()
                    if m.get("channel") == "l2Book":
                        d = m["data"]; b, a = d["levels"]
                        w.write([t, d["coin"], d["time"], [[x["px"], x["sz"], x["n"]] for x in b], [[x["px"], x["sz"], x["n"]] for x in a]])
        except Exception as e:
            await asyncio.sleep(2)
asyncio.run(main())
