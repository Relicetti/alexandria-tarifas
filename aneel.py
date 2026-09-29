"""
Bandeira tarifária oficial do mês, pelos dados abertos da ANEEL.

Fonte: dataset "Bandeiras Tarifárias" → CSV "Bandeira Tarifária - Acionamento"
(uma linha por mês: DatCompetencia, NomBandeiraAcionada, VlrAdicionalBandeira
em R$/MWh, SEM impostos). A ANEEL costuma publicar o mês seguinte no fim do
mês corrente.

O CSV (~140 linhas) fica em cache no volume (/data) e é rebaixado a cada
CACHE_HORAS; se a ANEEL estiver fora do ar, usa o cache velho.
"""
import csv
import io
import os
import time
import urllib.request
from pathlib import Path

URL_ACIONAMENTO = (
    "https://dadosabertos.aneel.gov.br/dataset/7f43a020-6dc5-44b8-80b4-d97eaa94436c"
    "/resource/0591b8f6-fe54-437b-b72b-1aa2efd46e42/download/bandeira-tarifaria-acionamento.csv"
)
CACHE_HORAS = 12

_DATA_DIR = Path(os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "tarifas.db"))).parent
CACHE_FILE = _DATA_DIR / "aneel_bandeira_acionamento.csv"

# Nome da ANEEL → prefixo dos campos b_<tipo>_* da fatura
TIPO_CAMPO = {"Amarela": "amarela", "Vermelha P1": "verm_p1", "Vermelha P2": "verm_p2"}


def _baixar() -> str:
    req = urllib.request.Request(URL_ACIONAMENTO, headers={"User-Agent": "alexandria-tarifas"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8-sig")


def _csv_texto() -> str:
    fresco = CACHE_FILE.exists() and time.time() - CACHE_FILE.stat().st_mtime < CACHE_HORAS * 3600
    if not fresco:
        try:
            texto = _baixar()
            if "DatCompetencia" in texto:
                try:
                    CACHE_FILE.write_text(texto, encoding="utf-8")
                except OSError:
                    pass  # sem volume (dev local) — segue sem cache
                return texto
        except Exception:
            pass  # ANEEL fora do ar: cai no cache, mesmo velho
    if CACHE_FILE.exists():
        return CACHE_FILE.read_text(encoding="utf-8")
    raise RuntimeError("Não foi possível obter as bandeiras da ANEEL (sem conexão e sem cache).")


def _num(s: str) -> float:
    return float((s or "0").replace(".", "").replace(",", "."))


def bandeiras() -> dict:
    """{'YYYY-MM': {'bandeira': 'Amarela', 'rs_mwh': 18.85, 'rs_kwh': 0.01885}}"""
    out = {}
    for row in csv.DictReader(io.StringIO(_csv_texto()), delimiter=";"):
        mes = (row.get("DatCompetencia") or "")[:7]
        if not mes:
            continue
        rs_mwh = _num(row.get("VlrAdicionalBandeira"))
        out[mes] = {
            "bandeira": (row.get("NomBandeiraAcionada") or "").strip(),
            "rs_mwh": rs_mwh,
            "rs_kwh": round(rs_mwh / 1000, 6),
        }
    return out


def _mes_anterior(mes: str) -> str:
    a, m = int(mes[:4]), int(mes[5:7])
    return f"{a - 1}-12" if m == 1 else f"{a}-{m - 1:02d}"


def dias_por_mes(leitura_anterior: str, leitura_atual: str) -> list:
    """
    Divide o período de leitura em dias por mês, como as distribuidoras fazem
    no pró-rata da bandeira: conta do dia da leitura anterior até a véspera da
    leitura atual (total = atual − anterior).
    08/07 → 06/08 = 24 dias em julho + 5 em agosto = 29.
    """
    from datetime import date
    ini, fim = date.fromisoformat(leitura_anterior), date.fromisoformat(leitura_atual)
    out, cur = [], ini
    while cur < fim:
        prox = date(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
        corte = min(prox, fim)
        out.append((f"{cur.year}-{cur.month:02d}", (corte - cur).days))
        cur = corte
    return out


def bandeira_periodo(leitura_anterior: str, leitura_atual: str) -> dict:
    """
    Bandeira de cada mês do período de leitura, com os dias em cada uma e o
    adicional médio ponderado pelos dias (R$/kWh, sem impostos) — é o valor
    que a fatura deveria cobrar por kWh antes dos impostos.
    """
    tab = bandeiras()
    partes, soma, total = [], 0.0, 0
    for mes, dias in dias_por_mes(leitura_anterior, leitura_atual):
        b = tab.get(mes)
        partes.append({"mes": mes, "dias": dias,
                       "bandeira": b["bandeira"] if b else None,
                       "rs_kwh": b["rs_kwh"] if b else None})
        total += dias
        if b:
            soma += dias * b["rs_kwh"]
    completo = all(p["bandeira"] for p in partes)
    return {
        "leitura_anterior": leitura_anterior,
        "leitura_atual": leitura_atual,
        "dias_total": total,
        "partes": partes,
        # só faz sentido com todos os meses publicados pela ANEEL
        "rs_kwh_ponderado": round(soma / total, 6) if completo and total else None,
    }


def bandeira_do_mes(mes: str) -> dict:
    """
    Bandeira oficial do mês de referência (YYYY-MM) e do mês anterior — a
    leitura da fatura costuma cobrir parte dos dois, então a fatura pode
    trazer as duas bandeiras.
    """
    mes = (mes or "")[:7]
    tab = bandeiras()
    ant = _mes_anterior(mes) if len(mes) == 7 else ""
    return {
        "mes": mes,
        "atual": tab.get(mes),
        "anterior": tab.get(ant),
        "mes_anterior": ant,
        "fonte": "ANEEL — Dados Abertos, Bandeira Tarifária (Acionamento)",
    }
