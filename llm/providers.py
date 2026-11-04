"""
Adattatore dei provider LLM.

  AnthropicProvider        SDK ufficiale `anthropic`, output JSON a schema (output_config.format),
                           prompt stabile in cache, fallback lato server sui rifiuti (Sonnet/Opus 5.5)
  OpenAICompatibleProvider Kimi (Moonshot) e Gemini via endpoint compatibili OpenAI: consulenti esterni
                           e Capi Pod ospiti. TUTTO il testo passa dal filtro dei segreti prima di uscire.
  DryRunProvider           nessuna chiave: risposta deterministica e valida per lo schema, costo zero,
                           marcata come SIMULATA nel portale. Serve a far girare la societa' senza spendere.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import yaml

from firm import paths
from . import redact


@dataclass
class LLMResult:
    text: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read: int = 0
    cache_write: int = 0
    simulated: bool = False
    stop_reason: str = ""
    extra: dict = field(default_factory=dict)


def _cfg() -> dict:
    return yaml.safe_load(open(os.path.join(paths.CONFIG, "models.yaml")))


class AnthropicProvider:
    name = "anthropic"

    def __init__(self):
        import anthropic
        self.client = anthropic.Anthropic()

    def complete(self, model: str, system: str, user: str, schema: dict, max_tokens: int,
                 effort: str = "low") -> LLMResult:
        kwargs = dict(
            model=model, max_tokens=max_tokens,
            # prompt stabile in testa e in cache (guida §6): i dati variabili stanno nel messaggio utente
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        )
        if model.startswith(("claude-opus-5-5", "claude-sonnet-5-5")):
            # fallback lato server sui rifiuti dei classificatori di sicurezza (opt-in consigliato)
            r = self.client.beta.messages.create(betas=["server-side-fallback-2026-07-01"],
                                                 fallbacks="default", **kwargs)
        else:
            r = self.client.messages.create(**kwargs)
        text = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "")
        u = r.usage
        return LLMResult(text=text, model=getattr(r, "model", model), provider=self.name,
                         input_tokens=u.input_tokens or 0, output_tokens=u.output_tokens or 0,
                         cache_read=getattr(u, "cache_read_input_tokens", 0) or 0,
                         cache_write=getattr(u, "cache_creation_input_tokens", 0) or 0,
                         stop_reason=r.stop_reason or "")


class OpenAICompatibleProvider:
    """Kimi / Gemini. Nessun dato sensibile in uscita: system e user vengono filtrati."""

    def __init__(self, name: str):
        c = _cfg()["providers"][name]
        self.name = name
        self.base_url = c["base_url"].rstrip("/")
        self.key = os.environ.get(c["env_key"], "")
        self.model = os.environ.get(c.get("model_env", ""), name)
        if not self.key:
            raise RuntimeError(f"manca {c['env_key']} in .env: chiavi nuove = grande richiesta ad Andrea")

    def complete(self, model: str, system: str, user: str, schema: dict, max_tokens: int,
                 effort: str = "low") -> LLMResult:
        import httpx
        sys_txt = redact.text(system + "\n\nRispondi SOLO con un oggetto JSON valido per questo schema:\n"
                              + json.dumps(schema, ensure_ascii=False))
        body = dict(model=self.model, max_tokens=max_tokens, response_format={"type": "json_object"},
                    messages=[{"role": "system", "content": sys_txt},
                              {"role": "user", "content": redact.text(user)}])
        r = httpx.post(f"{self.base_url}/chat/completions", json=body, timeout=120,
                       headers={"Authorization": f"Bearer {self.key}"})
        r.raise_for_status()
        j = r.json()
        u = j.get("usage", {})
        return LLMResult(text=j["choices"][0]["message"]["content"], model=self.name, provider=self.name,
                         input_tokens=u.get("prompt_tokens", 0), output_tokens=u.get("completion_tokens", 0),
                         stop_reason=j["choices"][0].get("finish_reason", ""))


def _example(schema: dict):
    """Istanza minima valida per lo schema (DryRun): sceglie il valore piu' prudente disponibile."""
    t = schema.get("type")
    if "enum" in schema:
        prudent = [v for v in schema["enum"] if str(v) in ("servono_dati", "non_so", "respingi", "chiedi_dati",
                                                          "nessuna_azione", "non_verificata", "giallo", "attendi")]
        return prudent[0] if prudent else schema["enum"][0]
    if t == "object":
        return {k: _example(v) for k, v in schema.get("properties", {}).items() if k in schema.get("required", [])}
    if t == "array":
        return []
    if t == "string":
        return "dati insufficienti (risposta simulata: nessuna chiave API configurata)"
    if t in ("number", "integer"):
        lo = schema.get("minimum", 0)
        return lo if t == "integer" else float(max(lo, min(schema.get("maximum", 0.5), 0.5)))
    if t == "boolean":
        return False
    return None


class DryRunProvider:
    name = "dry-run"

    def complete(self, model: str, system: str, user: str, schema: dict, max_tokens: int,
                 effort: str = "low") -> LLMResult:
        return LLMResult(text=json.dumps(_example(schema), ensure_ascii=False), model="dry-run",
                         provider=self.name, simulated=True, stop_reason="end_turn")


def for_agent(profile: dict):
    prov = profile.get("provider") or "anthropic"
    if prov == "anthropic":
        return AnthropicProvider() if os.environ.get("ANTHROPIC_API_KEY") else DryRunProvider()
    try:
        return OpenAICompatibleProvider(prov)
    except RuntimeError:
        return DryRunProvider()
