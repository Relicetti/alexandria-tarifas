# Agente local — gravação automática no LexDash

Este é o programa que roda **na sua própria máquina** (não no Railway) e faz
o botão "Gravar no LexDash 🖨" do dashboard funcionar: ele sobe um servidor
em `http://localhost:5002` que o navegador chama, abre uma janela de
navegador de verdade e preenche o grid "Atualizacao de tarifas usina" no
LexDash.

## Setup no macOS

1. **Python 3.10+** (verifique com `python3 --version`; instale via
   [python.org](https://www.python.org/downloads/macos/) ou `brew install python`
   se precisar).

2. Instale as dependências:
   ```bash
   cd agente_local
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   playwright install webkit
   ```

   > O motor usado é o **WebKit** do Playwright (o mais próximo do Safari
   > disponível para automação). Ele **não é** o Safari.app instalado no seu
   > Mac e não compartilha login/cookies com ele — por isso o login abaixo é
   > sempre feito dentro dessa janela do Playwright, não no Safari normal.

3. Configure as variáveis de ambiente (ajuste para o seu caso):
   ```bash
   export TARIFAS_API_URL="https://alexandria-tarifas-production.up.railway.app"
   export ADMIN_TOKEN="seu-token-se-o-app-exigir"
   ```
   (Pode colocar essas duas linhas no `~/.zshrc` para não precisar repetir
   toda vez que abrir um terminal novo.)

4. **Faça login uma vez** para salvar a sessão do LexDash:
   ```bash
   python login_lexdash.py
   ```
   Uma janela abre — faça login manualmente no LexDash, volte ao terminal e
   pressione ENTER. Isso cria `lexdash_session.json` nesta pasta.

5. **Suba o agente local**:
   ```bash
   python servidor_local.py
   ```
   Deixe esse terminal aberto — é ele que fica escutando na porta 5002.
   Agora o botão "Gravar no LexDash" / "Gravar no Sistema 🖨" no dashboard
   web volta a funcionar.

## Quando a sessão expirar

Se aparecer erro de "Sessao expirada", rode `python login_lexdash.py` de
novo (com `servidor_local.py` parado ou não, tanto faz) para regravar o
`lexdash_session.json`.

## Rodar manualmente pela linha de comando (sem o dashboard)

```bash
python preencher_lexdash.py --dry-run   # só mostra o que faria
python preencher_lexdash.py             # preenche de verdade
```

## Arquivos

- `preencher_lexdash.py` — lógica de automação do grid do LexDash (Playwright).
- `login_lexdash.py` — abre o navegador para login manual e salva a sessão.
- `servidor_local.py` — servidor Flask na porta 5002 chamado pelo dashboard.
- `lexdash_session.json` — gerado pelo login, **não versionar** (já está no
  `.gitignore` do repositório principal).
