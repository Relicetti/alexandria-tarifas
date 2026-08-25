"""
Preenche automaticamente o grid "Atualizacao de tarifas usina" no LexDash
com as tarifas aprovadas na tela de revisão do app.

Fluxo:
  1. Busca itens aprovados via API do app de tarifas
  2. Abre LexDash com sessão salva
  3. Navega para Atualizações > Atualizacao de tarifas usina
  4. Para cada mês encontrado:
     a. Seleciona o mês e clica Ir
     b. Passa GD1 (sem checkbox), GD2, e Cacau Show em passagens separadas
     c. Clica Salvar em cada passagem
  5. Marca os itens como preenchidos na API

Uso:
    python preencher_lexdash.py [--debug] [--dry-run]

Pré-requisito:
    - login_lexdash.py executado ao menos uma vez
    - TARIFAS_API_URL configurado (ex: https://seu-app.railway.app)
      ou rodando localmente (http://localhost:5001)
    - ADMIN_TOKEN configurado (se o app exigir)
"""
import argparse
import json
import os
import re
import sys

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import requests
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

ARQUIVO_SESSAO  = os.path.join(os.path.dirname(__file__), "lexdash_session.json")
URL_ATUALIZACOES = "https://crm-lex.energiacom.vc/fatger/atualizacao-fat"

# URL do app de tarifas — configura via variável de ambiente ou .env
TARIFAS_API_URL = os.environ.get("TARIFAS_API_URL", "https://alexandria-tarifas-production.up.railway.app")
ADMIN_TOKEN     = os.environ.get("ADMIN_TOKEN", "")

_MESES_PT = {
    "jan": "01", "fev": "02", "mar": "03", "abr": "04",
    "mai": "05", "jun": "06", "jul": "07", "ago": "08",
    "set": "09", "out": "10", "nov": "11", "dez": "12",
}


def _headers():
    h = {"Content-Type": "application/json"}
    if ADMIN_TOKEN:
        h["X-Admin-Token"] = ADMIN_TOKEN
    return h


def _buscar_aprovados() -> list[dict]:
    resp = requests.get(f"{TARIFAS_API_URL}/api/pendentes/aprovados", headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


def _marcar_preenchido(id: int):
    requests.post(f"{TARIFAS_API_URL}/api/pendentes/{id}/preenchido", headers=_headers(), timeout=10)


def _mes_ref_para_lex(mes_ref: str) -> str:
    """'ago. de 2026' → '08-2026'; '2026-07-01' / '2026-07' → '07-2026'"""
    m = re.match(r"^(\d{4})-(\d{2})(-\d{2})?$", mes_ref.strip())
    if m:
        ano, mes = m.group(1), m.group(2)
        return f"{mes}-{ano}"

    partes = mes_ref.lower().replace(".", "").split()
    for p in partes:
        if p[:3] in _MESES_PT:
            mes = _MESES_PT[p[:3]]
            ano = next((x for x in partes if len(x) == 4 and x.isdigit()), None)
            if ano:
                return f"{mes}-{ano}"
    return mes_ref


def _abrir_card_usina(pagina):
    """Clica no card 'Atualizacao de tarifas usina' (3º card)."""
    for sel in ["text=Atualizacao de tarifas usina", "text=Atualização de tarifas usina"]:
        loc = pagina.locator(sel).first
        if loc.count() > 0:
            loc.click(timeout=5000)
            pagina.wait_for_timeout(2000)
            return
    # fallback: 3º card
    cards = pagina.locator(".card, [class*='card']").all()
    if len(cards) >= 3:
        cards[2].click(timeout=5000)
        pagina.wait_for_timeout(2000)
    else:
        raise RuntimeError("Card 'Atualizacao de tarifas usina' não encontrado.")


def _campo_mes(pagina):
    """Localiza o campo MES DE REFERENCIA (MM-AAAA) e o botão 'Ir' associado.

    Confirmado via dump de <input> da página real: o campo tem placeholder
    exatamente 'MM-AAAA' (sem variação) — é o único campo de texto fora do
    grid, além da busca do menu no topo ('Buscar menu...'). A heurística
    anterior de "input antes do botão Ir" pegava esse campo de busca por
    engano (o Ir fica mais perto dele na árvore do DOM do que do campo do
    mês). Retorna (campo, botao_ir).
    """
    btn = pagina.locator("button:has-text('Ir'), input[value='Ir']").first

    campo = pagina.locator("input[placeholder='MM-AAAA']").first
    if campo.count() > 0:
        return campo, btn

    candidatos = [
        "input[placeholder*='mês'], input[placeholder*='mes']",
        "input[placeholder*='MM-YYYY'], input[placeholder*='MM-AAAA'], input[placeholder*='AAAA']",
        "input[name*='mes'], input[name*='mes_referencia']",
    ]
    for sel in candidatos:
        loc = pagina.locator(sel).first
        if loc.count() > 0:
            return loc, btn

    return pagina.locator("input").first, btn


def _dump_inputs_debug(pagina, log_fn=None):
    """Lista todos os <input> visíveis na página (id/name/placeholder/value)
    para diagnóstico — usado quando o campo do mês não bate com o esperado."""
    def _log(msg):
        try:
            print(msg)
        except Exception:
            pass
        if log_fn:
            log_fn(msg)

    try:
        infos = pagina.evaluate("""
            () => Array.from(document.querySelectorAll('input')).map((el, i) => {
                const r = el.getBoundingClientRect();
                return {
                    i, id: el.id, name: el.name, placeholder: el.placeholder,
                    value: el.value, type: el.type,
                    visible: r.width > 0 && r.height > 0,
                    x: Math.round(r.x), y: Math.round(r.y),
                };
            })
        """)
        _log(f"--- DEBUG: {len(infos)} <input> na página ---")
        for info in infos:
            _log(f"  [{info['i']}] id='{info['id']}' name='{info['name']}' "
                 f"placeholder='{info['placeholder']}' value='{info['value']}' "
                 f"type='{info['type']}' visible={info['visible']} pos=({info['x']},{info['y']})")
        _log("--- fim DEBUG ---")
    except Exception as e:
        _log(f"!! Erro no dump de inputs: {e}")


def _selecionar_mes(pagina, mes_lex: str, log_fn=None):
    """Preenche o campo MES DE REFERENCIA e clica Ir."""
    def _log(msg):
        try:
            print(msg)
        except Exception:
            pass
        if log_fn:
            log_fn(msg)

    _dump_inputs_debug(pagina, log_fn=log_fn)

    campo, btn_ir = _campo_mes(pagina)

    campo.click(timeout=5000, click_count=3)
    pagina.keyboard.press("Backspace")  # garante campo vazio antes de digitar
    campo.type(mes_lex, delay=80)
    pagina.wait_for_timeout(300)

    valor_atual = ""
    try:
        valor_atual = campo.input_value(timeout=2000)
    except Exception:
        pass

    if valor_atual != mes_lex:
        _log(f"!! Campo do mês ficou '{valor_atual}' (esperado '{mes_lex}') — tentando de novo com só dígitos.")
        campo.click(timeout=5000, click_count=3)
        pagina.keyboard.press("Backspace")
        campo.type("".join(c for c in mes_lex if c.isdigit()), delay=80)
        pagina.wait_for_timeout(300)
        try:
            valor_atual = campo.input_value(timeout=2000)
        except Exception:
            pass
        _log(f"Campo do mês agora: '{valor_atual}'.")

    _log(f"Clicando em Ir com o campo mostrando '{valor_atual}'...")

    # clica no MESMO botão Ir associado ao campo que acabou de ser preenchido
    # (não busca de novo — evita clicar num "Ir" de outra seção da página)
    if btn_ir.count() > 0:
        btn_ir.click(timeout=5000)
        pagina.wait_for_timeout(3000)
        return

    # fallback: procura qualquer botão "Ir" na página
    for sel in ["button:has-text('Ir')", "input[value='Ir']", "text=Ir"]:
        btn = pagina.locator(sel).first
        if btn.count() > 0:
            btn.click(timeout=5000)
            pagina.wait_for_timeout(3000)
            return

    raise RuntimeError(f"Botão 'Ir' não encontrado na tela.")


def _aguardar_grid(pagina):
    """Aguarda a tabela do grid carregar."""
    try:
        pagina.wait_for_function(
            "() => !document.body.innerText.includes('Carregando')",
            timeout=15000,
        )
    except PWTimeout:
        pass
    pagina.wait_for_timeout(1000)


def _react_check(pagina, cb_locator, checked: bool):
    """Marca/desmarca um checkbox React via native setter (mesmo método do input de valor)."""
    try:
        el = cb_locator.element_handle(timeout=3000)
        if el:
            pagina.evaluate("""
                ([el, val]) => {
                    const setter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'checked'
                    ).set;
                    setter.call(el, val);
                    el.dispatchEvent(new Event('input',  {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    el.dispatchEvent(new Event('click',  {bubbles: true}));
                }
            """, [el, checked])
            pagina.wait_for_timeout(600)
            return True
    except Exception:
        pass
    return False


def _marcar_checkbox_tipo(pagina, tipo: str):
    """
    Marca o checkbox de tipo no topo da grade via React native setter.
    tipo: 'GD2' | 'CacauShow' | 'GD1' (GD1 = nenhum / desmarca os outros)
    """
    if tipo == "GD1":
        for texto in ["TARIFA GD2", "TARIFA CACAU SHOW"]:
            cb = pagina.locator(f"label:has-text('{texto}') input[type='checkbox']").first
            if cb.count() == 0:
                cb = pagina.locator(f"text={texto}").locator("..").locator("input[type='checkbox']").first
            if cb.count() > 0:
                _react_check(pagina, cb, False)
        return

    label_map = {"GD2": "TARIFA GD2", "CacauShow": "TARIFA CACAU SHOW"}
    texto = label_map.get(tipo, "")
    if not texto:
        return

    cb = pagina.locator(f"label:has-text('{texto}') input[type='checkbox']").first
    if cb.count() == 0:
        cb = pagina.locator(f"text={texto}").locator("..").locator("input[type='checkbox']").first
    if cb.count() > 0:
        _react_check(pagina, cb, True)


def _escopo_modalidade(td, modalidade: str):
    """
    Algumas usinas (ex: 101/102/103 — geração remota) têm, dentro da MESMA
    célula da tabela, dois sub-blocos independentes: um rotulado "GC"
    (Geração Compartilhada) e outro "Autoconsumo", cada um com seu próprio
    checkbox + campo de valor. Sem essa função, o código sempre pegava o
    primeiro checkbox/input da célula (sempre o do "GC"), preenchendo a
    modalidade errada quando a fatura era Autoconsumo.

    Retorna o Locator do sub-bloco correto para a modalidade informada, ou
    a própria célula (td) se ela não tiver essa divisão (usinas comuns).
    """
    texto_alvo = "Autoconsumo" if "autoconsumo" in (modalidade or "").lower() else "GC"
    bloco = td.locator(f"xpath=.//span[normalize-space(text())='{texto_alvo}']/parent::div")
    if bloco.count() > 0:
        return bloco.first
    return td


def _preencher_linha(pagina, distribuidora: str, usinas: list, valor: float, modalidade: str = "", log_fn=None):
    """
    Encontra a linha da distribuidora no grid, marca os checkboxes e preenche o valor
    nas colunas de usina correspondentes.
    Retorna True se preencheu ao menos uma célula.
    """
    TO = 5000

    def _warn(msg):
        try:
            print(f"  !! {msg}")
        except Exception:
            pass
        if log_fn:
            log_fn(f"!! {msg}")

    # Localiza a linha por texto da distribuidora
    linha = pagina.locator(f"tr:has-text('{distribuidora}')").first
    if linha.count() == 0:
        _warn(f"Linha '{distribuidora}' nao encontrada no grid.")
        return False

    preencheu = False
    valor_str = f"{valor:.6f}".replace(".", ",")

    for usina_id in usinas:
        usina_id = str(usina_id).strip()

        th_cols = pagina.locator("thead tr th").all()
        col_idx = None
        for i, th in enumerate(th_cols):
            try:
                th_texto = th.inner_text(timeout=TO).strip()
            except Exception:
                th_texto = ""
            if f"({usina_id})" in th_texto:
                col_idx = i
                break

        if col_idx is None:
            _warn(f"Coluna usina {usina_id} nao encontrada.")
            continue

        tds = linha.locator("td").all()
        if col_idx >= len(tds):
            _warn(f"Coluna {col_idx} fora do range (linha tem {len(tds)} colunas).")
            continue

        td = tds[col_idx]
        escopo = _escopo_modalidade(td, modalidade)

        # Marca checkbox via native checked setter (igual ao que funciona no input)
        try:
            cb = escopo.locator("input[type='checkbox']").first
            if cb.count() > 0:
                cb_el = cb.element_handle(timeout=TO)
                if cb_el:
                    pagina.evaluate("""
                        el => {
                            const setter = Object.getOwnPropertyDescriptor(
                                window.HTMLInputElement.prototype, 'checked'
                            ).set;
                            setter.call(el, true);
                            el.dispatchEvent(new Event('input',  {bubbles: true}));
                            el.dispatchEvent(new Event('change', {bubbles: true}));
                            el.dispatchEvent(new Event('click',  {bubbles: true}));
                        }
                    """, cb_el)
                    pagina.wait_for_timeout(800)
        except Exception as e:
            _warn(f"Erro ao marcar checkbox usina {usina_id}: {e}")

        # Preenche o input via JavaScript (necessário para apps React)
        try:
            inp = escopo.locator("input[inputmode='decimal'], input:not([type='checkbox'])").first
            if inp.count() > 0:
                inp_el = inp.element_handle(timeout=TO)
                if inp_el:
                    pagina.evaluate("""
                        ([el, val]) => {
                            el.focus();
                            el.click();
                            const setter = Object.getOwnPropertyDescriptor(
                                window.HTMLInputElement.prototype, 'value'
                            ).set;
                            setter.call(el, val);
                            el.dispatchEvent(new Event('input',  {bubbles: true}));
                            el.dispatchEvent(new Event('change', {bubbles: true}));
                            el.dispatchEvent(new Event('blur',   {bubbles: true}));
                        }
                    """, [inp_el, valor_str])
                    preencheu = True
        except Exception as e:
            _warn(f"Erro ao preencher usina {usina_id}: {e}")

    return preencheu


def _salvar(pagina, log_fn=None):
    """Clica no botão Salvar e aguarda confirmação."""
    def _warn(msg):
        try: print(msg)
        except Exception: pass
        if log_fn: log_fn(msg)

    # Loga todos os botões visíveis para diagnóstico
    try:
        btns = pagina.locator("button").all()
        textos = []
        for b in btns:
            try: textos.append(b.inner_text(timeout=1000).strip())
            except Exception: pass
        _warn(f"Botoes na pagina: {textos}")
    except Exception:
        pass

    for sel in [
        "button:has-text('Salvar')",
        "button:has-text('salvar')",
        "button:has-text('SALVAR')",
        "input[value='Salvar']",
        "input[value='SALVAR']",
    ]:
        btn = pagina.locator(sel).first
        if btn.count() > 0:
            try:
                btn.click(timeout=5000, force=True)
                pagina.wait_for_timeout(3000)
                _warn("Salvar clicado.")
                return
            except Exception as e:
                _warn(f"Erro ao clicar Salvar ({sel}): {e}")

    _warn("!! Botao Salvar nao encontrado — verifique os nomes acima.")


def _tipo_passagem(item: dict) -> str:
    """Determina o tipo de passagem: 'GD1', 'GD2', ou 'CacauShow'."""
    modal = (item.get("modalidade") or "").lower()
    if "cacau" in modal:
        return "CacauShow"
    if item.get("tipo_gd") == "GD2":
        return "GD2"
    return "GD1"


def preencher(itens: list[dict], dry_run=False, debug=False, log_fn=None):
    """
    log_fn(msg): callback chamado a cada etapa — útil para atualizar status em tempo real.
    Se None, apenas printa.
    """
    def _log(msg: str):
        try:
            print(msg)
        except Exception:
            pass
        if log_fn:
            log_fn(msg)

    if not os.path.exists(ARQUIVO_SESSAO):
        raise RuntimeError("Sessão não encontrada. Rode login_lexdash.py primeiro.")

    # Agrupa por mês_lex → tipo → lista de itens
    por_mes: dict[str, dict[str, list]] = {}
    for item in itens:
        mes = item.get("mes_lex") or _mes_ref_para_lex(item.get("mes_ref", ""))
        tipo = _tipo_passagem(item)
        por_mes.setdefault(mes, {}).setdefault(tipo, []).append(item)

    _log(f"Meses: {list(por_mes.keys())}")
    for mes, tipos in por_mes.items():
        for tipo, its in tipos.items():
            _log(f"  {mes} | {tipo}: {len(its)} distribuidora(s)")

    if dry_run:
        _log("[dry-run] Nada preenchido.")
        return

    _log("Abrindo navegador (WebKit/Safari)…")

    # WebKit é o motor do Playwright mais próximo do Safari (não é o Safari
    # instalado no Mac — não compartilha cookies/login com ele).
    with sync_playwright() as p:
        navegador = p.webkit.launch(headless=False)
        contexto = navegador.new_context(storage_state=ARQUIVO_SESSAO, viewport=None)
        pagina   = contexto.new_page()


        _log(f"Navegando para {URL_ATUALIZACOES}…")
        pagina.goto(URL_ATUALIZACOES, timeout=20000, wait_until="domcontentloaded")
        pagina.wait_for_timeout(1000)
        # Maximiza e reseta zoom via JS
        pagina.evaluate("""() => {
            window.moveTo(0, 0);
            window.resizeTo(screen.availWidth, screen.availHeight);
        }""")
        pagina.keyboard.press("Meta+0")
        pagina.wait_for_timeout(500)

        url_atual = pagina.url.lower()
        if "login" in url_atual or "signin" in url_atual or "auth" in url_atual:
            navegador.close()
            raise RuntimeError("Sessao expirada. Rode login_lexdash.py de novo.")
        if "fatger" not in url_atual and "atualizacao" not in url_atual:
            navegador.close()
            raise RuntimeError(f"URL inesperada: {pagina.url}")

        _log("Abrindo card de tarifas…")
        _abrir_card_usina(pagina)
        _aguardar_grid(pagina)

        for mes_lex, tipos in por_mes.items():
            _log(f"Mes {mes_lex}…")
            _selecionar_mes(pagina, mes_lex, log_fn=log_fn)
            _aguardar_grid(pagina)

            for tipo in ["GD1", "GD2", "CacauShow"]:
                its = tipos.get(tipo, [])
                if not its:
                    continue

                _log(f"Preenchendo {tipo} ({len(its)} item(s))…")
                _marcar_checkbox_tipo(pagina, tipo)

                algum = False
                for item in its:
                    usinas = json.loads(item.get("usinas", "[]"))
                    if isinstance(usinas, str):
                        usinas = [u.strip() for u in usinas.split(",")]
                    tarifa = item.get("tarifa_geracao")
                    if not tarifa:
                        _log(f"Sem tarifa: {item['distribuidora']}, pulando.")
                        continue
                    modalidade = item.get("modalidade") or ""
                    _log(f"{item['distribuidora']} -> usinas {usinas} -> {tarifa:.6f} ({modalidade or 'sem modalidade'})")
                    ok = _preencher_linha(pagina, item["distribuidora"], usinas, tarifa, modalidade=modalidade, log_fn=log_fn)
                    if ok:
                        algum = True
                        # Rola a linha preenchida para o centro da tela
                        try:
                            linha = pagina.locator(f"tr:has-text('{item['distribuidora']}')").first
                            linha.scroll_into_view_if_needed(timeout=3000)
                            pagina.wait_for_timeout(300)
                        except Exception:
                            pass

                if algum:
                    # Detecta Salvar via rede: aguarda o usuário clicar
                    _log(f"Marque o checkbox e clique Salvar no browser.")

                    salvo = {"ok": False}

                    def _on_response(resp):
                        if resp.status < 400 and resp.request.method in ("POST", "PUT", "PATCH"):
                            if any(k in resp.url for k in ("tarifa", "salvar", "save", "update", "fat")):
                                salvo["ok"] = True

                    pagina.on("response", _on_response)

                    # Aguarda até 5 minutos pelo Salvar
                    for _ in range(150):
                        pagina.wait_for_timeout(2000)
                        if salvo["ok"]:
                            break

                    pagina.remove_listener("response", _on_response)

                    if salvo["ok"]:
                        _log(f"Salvo detectado ({tipo}).")
                        for item in its:
                            if item.get("id"):
                                _marcar_preenchido(item["id"])
                    else:
                        _log(f"Timeout aguardando Salvar ({tipo}).")

        navegador.close()
        _log("Concluido.")


def principal():
    ap = argparse.ArgumentParser(description="Preenche grid de tarifas no LexDash")
    ap.add_argument("--debug",   action="store_true", help="Browser visível")
    ap.add_argument("--dry-run", action="store_true", help="Só mostra o que faria")
    args = ap.parse_args()

    print(f"Buscando aprovados em {TARIFAS_API_URL} ...")
    try:
        itens = _buscar_aprovados()
    except Exception as e:
        print(f"Erro ao buscar aprovados: {e}")
        sys.exit(1)

    if not itens:
        print("Nenhum item aprovado aguardando preenchimento.")
        return

    print(f"{len(itens)} item(ns) aprovado(s).")
    preencher(itens, dry_run=args.dry_run, debug=args.debug)


if __name__ == "__main__":
    principal()
