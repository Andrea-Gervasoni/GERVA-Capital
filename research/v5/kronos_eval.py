#!/usr/bin/env python
"""
kronos_eval.py -- out-of-sample evaluation of the Kronos candlestick foundation model
(https://github.com/shiyu-coder/Kronos; model NeoQuasar/Kronos-small, tokenizer
NeoQuasar/Kronos-Tokenizer-base) on real cached market data.

TEST ON HISTORICAL DATA ONLY. Nothing here is a live or paper-trading result.

What it measures, per dataset (see research/v5/kronos_eval.md for the write-up):
  1. calibration  : coverage of the model's p10-p90 / p25-p75 band at the horizon, vs a naive
                    zero-drift bootstrap of the context window's own returns;
  2. direction    : hit rate of sign(median predicted return), vs always-long and momentum;
  3. IC           : Spearman(predicted mean return, realized return) at horizon and 1 step;
  4. trading rule : long/short (and long-only) on predicted mean return, held to horizon,
                    net of costs, vs buy-and-hold over the same windows;
  5. race         : P(target +2 ATR before stop -1 ATR) predicted vs realized.

Everything that could be tuned was fixed BEFORE any result was looked at (see PREREG below).

Setup (outside the repo):
  git clone --depth 1 https://github.com/shiyu-coder/Kronos /tmp/kronos_eval/kronos_src
  pip install torch --index-url https://download.pytorch.org/whl/cpu
  pip install einops huggingface_hub safetensors tqdm numpy pandas scipy pyarrow

Usage:
  python kronos_eval.py --selftest                      # cached sampler == official forward pass
  python kronos_eval.py --dataset btc_1h --context 256 --horizon 24 --n-samples 100
  python kronos_eval.py --suite                         # every pre-registered config
  python kronos_eval.py --suite --only btc_1h_c256_h24 --threads 1 --max-minutes 20
                                                        # time-capped: keeps the origins done so
                                                        # far, spread evenly over the test period;
                                                        # interrupted runs resume from a checkpoint
  python kronos_eval.py --suite --analyze-only          # re-do the statistics from cached paths

Inference note. The official `auto_regressive_inference` re-runs the whole transformer over the
full window at every step and returns only the AVERAGE of the sampled paths. Here the same
weights are driven through a key/value-cached sampler that (a) computes the context once per
origin, (b) returns every individual path. `--selftest` checks that its logits and decoded
candles match the official `decode_s1` / `decode_s2` / `tokenizer.decode` to float tolerance.
Sampling itself uses the repo's own `sample_from_logits`.
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------------------
# PRE-REGISTERED choices (fixed before looking at any result; do not tune)
# --------------------------------------------------------------------------------------
PREREG = dict(
    model_id="NeoQuasar/Kronos-small",
    tokenizer_id="NeoQuasar/Kronos-Tokenizer-base",
    # Paper (arXiv 2508.02739, App. "Forecasting Task Setup"): "The pre-training data for
    # Kronos extends up to June 2024 ... our test period for all tasks begins in July 2024".
    train_cutoff="2024-06-30",
    test_start="2024-07-01",
    test_end="2026-10-31",
    # HF weights last modified 2025-09-09: origins after this date are unseen even if the
    # released checkpoint were newer than the paper says (used for a sub-period split).
    hf_last_modified="2025-09-10",
    T=1.0, top_p=0.9, top_k=0,          # README / KronosPredictor.predict defaults
    n_samples=50,                       # planned 200; cut to 50 to fit the CPU time budget
    thresholds=("0", "0.5*ctx_vol*sqrt(H)"),
    stop_atr=1.0, target_atr=2.0, atr_n=14,
    n_boot=2000, baseline_paths=1000, seed=12345,
)

COSTS = {"crypto": [0.0007, 0.0030], "spy": [0.0002]}   # per side
BARS_PER_YEAR = {"btc_1h": 8760, "eth_1h": 8760, "sol_1h": 8760, "btc_1d": 365, "eth_1d": 365,
                 "spy_1d": 252, "qqq_1d": 252, "spy_1h": 252 * 7}

# name -> (dataset, context, horizon, step, top_p).  step = H+1 on intraday data so that windows
# do not overlap and the origin's hour-of-day rotates; step = 1 on daily data (overlapping
# horizons, handled with block bootstrap + a non-overlapping subsample for trades).
SUITE = {
    "btc_1h_c256_h24": ("btc_1h", 256, 24, 25, 0.9),
    "btc_1h_c128_h48": ("btc_1h", 128, 48, 49, 0.9),    # the social-media recipe (128 in, 48 out)
    "eth_1h_c256_h24": ("eth_1h", 256, 24, 25, 0.9),
    "btc_1d_c256_h7": ("btc_1d", 256, 7, 1, 0.9),
    "spy_1d_c256_h5": ("spy_1d", 256, 5, 1, 0.9),
    "spy_1h_c256_h7": ("spy_1h", 256, 7, 8, 0.9),
    "btc_1h_c256_h24_topp1": ("btc_1h", 256, 24, 25, 1.0),  # sensitivity: untruncated sampling
}
SUITE_ORIGINS = {"btc_1h_c256_h24_topp1": 400}               # cap for the sensitivity run only

REPO = "/home/user/GERVA-Capital"
KRONOS_SRC = os.environ.get("KRONOS_SRC", "/tmp/kronos_eval/kronos_src")
COLS = ["open", "high", "low", "close", "volume", "amount"]


# --------------------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------------------
def load_dataset(name, cache=os.path.join(REPO, "data_cache")):
    sys.path.insert(0, REPO)
    from gerva.data import Store
    st = Store(cache)
    asset, freq = name.split("_")
    if asset in ("btc", "eth", "sol"):
        sym = asset.upper() + "USDT"
        if freq == "1h":
            d = st.get(f"bn_spot_5m_{sym}")
            agg = {"open": "first", "high": "max", "low": "min", "close": "last",
                   "volume": "sum", "quote_volume": "sum"}
            r = d.resample("1h").agg(agg)
            cnt = d["close"].resample("1h").count()
            r = r[cnt == 12]                      # complete hours only
        else:
            r = st.get(f"bn_spot_1d_{sym}")
        r = r.rename(columns={"quote_volume": "amount"})
    else:
        sym = asset.upper()
        if freq == "1d":
            r = st.get(f"yahoo_1d_{sym}").copy()
            f = r["adj"] / r["close"]             # total-return adjustment of OHLC
            for c in ("open", "high", "low", "close"):
                r[c] = r[c] * f
        else:
            r = st.get(f"yahoo_1h_{sym}").copy()
            r = r[(r.index.minute == 30) & (r["volume"] > 0)]   # drop partial/odd bars
        # same convention as KronosPredictor when 'amount' is missing
        r["amount"] = r["volume"] * r[["open", "high", "low", "close"]].mean(axis=1)
    r = r[COLS].dropna()
    r = r[~r.index.duplicated()].sort_index()
    return r


def time_feats(idx):
    return np.stack([np.asarray(getattr(idx, k)) for k in ("minute", "hour", "day_of_week", "day", "month")], axis=1).astype(np.float32)


def pick_origins(df, context, horizon, step, start, end, n_origins=None):
    """origin t = integer position of the last context bar; forecasts cover t+1 .. t+H."""
    ts = df.index
    lo = max(context - 1, int(np.searchsorted(ts, pd.Timestamp(start))))
    hi = int(np.searchsorted(ts, pd.Timestamp(end) + pd.Timedelta(days=1))) - 1 - horizon
    o = np.arange(lo, hi + 1, step)
    if n_origins and len(o) > n_origins:
        o = o[np.unique(np.linspace(0, len(o) - 1, n_origins).round().astype(int))]
    return o


# --------------------------------------------------------------------------------------
# key/value-cached Kronos sampler (same weights, same maths, returns every path)
# --------------------------------------------------------------------------------------
class FastKronosSampler:
    def __init__(self, tokenizer, model, clip=5.0):
        import torch
        self.torch = torch
        self.tok = tokenizer.eval()
        self.mdl = model.eval()
        self.clip = clip

    # rotary embedding at absolute positions `pos`
    def _cs(self, rot, pos):
        t = self.torch
        fr = pos.to(rot.inv_freq.dtype)[:, None] * rot.inv_freq[None, :]
        emb = t.cat((fr, fr), dim=-1)
        return emb.cos(), emb.sin()

    @staticmethod
    def _rot(x, cos, sin):
        import torch
        x1, x2 = x.chunk(2, dim=-1)
        return x * cos + torch.cat((-x2, x1), dim=-1) * sin

    def _block_ctx(self, layer, x):
        """full causal pass over the shared context; returns output and rotated K / V."""
        t = self.torch
        F = t.nn.functional
        att = layer.self_attn
        h = layer.norm1(x)
        B, L, D = h.shape
        nh, hd = att.n_heads, att.head_dim
        q = att.q_proj(h).view(B, L, nh, hd).transpose(1, 2)
        k = att.k_proj(h).view(B, L, nh, hd).transpose(1, 2)
        v = att.v_proj(h).view(B, L, nh, hd).transpose(1, 2)
        cos, sin = self._cs(att.rotary, t.arange(L))
        q, k = self._rot(q, cos, sin), self._rot(k, cos, sin)
        a = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        x = x + att.out_proj(a.transpose(1, 2).reshape(B, L, D))
        x = x + layer.ffn(layer.norm2(x))
        return x, k, v

    def _block_new(self, layer, x, pos0, ck, cv, gk, gv, g0, B, S):
        """m new positions (pos0..pos0+m-1) for N=B*S paths attending to the shared context
        cache (ck, cv: B-level) and to each path's own generated cache (gk, gv: N-level,
        preallocated buffers holding g0 valid entries; None = no generated prefix)."""
        t = self.torch
        att = layer.self_attn
        h = layer.norm1(x)
        N, m, D = h.shape
        nh, hd = att.n_heads, att.head_dim
        L = ck.shape[2]
        q = att.q_proj(h).view(N, m, nh, hd).transpose(1, 2)
        k = att.k_proj(h).view(N, m, nh, hd).transpose(1, 2)
        v = att.v_proj(h).view(N, m, nh, hd).transpose(1, 2)
        cos, sin = self._cs(att.rotary, t.arange(pos0, pos0 + m))
        q, k = self._rot(q, cos, sin), self._rot(k, cos, sin)
        if gk is None:
            gk, gv = k, v
        else:
            gk[:, :, g0:g0 + m] = k
            gv[:, :, g0:g0 + m] = v
            gk, gv = gk[:, :, :g0 + m], gv[:, :, :g0 + m]
        g = gk.shape[2]
        qB = q.reshape(B, S, nh, m, hd).permute(0, 2, 1, 3, 4).reshape(B, nh, S * m, hd)
        sc = t.matmul(qB, ck.transpose(-1, -2))
        sc = sc.reshape(B, nh, S, m, L).permute(0, 2, 1, 3, 4).reshape(N, nh, m, L)
        sg = t.matmul(q, gk.transpose(-1, -2))                      # (N, nh, m, g)
        if m > 1:                                                    # causal among the new ones
            mask = t.ones(m, m, dtype=t.bool).triu(1)
            sg[..., g - m:] = sg[..., g - m:].masked_fill(mask, float("-inf"))
        w = t.softmax(t.cat((sc, sg), dim=-1) * (hd ** -0.5), dim=-1)
        wc, wg = w[..., :L], w[..., L:]
        wcB = wc.reshape(B, S, nh, m, L).permute(0, 2, 1, 3, 4).reshape(B, nh, S * m, L)
        oc = t.matmul(wcB, cv).reshape(B, nh, S, m, hd).permute(0, 2, 1, 3, 4).reshape(N, nh, m, hd)
        a = oc + t.matmul(wg, gv)
        x = x + att.out_proj(a.transpose(1, 2).reshape(N, m, D))
        x = x + layer.ffn(layer.norm2(x))
        return x

    def _dep_attend(self, sib, dk, dv, gdk, gdv, B, S):
        """DependencyAwareLayer cross-attention for the last position (query length 1 => the
        official code's rotary is the identity)."""
        t = self.torch
        ca = self.mdl.dep_layer.cross_attn
        N = sib.shape[0]
        nh, hd = ca.n_heads, ca.head_dim
        L = dk.shape[2]
        q = ca.q_proj(sib).view(N, 1, nh, hd).transpose(1, 2)        # (N, nh, 1, hd)
        qB = q.reshape(B, S, nh, hd).permute(0, 2, 1, 3)             # (B, nh, S, hd)
        sc = t.matmul(qB, dk.transpose(-1, -2)).permute(0, 2, 1, 3).reshape(N, nh, 1, L)
        if gdk is not None:
            sc = t.cat((sc, t.matmul(q, gdk.transpose(-1, -2))), dim=-1)
        w = t.softmax(sc * (hd ** -0.5), dim=-1)
        wcB = w[..., :L].reshape(B, S, nh, L).permute(0, 2, 1, 3)
        o = t.matmul(wcB, dv).permute(0, 2, 1, 3).reshape(N, nh, 1, hd)
        if gdk is not None:
            o = o + t.matmul(w[..., L:], gdv)
        return ca.out_proj(o.transpose(1, 2).reshape(N, 1, nh * hd))

    def sample(self, x_norm, x_stamp, y_stamp, S, T=1.0, top_p=0.9, top_k=0, debug=False):
        """x_norm (B,L,6) z-scored context, stamps (B,L,5)/(B,H,5).
        Returns paths (B,S,H,6) and the decoded context (B,L,6), both in z-score space."""
        t = self.torch
        from model.kronos import sample_from_logits
        m, tok = self.mdl, self.tok
        with t.no_grad():
            x = t.clip(t.as_tensor(x_norm, dtype=t.float32), -self.clip, self.clip)
            xs = t.as_tensor(x_stamp, dtype=t.float32)
            ys = t.as_tensor(y_stamp, dtype=t.float32)
            B, L, _ = x.shape
            H = ys.shape[1]
            N = B * S
            assert L + H <= 512, "context + horizon must fit the 512-token window"
            s1, s2 = tok.encode(x, half=True)
            h = m.embedding([s1, s2]) + m.time_emb(xs)
            ck, cv = [], []
            for layer in m.transformer:
                h, k, v = self._block_ctx(layer, h)
                ck.append(k)
                cv.append(v)
            ctx = m.norm(h)
            ca = m.dep_layer.cross_attn
            dk = ca.k_proj(ctx).view(B, L, ca.n_heads, ca.head_dim).transpose(1, 2)
            dv = ca.v_proj(ctx).view(B, L, ca.n_heads, ca.head_dim).transpose(1, 2)
            last = ctx[:, -1].repeat_interleave(S, dim=0)            # (N, D)
            nl = len(m.transformer)
            a0 = m.transformer[0].self_attn
            gk = [t.empty(N, a0.n_heads, max(H - 1, 1), a0.head_dim) for _ in range(nl)]
            gv = [t.empty(N, a0.n_heads, max(H - 1, 1), a0.head_dim) for _ in range(nl)]
            gdk_buf = t.empty(N, ca.n_heads, max(H - 1, 1), ca.head_dim)
            gdv_buf = t.empty(N, ca.n_heads, max(H - 1, 1), ca.head_dim)
            gdk = gdv = None
            g1 = t.empty(N, H, dtype=t.long)
            g2 = t.empty(N, H, dtype=t.long)
            dbg = {"s1": [], "s2": []}
            for i in range(H):
                l1 = m.head(last)
                if debug:
                    dbg["s1"].append(l1.clone())
                t1 = sample_from_logits(l1, temperature=T, top_k=top_k, top_p=top_p, sample_logits=True)
                sib = m.embedding.emb_s1(t1)                         # (N,1,D)
                ao = self._dep_attend(sib, dk, dv, gdk, gdv, B, S)
                l2 = m.head.cond_forward(m.dep_layer.norm(last[:, None, :] + ao))[:, -1, :]
                if debug:
                    dbg["s2"].append(l2.clone())
                t2 = sample_from_logits(l2, temperature=T, top_k=top_k, top_p=top_p, sample_logits=True)
                g1[:, i], g2[:, i] = t1.squeeze(-1), t2.squeeze(-1)
                if i == H - 1:
                    break
                st = ys[:, i:i + 1].repeat_interleave(S, dim=0)
                h = m.embedding([t1, t2]) + m.time_emb(st)
                for li, layer in enumerate(m.transformer):
                    h = self._block_new(layer, h, L + i, ck[li], cv[li], gk[li], gv[li], i, B, S)
                nc = m.norm(h)                                        # (N,1,D)
                gdk_buf[:, :, i:i + 1] = ca.k_proj(nc).view(N, 1, ca.n_heads, ca.head_dim).transpose(1, 2)
                gdv_buf[:, :, i:i + 1] = ca.v_proj(nc).view(N, 1, ca.n_heads, ca.head_dim).transpose(1, 2)
                gdk, gdv = gdk_buf[:, :, :i + 1], gdv_buf[:, :, :i + 1]
                last = nc[:, 0]
            # tokenizer decoder (causal): context once, generated part per path
            zc = tok.post_quant_embed(tok.indices_to_bits([s1, s2], half=True))
            tk, tv = [], []
            for layer in tok.decoder:
                zc, k, v = self._block_ctx(layer, zc)
                tk.append(k)
                tv.append(v)
            ctx_dec = tok.head(zc)
            zg = tok.post_quant_embed(tok.indices_to_bits([g1, g2], half=True))
            for li, layer in enumerate(tok.decoder):
                zg = self._block_new(layer, zg, L, tk[li], tv[li], None, None, 0, B, S)
            out = tok.head(zg).view(B, S, H, -1)
        if debug:
            return out, ctx_dec, dict(s1=s1, s2=s2, g1=g1, g2=g2, l1=dbg["s1"], l2=dbg["s2"])
        return out.numpy(), ctx_dec.numpy()


def load_kronos():
    sys.path.insert(0, KRONOS_SRC)
    import torch  # noqa: F401
    from model import Kronos, KronosTokenizer
    tok = KronosTokenizer.from_pretrained(PREREG["tokenizer_id"])
    mdl = Kronos.from_pretrained(PREREG["model_id"])
    return tok.eval(), mdl.eval()


def selftest():
    """cached sampler vs the repo's own forward pass on real data."""
    import torch
    tok, mdl = load_kronos()
    fs = FastKronosSampler(tok, mdl)
    df = load_dataset("btc_1h")
    L, H, S, B = 96, 6, 3, 2
    o = pick_origins(df, L, H, 5000, "2025-01-01", "2026-06-30")[:B]
    xn, xs, ys, _, _ = build_batch(df, o, L, H)
    torch.manual_seed(0)
    out, ctx_dec, d = fs.sample(xn, xs, ys, S, T=1.0, top_p=0.9, debug=True)
    xs_t = torch.as_tensor(xs).repeat_interleave(S, 0)
    ys_t = torch.as_tensor(ys).repeat_interleave(S, 0)
    full_stamp = torch.cat([xs_t, ys_t], 1)
    f1 = torch.cat([d["s1"].repeat_interleave(S, 0), d["g1"]], 1)
    f2 = torch.cat([d["s2"].repeat_interleave(S, 0), d["g2"]], 1)
    e1 = e2 = 0.0
    with torch.no_grad():
        for i in range(H):
            n = L + i
            l1, c = mdl.decode_s1(f1[:, :n], f2[:, :n], full_stamp[:, :n])
            l2 = mdl.decode_s2(c, d["g1"][:, i:i + 1])
            e1 = max(e1, float((l1[:, -1] - d["l1"][i]).abs().max()))
            e2 = max(e2, float((l2[:, -1] - d["l2"][i]).abs().max()))
        z = tok.decode([f1, f2], half=True)
        e3 = float((z[:, -H:] - out.reshape(B * S, H, -1)).abs().max())
        e4 = float((z[::S, :L] - ctx_dec).abs().max())
    print(f"max |dlogit| s1={e1:.2e} s2={e2:.2e}; max |d decoded| future={e3:.2e} context={e4:.2e}")
    ok = max(e1, e2) < 5e-3 and max(e3, e4) < 1e-3
    print("SELFTEST", "PASSED" if ok else "FAILED")
    return ok


# --------------------------------------------------------------------------------------
# forecasting
# --------------------------------------------------------------------------------------
def build_batch(df, origins, L, H):
    vals = df[COLS].values.astype(np.float64)
    tf = time_feats(df.index)
    xn, xs, ys, mu, sd = [], [], [], [], []
    for t in origins:
        x = vals[t - L + 1:t + 1].astype(np.float32)
        m_, s_ = x.mean(0), x.std(0)
        xn.append(np.clip((x - m_) / (s_ + 1e-5), -5, 5))
        xs.append(tf[t - L + 1:t + 1])
        ys.append(tf[t + 1:t + 1 + H])
        mu.append(m_)
        sd.append(s_)
    return np.stack(xn), np.stack(xs), np.stack(ys), np.stack(mu), np.stack(sd)


def race_first(high, low, stop, target):
    """bar-by-bar race. Returns (target_first, stop_first); a bar touching both counts as stop."""
    H = high.shape[-1]
    hs, ht = low <= stop, high >= target
    fs_ = np.where(hs.any(-1), hs.argmax(-1), H + 1)
    ft_ = np.where(ht.any(-1), ht.argmax(-1), H + 1)
    return ft_ < fs_, (fs_ <= ft_) & (fs_ <= H)


def spread_order(n):
    """bit-reversal order: every prefix of it is spread evenly over 0..n-1 (so a run that is
    stopped by the time budget still covers the whole test period)."""
    bits = max(1, (n - 1).bit_length())
    rev = (int(format(i, f"0{bits}b")[::-1], 2) for i in range(1 << bits))
    return np.array([r for r in rev if r < n])


def run_forecasts(name, dataset, L, H, step, top_p, n_samples, n_origins, batch_paths, out_dir, seed, start, end,
                  deadline=None):
    import torch
    path = os.path.join(out_dir, name + ".npz")
    part = os.path.join(out_dir, name + ".part.npz")
    if os.path.exists(path):
        print(f"[{name}] cached -> {path}")
        return path
    df = load_dataset(dataset)
    origins = pick_origins(df, L, H, step, start, end, n_origins)
    tok, mdl = load_kronos()
    fs = FastKronosSampler(tok, mdl)
    rng = np.random.default_rng(seed)
    o, h, l, c = (df[k].values.astype(np.float64) for k in ("open", "high", "low", "close"))
    n, S = len(origins), n_samples
    n_planned = n
    P = {k: np.zeros((n, S, H), np.float32) for k in ("close", "high", "low")}
    recon_c0 = np.zeros(n)
    done = np.zeros(n, bool)
    prev_s = 0.0
    if os.path.exists(part):                         # resume an interrupted run
        zp = np.load(part)
        if zp["p_close"].shape == P["close"].shape and np.array_equal(zp["origins"], origins):
            P = {"close": zp["p_close"].copy(), "high": zp["p_high"].copy(), "low": zp["p_low"].copy()}
            recon_c0, done, prev_s = zp["recon_c0"].copy(), zp["done"].copy(), float(zp["seconds"])
            print(f"[{name}] resuming: {int(done.sum())}/{n} origins already done", flush=True)

    def checkpoint():
        np.savez(part + ".tmp.npz", origins=origins, p_close=P["close"], p_high=P["high"], p_low=P["low"],
                 recon_c0=recon_c0, done=done, seconds=prev_s + time.time() - t0)
        os.replace(part + ".tmp.npz", part)

    # non-overlapping configs are processed in spread order, overlapping (daily) ones in time order
    order = spread_order(n) if step >= H else np.arange(n)
    todo = order[~done[order]]
    Bo = max(1, batch_paths // S)
    t0 = last_ck = time.time()
    for b0 in range(0, len(todo), Bo):
        ib = todo[b0:b0 + Bo]
        ob = origins[ib]
        torch.manual_seed(seed + int(ob[0]))         # per-batch seed => resumable and reproducible
        xn, xs, ys, mu, sd = build_batch(df, ob, L, H)
        out, ctx_dec = fs.sample(xn, xs, ys, S, T=PREREG["T"], top_p=top_p, top_k=PREREG["top_k"])
        out = out * (sd[:, None, None, :] + 1e-5) + mu[:, None, None, :]
        px = out[..., :4]
        P["close"][ib] = px[..., 3]
        P["high"][ib] = px.max(-1)
        P["low"][ib] = px.min(-1)
        recon_c0[ib] = ctx_dec[:, -1, 3] * (sd[:, 3] + 1e-5) + mu[:, 3]
        done[ib] = True
        if time.time() - last_ck > 90:
            checkpoint()
            last_ck = time.time()
            print(f"[{name}] {int(done.sum())}/{n} origins, {prev_s + time.time() - t0:.0f}s", flush=True)
        if deadline and time.time() > deadline:
            print(f"[{name}] time budget reached: keeping {int(done.sum())}/{n} origins", flush=True)
            break
    infer_s = prev_s + time.time() - t0
    checkpoint()
    keep = np.where(done)[0]
    origins, recon_c0 = origins[keep], recon_c0[keep]
    P = {k: v[keep] for k, v in P.items()}
    n = len(origins)

    # realized + context features + naive baseline
    c0 = c[origins]
    fut = origins[:, None] + np.arange(1, H + 1)[None, :]
    rc, rh, rl = c[fut], h[fut], l[fut]
    an = PREREG["atr_n"]
    Sb = PREREG["baseline_paths"]
    atr, vol1, momH, mom1 = (np.empty(n) for _ in range(4))
    base_q, base_pt, base_ps = np.empty((n, 4)), np.empty(n), np.empty(n)
    for i, t in enumerate(origins):
        w = slice(t - an + 1, t + 1)
        tr = np.maximum(h[w] - l[w], np.maximum(abs(h[w] - c[t - an:t]), abs(l[w] - c[t - an:t])))
        atr[i] = tr.mean()
        cw = c[t - L + 1:t + 1]
        r1 = np.diff(np.log(cw))
        vol1[i] = r1.std()
        momH[i] = c[t] / c[t - H] - 1
        mom1[i] = c[t] / c[t - 1] - 1
        # naive baseline: iid bootstrap of the context's own bars, close-to-close drift removed
        mu_r = r1.mean()
        rcx = r1 - mu_r
        rhx = np.log(h[t - L + 2:t + 1] / cw[:-1]) - mu_r
        rlx = np.log(l[t - L + 2:t + 1] / cw[:-1]) - mu_r
        idx = rng.integers(0, len(r1), size=(Sb, H))
        cum = np.cumsum(rcx[idx], axis=1)
        prev = np.concatenate([np.zeros((Sb, 1)), cum[:, :-1]], axis=1)
        bc = c0[i] * np.exp(cum)
        bh = np.maximum(c0[i] * np.exp(prev + rhx[idx]), bc)
        bl = np.minimum(c0[i] * np.exp(prev + rlx[idx]), bc)
        base_q[i] = np.quantile(bc[:, -1], [0.1, 0.25, 0.75, 0.9], method="weibull")
        tf_, sf_ = race_first(bh, bl, c0[i] - PREREG["stop_atr"] * atr[i], c0[i] + PREREG["target_atr"] * atr[i])
        base_pt[i], base_ps[i] = tf_.mean(), sf_.mean()
    meta = dict(name=name, dataset=dataset, context=L, horizon=H, step=step, top_p=top_p, T=PREREG["T"],
                n_samples=S, n_origins=int(n), n_planned=int(n_planned), infer_seconds=infer_s, start=start, end=end, seed=seed,
                first_origin=str(df.index[origins[0]]), last_origin=str(df.index[origins[-1]]),
                torch=torch.__version__, threads=torch.get_num_threads())
    np.savez_compressed(path, origin_ns=df.index[origins].values.astype("datetime64[ns]").astype(np.int64),
                        c0=c0, recon_c0=recon_c0, p_close=P["close"], p_high=P["high"], p_low=P["low"],
                        r_close=rc, r_high=rh, r_low=rl, atr=atr, vol1=vol1, momH=momH, mom1=mom1,
                        base_q=base_q, base_pt=base_pt, base_ps=base_ps, meta=json.dumps(meta))
    print(f"[{name}] done: {n} origins x {S} paths x {H} steps in {infer_s:.0f}s -> {path}")
    return path


# --------------------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------------------
def wilson(k, n, z=1.959964):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    hw = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - hw, c + hw)


def boot_ci(fn, n, block, rng, n_boot):
    """moving-block bootstrap percentile CI of fn(index array)."""
    block = max(1, min(block, n))
    nb = int(math.ceil(n / block))
    vals = []
    for _ in range(n_boot):
        st = rng.integers(0, n - block + 1, size=nb)
        idx = (st[:, None] + np.arange(block)[None, :]).ravel()[:n]
        v = fn(idx)
        if np.isfinite(v):
            vals.append(v)
    if len(vals) < 10:
        return (float("nan"), float("nan"))
    return tuple(float(x) for x in np.percentile(vals, [2.5, 97.5]))


def spearman(a, b):
    from scipy.stats import rankdata
    if len(a) < 5:
        return float("nan")
    ra, rb = rankdata(a), rankdata(b)
    sa, sb = ra.std(), rb.std()
    if sa == 0 or sb == 0:
        return float("nan")
    return float(((ra - ra.mean()) * (rb - rb.mean())).mean() / (sa * sb))


def ic_block(pred, real, block, rng, n_boot):
    ic = spearman(pred, real)
    n = len(pred)
    ne = n / block                                   # crude effective n under overlap
    t = ic * math.sqrt(max(ne - 2, 1) / max(1 - ic * ic, 1e-12))
    lo, hi = boot_ci(lambda ix: spearman(pred[ix], real[ix]), n, block, rng, n_boot)
    return dict(ic=ic, t=t, n=n, n_eff=ne, ci=[lo, hi])


def perf(ret, ppy):
    ret = np.asarray(ret, float)
    eq = np.cumprod(1 + ret)
    peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[1:]
    sd = ret.std(ddof=1) if len(ret) > 1 else float("nan")
    return dict(mean=float(ret.mean()), sharpe=float(ret.mean() / sd * math.sqrt(ppy)) if sd and sd > 0 else float("nan"),
                maxdd=float((eq / peak - 1).min()), total=float(eq[-1] - 1),
                tstat=float(ret.mean() / sd * math.sqrt(len(ret))) if sd and sd > 0 else float("nan"))


def analyze(path, n_boot=None, seed=None):
    n_boot = n_boot or PREREG["n_boot"]
    z = np.load(path, allow_pickle=False)
    meta = json.loads(str(z["meta"]))
    rng = np.random.default_rng(seed or PREREG["seed"])
    H, step, ds = meta["horizon"], meta["step"], meta["dataset"]
    c0, pc, rc = z["c0"], z["p_close"].astype(np.float64), z["r_close"]
    n, S = pc.shape[0], pc.shape[1]
    block = int(math.ceil(H / step)) if step < H else 1
    sub = np.arange(0, n, block)                     # non-overlapping origins
    when = z["origin_ns"].astype("datetime64[ns]")
    res = dict(meta=meta, n=int(n), n_nonoverlap=int(len(sub)), block=block)

    real = rc[:, -1] / c0 - 1
    real1 = rc[:, 0] / c0 - 1
    ph = pc[:, :, -1]
    pred_mean = ph.mean(1) / c0 - 1
    pred_med = np.median(ph, 1) / c0 - 1
    pred_mean1 = pc[:, :, 0].mean(1) / c0 - 1
    rc0 = z["recon_c0"]
    pred_mean_ra = ph.mean(1) / rc0 - 1              # anchored on the tokenizer's own last close
    pred_mean1_ra = pc[:, :, 0].mean(1) / rc0 - 1
    # Monte-Carlo reliability of the signal: Spearman between the predicted means of two
    # disjoint halves of the paths, Spearman-Brown corrected to the full sample count.
    r_half = spearman(ph[:, :S // 2].mean(1) / c0, ph[:, S // 2:].mean(1) / c0)
    res["signal"] = dict(reliability=float(2 * r_half / (1 + r_half)), r_half=r_half,
                         pred_mean_sd_pct=float(pred_mean.std() * 100), real_sd_pct=float(real.std() * 100),
                         pred_mean_abs_med_pct=float(np.median(abs(pred_mean)) * 100))
    res["recon_err_bp"] = dict(median_abs=float(np.median(abs(rc0 / c0 - 1)) * 1e4),
                               p90_abs=float(np.quantile(abs(rc0 / c0 - 1), 0.9) * 1e4),
                               sigma1_bp=float(np.median(z["vol1"]) * 1e4),
                               sigmaH_bp=float(np.median(z["vol1"]) * math.sqrt(H) * 1e4))

    # 1. calibration ------------------------------------------------------------------
    q = np.quantile(ph, [0.1, 0.25, 0.75, 0.9], axis=1, method="weibull").T
    bq = z["base_q"]
    cal = {}
    for lab, Q in (("kronos", q), ("naive", bq)):
        y = rc[:, -1]
        in80 = (y >= Q[:, 0]) & (y <= Q[:, 3])
        in50 = (y >= Q[:, 1]) & (y <= Q[:, 2])
        cal[lab] = dict(cov80=float(in80.mean()), cov80_ci=boot_ci(lambda ix: in80[ix].mean(), n, block, rng, n_boot),
                        cov50=float(in50.mean()), cov50_ci=boot_ci(lambda ix: in50[ix].mean(), n, block, rng, n_boot),
                        below_p10=float((y < Q[:, 0]).mean()), above_p90=float((y > Q[:, 3]).mean()),
                        width80_med_pct=float(np.median((Q[:, 3] - Q[:, 0]) / c0) * 100))
    cal["width_ratio_med"] = float(np.median((q[:, 3] - q[:, 0]) / (bq[:, 3] - bq[:, 0])))
    cal["mean_bias_pct"] = float(np.mean(pred_mean - real) * 100)
    cal["mean_pred_ret_pct"] = float(np.mean(pred_mean) * 100)
    cal["mean_real_ret_pct"] = float(np.mean(real) * 100)
    res["calibration"] = cal

    # volatility sanity check: does band width rank realized |move|?
    width = (q[:, 3] - q[:, 0]) / c0
    res["vol_ic"] = dict(kronos=ic_block(width, abs(real), block, rng, n_boot),
                         naive=ic_block((bq[:, 3] - bq[:, 0]) / c0, abs(real), block, rng, n_boot))

    # 2. direction (non-overlapping origins) --------------------------------------------
    rs, ms = real[sub], pred_med[sub]
    nz = rs != 0
    up = rs[nz] > 0
    k_m = int(((ms[nz] > 0) == up).sum())
    k_mom = int(((z["momH"][sub][nz] > 0) == up).sum())
    k_l = int(up.sum())
    nn = int(nz.sum())
    from scipy.stats import binomtest
    hit = (ms[nz] > 0) == up
    d = dict(n=nn, kronos=k_m / nn, kronos_ci=wilson(k_m, nn), p_vs_50=float(binomtest(k_m, nn, 0.5).pvalue),
             always_long=k_l / nn, always_long_ci=wilson(k_l, nn),
             momentum=k_mom / nn, momentum_ci=wilson(k_mom, nn),
             share_pred_long=float((ms[nz] > 0).mean()),
             diff_vs_long=float(hit.mean() - up.mean()),
             diff_vs_long_ci=boot_ci(lambda ix: hit[ix].mean() - up[ix].mean(), nn, 1, rng, n_boot))
    cut = np.datetime64(PREREG["hf_last_modified"])
    for lab, msk in (("pre_release", when[sub][nz] < cut), ("post_release", when[sub][nz] >= cut)):
        kk, mm = int(hit[msk].sum()), int(msk.sum())
        d[lab] = dict(n=mm, hit=kk / mm if mm else float("nan"), ci=wilson(kk, mm),
                      always_long=float(up[msk].mean()) if mm else float("nan"))
    res["direction"] = d

    # 3. information coefficient --------------------------------------------------------
    ic = dict(horizon=ic_block(pred_mean, real, block, rng, n_boot),
              step1=ic_block(pred_mean1, real1, 1, rng, n_boot),
              horizon_recon_anchor=ic_block(pred_mean_ra, real, block, rng, n_boot),
              step1_recon_anchor=ic_block(pred_mean1_ra, real1, 1, rng, n_boot),
              momentum_horizon=ic_block(z["momH"], real, block, rng, n_boot),
              momentum_step1=ic_block(z["mom1"], real1, 1, rng, n_boot))
    for lab, msk in (("pre_release", when < cut), ("post_release", when >= cut)):
        ic["horizon_" + lab] = ic_block(pred_mean[msk], real[msk], block, rng, n_boot) if msk.sum() > 20 else None
    res["ic"] = ic

    # 4. trading rule (non-overlapping origins) -----------------------------------------
    ppy = BARS_PER_YEAR[ds] / (block * step)
    thr2 = 0.5 * z["vol1"][sub] * math.sqrt(H)
    sig, r = pred_mean[sub], real[sub]
    costs = [0.0] + (COSTS["spy"] if ds.startswith(("spy", "qqq")) else COSTS["crypto"])
    tr = dict(periods_per_year=ppy, buy_hold=perf(r, ppy), rows=[])
    for thn, th in (("0", np.zeros_like(sig)), ("0.5vol", thr2)):
        for var in ("long_short", "long_only"):
            pos = np.where(sig > th, 1.0, np.where((sig < -th) & (var == "long_short"), -1.0, 0.0))
            ntr = int((pos != 0).sum())
            turn = np.abs(np.diff(np.concatenate([[0.0], pos, [0.0]])))
            for cst in costs:
                net = pos * r - 2 * cst * np.abs(pos)                       # round trip every trade
                net_roll = pos * r - cst * (turn[:-1] + np.where(np.arange(len(pos)) == len(pos) - 1, turn[-1], 0))
                tm = net[pos != 0]
                p_ = perf(net, ppy)
                row = dict(threshold=thn, variant=var, cost_side=cst, n_trades=ntr, n_long=int((pos > 0).sum()),
                           n_short=int((pos < 0).sum()), n_windows=int(len(pos)),
                           mean_net_trade_bp=float(tm.mean() * 1e4) if ntr else float("nan"),
                           mean_net_trade_ci_bp=[x * 1e4 for x in boot_ci(lambda ix: tm[ix].mean(), ntr, 1, rng, n_boot)] if ntr > 5 else [float("nan")] * 2,
                           win_rate=float((tm > 0).mean()) if ntr else float("nan"),
                           sharpe=p_["sharpe"], maxdd=p_["maxdd"], total=p_["total"], tstat=p_["tstat"],
                           sharpe_roll=perf(net_roll, ppy)["sharpe"], total_roll=perf(net_roll, ppy)["total"])
                tr["rows"].append(row)
    res["trading"] = tr

    # 5. race to stop / target ------------------------------------------------------------
    stop = c0 - PREREG["stop_atr"] * z["atr"]
    targ = c0 + PREREG["target_atr"] * z["atr"]
    mt, ms_ = race_first(z["p_high"], z["p_low"], stop[:, None, None], targ[:, None, None])
    p_t, p_s = mt.mean(1), ms_.mean(1)
    yt, ys_ = race_first(z["r_high"], z["r_low"], stop[:, None], targ[:, None])
    yt_f = yt.astype(float)

    def auc(p, y):
        from scipy.stats import rankdata
        y = y.astype(bool)
        if y.all() or (~y).all():
            return float("nan")
        rk = rankdata(p)
        return float((rk[y].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum()))

    race = dict(real_target=float(yt.mean()), real_stop=float(ys_.mean()), real_neither=float(1 - yt.mean() - ys_.mean()),
                pred_target=float(p_t.mean()), pred_stop=float(p_s.mean()), pred_neither=float(1 - p_t.mean() - p_s.mean()),
                naive_target=float(z["base_pt"].mean()), naive_stop=float(z["base_ps"].mean()),
                brier_kronos=float(((p_t - yt_f) ** 2).mean()), brier_naive=float(((z["base_pt"] - yt_f) ** 2).mean()),
                brier_const_insample=float(((yt_f.mean() - yt_f) ** 2).mean()),
                auc_kronos=auc(p_t, yt), auc_kronos_ci=boot_ci(lambda ix: auc(p_t[ix], yt[ix]), n, block, rng, n_boot),
                auc_naive=auc(z["base_pt"], yt), atr_pct_med=float(np.median(z["atr"] / c0) * 100), bins=[])
    order = np.argsort(p_t, kind="stable")
    for b in np.array_split(order, 5):
        k_, m_ = int(yt[b].sum()), len(b)
        race["bins"].append(dict(p_lo=float(p_t[b].min()), p_hi=float(p_t[b].max()), p_mean=float(p_t[b].mean()),
                                 realized=k_ / m_, ci=wilson(k_, m_), n=m_))
    res["race"] = race
    return res


# --------------------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------------------
def _pc(x, d=1):
    return "n/d" if x is None or not np.isfinite(x) else f"{100 * x:.{d}f}%"


def _ci(ci, d=1, pct=True):
    if ci is None or not np.all(np.isfinite(ci)):
        return "n/d"
    return f"[{100 * ci[0]:.{d}f}; {100 * ci[1]:.{d}f}]" if pct else f"[{ci[0]:+.3f}; {ci[1]:+.3f}]"


def tables_md(R):
    L = []
    names = list(R)
    L.append("### Tabella A - Configurazioni e campioni\n")
    L.append("| config | dataset | contesto | orizzonte | passo | top_p | percorsi | origini usate / pianificate | non sovrapposte | prima origine | ultima origine | inferenza (s, 1 thread) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for k in names:
        m = R[k]["meta"]
        L.append(f"| {k} | {m['dataset']} | {m['context']} | {m['horizon']} | {m['step']} | {m['top_p']} | {m['n_samples']} | {R[k]['n']} / {m.get('n_planned', R[k]['n'])} | {R[k]['n_nonoverlap']} | {m['first_origin'][:10]} | {m['last_origin'][:10]} | {m['infer_seconds']:.0f} |")
    L.append("\n### Tabella B - Calibrazione all'orizzonte (quota di chiusure reali dentro la banda; atteso 80% / 50%)\n")
    L.append("| config | Kronos p10-p90 | IC95% | Kronos p25-p75 | IC95% | sotto p10 / sopra p90 | naive p10-p90 | naive p25-p75 | larghezza banda Kronos/naive (mediana) |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for k in names:
        c = R[k]["calibration"]
        a, b = c["kronos"], c["naive"]
        L.append(f"| {k} | {_pc(a['cov80'])} | {_ci(a['cov80_ci'])} | {_pc(a['cov50'])} | {_ci(a['cov50_ci'])} | {_pc(a['below_p10'])} / {_pc(a['above_p90'])} | {_pc(b['cov80'])} {_ci(b['cov80_ci'])} | {_pc(b['cov50'])} {_ci(b['cov50_ci'])} | {c['width_ratio_med']:.2f} |")
    L.append("\n### Tabella C - Direzione (origini non sovrapposte; IC95% di Wilson)\n")
    L.append("| config | n | Kronos (segno mediana) | IC95% | p vs 50% | sempre long | momentum (segno ultimo rend. H barre) | Kronos - sempre long | IC95% diff. | quota previsioni long |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for k in names:
        d = R[k]["direction"]
        L.append(f"| {k} | {d['n']} | {_pc(d['kronos'])} | {_ci(d['kronos_ci'])} | {d['p_vs_50']:.2f} | {_pc(d['always_long'])} | {_pc(d['momentum'])} {_ci(d['momentum_ci'])} | {100 * d['diff_vs_long']:+.1f} pp | {_ci(d['diff_vs_long_ci'])} | {_pc(d['share_pred_long'])} |")
    L.append("\n### Tabella D - Information coefficient (Spearman, rendimento medio previsto vs realizzato)\n")
    L.append("| config | IC orizzonte | t | IC95% bootstrap | IC 1 passo | t | IC95% bootstrap | IC momentum orizzonte | IC momentum 1 passo | IC orizzonte (ancora = close ricostruito) | IC 1 passo (ancora ricostruita) |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for k in names:
        i = R[k]["ic"]
        f = lambda x: f"{x['ic']:+.3f}"
        L.append(f"| {k} | {f(i['horizon'])} | {i['horizon']['t']:+.2f} | {_ci(i['horizon']['ci'], pct=False)} | {f(i['step1'])} | {i['step1']['t']:+.2f} | {_ci(i['step1']['ci'], pct=False)} | {f(i['momentum_horizon'])} | {f(i['momentum_step1'])} | {f(i['horizon_recon_anchor'])} (t {i['horizon_recon_anchor']['t']:+.2f}) | {f(i['step1_recon_anchor'])} (t {i['step1_recon_anchor']['t']:+.2f}) |")
    L.append("\n### Tabella E - Regola di trading netta dei costi (origini non sovrapposte, uscita all'orizzonte, andata+ritorno pagati a ogni trade)\n")
    L.append("| config | soglia | variante | costo/lato | trade (long/short) su finestre | netto medio per trade (bp) | IC95% (bp) | % vincenti | Sharpe ann. | max drawdown | rend. totale | Sharpe ann. se costo solo sui cambi di posizione |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for k in names:
        t = R[k]["trading"]
        bh = t["buy_hold"]
        L.append(f"| {k} | - | **buy&hold stesse finestre** | 0 | {R[k]['n_nonoverlap']} | {bh['mean'] * 1e4:+.1f} | - | - | {bh['sharpe']:+.2f} | {_pc(bh['maxdd'])} | {_pc(bh['total'])} | - |")
        for r in t["rows"]:
            ci = r["mean_net_trade_ci_bp"]
            cis = "n/d" if not np.all(np.isfinite(ci)) else f"[{ci[0]:+.1f}; {ci[1]:+.1f}]"
            L.append(f"| {k} | {r['threshold']} | {r['variant']} | {100 * r['cost_side']:.2f}% | {r['n_trades']} ({r['n_long']}/{r['n_short']}) su {r['n_windows']} | {r['mean_net_trade_bp']:+.1f} | {cis} | {_pc(r['win_rate'])} | {r['sharpe']:+.2f} | {_pc(r['maxdd'])} | {_pc(r['total'])} | {r['sharpe_roll']:+.2f} |")
    L.append("\n### Tabella F - Gara stop/target (stop = -1 ATR14, target = +2 ATR14, entro l'orizzonte)\n")
    L.append("| config | realizzato: target / stop / nessuno | Kronos previsto: target / stop / nessuno | naive: target / stop | Brier Kronos | Brier naive | Brier costante (in-sample) | AUC Kronos | IC95% | AUC naive |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for k in names:
        r = R[k]["race"]
        L.append(f"| {k} | {_pc(r['real_target'])} / {_pc(r['real_stop'])} / {_pc(r['real_neither'])} | {_pc(r['pred_target'])} / {_pc(r['pred_stop'])} / {_pc(r['pred_neither'])} | {_pc(r['naive_target'])} / {_pc(r['naive_stop'])} | {r['brier_kronos']:.4f} | {r['brier_naive']:.4f} | {r['brier_const_insample']:.4f} | {r['auc_kronos']:.3f} | {_ci(r['auc_kronos_ci'], pct=False).replace('+', '')} | {r['auc_naive']:.3f} |")
    L.append("\n### Tabella G - Affidabilita' della probabilita' \"target prima dello stop\" (quintili della probabilita' prevista)\n")
    L.append("| config | quintile | P prevista (min-max) | P prevista media | frequenza realizzata | IC95% | n |")
    L.append("|---|---|---|---|---|---|---|")
    for k in names:
        for j, b in enumerate(R[k]["race"]["bins"]):
            L.append(f"| {k} | {j + 1} | {b['p_lo']:.2f}-{b['p_hi']:.2f} | {_pc(b['p_mean'])} | {_pc(b['realized'])} | {_ci(b['ci'])} | {b['n']} |")
    L.append("\n### Tabella H - Controlli: volatilita', errore di ricostruzione, sotto-periodi\n")
    L.append("| config | IC larghezza banda vs \\|rend. realizzato\\| (Kronos) | idem naive | errore ricostruzione ultimo close (mediana, bp) | sigma 1 barra (bp) | bias medio previsto-realizzato | affidabilita' Monte Carlo del segnale | dev.st. rend. medio previsto / realizzato | hit pre 2025-09-10 (n) | hit post 2025-09-10 (n) | IC orizzonte pre | IC orizzonte post |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for k in names:
        r = R[k]
        d, i = r["direction"], r["ic"]
        g = lambda x: "n/d" if x is None else f"{x['ic']:+.3f} (t {x['t']:+.2f})"
        L.append(f"| {k} | {r['vol_ic']['kronos']['ic']:+.3f} (t {r['vol_ic']['kronos']['t']:+.1f}) | {r['vol_ic']['naive']['ic']:+.3f} | {r['recon_err_bp']['median_abs']:.1f} | {r['recon_err_bp']['sigma1_bp']:.1f} | {r['calibration']['mean_bias_pct']:+.2f}% | {r['signal']['reliability']:.2f} | {r['signal']['pred_mean_sd_pct']:.2f}% / {r['signal']['real_sd_pct']:.2f}% | {_pc(d['pre_release']['hit'])} ({d['pre_release']['n']}) | {_pc(d['post_release']['hit'])} ({d['post_release']['n']}) | {g(i['horizon_pre_release'])} | {g(i['horizon_post_release'])} |")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="btc_1h", help="btc_1h eth_1h sol_1h btc_1d eth_1d spy_1d qqq_1d spy_1h")
    ap.add_argument("--context", type=int, default=256)
    ap.add_argument("--horizon", type=int, default=24)
    ap.add_argument("--step", type=int, default=None, help="bars between origins (default H+1 intraday, 1 daily)")
    ap.add_argument("--n-origins", type=int, default=None, help="cap; evenly thinned if more are available")
    ap.add_argument("--n-samples", type=int, default=PREREG["n_samples"])
    ap.add_argument("--top-p", type=float, default=PREREG["top_p"])
    ap.add_argument("--start", default=PREREG["test_start"])
    ap.add_argument("--end", default=PREREG["test_end"])
    ap.add_argument("--batch-paths", type=int, default=800, help="paths per forward batch (origins*samples)")
    ap.add_argument("--out-dir", default="/tmp/kronos_eval/out")
    ap.add_argument("--seed", type=int, default=PREREG["seed"])
    ap.add_argument("--threads", type=int, default=None)
    ap.add_argument("--max-minutes", type=float, default=None,
                    help="wall-clock budget for the whole process; the config running when it expires "
                         "keeps the origins done so far (spread evenly over the test period)")
    ap.add_argument("--suite", action="store_true", help="run every pre-registered config")
    ap.add_argument("--only", default=None, help="comma list of suite names")
    ap.add_argument("--analyze-only", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    if a.threads:
        import torch
        torch.set_num_threads(a.threads)
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if a.suite:
        cfgs = {k: SUITE[k] for k in (a.only.split(",") if a.only else SUITE)}
    else:
        step = a.step or (1 if a.dataset.endswith("1d") else a.horizon + 1)
        nm = f"{a.dataset}_c{a.context}_h{a.horizon}" + ("" if a.top_p == PREREG["top_p"] else f"_topp{a.top_p:g}")
        cfgs = {nm: (a.dataset, a.context, a.horizon, step, a.top_p)}
    R = {}
    deadline = time.time() + 60 * a.max_minutes if a.max_minutes else None
    for name, (ds, L, H, step, top_p) in cfgs.items():
        path = os.path.join(a.out_dir, name + ".npz")
        if not a.analyze_only:
            no = SUITE_ORIGINS.get(name, a.n_origins) if a.suite else a.n_origins
            run_forecasts(name, ds, L, H, step, top_p, a.n_samples, no, a.batch_paths, a.out_dir,
                          a.seed, a.start, a.end, deadline)
        if os.path.exists(path):
            R[name] = analyze(path)
    tag = "suite" if a.suite and not a.only else "_".join(R)[:80]
    with open(os.path.join(a.out_dir, f"results_{tag}.json"), "w") as f:
        json.dump(dict(prereg=PREREG, results=R), f, indent=1, default=float)
    md = tables_md(R)
    with open(os.path.join(a.out_dir, f"tables_{tag}.md"), "w") as f:
        f.write(md)
    print(md)


if __name__ == "__main__":
    main()
