"""
Faz login no LexDash e salva a sessão (cookies/storage) em
lexdash_session.json, usada depois por preencher_lexdash.py /
servidor_local.py para abrir o site já autenticado.

Se LEXDASH_USER e LEXDASH_PASS estiverem configurados (no .env desta pasta),
o login é feito sozinho, sem intervenção. Sem essas variáveis, abre a janela
pra você logar manualmente (comportamento antigo).

Uso:
    python login_lexdash.py           # janela visível, log detalhado
    python login_lexdash.py --headless  # sem janela (usado pelo agente
                                         # quando a sessão expira sozinha)

Chamado automaticamente pelo agente (servidor_local.py / preencher_lexdash.py)
quando detecta "Sessao expirada" durante um preenchimento — não precisa
mais rodar manualmente, a não ser que o login automático falhe (ex.: LexDash
mudou a tela de login) ou que LEXDASH_USER/LEXDASH_PASS não estejam
configurados.
"""
import argparse
import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from playwright.sync_api import sync_playwright

ARQUIVO_SESSAO = os.path.join(os.path.dirname(__file__), "lexdash_session.json")
URL_LOGIN = "https://crm-lex.energiacom.vc/"


def _login_automatico(pagina, usuario: str, senha: str, log_fn=None) -> bool:
    """Preenche usuário/senha e submete o formulário de login sozinho.
    Retorna True se conseguiu, False se não achou os campos esperados
    (nesse caso quem chamou deve cair pro login manual)."""
    def _log(msg):
        try:
            print(msg)
        except Exception:
            pass
        if log_fn:
            log_fn(msg)

    campos_usuario = [
        "input[type='email']",
        "input[name*='user' i]",
        "input[name*='login' i]",
        "input[placeholder*='usuário' i]",
        "input[placeholder*='usuario' i]",
        "input[placeholder*='email' i]",
        "input[placeholder*='e-mail' i]",
        "input[type='text']",
    ]
    campo_usuario = None
    for sel in campos_usuario:
        loc = pagina.locator(sel).first
        if loc.count() > 0:
            campo_usuario = loc
            break
    if not campo_usuario:
        _log("!! Login automático: campo de usuário não encontrado.")
        return False

    campo_senha = pagina.locator("input[type='password']").first
    if campo_senha.count() == 0:
        _log("!! Login automático: campo de senha não encontrado.")
        return False

    # A tela de login tem alguma animação/transição de entrada que não roda
    # (ou não termina) em modo headless — o campo existe no HTML mas nunca
    # fica "visível" pros critérios do Playwright, então clicar/fill()
    # trava em timeout. Preenche direto via JS (native setter + eventos de
    # input/change), o mesmo truque já usado no preenchimento do grid de
    # tarifas — funciona independente de o elemento estar "visível" ou não.
    def _set_via_js(campo, valor):
        el = campo.element_handle(timeout=5000)
        if not el:
            return False
        pagina.evaluate("""
            ([el, val]) => {
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value'
                ).set;
                setter.call(el, val);
                el.dispatchEvent(new Event('input',  {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
            }
        """, [el, valor])
        return True

    try:
        if not _set_via_js(campo_usuario, usuario):
            _log("!! Login automático: não consegui pegar o elemento do campo de usuário.")
            return False
        if not _set_via_js(campo_senha, senha):
            _log("!! Login automático: não consegui pegar o elemento do campo de senha.")
            return False
    except Exception as e:
        _log(f"!! Login automático: erro preenchendo campos via JS: {e}")
        return False

    pagina.wait_for_timeout(300)

    try:
        v_user = campo_usuario.input_value(timeout=2000)
        v_senha_len = len(campo_senha.input_value(timeout=2000) or "")
        _log(f"Diagnostico: campo usuario='{v_user}' campo senha tem {v_senha_len} caractere(s).")
    except Exception:
        pass

    # Clica no botão de submit também via JS (o clique "de verdade" do
    # Playwright teria o mesmo problema de visibilidade).
    clicou = False
    sel_usado = None
    for sel in [
        "button[type='submit']",
        "button:has-text('Entrar')",
        "button:has-text('Login')",
        "button:has-text('Acessar')",
        "button:has-text('Continuar')",
        "button:has-text('Fazer login')",
        "input[type='submit']",
    ]:
        btn = pagina.locator(sel).first
        if btn.count() > 0:
            try:
                btn_el = btn.element_handle(timeout=3000)
                if btn_el:
                    pagina.evaluate("(el) => el.click()", btn_el)
                    clicou = True
                    sel_usado = sel
                    break
            except Exception:
                continue

    if clicou:
        _log(f"Diagnostico: cliquei no botão via seletor {sel_usado!r}.")
    else:
        try:
            botoes = pagina.locator("button").all_inner_texts()
            _log(f"Diagnostico: nenhum botão de submit bateu nos seletores conhecidos. Botões na página: {botoes}")
        except Exception:
            pass

    if not clicou:
        # último recurso: dá Enter no campo de senha via JS (dispatch de keydown)
        try:
            senha_el = campo_senha.element_handle(timeout=3000)
            pagina.evaluate("""
                (el) => el.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}))
            """, senha_el)
        except Exception:
            pass

    pagina.wait_for_timeout(3000)

    # confirma que saiu da tela de login (URL não é mais /login)
    if "login" in pagina.url.lower():
        _log(f"!! Login automático: ainda na tela de login depois do submit (url={pagina.url}) — provavelmente falhou.")
        return False

    return True


def fazer_login(headless: bool = False, log_fn=None) -> bool:
    """Faz login (automático se LEXDASH_USER/LEXDASH_PASS existirem, senão
    manual — só funciona manual se headless=False) e salva a sessão.
    Retorna True em caso de sucesso."""
    def _log(msg):
        try:
            print(msg)
        except Exception:
            pass
        if log_fn:
            log_fn(msg)

    usuario = os.environ.get("LEXDASH_USER")
    senha = os.environ.get("LEXDASH_PASS")

    with sync_playwright() as p:
        navegador = p.webkit.launch(headless=headless)
        # Em modo headless não existe janela real pra "viewport=None" seguir
        # (usaria o tamanho da janela do sistema) — fixa um tamanho de
        # desktop explícito pra não cair num layout mobile que esconde os
        # campos do formulário.
        contexto = navegador.new_context(viewport=None if not headless else {"width": 1440, "height": 900})
        pagina = contexto.new_page()
        pagina.goto(URL_LOGIN, timeout=30000, wait_until="domcontentloaded")

        ok = False
        if usuario and senha:
            _log("Tentando login automático no LexDash...")
            ok = _login_automatico(pagina, usuario, senha, log_fn=log_fn)
            if not ok and not headless:
                _log("Login automático não funcionou — faça manualmente na janela.")
                input("Depois de logar (e a página inicial carregar), pressione ENTER aqui... ")
                ok = True
        elif not headless:
            _log("Faça login no LexDash na janela que abriu.")
            input("Depois de logar (e a página inicial carregar), pressione ENTER aqui... ")
            ok = True
        else:
            _log("!! LEXDASH_USER/LEXDASH_PASS não configurados — não dá pra logar sem janela visível.")

        if ok:
            contexto.storage_state(path=ARQUIVO_SESSAO)
            _log(f"Sessão salva em {ARQUIVO_SESSAO}")

        navegador.close()
        return ok


def principal():
    ap = argparse.ArgumentParser(description="Login no LexDash")
    ap.add_argument("--headless", action="store_true", help="Sem janela visível (requer LEXDASH_USER/LEXDASH_PASS)")
    args = ap.parse_args()

    ok = fazer_login(headless=args.headless)
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    principal()
