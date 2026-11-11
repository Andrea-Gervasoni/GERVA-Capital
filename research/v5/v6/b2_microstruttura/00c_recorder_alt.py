"""Terzo recorder: Hyperliquid bbo + trades per 20 perps meno liquidi (spread larghi) -> hl_altbbo_*, hl_alttr_*"""
import asyncio, json, time, gzip, os, websockets
COINS = ["ZEC","HYPE","NEAR","XRP","kPEPE","PUMP","LIT","XMR","GRAM","TAO","VVV","ZRO","TRUMP","INJ","FARTCOIN","ETHFI","CRV","JUP","XPL","AERO"]
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
    wb = W("hl_altbbo"); wt = W("hl_alttr")
    while True:
        try:
            async with websockets.connect("wss://api.hyperliquid.xyz/ws", open_timeout=20, max_size=2**24) as ws:
                for c in COINS:
                    for ty in ("bbo", "trades"):
                        await ws.send(json.dumps({"method": "subscribe", "subscription": {"type": ty, "coin": c}}))
                last = time.time()
                while True:
                    m = json.loads(await asyncio.wait_for(ws.recv(), 30)); t = time.time_ns()
                    if time.time() - last > 25: await ws.send(json.dumps({"method": "ping"})); last = time.time()
                    ch = m.get("channel"); d = m.get("data")
                    if ch == "bbo":
                        b, a = d["bbo"]
                        wb.write([t, d["coin"], d["time"], b and b["px"], b and b["sz"], a and a["px"], a and a["sz"]])
                    elif ch == "trades":
                        for x in d: wt.write([t, x["coin"], x["time"], x["side"], x["px"], x["sz"], x["tid"]])
        except Exception as e:
            await asyncio.sleep(2)
asyncio.run(main())
