"""Recorder live v6 (B2): Hyperliquid l2Book/bbo/trades, Binance USDT-M bookTicker/aggTrade,
Kraken Futures ticker/trade. Scrive jsonl.gz a blocchi di 5 minuti in data_cache/v6_live/.
Ogni riga: [t_locale_ns, stream, simbolo, ...campi]. Avvio: /tmp/gv/bin/python 00_recorder.py &
"""
import asyncio, json, time, gzip, os, sys, zlib
import websockets

OUT = "/home/user/GERVA-Capital/data_cache/v6_live"
os.makedirs(OUT, exist_ok=True)
ROT = 300
COINS = ["BTC", "ETH", "SOL"]

class W:
    def __init__(self, name):
        self.name = name; self.f = None; self.slot = None; self.n = 0; self.lastflush = 0
    def write(self, row):
        now = time.time(); slot = int(now // ROT)
        if slot != self.slot:
            if self.f: self.f.close()
            ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime(now))
            self.f = gzip.open(f"{OUT}/{self.name}_{ts}.jsonl.gz", "at", compresslevel=5)
            self.slot = slot
        self.f.write(json.dumps(row, separators=(",", ":")) + "\n"); self.n += 1
        if now - self.lastflush > 15:
            self.f.flush(); self.lastflush = now

WR = {}
def w(name):
    if name not in WR: WR[name] = W(name)
    return WR[name]

async def run(name, url, subs, handler, ping=None):
    while True:
        try:
            async with websockets.connect(url, open_timeout=20, max_size=2**24, ping_interval=20, ping_timeout=30) as ws:
                for s in subs: await ws.send(json.dumps(s))
                w("events").write([time.time_ns(), name, "connected"])
                last = time.time()
                while True:
                    try:
                        m = await asyncio.wait_for(ws.recv(), 30)
                    except asyncio.TimeoutError:
                        if ping: await ws.send(json.dumps(ping)); continue
                        raise
                    t = time.time_ns()
                    if ping and time.time() - last > 25:
                        await ws.send(json.dumps(ping)); last = time.time()
                    handler(t, json.loads(m))
        except Exception as e:
            w("events").write([time.time_ns(), name, "error", repr(e)[:200]])
            await asyncio.sleep(2)

def h_hl(t, m):
    ch = m.get("channel"); d = m.get("data")
    if ch == "l2Book":
        b, a = d["levels"]
        w("hl_l2").write([t, d["coin"], d["time"], [[x["px"], x["sz"], x["n"]] for x in b[:20]], [[x["px"], x["sz"], x["n"]] for x in a[:20]]])
    elif ch == "bbo":
        b, a = d["bbo"]
        w("hl_bbo").write([t, d["coin"], d["time"], b and b["px"], b and b["sz"], a and a["px"], a and a["sz"]])
    elif ch == "trades":
        for x in d:
            w("hl_tr").write([t, x["coin"], x["time"], x["side"], x["px"], x["sz"], x["tid"]])

_bn_last = {}
def h_bn(t, m):
    d = m.get("data", m); e = d.get("e")
    if e == "bookTicker":
        s = d["s"]; k = (d["b"], d["a"]); p = _bn_last.get(s)
        # tieni ogni cambio di prezzo; altrimenti al massimo uno ogni 100 ms (le size cambiano migliaia di volte al secondo)
        if p is None or p[0] != k or t - p[1] > 100_000_000:
            _bn_last[s] = (k, t)
            w("bn_bt").write([t, s, d["T"], d["E"], d["b"], d["B"], d["a"], d["A"]])
    elif e == "depthUpdate":
        w("bn_d5").write([t, d["s"], d["T"], d["E"], d["b"][:5], d["a"][:5]])
    elif e == "aggTrade":
        w("bn_tr").write([t, d["s"], d["T"], d["E"], d["p"], d["q"], 1 if d["m"] else 0])
    elif e == "forceOrder":
        o = d["o"]; w("bn_liq").write([t, o["s"], o["T"], o["S"], o["p"], o["q"], o["ap"]])

_sp_last = {}
def h_sp(t, m):
    d = m.get("data", m)
    if "b" in d and "a" in d and "s" in d and "e" not in d:
        s = d["s"]; k = (d["b"], d["a"]); p = _sp_last.get(s)
        if p is None or p[0] != k or t - p[1] > 100_000_000:
            _sp_last[s] = (k, t)
            w("sp_bt").write([t, s, d["u"], d["b"], d["B"], d["a"], d["A"]])
    elif d.get("e") == "aggTrade":
        w("sp_tr").write([t, d["s"], d["T"], d["E"], d["p"], d["q"], 1 if d["m"] else 0])

def h_kr(t, m):
    f = m.get("feed")
    if f == "ticker" and "bid" in m:
        w("kr_tk").write([t, m["product_id"], m["time"], m["bid"], m["bid_size"], m["ask"], m["ask_size"], m.get("last"), m.get("markPrice")])
    elif f == "trade" and "price" in m:
        w("kr_tr").write([t, m["product_id"], m["time"], m["side"], m["price"], m["qty"]])
    elif f in ("book_snapshot",):
        w("kr_bk").write([t, m["product_id"], m["timestamp"], "S", m["bids"][:20], m["asks"][:20]])
    elif f == "book" and "price" in m:
        w("kr_bk").write([t, m["product_id"], m["timestamp"], m["side"], m["price"], m["qty"]])

async def main():
    hl_subs = []
    for c in COINS:
        for ty in ("l2Book", "bbo", "trades"):
            hl_subs.append({"method": "subscribe", "subscription": {"type": ty, "coin": c}})
    bn_streams = "/".join(f"{c.lower()}usdt@{s}" for c in COINS for s in ("bookTicker", "depth5@100ms"))
    bn_mkt = "/".join(f"{c.lower()}usdt@{s}" for c in COINS for s in ("aggTrade", "forceOrder"))
    sp_streams = "/".join(f"{c.lower()}usdt@{s}" for c in COINS for s in ("bookTicker", "aggTrade"))
    kr_p = ["PF_XBTUSD", "PF_ETHUSD", "PF_SOLUSD"]
    kr_subs = [{"event": "subscribe", "feed": f, "product_ids": kr_p} for f in ("ticker", "trade", "book")]
    await asyncio.gather(
        run("hl", "wss://api.hyperliquid.xyz/ws", hl_subs, h_hl, ping={"method": "ping"}),
        run("bn", "wss://fstream.binance.com/stream?streams=" + bn_streams, [], h_bn),
        run("bnm", "wss://fstream.binance.com/market/stream?streams=" + bn_mkt, [], h_bn),
        run("sp", "wss://data-stream.binance.vision/stream?streams=" + sp_streams, [], h_sp),
        run("kr", "wss://futures.kraken.com/ws/v1", kr_subs, h_kr),
    )
asyncio.run(main())
