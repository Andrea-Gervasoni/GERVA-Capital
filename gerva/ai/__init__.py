"""
Livello AI di GERVA: ricerca continua, regime, rischio prima dell'ingresso, decadimento delle strategie.

Chi decide che cosa:
    agenti LLM (desk.py)        leggono notizie, macro, utili, sentiment: propongono RIDUZIONI o VETI, con le fonti
    regime (regime.py)          classificatore deterministico del regime di mercato -> moltiplicatore <= 1
    decadimento (decay.py)      confronto dal vivo contro backtest per strategia -> riduce o mette in pausa
    overlay (overlay.py)        unisce i tre, valida, scade; il ciclo lo applica ai pesi
    motore di rischio           ha SEMPRE l'ultima parola (gerva/risk/engine.py), e gli agenti non lo possono toccare

L'AI non puo' aumentare un'esposizione ne' fornire numeri al dimensionamento: puo' solo abbassare un moltiplicatore
tra 0 e 1. Il motivo e' nei dati: gli LLM che decidono le operazioni non battono l'indice dopo i costi, mentre come
filtro un errore costa un'occasione persa, non denaro (docs/archivio_RIFONDAZIONE_v2.md, sezioni 2.6 e 10).
"""
from .overlay import Overlay, combine, load, save

__all__ = ["Overlay", "combine", "load", "save"]
