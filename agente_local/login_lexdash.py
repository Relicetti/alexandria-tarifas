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

    campo_usuario.click(timeout=5000)
    campo_usuario.fill(usuario)
    campo_senha.click(timeout=5000)
    campo_senha.fill(senha)

    clicou = False
    for sel in [
        "button[type='submit']",
        "button:has-text('Entrar')",
        "button:has-text('Login')",
        "button:has-text('Acessar')",
        "input[type='submit']",
    ]:
        btn = pagina.locator(sel).first
        if btn.count() > 0:
            btn.click(timeout=5000)
            clicou = True
            break
    if not clicou:
        campo_senha.press("Enter")

    pagina.wait_for_timeout(3000)

    # confirma que saiu da tela de login (campo de senha sumiu)
    if pagina.locator("input[type='password']").count() > 0:
        _log("!! Login automático: campo de senha ainda visível depois do submit — provavelmente falhou.")
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
        contexto = navegador.new_context(viewport=None)
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
