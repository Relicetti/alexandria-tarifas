# Agente local — gravação automática no LexDash

Este é o programa que roda **na sua própria máquina** (não no Railway) e faz
o botão "Gravar no LexDash 🖨" do dashboard funcionar: ele sobe um servidor
em `https://localhost:5002` que o navegador chama, abre uma janela de
navegador de verdade e preenche o grid "Atualizacao de tarifas usina" no
LexDash.

## Setup no macOS (uma vez só)

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
   > Isso é só o navegador que roda a automação; para acessar o
   > *dashboard* você pode usar Safari, Chrome, o que preferir (veja o
   > passo do certificado abaixo).

3. Gere um certificado local confiável, para o agente rodar em **HTTPS**
   (o dashboard é `https://` e o Safari bloqueia chamadas dele para um
   `http://localhost` simples — com HTTPS funciona em qualquer navegador):
   ```bash
   brew install mkcert
   mkcert -install
   mkcert -cert-file cert.pem -key-file key.pem localhost 127.0.0.1 ::1
   ```
   `mkcert -install` cria uma autoridade certificadora local e a registra
   como confiável no seu Mac (uma vez só) — depois disso `cert.pem`/`key.pem`
   funcionam sem aviso de segurança em Safari, Chrome, etc. Esses dois
   arquivos não são versionados (estão no `.gitignore`).

4. Crie o arquivo `.env` nesta pasta com as credenciais (troque o valor de
   `ADMIN_TOKEN` pelo token real do seu deploy, disponível em
   Railway → seu projeto → Variables):
   ```bash
   cat > .env <<'EOF'
   TARIFAS_API_URL=https://alexandria-tarifas-production.up.railway.app
   ADMIN_TOKEN=alex-upload-2026
   LEXDASH_USER=seu-usuario-do-lexdash
   LEXDASH_PASS=sua-senha-do-lexdash
   EOF
   ```
   Esse arquivo não é versionado (está no `.gitignore`) — mas fica em texto
   puro nesta pasta do seu Mac. `LEXDASH_USER`/`LEXDASH_PASS` são opcionais:
   com eles, o agente reloga sozinho no LexDash quando a sessão expira (sem
   precisar rodar `login_lexdash.py` manualmente); sem eles, o login continua
   manual como antes.

5. **Faça login uma vez** para salvar a sessão do LexDash:
   ```bash
   python login_lexdash.py
   ```
   Uma janela abre — faça login manualmente no LexDash, volte ao terminal e
   pressione ENTER. Isso cria `lexdash_session.json` nesta pasta.

6. **Instale o autostart** — o agente sobe sozinho a cada login no Mac,
   rodando em segundo plano (sem precisar abrir Terminal nunca mais):
   ```bash
   chmod +x instalar_autostart.sh desinstalar_autostart.sh
   ./instalar_autostart.sh
   ```

Pronto. A partir de agora, basta abrir o dashboard (Safari, Chrome, o que
preferir) e clicar no botão 🖨 — o agente já está rodando em segundo plano
e o navegador automatizado abre sozinho.

## Se algo não funcionar

- **Ver o log do agente**: `cat agente_local/agente.log` (ou `tail -f` para
  acompanhar em tempo real).
- **Reiniciar o agente** (ex.: depois de um `git pull` com mudanças no
  código): `launchctl kickstart -k gui/$(id -u)/com.alexandria.lexdash-agente`
- **Sessão do LexDash expirou** ("Sessao expirada" no log): se
  `LEXDASH_USER`/`LEXDASH_PASS` estiverem no `.env`, o agente reloga sozinho
  automaticamente na próxima tentativa — não precisa fazer nada. Se não
  estiverem configurados (ou se o login automático falhar, ex.: LexDash
  mudou a tela de login), rode `python login_lexdash.py` manualmente e
  reinicie o agente (comando acima).
- **Desinstalar o autostart**: `./desinstalar_autostart.sh`

## Replicar tarifas pendentes entre usinas irmãs

As usinas **2 a 8** têm a tarifa calculada do mesmo jeito, e as **101, 102 e
103** também entre si. O botão **🔁 Replicar tarifas pendentes** (tela
Revisar) usa isso:

1. Baixa a lista da tela *Tarifas pendentes de cadastro* (Streamlit,
   `PENDENTES_URL` — tem padrão, só precisa ir no `.env` se o link mudar) e
   lê o que já está gravado no LexDash.
2. Para cada pendente, procura o valor numa usina irmã com a mesma
   concessionária (nome exato), mês, modalidade e GD1/GD2. Se as irmãs
   divergirem, não grava e avisa.
3. Mostra uma **tela de verificação** com tudo o que seria gravado — você
   desmarca o que não quiser.
4. Ao clicar *Gravar selecionadas*, abre o LexDash, preenche só células
   vazias e espera você clicar **Salvar** em cada passagem (GD1 / GD2 /
   Cacau Show). Depois confere pela API se ficou gravado.

Limitação: a grade não tem campo GD2 para Cacau Show, então esses pendentes
ficam de fora.

## Rodar manualmente pela linha de comando (sem o dashboard)

```bash
source .venv/bin/activate
python preencher_lexdash.py --dry-run   # só mostra o que faria
python preencher_lexdash.py             # preenche de verdade
python replicar_tarifas.py              # só mostra o que replicaria
python replicar_tarifas.py --gravar     # replica tudo (espera o Salvar)
```

## Arquivos

- `preencher_lexdash.py` — lógica de automação do grid do LexDash (Playwright).
- `replicar_tarifas.py` — replica tarifas pendentes a partir das usinas irmãs.
- `login_lexdash.py` — abre o navegador para login manual e salva a sessão.
- `servidor_local.py` — servidor Flask na porta 5002 chamado pelo dashboard.
- `instalar_autostart.sh` / `desinstalar_autostart.sh` — liga/desliga o
  início automático a cada login no Mac (LaunchAgent).
- `.env` — `TARIFAS_API_URL` e `ADMIN_TOKEN`, gerado no passo 4, **não
  versionado**.
- `cert.pem` / `key.pem` — certificado HTTPS local gerado pelo `mkcert`
  (passo 3), **não versionados**.
- `lexdash_session.json` — gerado pelo login, **não versionado**.
- `agente.log` — log do agente quando rodando via autostart, **não
  versionado**.
