"""
Abre o LexDash num navegador visível para você fazer login manualmente e
salva a sessão (cookies/storage) em lexdash_session.json, usada depois por
preencher_lexdash.py / servidor_local.py para abrir o site já autenticado.

Uso:
    python login_lexdash.py

Rode este script sempre que a sessão expirar (o preencher_lexdash.py avisa
com "Sessao expirada. Rode login_lexdash.py de novo.").
"""
import os

from playwright.sync_api import sync_playwright

ARQUIVO_SESSAO = os.path.join(os.path.dirname(__file__), "lexdash_session.json")
URL_LOGIN = "https://crm-lex.energiacom.vc/"


def principal():
    with sync_playwright() as p:
        # WebKit é o motor do Playwright mais próximo do Safari (não é o
        # Safari instalado no Mac — não compartilha cookies/login com ele).
        navegador = p.webkit.launch(headless=False)
        contexto = navegador.new_context(viewport=None)
        pagina = contexto.new_page()

        pagina.goto(URL_LOGIN, timeout=30000, wait_until="domcontentloaded")

        print("Faça login no LexDash na janela que abriu.")
        input("Depois de logar (e a página inicial carregar), pressione ENTER aqui... ")

        contexto.storage_state(path=ARQUIVO_SESSAO)
        print(f"Sessão salva em {ARQUIVO_SESSAO}")

        navegador.close()


if __name__ == "__main__":
    principal()
