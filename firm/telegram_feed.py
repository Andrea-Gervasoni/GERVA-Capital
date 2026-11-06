"""
Segnali da Telegram: la societa' legge i gruppi e i canali che Andrea indica e passa i segnali alla sala segnali.

Come si collega (e perche' cosi'):
  * Andrea e' un MEMBRO delle sale segnali, non l'amministratore: un bot non si puo' aggiungere. Si usa quindi l'account di
    Andrea in SOLA LETTURA (libreria Telethon, API ufficiale di Telegram): la societa' ascolta i messaggi nuovi, non scrive mai.
  * credenziali: TELEGRAM_API_ID e TELEGRAM_API_HASH (gratis su my.telegram.org) e una sessione salvata in var/telegram.session
    (permessi 600) dopo un accesso fatto UNA volta da Andrea sul suo Terminale. La sessione equivale all'accesso all'account:
    mai in chat, mai nei log, mai in git. Il filtro dei segreti (llm/redact.py) la oscura comunque.
  * il testo dei messaggi e' un dato NON FIDATO (chiunque nel gruppo puo' scrivere): non da' ordini, passa per la sala segnali
    (controlli del codice, analisi, veto del Rischio, tetti). Ci sono filtri sul ritmo e sui doppioni.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import threading

from . import db, events, paths, signals
from . import settings as S

MAX_AGE_MIN = 15                      # un messaggio piu' vecchio (recuperato dopo una pausa) non si tratta come segnale nuovo
MAX_LEN = 2000


def looks_like_signal(text: str) -> bool:
    """Filtro economico prima di spendere una chiamata: moneta + azione + almeno un livello (ingresso, stop, obiettivo)."""
    u = text.upper()
    coin = any(re.search(rf"(?<![A-Z]){c}(?![A-Z])", u) for c in signals.COINS)
    action = re.search(r"\b(BUY|LONG|SELL|SHORT|COMPRA|VENDI|ACQUISTA)\b", u)
    levels = re.search(r"\b(ENTRY|INGRESSO|ENTRATA|SL|STOP|TP\d?|TARGET|TAKE PROFIT|OBIETTIVO)\b", u)
    return bool(coin and action and levels)


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip().upper()


def handle_message(text: str, chat: str, when: dt.datetime | None = None, now: dt.datetime | None = None, background: bool = True) -> dict:
    """Decide se un messaggio entra nella sala segnali. Ritorna dict(azione=..., id=...)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    text = (text or "").strip()
    if len(text) < 15 or len(text) > MAX_LEN or not looks_like_signal(text):
        return dict(azione="ignorato")
    if when and (now - when.astimezone(dt.timezone.utc)).total_seconds() > MAX_AGE_MIN * 60:
        return dict(azione="troppo_vecchio")
    key = _norm(text)
    since = (now - dt.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
    if any(_norm(r["testo"]) == key for r in db.q("SELECT testo FROM signals WHERE ts>=?", (since,))):
        return dict(azione="doppione")
    hour_ago = (now - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S")
    n = db.one("SELECT COUNT(*) n FROM signals WHERE fonte LIKE 'Telegram:%' AND ts>=?", (hour_ago,))["n"]
    if n >= int(S.get("signals.telegram_max_per_hour", 10)):
        events.publish("signal.throttled", "telegram", dict(chat=chat[:40]))
        return dict(azione="limite_orario")
    sid = signals.create(text, f"Telegram: {chat}"[:60])
    execute = bool(S.get("signals.telegram_execute", True))

    def work():
        try:
            signals.process(sid, execute=execute)
        except Exception as e:                                  # mai 'accettato' per un errore
            db.ex("UPDATE signals SET stato='osservato', motivo=? WHERE id=?", (f"analisi non riuscita: {str(e)[:120]}", sid))
    if background:
        threading.Thread(target=work, daemon=True).start()
    else:
        work()
    return dict(azione="inviato", id=sid)


# ---------------------------------------------------------------------------------------------- collegamento (Telethon)
def _creds() -> tuple[int, str, str]:
    api_id, api_hash = os.environ.get("TELEGRAM_API_ID", ""), os.environ.get("TELEGRAM_API_HASH", "")
    if not api_id.isdigit() or not api_hash:
        raise SystemExit("mancano TELEGRAM_API_ID e TELEGRAM_API_HASH in .env (si ottengono gratis su my.telegram.org)")
    return int(api_id), api_hash, os.path.join(paths.VAR, "telegram")


def _client():
    try:
        from telethon import TelegramClient
    except ImportError:
        raise SystemExit("serve telethon: .venv/bin/pip install telethon")
    api_id, api_hash, session = _creds()
    return TelegramClient(session, api_id, api_hash)


def _qr_login(client, run) -> None:
    """Accesso con il codice QR: niente SMS e niente codice. Si inquadra dal telefono (Impostazioni > Dispositivi)."""
    import asyncio
    from telethon.errors import SessionPasswordNeededError
    try:
        import qrcode
    except ImportError:
        raise SystemExit("serve qrcode: .venv/bin/pip install qrcode")
    run(client.connect())
    if run(client.is_user_authorized()):
        return
    qr = run(client.qr_login())
    for tentativo in range(6):
        q = qrcode.QRCode(border=1)
        q.add_data(qr.url)
        q.make()
        print("\nSul telefono: Telegram > Impostazioni > Dispositivi > Collega un dispositivo desktop, e inquadra questo codice")
        print("(scade in pochi secondi: se non fai in tempo se ne crea uno nuovo da solo)\n")
        q.print_ascii(invert=True)
        try:
            run(qr.wait(30))
            return
        except SessionPasswordNeededError:
            import getpass
            run(client.sign_in(password=getpass.getpass("Password della verifica in due passaggi: ")))
            return
        except (asyncio.TimeoutError, TimeoutError):
            run(qr.recreate())
    raise SystemExit("codice QR scaduto troppe volte: riprova")


def login(sms: bool = False, qr: bool = False) -> None:
    """Accesso interattivo, UNA volta, sul Terminale di Andrea: telefono e codice non passano da nessun'altra parte.
    sms=True chiede a Telegram di mandare il codice per SMS invece che nell'app (utile se l'app non lo mostra)."""
    client = _client()
    run = client.loop.run_until_complete
    if qr:
        _qr_login(client, run)
    elif not sms:
        client.start()                                                       # telefono, codice e (se c'e') password a 2 fattori
    else:
        from telethon.errors import SessionPasswordNeededError
        run(client.connect())
        if not run(client.is_user_authorized()):
            phone = input("Numero di telefono con prefisso (+39...): ").strip().replace(" ", "")
            sent = run(client.send_code_request(phone))                      # Telegram sceglie il canale: di solito l'app
            code = input("Codice (scrivilo qui). Se non arriva dopo 1-2 minuti premi solo Invio per chiedere l'SMS: ").strip()
            if not code:
                from telethon.errors import RPCError
                from telethon.tl.functions.auth import ResendCodeRequest
                try:
                    sent = run(client(ResendCodeRequest(phone, sent.phone_code_hash)))
                except RPCError as e:
                    raise SystemExit(f"Telegram non permette un altro invio adesso ({type(e).__name__}): aspetta mezz'ora e riprova")
                code = input("Codice ricevuto (SMS o chiamata): ").strip()
            try:
                run(client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash))
            except SessionPasswordNeededError:
                import getpass
                run(client.sign_in(password=getpass.getpass("Password della verifica in due passaggi: ")))
    try:
        os.chmod(os.path.join(paths.VAR, "telegram.session"), 0o600)
    except OSError:
        pass
    print("\nCollegato. I tuoi gruppi e canali:")
    dialogs = [d for d in run(client.get_dialogs()) if d.is_group or d.is_channel]
    for d in dialogs[:60]:
        print(f"  - {d.name}")
    names = input("\nScrivi i NOMI delle sale segnali da ascoltare, separati da virgola: ").strip()
    if names:
        env = os.path.join(paths.ROOT, ".env")
        lines = [l for l in open(env).read().splitlines() if not l.startswith("TELEGRAM_CHATS=")] if os.path.exists(env) else []
        open(env, "w").write("\n".join(lines + [f"TELEGRAM_CHATS={names}"]) + "\n")
        os.chmod(env, 0o600)
        print("Salvato in .env. Ora puoi avviare l'ascolto: firm.py telegram")
    client.disconnect()


def run() -> None:
    """Ascolta i messaggi nuovi nelle sale indicate (TELEGRAM_CHATS, nomi separati da virgola). Solo lettura."""
    from telethon import events as tl_events
    wanted = [x.strip().lower() for x in os.environ.get("TELEGRAM_CHATS", "").split(",") if x.strip()]
    if not wanted:
        raise SystemExit("manca TELEGRAM_CHATS in .env: lancia prima firm.py telegram-login")
    client = _client()
    client.start()                                                           # usa la sessione salvata: nessuna domanda
    ids: dict[int, str] = {}
    for d in client.loop.run_until_complete(client.get_dialogs()):
        if any(w in d.name.lower() for w in wanted):
            ids[d.id] = d.name
    if not ids:
        raise SystemExit("nessuna delle sale in TELEGRAM_CHATS corrisponde ai tuoi gruppi")
    print("ascolto (solo lettura):", ", ".join(ids.values()))

    @client.on(tl_events.NewMessage())
    async def on_message(ev):
        if ev.chat_id in ids and ev.raw_text:
            r = handle_message(ev.raw_text, ids[ev.chat_id], ev.date)
            if r["azione"] == "inviato":
                print(f"segnale #{r['id']} da {ids[ev.chat_id]}", flush=True)
    client.run_until_disconnected()
