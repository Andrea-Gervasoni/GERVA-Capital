"""
Motore di rischio in tempo reale. Deterministico, senza LLM, valutato a ogni ciclo PRIMA di qualunque ordine.

Stati (dal piu' libero al piu' chiuso):
    NORMAL   esposizione piena
    REDUCED  esposizione dimezzata            caduta >= dd_reduce  oppure  perdita del giorno >= daily_loss
    HALTED   esposizione a un quarto, nessun  caduta >= dd_halt    oppure  perdita della settimana >= weekly_loss
             aumento di rischio               oppure dati vecchi / riconciliazione fallita / errori ripetuti
    KILLED   tutto chiuso, bloccato           caduta >= dd_kill    oppure  file KILL (dashboard o a mano)

Regole che non si possono configurare via:
  * la leva non supera mai HARD_MAX_LEVERAGE, qualunque cosa dica il file di configurazione;
  * si scende di stato subito, si risale solo con isteresi (la caduta deve rientrare sotto meta' soglia);
  * KILLED e' a ritenuta: si esce solo togliendo il file KILL E dando il comando `gerva reset-kill`;
  * un ordine che RIDUCE una posizione passa sempre; i controlli bloccano solo cio' che aumenta il rischio.

Perche' queste soglie (config/gerva.yaml): nel Monte Carlo del portafoglio a 2x la caduta massima mediana a 3 anni
e' del 17% e il 5° percentile del 27%; il KILL al 20% dal massimo taglia quella coda. Lo scalino al 10% dimezza
prima: dimezzare a -10% e chiudere a -20% limita la perdita al 20% anche se le strategie hanno smesso di funzionare.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

HARD_MAX_LEVERAGE = 3.0
STATES = ("NORMAL", "REDUCED", "HALTED", "KILLED")
SCALE = {"NORMAL": 1.0, "REDUCED": 0.5, "HALTED": 0.25, "KILLED": 0.0}


@dataclass
class Limits:
    max_leverage: float = 2.0            # tetto operativo dell'esposizione lorda / patrimonio
    vol_target: float = 0.15             # volatilita' annua obiettivo del portafoglio
    dd_reduce: float = 0.10
    dd_halt: float = 0.15
    dd_kill: float = 0.20
    daily_loss: float = 0.04
    weekly_loss: float = 0.08
    max_weight: float = 0.35             # peso massimo di un singolo strumento (valore assoluto)
    max_venue: dict = field(default_factory=lambda: {"crypto": 0.40})   # esposizione massima per sede (rischio di controparte)
    max_order_frac: float = 0.25         # nessun ordine sopra il 25% del patrimonio (errore di battitura)
    max_price_dev: float = 0.05          # prezzo dell'ordine entro il 5% dall'ultimo prezzo noto
    min_order: float = 25.0              # ordini piu' piccoli non si inviano (costano piu' di quanto valgono)
    max_data_age_h: dict = field(default_factory=lambda: {"crypto": 36.0, "ibkr": 100.0})
    max_errors: int = 5                  # cicli falliti di fila prima di HALTED

    def __post_init__(self):
        if not 0 < self.max_leverage <= HARD_MAX_LEVERAGE:
            raise ValueError(f"max_leverage deve stare in (0, {HARD_MAX_LEVERAGE}]")
        if not 0 < self.dd_reduce < self.dd_halt < self.dd_kill < 1:
            raise ValueError("serve 0 < dd_reduce < dd_halt < dd_kill < 1")


@dataclass
class Assessment:
    state: str
    scale: float
    reasons: list
    drawdown: float                      # negativo: -0.07 = 7% sotto il massimo
    day_pnl: float
    week_pnl: float
    high_water: float


class RiskEngine:
    def __init__(self, limits: Limits, journal, kill_file: str):
        self.l, self.j, self.kill_file = limits, journal, kill_file

    # ---- KILL --------------------------------------------------------------
    def kill_requested(self) -> bool:
        return os.path.exists(self.kill_file)

    def trigger_kill(self, reason: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.kill_file)), exist_ok=True)
        if not os.path.exists(self.kill_file):
            tmp = self.kill_file + ".tmp"
            with open(tmp, "w") as f:
                f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {reason}\n")
            os.replace(tmp, self.kill_file)
        self.j.set("risk.state", "KILLED")
        self.j.event("critical", "risk", f"KILL: {reason}")

    def reset_kill(self) -> bool:
        """Solo a mano, e solo dopo che il file KILL e' stato tolto. Riparte da HALTED, non da NORMAL."""
        if self.kill_requested():
            return False
        self.j.set("risk.state", "HALTED")
        self.j.set("risk.high_water", None)          # il massimo riparte dal valore attuale: niente KILL immediato al riavvio
        self.j.event("warn", "risk", "KILL azzerato a mano: stato HALTED, massimo storico ripartito")
        return True

    # ---- valutazione --------------------------------------------------------
    def assess(self, equity: float, now: float | None = None, data_stale: list | None = None,
               unreconciled: bool = False, error_streak: int = 0) -> Assessment:
        now = now or time.time()
        prev = self.j.get("risk.state", "NORMAL")
        hw = self.j.get("risk.high_water")
        hw = equity if not hw else max(hw, equity)
        self.j.set("risk.high_water", hw)
        dd = equity / hw - 1.0 if hw > 0 else 0.0
        day_ref, week_ref = self._ref(now, 86400.0, equity), self._ref(now, 7 * 86400.0, equity)
        day, week = equity / day_ref - 1.0, equity / week_ref - 1.0
        reasons, state = [], "NORMAL"

        def worse(s, why):
            nonlocal state
            reasons.append(why)
            if STATES.index(s) > STATES.index(state):
                state = s
        if self.kill_requested():
            worse("KILLED", "file KILL presente")
        if prev == "KILLED":
            worse("KILLED", "KILL a ritenuta: serve il comando reset-kill")
        if dd <= -self.l.dd_kill:
            worse("KILLED", f"caduta {dd:.1%} oltre il limite {-self.l.dd_kill:.0%}")
        if dd <= -self.l.dd_halt:
            worse("HALTED", f"caduta {dd:.1%} oltre {-self.l.dd_halt:.0%}")
        elif dd <= -self.l.dd_reduce:
            worse("REDUCED", f"caduta {dd:.1%} oltre {-self.l.dd_reduce:.0%}")
        if week <= -self.l.weekly_loss:
            worse("HALTED", f"perdita a 7 giorni {week:.1%} oltre {-self.l.weekly_loss:.0%}")
        if day <= -self.l.daily_loss:
            worse("REDUCED", f"perdita a 24 ore {day:.1%} oltre {-self.l.daily_loss:.0%}")
        if data_stale:
            worse("HALTED", "dati vecchi: " + ", ".join(data_stale))
        if unreconciled:
            worse("HALTED", "ordini non riconciliati con il broker")
        if error_streak >= self.l.max_errors:
            worse("HALTED", f"{error_streak} cicli falliti di fila")
        # isteresi: si risale solo quando la caduta e' rientrata sotto META' della soglia che aveva fatto scendere
        if state != "KILLED" and STATES.index(state) < STATES.index(prev):
            if prev == "HALTED" and dd <= -self.l.dd_halt / 2:
                worse("HALTED", f"in attesa del rientro sotto {-self.l.dd_halt / 2:.1%}")
            elif prev in ("HALTED", "REDUCED") and dd <= -self.l.dd_reduce / 2:
                worse("REDUCED", f"in attesa del rientro sotto {-self.l.dd_reduce / 2:.1%}")
        if state == "KILLED" and prev != "KILLED":
            self.trigger_kill("; ".join(reasons))
        if state != prev:
            self.j.event("critical" if state in ("KILLED", "HALTED") else "warn", "risk",
                         f"stato {prev} -> {state}: {'; '.join(reasons) or 'rientro'}")
        self.j.set("risk.state", state)
        return Assessment(state, SCALE[state], reasons, dd, day, week, hw)

    def _ref(self, now: float, span: float, equity: float) -> float:
        r = self.j.db.execute("SELECT equity FROM nav WHERE ts<=? ORDER BY ts DESC LIMIT 1", (now - span,)).fetchone()
        if r:
            return r["equity"]
        r = self.j.db.execute("SELECT equity FROM nav ORDER BY ts LIMIT 1").fetchone()
        return r["equity"] if r else equity

    # ---- pesi e ordini ------------------------------------------------------
    def clamp_weights(self, w: dict[str, float], venue_of: dict[str, str]) -> tuple[dict[str, float], list[str]]:
        """Applica i tetti ai pesi obiettivo: singolo strumento, sede, leva. Riduce soltanto, non aumenta mai."""
        notes = []
        w = dict(w)
        for k, v in w.items():
            if abs(v) > self.l.max_weight:
                w[k] = self.l.max_weight * (1 if v > 0 else -1)
                notes.append(f"{k} limitato al {self.l.max_weight:.0%}")
        for venue, cap in self.l.max_venue.items():
            tot = sum(abs(v) for k, v in w.items() if venue_of.get(k) == venue)
            if tot > cap:
                for k in w:
                    if venue_of.get(k) == venue:
                        w[k] *= cap / tot
                notes.append(f"sede {venue} ridotta dal {tot:.0%} al {cap:.0%}")
        gross = sum(abs(v) for v in w.values())
        if gross > self.l.max_leverage:
            w = {k: v * self.l.max_leverage / gross for k, v in w.items()}
            notes.append(f"leva ridotta da {gross:.2f}x a {self.l.max_leverage:.2f}x")
        return w, notes

    def check_order(self, symbol: str, delta_value: float, cur_value: float, price: float, last_price: float,
                    equity: float, state: str) -> tuple[bool, str]:
        """delta_value: controvalore con segno dell'ordine; cur_value: valore con segno della posizione attuale."""
        reducing = abs(cur_value + delta_value) < abs(cur_value) - 1e-9 and (cur_value + delta_value) * cur_value >= 0
        if state == "KILLED" and not reducing:
            return False, "KILL attivo: solo chiusure"
        if state == "HALTED" and not reducing:
            return False, "HALTED: nessun aumento di rischio"
        if price <= 0 or last_price <= 0:
            return False, "prezzo non valido"
        if abs(price / last_price - 1.0) > self.l.max_price_dev:
            return False, f"prezzo fuori dal {self.l.max_price_dev:.0%} dall'ultimo noto"
        if not reducing and abs(delta_value) > self.l.max_order_frac * equity:
            return False, f"ordine oltre il {self.l.max_order_frac:.0%} del patrimonio"
        if abs(delta_value) < self.l.min_order and not (reducing and abs(cur_value + delta_value) < 1e-6):
            return False, "sotto l'ordine minimo"
        return True, ""
