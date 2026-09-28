"""
Replica no LexDash tarifas já cadastradas em uma usina para as usinas "irmãs"
que ainda estão pendentes.

As usinas 2 a 8 são calculadas do mesmo jeito (ex.: EDP SP GD1 GC da usina 3
é igual à da 5 e da 6), e as usinas 101, 102 e 103 também entre si. Então,
se a tela "Tarifas pendentes de cadastro" (Streamlit) acusa que falta, por
exemplo, EDP SP / usina 5 / 09-2026 / GC / GD1, e a usina 3 já tem esse valor
no LexDash, o mesmo valor é gravado na usina 5.

Fluxo:
  1. planejar(): baixa o CSV "cadastros" da tela de pendentes (PENDENTES_URL),
     lê as tarifas já gravadas no LexDash (API tarifas-variaveis) e monta o
     plano: para cada pendente, procura o valor nas usinas irmãs (mesma
     concessionária, mês, modalidade e GD1/GD2). Só replica quando todas as
     irmãs preenchidas concordam; se divergirem, pula e avisa.
  2. Tela de verificação no /revisar: o usuário escolhe o que gravar.
  3. gravar(): abre o grid, preenche as células (só as que estão vazias) e
     espera o usuário conferir e clicar Salvar em cada passagem (GD1 / GD2 /
     Cacau); depois confere via API se os valores ficaram gravados.

Uso:
    python replicar_tarifas.py            # só mostra o plano
    python replicar_tarifas.py --gravar   # grava tudo
"""
import argparse
import csv
import io
import os
from collections import defaultdict

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from playwright.sync_api import sync_playwright

import preencher_lexdash as pl

PENDENTES_URL = os.environ.get(
    "PENDENTES_URL",
    "https://alex-dev-01.taila7e218.ts.net:10000/pub/fb8f2dcd3e956f6f9365a63afbbca331/",
)
URL_API_TARIFAS = "https://crm-lex.energiacom.vc/api/data/tarifas-variaveis"

# Usinas cuja tarifa é calculada do mesmo jeito dentro do grupo
GRUPOS_USINAS = [frozenset(range(2, 9)), frozenset({101, 102, 103})]

# Passagens do grid: os checkboxes "Tarifa GD2" e "Tarifa Cacau Show" são
# mutuamente exclusivos (marcar um desmarca o outro). Na visão Cacau Show a
# célula é única e só existe o valor GD1 — não há como gravar GD2 de Cacau.
VISOES = ["GD1", "GD2", "CacauShow"]
CAMPOS = ("tarifa_variavel_calculada", "tarifa_variavel_gd2")

SEM_FONTE = "nenhuma usina irmã calculada"


def _grupo(usina: int):
    return next((g for g in GRUPOS_USINAS if usina in g), None)


def _float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _logger(log_fn):
    def log(msg):
        try:
            print(msg)
        except Exception:
            pass
        if log_fn:
            log_fn(msg)
    return log


def baixar_pendentes(p, log) -> list:
    """Abre a tela de pendentes (Streamlit), clica Atualizar e baixa o CSV
    de cadastros. Cada linha = concessionária × usina × mês × modalidade."""
    log("Baixando lista de tarifas pendentes…")
    navegador = p.webkit.launch(headless=True)
    try:
        ctx = navegador.new_context(ignore_https_errors=True, accept_downloads=True)
        pagina = ctx.new_page()
        pagina.goto(PENDENTES_URL, timeout=30000)
        pagina.wait_for_selector("text=Cadastros a fazer", timeout=60000)
        atualizar = pagina.locator("button:has-text('Atualizar')").first
        if atualizar.count() > 0:
            atualizar.click()
            pagina.wait_for_timeout(1500)
            pagina.wait_for_selector("text=Cadastros a fazer", timeout=60000)
        botao = pagina.locator("button:has-text('CSV (cadastros)')").first
        botao.wait_for(timeout=60000)
        with pagina.expect_download(timeout=30000) as dl:
            botao.click()
        caminho = dl.value.path()
        with open(caminho, encoding="utf-8-sig") as f:
            linhas = list(csv.DictReader(io.StringIO(f.read())))
    finally:
        navegador.close()
    log(f"{len(linhas)} cadastro(s) pendente(s) na lista.")
    return linhas


def buscar_tarifas(pagina, meses) -> dict:
    """{'2026-09': [registros de tarifas_variaveis], ...} via API do LexDash
    (usa a sessão já aberta na página)."""
    out = {}
    for mes in meses:
        r = pagina.request.post(URL_API_TARIFAS, data={"mes_referencia": f"{mes}-01"})
        if not r.ok:
            raise RuntimeError(f"API tarifas-variaveis respondeu {r.status} para {mes}.")
        out[mes] = r.json()
    return out


def _visao_e_campo(pendente):
    """(visao, campo) de um pendente, ou (None, motivo) se não dá pra gravar."""
    gd2 = str(pendente.get("gd2")).strip().lower() == "true"
    campo = CAMPOS[1] if gd2 else CAMPOS[0]
    if pendente["modalidade"] == "cacaushow":
        if gd2:
            return None, "Cacau Show GD2 não tem campo no grid"
        return "CacauShow", campo
    return ("GD2" if gd2 else "GD1"), campo


def montar_plano(pendentes: list, tarifas: dict):
    """Retorna (acoes, pulados), ambos listas de dicts com mes, distribuidora,
    usina, usina_nome, modalidade, gd e faturas_travadas.
    acao   += visao, campo, valor, fontes (usinas de onde veio o valor)
    pulado += motivo — só para pendentes de usinas dos grupos."""
    acoes, pulados = [], []
    for pd in pendentes:
        usina = int(pd["usina_id"])
        grupo = _grupo(usina)
        if not grupo:
            continue
        mes, dist, modal = pd["mes_referencia"], pd["distribuidora"], pd["modalidade"]
        base = dict(
            mes=mes, distribuidora=dist, usina=usina, usina_nome=pd.get("usina_nome", ""),
            modalidade=modal, gd="GD2" if str(pd.get("gd2")).strip().lower() == "true" else "GD1",
            faturas_travadas=int(_float(pd.get("faturas_travadas")) or 0),
        )
        visao, campo = _visao_e_campo(pd)
        if visao is None:
            pulados.append(dict(base, motivo=campo))
            continue

        # Nome da concessionária tem que bater exatamente: o LexDash tem, por
        # exemplo, "ESS" e "Energisa Sul-Sudeste" como cadastros distintos.
        fontes = defaultdict(list)
        for r in tarifas.get(mes, []):
            if (r["concessionaria"] == dist and r["modalidade"] == modal
                    and r["id_usina"] in grupo and r["id_usina"] != usina):
                v = _float(r.get(campo))
                if v:  # ignora vazio e 0,000000
                    fontes[round(v, 6)].append(r["id_usina"])

        if not fontes:
            pulados.append(dict(base, motivo=SEM_FONTE))
        elif len(fontes) > 1:
            detalhe = "; ".join(f"{v:.6f} (u{','.join(map(str, us))})" for v, us in fontes.items())
            pulados.append(dict(base, motivo=f"irmãs divergem: {detalhe}"))
        else:
            valor, us = next(iter(fontes.items()))
            acoes.append(dict(base, visao=visao, campo=campo, valor=valor, fontes=us))
    acoes.sort(key=lambda a: (a["mes"], a["distribuidora"], a["usina"]))
    return acoes, pulados


def validar_acoes(acoes) -> list:
    """Confere as ações vindas da tela de verificação antes de gravar."""
    ok = []
    for a in acoes or []:
        usina = int(a["usina"])
        valor = _float(a.get("valor"))
        if (not _grupo(usina) or a.get("visao") not in VISOES
                or a.get("campo") not in CAMPOS or not valor):
            raise ValueError(f"Ação inválida: {a}")
        ok.append(dict(a, usina=usina, valor=valor))
    return ok


def _definir_visao(pagina, visao: str):
    """Deixa os checkboxes do topo do grid no estado da visão pedida."""
    alvo = {"Tarifa GD2": visao == "GD2", "Tarifa Cacau Show": visao == "CacauShow"}
    # desmarca antes de marcar: os dois são mutuamente exclusivos
    for texto, marcado in sorted(alvo.items(), key=lambda kv: kv[1]):
        cb = pagina.locator(f"label:has-text('{texto}') input[type='checkbox']").first
        cb.set_checked(marcado, timeout=5000)
        pagina.wait_for_timeout(500)
    for texto, marcado in alvo.items():
        cb = pagina.locator(f"label:has-text('{texto}') input[type='checkbox']").first
        if cb.is_checked() != marcado:
            raise RuntimeError(f"Não consegui deixar '{texto}' {'marcado' if marcado else 'desmarcado'}.")
    pagina.wait_for_timeout(1500)


def _localizar_escopo(pagina, acao):
    """Célula (ou sub-bloco GC/Autoconsumo) da ação no grid, ou (None, motivo).
    Acha a linha pelo nome EXATO da concessionária (a busca por substring do
    preencher_lexdash confundiria, por ex., 'ESS' com outras linhas)."""
    idx_linha, idx_col = pagina.evaluate(
        """([nome, usina]) => {
            const linhas = Array.from(document.querySelectorAll('tbody tr'));
            const i = linhas.findIndex(tr => {
                const td = tr.querySelector('td');
                return td && td.innerText.trim() === nome;
            });
            const ths = Array.from(document.querySelectorAll('thead tr th'));
            const j = ths.findIndex(th => th.innerText.trim().endsWith(`(${usina})`));
            return [i, j];
        }""",
        [acao["distribuidora"], acao["usina"]],
    )
    if idx_linha < 0:
        return None, "linha da concessionária não existe no grid"
    if idx_col < 0:
        return None, "coluna da usina não existe no grid"
    td = pagina.locator("tbody tr").nth(idx_linha).locator("td").nth(idx_col)
    modal = "" if acao["visao"] == "CacauShow" else acao["modalidade"]
    return pl._escopo_modalidade(td, modal), None


def _conferir(pagina, acoes, log):
    """Relê a API e loga quais ações ficaram gravadas."""
    tarifas = buscar_tarifas(pagina, sorted({a["mes"] for a in acoes}))
    ok = 0
    for a in acoes:
        gravado = next(
            (_float(r.get(a["campo"])) for r in tarifas[a["mes"]]
             if r["concessionaria"] == a["distribuidora"] and r["id_usina"] == a["usina"]
             and r["modalidade"] == a["modalidade"]),
            None,
        )
        if gravado is not None and abs(gravado - a["valor"]) < 1e-6:
            ok += 1
        else:
            log(f"!! {a['distribuidora']} u{a['usina']} {a['mes']}: esperado {a['valor']:.6f}, "
                f"LexDash tem {gravado if gravado is not None else 'vazio'}.")
    log(f"Conferência: {ok}/{len(acoes)} gravada(s) no LexDash.")


def planejar(log_fn=None) -> dict:
    """Monta o plano sem abrir janela nem gravar nada:
    {"acoes": [...], "pulados": [...]}."""
    log = _logger(log_fn)
    if not os.path.exists(pl.ARQUIVO_SESSAO):
        raise RuntimeError("Sessão do LexDash não encontrada. Rode login_lexdash.py primeiro.")

    with sync_playwright() as p:
        pendentes = baixar_pendentes(p, log)
        navegador, pagina = pl._abrir_sessao_valida(p, log_fn=log_fn, headless=True)
        try:
            tarifas = buscar_tarifas(pagina, sorted({pd["mes_referencia"] for pd in pendentes}))
        finally:
            navegador.close()

    acoes, pulados = montar_plano(pendentes, tarifas)
    log(f"{len(acoes)} tarifa(s) para replicar; {len(pulados)} pendente(s) de usinas "
        f"2–8/101–103 sem como replicar.")
    return {"acoes": acoes, "pulados": pulados}


def gravar(acoes: list, log_fn=None):
    """Abre o LexDash, preenche as ações (só células vazias) e espera o
    usuário clicar Salvar em cada passagem; depois confere via API."""
    log = _logger(log_fn)
    acoes = validar_acoes(acoes)
    if not acoes:
        log("Nenhuma tarifa selecionada.")
        return

    with sync_playwright() as p:
        navegador, pagina = pl._abrir_sessao_valida(p, log_fn=log_fn)
        try:
            pl._abrir_card_usina(pagina)
            pl._aguardar_grid(pagina)

            por_mes = defaultdict(lambda: defaultdict(list))
            for a in acoes:
                por_mes[a["mes"]][a["visao"]].append(a)

            for mes in sorted(por_mes):
                ano, mm = mes.split("-")
                log(f"Mês {mm}-{ano}…")
                pl._selecionar_mes(pagina, f"{mm}-{ano}", log_fn=log_fn)
                pl._aguardar_grid(pagina)

                for visao in VISOES:
                    its = por_mes[mes].get(visao, [])
                    if not its:
                        continue
                    _definir_visao(pagina, visao)
                    preenchidas = []
                    for a in its:
                        rotulo = f"{a['distribuidora']} u{a['usina']} {a['modalidade']}"
                        escopo, motivo = _localizar_escopo(pagina, a)
                        if escopo is None:
                            log(f"!! {rotulo}: {motivo}, pulando.")
                            continue
                        atual = escopo.locator("input:not([type='checkbox'])").first.input_value(timeout=5000)
                        if atual.strip():
                            log(f"!! {rotulo}: célula já tem {atual}, não sobrescrevo.")
                            continue
                        valor_str = f"{a['valor']:.6f}".replace(".", ",")
                        if pl._setar_celula(pagina, escopo, valor_str, rotulo, log):
                            preenchidas.append(a)

                    if not preenchidas:
                        continue
                    log(f"{mm}-{ano} {visao}: {len(preenchidas)} célula(s) preenchida(s). "
                        f"Confira no LexDash e clique Salvar.")
                    if pl._aguardar_salvar(pagina):
                        log(f"Salvo detectado ({visao}).")
                        pagina.wait_for_timeout(1500)
                        _conferir(pagina, preenchidas, log)
                    else:
                        log(f"Timeout aguardando Salvar ({visao}).")
        finally:
            navegador.close()
    log("Concluído.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Replica tarifas entre usinas irmãs no LexDash")
    ap.add_argument("--gravar", action="store_true",
                    help="Grava todo o plano (sem isso, só mostra o que faria)")
    args = ap.parse_args()
    plano = planejar()
    for a in plano["acoes"]:
        print(f"  → {a['distribuidora']} u{a['usina']} {a['mes']} {a['modalidade']} {a['gd']}: "
              f"{a['valor']:.6f} (igual u{','.join(map(str, a['fontes']))})")
    for x in plano["pulados"]:
        if x["motivo"] != SEM_FONTE:
            print(f"  · pulado {x['distribuidora']} u{x['usina']} {x['mes']} "
                  f"{x['modalidade']} {x['gd']}: {x['motivo']}")
    if args.gravar:
        gravar(plano["acoes"])
