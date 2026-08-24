"""
Agente local — fica rodando no seu Mac, escutando em http://localhost:5002.

É nele que o dashboard do app de tarifas (botão "Gravar no LexDash" /
"Gravar no Sistema" 🖨) bate para abrir o navegador e preencher o grid do
LexDash automaticamente.

Rotas (mesmo contrato que os templates index.html / revisar.html esperam):
    POST /gravar-lexdash          → preenche todos os itens aprovados
    POST /gravar-fatura           → preenche uma única fatura ({"fatura_id": N})
    GET  /gravar-lexdash/status   → {"estado": "idle|rodando|ok|erro", "log": "..."}

Uso:
    python servidor_local.py

Pré-requisito:
    - login_lexdash.py executado ao menos uma vez (gera lexdash_session.json)
    - TARIFAS_API_URL configurado (padrão: o Railway em produção)
    - ADMIN_TOKEN configurado, se o app exigir
"""
import json
import os
import threading
import traceback

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

import preencher_lexdash as pl

app = Flask(__name__)
# O dashboard roda em outro domínio (Railway) e chama este servidor local via
# fetch('http://localhost:5002/...'); sem CORS liberado o navegador bloqueia.
CORS(app)

_lock = threading.Lock()
_estado = {"estado": "idle", "log": ""}


def _set_estado(estado, log=None):
    with _lock:
        _estado["estado"] = estado
        if log is not None:
            _estado["log"] = log


def _append_log(msg):
    with _lock:
        _estado["log"] = (_estado["log"] + "\n" + msg).strip()


def _rodar(itens):
    """Executa preencher() em background e atualiza o estado global."""
    _set_estado("rodando", "")
    try:
        pl.preencher(itens, log_fn=_append_log)
        _set_estado("ok")
    except Exception as e:
        print("!! Erro durante preenchimento:")
        traceback.print_exc()
        _append_log(f"ERRO: {e}")
        _set_estado("erro")


@app.route("/gravar-lexdash", methods=["POST"])
def gravar_lexdash():
    if _estado["estado"] == "rodando":
        return jsonify({"msg": "Já existe um preenchimento em andamento."}), 409

    try:
        itens = pl._buscar_aprovados()
    except Exception as e:
        print("!! Erro ao buscar aprovados:")
        traceback.print_exc()
        return jsonify({"msg": f"Erro ao buscar aprovados: {e}"}), 500

    if not itens:
        return jsonify({"msg": "Nenhum item aprovado aguardando preenchimento."}), 400

    threading.Thread(target=_rodar, args=(itens,), daemon=True).start()
    return jsonify({"ok": True})


@app.route("/gravar-fatura", methods=["POST"])
def gravar_fatura():
    if _estado["estado"] == "rodando":
        return jsonify({"msg": "Já existe um preenchimento em andamento."}), 409

    body = request.get_json(silent=True) or {}
    fatura_id = body.get("fatura_id")
    if not fatura_id:
        return jsonify({"msg": "fatura_id é obrigatório."}), 400

    try:
        resp = requests.get(
            f"{pl.TARIFAS_API_URL}/api/faturas/{fatura_id}",
            headers=pl._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        fatura = resp.json()
    except Exception as e:
        print(f"!! Erro ao buscar fatura {fatura_id} em {pl.TARIFAS_API_URL}:")
        traceback.print_exc()
        return jsonify({"msg": f"Erro ao buscar fatura: {e}"}), 500

    if not fatura.get("tarifa_geracao"):
        return jsonify({"msg": "Fatura sem tarifa_geracao calculada."}), 400

    item = {
        "id": None,  # não é um item de faturas_pendentes: não marca "preenchido" na API
        "distribuidora": fatura.get("distribuidora"),
        "mes_ref": fatura.get("mes_referencia"),
        "tipo_gd": fatura.get("tipo_gd"),
        "modalidade": fatura.get("modalidade"),
        "tarifa_geracao": fatura.get("tarifa_geracao"),
        "usinas": json.dumps([fatura.get("usina_id")]),
    }

    threading.Thread(target=_rodar, args=([item],), daemon=True).start()
    return jsonify({"ok": True})


@app.route("/gravar-lexdash/status")
def gravar_lexdash_status():
    with _lock:
        return jsonify(dict(_estado))


if __name__ == "__main__":
    print(f"Agente local rodando em http://localhost:5002  (API: {pl.TARIFAS_API_URL})")
    app.run(host="127.0.0.1", port=5002, debug=False)
