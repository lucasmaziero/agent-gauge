<div align="center">

# Agent Gauge

**Os limites do seu agente de código num widget flutuante na área de trabalho.**

Monitora **Claude Code** ou **Codex**, um de cada vez, alternando pelo menu.

[English](README.md) · **Português**

[![CI](https://github.com/lucasmaziero/agent-gauge/actions/workflows/ci.yml/badge.svg)](https://github.com/lucasmaziero/agent-gauge/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/lucasmaziero/agent-gauge)](https://github.com/lucasmaziero/agent-gauge/releases/latest)
[![Python](https://img.shields.io/badge/python-3.11+-3776ab)](https://www.python.org)
[![Plataforma](https://img.shields.io/badge/plataforma-Windows%20%C2%B7%20macOS%20%C2%B7%20Linux-6e7681)](#instalação)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

<img src="docs/shot-widget.png" width="440" alt="Widget flutuante mostrando 37% da janela de 5 horas">

<a href="https://lucasmaziero.github.io/agent-gauge/"><b>lucasmaziero.github.io/agent-gauge</b></a>

</div>

---

## Como funciona

Os dois agentes medem as mesmas duas coisas: uma janela móvel de **cinco horas** e uma **semanal**,
de 18000 e 604800 segundos exatos, cada uma reportada como porcentagem com hora de reset. É isso o
medidor inteiro, e é por isso que um widget só veste qualquer um dos dois sem redesenhar nada.

A diferença está no que custa cada leitura.

**Claude Code.** A Anthropic não publica endpoint de uso para contas de assinatura. A utilização
viaja de carona nos headers `anthropic-ratelimit-unified-*` de qualquer resposta, então o widget faz
a menor requisição que existe — um `POST /v1/messages` com `max_tokens: 1` — só para lê-los:

| Header | Vira |
| --- | --- |
| `unified-5h-utilization` | porcentagem da janela de 5 horas |
| `unified-7d-utilization` | porcentagem da janela de 7 dias |
| `unified-5h-reset` / `unified-7d-reset` | relógio e contagem regressiva de cada reset |
| `unified-status` / `representative-claim` | chip de status e qual janela é o gargalo |

**Codex.** Existe endpoint de uso, então a leitura **não custa nada**: nenhuma requisição contra sua
cota, nenhum token gasto. O `backend-api/wham/usage` devolve `primary_window` e `secondary_window`
com as mesmas porcentagens e resets, mais o nome do plano.

Uma coisa ele não devolve: o `representative-claim` da Anthropic, a resposta do próprio servidor
sobre qual janela é o gargalo. Então, no Codex, o painel simplesmente não diz — até o
`limit_reached_type` informar que uma delas foi de fato atingida. Qual janela morde primeiro é uma
afirmação sobre o futuro, e duas porcentagens não sustentam uma.

Esse endpoint é a única ressalva que vale dizer sem rodeios: ele pertence ao backend web do ChatGPT
e não é API publicada. Não tem contrato nem política de depreciação, então no dia em que mudar de
formato essa metade para de funcionar. Cada campo é lido defensivamente, e uma resposta que não
traga as duas janelas é reportada como leitura que falhou, não adivinhada — um medidor mostrando
zero com confiança seria pior que um admitindo que não sabe.

Duas consequências de o app rodar na **mesma máquina** que o agente:

- **Nada para configurar.** O token sai de onde o próprio agente o guardou, relido a cada ciclo:
  `~/.claude/.credentials.json` no Windows e no Linux e o chaveiro de login no macOS para o Claude
  Code, `~/.codex/auth.json` para o Codex. Quando o agente renova, o widget acompanha.
- **Contagem real de tokens, onde ela existe.** Porcentagem é tudo o que as duas APIs carregam. O
  Claude Code escreve transcripts em `~/.claude/projects/**/*.jsonl` e esses números absolutos são
  lidos direto do disco. O Codex guarda o histórico em SQLite, sem totais de uso, então essa linha
  do painel fica vazia em vez de errada.

Nada é renovado por você. Os dois agentes rotacionam os próprios tokens enquanto rodam, e os dois
carregam um refresh token que isto poderia gastar — mas refresh tokens costumam ser de uso único com
rotação, então gastar um poderia deixar o agente com um token inválido e te deslogar dele. É jeito
desproporcional de perder a leitura de um medidor.

## Instalação

Todos os downloads ficam na [página de releases][releases], cada um com seu SHA-256 ao lado. Os três
builds não são assinados, e cada sistema reclama do seu jeito; abaixo está como passar por isso.

Em qualquer um deles é preciso ter feito login na máquina do agente que você quer monitorar. Sem
isso, no lugar do número o widget diz isso e oferece a página de setup daquele agente.

[releases]: https://github.com/lucasmaziero/agent-gauge/releases/latest

### Windows

`AgentGauge-<versão>.exe`, dois cliques. A instalação é **por usuário**, em
`%LOCALAPPDATA%\Programs\Agent Gauge`. Não pede admin nem passa por UAC. O assistente
oferece atalho na área de trabalho e iniciar junto com o Windows, ambos opcionais. Desinstala pelo
painel **Aplicativos instalados**, perguntando antes se deve apagar também suas preferências.

Sem assinatura, então o SmartScreen avisa "editor desconhecido" no primeiro download.

### macOS

`AgentGauge-<versão>-arm64.dmg` para Apple Silicon, `-x86_64` para Intel. Abra e arraste o app para
Applications. Ele não aparece no Dock, de propósito (`LSUIElement`): a barra de menus e o widget
flutuante são a interface inteira.

O bundle é assinado ad-hoc, não com um Developer ID, então o Gatekeeper recusa na primeira abertura.
Clique com o botão direito e escolha **Abrir**, que oferece a exceção que o duplo clique não dá, ou:

```bash
xattr -dr com.apple.quarantine "/Applications/Agent Gauge.app"
```

A primeira coleta abre um pedido de acesso ao chaveiro, porque no macOS o token mora lá e não num
arquivo. Escolha **Sempre permitir** e ele não pergunta de novo.

### Linux

`AgentGauge-<versão>.AppImage`, marcado como executável:

```bash
chmod +x AgentGauge-*.AppImage
./AgentGauge-*.AppImage
```

Duas ressalvas de desktop que vale saber antes de abrir um bug:

- **O GNOME não tem bandeja do sistema.** O ícone só aparece com uma extensão AppIndicator
  instalada. Sem ela o app percebe e mantém o widget flutuante na tela, já que o menu do botão
  direito dele tem os mesmos comandos.
- **O Wayland proíbe uma janela de se posicionar**, então a posição salva não pode ser restaurada.
  Onde houver um servidor X alcançável o app pede XWayland e a posição volta a funcionar; se você
  definir `QT_QPA_PLATFORM`, sua escolha sempre prevalece.

### Do código-fonte

Funciona nos três, e é o único caminho numa arquitetura sem build pronto.

```bash
uv sync
uv run agent-gauge       # o ./run.sh desgruda do terminal
```

```powershell
uv sync
uv run agent-gauge       # ou .\run.bat, que sobe sem janela de console
```

## Uso

<img src="docs/shot-panel-pt.png" width="380" align="right" alt="Painel expandido">

**Widget.** Nenhum número aparece duas vezes: o anel responde *quanto já gastei da janela de 5h*, a
linha `5h` responde *quanto falta para ela resetar* (com o horário do reset à direita) e a linha `7d`
cobre a semana.

Em volta do anel corre um segundo anel, cinza sobre trilho, descontando até a próxima coleta, e ele
vira um giro verde enquanto a coleta acontece. O cinza é proposital: em uso alto o medidor fica
laranja ou vermelho, e um anel concêntrico da mesma família de cor se funde com ele.

A coluna da direita tem três andares: o mascote no topo, o botão de **atualizar agora** no meio e o
menu embaixo. Arraste o resto do cartão para posicionar (a posição fica salva), clique para abrir o
painel, ou use o botão direito em qualquer lugar para o menu.

**Painel.** A janela de 5h é o que morde primeiro, então fica num cartão com número grande e
medidor de 18 segmentos; a de 7 dias é apoio e vive solta sobre a superfície, com barra contínua.
Abaixo de um fio divisor vêm os metadados: chip de status (`OK` / `ATENÇÃO` / `BLOQUEADO`), tokens
reais da janela, incidentes abertos em `status.claude.com` e o carimbo da última coleta.

O mascote do cabeçalho acinzenta quando há erro de coleta ou incidente aberto, o mesmo sinal que o
selo do widget dá.

**Sem token** não há o que carimbar com hora, então o rodapé carrega a saída: um link para a página
de setup do agente que está sendo monitorado. Ele nomeia o beco exato — **Instalar o Claude Code**
ou **Instalar o Codex** quando o diretório daquele agente não está na máquina, **Como fazer login**
quando está lá mas sem token utilizável. Toda mensagem desse caminho também nomeia o agente, e
nenhuma delas nomeia um comando: `claude` não é o que um usuário de Codex digita.

Esse diretório — `~/.claude` ou `~/.codex` — é o teste, e não um binário no PATH, porque os apps de
desktop e as extensões de IDE o escrevem sem nunca instalar uma CLI, e checar o PATH diria a um
usuário ativo que ele nunca instalou nada. Nada é instalado por você: despejar script de instalação
num shell em nome de alguém não é coisa que um widget de uso deva fazer.

**Trocar de agente.** Um de cada vez, em **Monitorando**, no menu. O cabeçalho do painel nomeia o
que está à vista e veste a marca dele — a do Claude Code ou a do Codex — porque o anel e as linhas
são idênticos nos dois casos, e marca sobre números do outro agente é a única coisa que isto não
pode errar. Trocar descarta o snapshot, o estado do alerta e o histórico da taxa de queima: uma taxa
misturando janelas de dois agentes seria ficção. A marca do próprio app não é de nenhum dos dois: é
o medidor.

**Bandeja.** O ícone é o anel com o número dentro, desenhado num tamanho por vez para o shell não
precisar reduzir nada, inclusive nos tamanhos que a escala do monitor pede (25px a 125%). O tooltip
traz as duas janelas.

**Alertas.** Um widget é um mostrador, e mostrador só funciona se você olhar. Uma vez por janela
de cinco horas, quando o número cruza o limiar pela primeira vez, o app avisa pelas notificações do
próprio sistema — e diz o que dá para agir em cima: não que você está em 80%, mas que nesse ritmo
você estoura em quarenta minutos. O limiar fica no menu, e desligar também.

**Sobre.** Um cartão pequeno com a versão, o autor, a licença e o repositório, mais um botão
**Verificar atualizações**. Essa verificação só roda quando você aperta: não há checagem em segundo
plano nem atualização automática. Ele lê a última tag do GitHub e, se estiver à frente do build em
uso, vira link para a página de download — que nomeia o arquivo de cada sistema, enquanto a página
do release são oito arquivos e deixa você descobrir quais dois são os seus. Baixar e instalar
continua sendo seu de qualquer forma.

Verificação que falha nunca é redigida como aprovada, e as formas de falhar não são redigidas umas
como as outras: rede morta, limite de taxa do GitHub, status HTTP e resposta ilegível dizem cada uma
o que é, e todas vão para o `errors.log`. Antes todas diziam "não consegui alcançar o GitHub" — que
para o limite de taxa é resposta errada, não vaga, já que as sessenta requisições por hora são
contadas por IP e um escritório inteiro esgota sem esta máquina fazer uma.

<br clear="right">

<div align="center"><img src="docs/tray.png" width="260" alt="Ícone da bandeja em 6%, 47%, 83% e 100%"></div>

### Menu

| Item | O que faz |
| --- | --- |
| Atualizar agora | Força um ciclo fora do intervalo |
| Abrir painel | Mesmo que clicar no widget |
| Mostrar widget | Deixa só o ícone da bandeja |
| Modo compacto | Reduz o widget ao anel |
| Travar posição | Ignora o arrasto |
| Intervalo | 30 s a 15 min, padrão 2 min; é um piso, não uma cadência fixa |
| Monitorando | Claude Code ou Codex; trocar limpa o que pertencia ao outro |
| Alertar em | Notifica uma vez por janela nessa porcentagem, padrão 80%; Desligado desliga |
| Idioma | Automático, Português, English |
| Iniciar com o *&lt;seu sistema&gt;* | Leva o nome do sistema em que roda; um mecanismo para cada, ver abaixo |
| Verificar atualizações | Pergunta ao GitHub qual é a última tag, uma vez, quando você clica |
| Sobre | Versão, autor, licença e a mesma verificação de atualização |

Autostart e preferências são as únicas coisas que mudam de plataforma para plataforma. O
`history.json` e o `errors.log` ficam ao lado do `settings.json`, no mesmo diretório, com as
amostras da taxa de queima e o registro dos ciclos que falharam:

| | Autostart | Preferências |
| --- | --- | --- |
| Windows | `HKCU\...\CurrentVersion\Run` | `%APPDATA%\AgentGauge\settings.json` |
| macOS | `~/Library/LaunchAgents/com.lucasmaziero.agent-gauge.plist` | `~/Library/Application Support/AgentGauge/settings.json` |
| Linux | `~/.config/autostart/agent-gauge.desktop` | `$XDG_CONFIG_HOME/agent-gauge/settings.json` |

Os três são por usuário: nenhum pede admin, e nenhum escreve fora da sua pasta pessoal.

### Idioma

A interface vem em português e inglês. Por padrão segue o idioma do sistema; o menu tem **Idioma**
com Automático, Português e English, e a escolha fica salva nas preferências. A troca vale na hora,
sem reiniciar.

Não é só rótulo: o dia da semana (`sex` / `Fri`), o separador decimal (`6,0M` / `6.0M`) e o plural
de sessões acompanham o idioma. Traduzir só os rótulos deixa o resultado meio convertido, que é pior
que não traduzir.

As strings ficam em `src/agent_gauge/i18n.py`, um dicionário por idioma. Acrescentar um idioma é
copiar o dicionário do inglês, traduzir os valores e registrar em `LANGUAGES`; um teste garante que
as chaves e os campos de formatação `{assim}` batem entre todos os idiomas.

## Estrutura

```
src/agent_gauge/   código do app       tests/       suíte de testes
installer/          empacotamento       tools/       geradores de ícone e preview
```

| Módulo | Papel |
| --- | --- |
| `paths.py` | Onde cada sistema guarda credenciais, transcripts e preferências |
| `credentials.py` | Lê o token OAuth do Claude Code, do arquivo ou do chaveiro do macOS |
| `autostart.py` | Iniciar com a sessão: chave Run, LaunchAgent ou entrada .desktop |
| `providers/` | Um `Provider` por agente: credenciais, coleta, incidentes, totais de tokens |
| `signin.py` | Separa os dois becos sem token e abre a página de setup |
| `diag.py` | Registro limitado de ciclos que falharam, escrito só quando um falha |
| `net.py` | O único contexto TLS de todas as chamadas HTTPS, verificado pelo sistema |
| `release.py` | Lê a última tag publicada e compara com este build |
| `about.py` | Versão, autor e a verificação de atualização, num cartão |
| `api.py` | Consulta de uso e incidentes; `parse()` separado para testar sem rede |
| `tokens.py` | Soma tokens da janela pelos transcripts locais |
| `poller.py` | Thread de coleta, histórico, burn rate e projeção |
| `theme.py` | Paleta, escala de espaçamento de 4pt e formatadores |
| `paint.py` | Primitivas de desenho: anel, medidor, chip, sombra, ícones |
| `brand.py` | Mascote do Claude Code a partir do SVG oficial, embutido como string |
| `i18n.py` | Strings da interface, um dicionário por idioma |
| `widget.py` | Barra flutuante |
| `panel.py` | Painel expandido |
| `app.py` | Bandeja, menu e montagem |

## Desenvolvimento

```powershell
uv sync                                           # cria o .venv com o grupo de dev
uv run pytest                                     # 263 testes, sem rede e sem janela
uv run ruff check .                               # lint (regras em pyproject.toml)
uv run python tools/preview.py docs/preview.png   # render offline das duas telas
$env:AGENT_GAUGE_DEBUG=1; uv run agent-gauge    # imprime cada ciclo no console
```

Os testes de render usam `QT_QPA_PLATFORM=offscreen` (ver `tests/conftest.py`) e verificam que todo
caminho de pintura roda sem estourar nos estados reais: sem dado, ao vivo, erro, coletando e modo
compacto.

Nesse modo o Qt troca o banco de fontes do sistema por um stub cuja fonte de fallback é ~1,8x mais
larga que a Segoe UI. Duas consequências:

- os testes que medem geometria de texto ficam condicionados à fonte (fixture `real_fonts`) e se
  pulam no modo headless. Para rodar a suíte inteira contra a fonte de verdade:

  ```powershell
  $env:QT_QPA_PLATFORM = "windows"; uv run pytest     # Windows
  ```

  ```bash
  QT_QPA_PLATFORM=cocoa uv run pytest                 # macOS
  QT_QPA_PLATFORM=xcb uv run pytest                   # Linux
  ```

- o `tools/preview.py` **não** usa offscreen de propósito: nesse modo todo glifo vira quadradinho.

Essa trava é mais rígida que "conseguimos uma fonte". As constantes de geometria do `widget.py`
saíram das métricas de uma família só, e o `paint.MEASURED` registra quais famílias já foram
conferidas desde então.

```powershell
uv run python tools/measure_font.py                     # o que o app resolveu
uv run python tools/measure_font.py "Noto Sans"         # uma família instalada
uv run python tools/measure_font.py caminho\Inter.ttf    # um arquivo, sem instalar
```

Ela roda as mesmas doze verificações dos testes e imprime os números. O arquivo de fonte é carregado
só naquele processo, via `QFontDatabase`, então medir uma face não significa instalá-la. A mesma
chave existe em tempo de execução: o `AGENT_GAUGE_FONT` fixa uma família, para um desktop cujo
padrão meça mal.

O que isso revelou:

| Família | Resultado |
| --- | --- |
| Segoe UI Variable Display | as doze cabem; é a face contra a qual o desenho foi feito |
| Noto Sans | as doze cabem |
| Ubuntu | as doze cabem |
| Cantarell | `56min` estoura a linha por 0,1px e é elidido |
| Inter | duas linhas estouram; a mais larga passava quase 2px |

Saíram duas mudanças daí. O número do medidor agora **se dimensiona**: parte do corpo que o desenho
usa e desce até liberar o traço, então ele encolhe um ponto em vez de atravessar o anel. No Segoe UI
nada se move, porque nada precisava. E a entrada de Linux do `paint.CANDIDATES` sumiu: ela começava
pela Inter, que nenhum desktop distribui e que mede pior de todas, ou seja, estava sobrepondo a
fonte configurada pelo usuário por uma que encaixa pior. O Linux agora usa o que o desktop define,
que é o que o `QFontDatabase` já reportava.

As linhas continuam elidindo em vez de colidir quando uma face corre larga, que é a resposta certa
para texto que realmente não cabe — mas é truncamento, então uma família só entra no `MEASURED`
quando nada trunca. O macOS segue sem medição: a SF Pro não é distribuída num formato que isso
consiga carregar.

A camada de plataforma em si dá para testar de qualquer lugar: `paths`, `autostart` e o ramo do
chaveiro em `credentials` leem flags de módulo que os testes fixam, então o `test_paths.py` e o
`test_autostart.py` exercitam os caminhos de macOS e Linux rodando no Windows e vice-versa. Só o
backend de registro fica para uma máquina que tenha registro.

## Gerando os pacotes

Cada plataforma gera o próprio artefato, nela mesma. Não há compilação cruzada aqui: o PyInstaller
congela o interpretador e as bibliotecas Qt da máquina em que roda.

```powershell
.\installer\build.ps1                  # ícone -> PyInstaller -> Inno Setup
.\installer\build.ps1 -SkipInstaller   # só a pasta portátil em build\dist
.\installer\build.ps1 -Clean           # apaga build\ antes, inclusive os caches
```

```bash
./installer/build.sh                   # ícone -> PyInstaller -> .dmg ou .AppImage
./installer/build.sh --skip-package    # só a pasta portátil em build/dist
./installer/build.sh --clean           # apaga build/ antes, inclusive os caches
```

| Plataforma | Precisa de | Gera |
| --- | --- | --- |
| Windows | Inno Setup (`winget install JRSoftware.InnoSetup`) | `build/AgentGauge-<versão>.exe`, ~21 MB comprimidos para 70 MB instalados |
| macOS | Command line tools do Xcode, por causa de `iconutil`, `codesign` e `hdiutil` | `build/AgentGauge-<versão>-<arch>.dmg` |
| Linux | `appimagetool`, baixado na primeira execução | `build/AgentGauge-<versão>.AppImage` |

Cada execução deixa **um único** artefato em `build/`, o recém-gerado: guardar versões antigas lado
a lado é como se distribui o arquivo errado por engano.

| Arquivo | Papel |
| --- | --- |
| `installer/build.ps1` | Windows: os três passos, versão lida do `pyproject.toml` |
| `installer/build.sh` | macOS e Linux: os mesmos três passos, mais assinatura e empacotamento |
| `installer/agent-gauge.spec` | PyInstaller, compartilhado: onedir, sem console, ícone e metadados por SO |
| `installer/agent-gauge.iss` | Inno Setup: instalação por usuário, atalhos, autostart, desinstalador |
| `installer/entry.py` | Entry point do build congelado (o `__main__.py` usa import relativo) |
| `tools/gen_icon.py` | `.ico`, `.iconset` ou árvore hicolor, escolhidos pelo caminho de saída |
| `tools/measure_font.py` | Roda as verificações de geometria do layout em qualquer fonte |

Decisões do empacotamento:

- **onedir, não onefile.** O `--onefile` descompacta todo o runtime do Qt numa pasta temporária a
  cada execução, um a dois segundos num app que mora na bandeja e sobe com a sessão.
- **`opengl32sw.dll` fora do pacote.** São 20 MB do OpenGL por software da Mesa, um quinto do
  bundle, e esta interface é pintada só pelo raster engine do Qt.
- **`QtDBus` fica de fora em todo lugar menos no Linux**, onde ele não é opcional: um ícone de
  bandeja num desktop Linux moderno *é* um StatusNotifierItem em D-Bus, e tirar o módulo deixa o app
  sem bandeja nenhuma.
- **O `.ico` é montado à mão, o `.icns` não.** Importar Pillow no mesmo processo do PySide6 carrega
  uma segunda libpng/zlib e o encoder PNG do Qt morre com violação de acesso, então o contêiner ICO
  é escrito direto — 40 linhas, e nenhum conflito de DLL. Para o macOS o gerador emite um diretório
  `.iconset` e deixa o `iconutil` da Apple montar o contêiner: um feito à mão que o macOS recusa
  caladinho seria a troca pior.
- **A assinatura ad-hoc no macOS não é cosmética.** Um binário arm64 sem assinatura é morto na
  abertura, então o `build.sh` sempre assina; o `CODESIGN_ID` troca por um Developer ID de verdade
  quando houver um.
- **A AppImage é gerada na imagem mais antiga do Ubuntu ainda suportada**, porque ela herda a glibc
  da máquina que a construiu e uma mais nova se recusaria a subir em distros mais velhas.

## Notas de implementação

Coisas que custaram tempo e que o código sozinho não explica:

- **`QGraphicsDropShadowEffect` em janela translúcida no Windows congela o conteúdo** depois do
  primeiro frame, e o widget desenhava `--` para sempre. A sombra é pintada à mão em `paint.shadow()`
  e cada janela reserva uma margem transparente para ela.
- **O receptor dos sinais do poller precisa ser `QObject`.** Ligado a um objeto Python comum, a
  conexão vira direta e o desenho acontece na thread da coleta.
- **Clicar no widget com o painel aberto chega em duas partes.** O `Qt.Popup` se fecha sozinho no
  clique de fora e o widget recebe o mesmo clique em seguida; sem guarda, o painel fechava e reabria
  no mesmo gesto. `Panel.just_closed()` engole o segundo evento por 250 ms.
- **A confiança HTTPS passa pelo sistema operacional, não pela loja do próprio OpenSSL.** O Windows
  mantém em disco um conjunto pequeno de certificados raiz e busca os demais sob demanda pela
  CryptoAPI — por isso um navegador abre um site que o Python, verificando pelo OpenSSL, recusa com
  "unable to get local issuer certificate". Não é hipotético: foi relatado de uma máquina onde o
  medidor lia a Anthropic normalmente, o navegador abria o `api.github.com` normalmente, e a
  verificação de atualização dentro do mesmo app não conseguia. O `net.context()` entrega a
  verificação ao sistema, então a resposta é a mesma em que todo o resto daquela máquina acredita,
  inclusive a CA de um proxy corporativo — e toda chamada HTTPS do app passa por ele. Antes, uma
  das cinco passava contexto e quatro não, e foi por isso que a diferença ficou invisível tanto
  tempo. Onde a camada do sistema não estiver disponível o verificador antigo ainda roda — recusar
  a conexão seria pior —, mas esse fallback escreve uma linha no `errors.log`, porque correção que
  se desliga em silêncio é indistinguível de correção nenhuma.
- **Falha às 3 da manhã não deixava rastro.** A mensagem ficava na tela até o ciclo seguinte
  sobrescrever, então quando alguém ia olhar o app já tinha se recuperado e a evidência tinha
  sumido. O `errors.log` agora guarda os últimos duzentos ciclos com falha e o contexto que os
  separa: o status HTTP, quanto tempo desde o último ciclo bom, quando o Claude Code reescreveu as
  credenciais pela última vez, e se o token estava mesmo vencido. Sucesso não é registrado, então o
  arquivo continuar vazio já é o sinal. Nenhum dos dois tokens é escrito nele, e um teste lê o
  arquivo inteiro de volta para provar.

  Uma sequência da mesma falha colapsa numa linha só, com os valores mais recentes, uma contagem
  `repeat=` e o início em `since=`. Não é firula: o primeiro apagão que isso capturou repetiu de
  dois em dois minutos por quatro horas, escreveu 130 linhas idênticas e empurrou o começo do
  próprio apagão para fora do arquivo.
- **Um pacote perdido parecia defeito.** Não havia retry, então uma conexão que falhava por um
  segundo pintava o widget de vermelho até o ciclo seguinte — quinze minutos disso no intervalo mais
  longo. Agora o probe é tentado duas vezes. Resposta HTTP não é repetida: o 429 carrega os headers
  de limite que são a razão da requisição, e repetir dobraria o custo de estar limitado.
- **Token expirado é estado de espera, não falha.** O access token do Claude Code vive oito horas
  e só é renovado enquanto o Claude Code roda, então uma noite fora termina sem token utilizável —
  medido, não suposto: três ciclos seguidos de 8,00 h cada. Pintar isso de vermelho fazia o widget
  gritar lobo pela própria condição normal, então agora ele espera em cinza e diz isso. Vermelho
  ficou para o que está mesmo errado. A requisição também não é enviada: o `expiresAt` é o carimbo
  contra o qual o Claude Code renova, então ela só voltaria 401.
- **A recuperação não espera mais o próximo ciclo.** Enquanto o token está vencido, a única coisa
  que pode mudar a resposta é o Claude Code reescrever as credenciais, então o carimbo daquele
  arquivo é observado no lugar do relógio. Usar o Claude Code traz o widget de volta em uns cinco
  segundos em vez de até um intervalo inteiro, e um `stat` não custa nada.
- **O que ele não vai fazer é renovar o token sozinho.** O refresh token está ali e funcionaria.
  Refresh tokens costumam ser de uso único com rotação, então um widget que gastasse um poderia
  deixar o Claude Code com um token inválido e te deslogar dele — jeito desproporcional de perder
  uma leitura de medidor.
- **A taxa de queima morria por horas depois de cada reset de janela.** O deque de amostras era
  limitado por quantidade, não por tempo, então as leituras da janela anterior continuavam nele; o
  `burn_rate()` via a porcentagem cair, tomava aquilo por reset e devolvia zero até elas saírem pela
  idade — até seis horas. Agora as amostras são descartadas quando são anteriores à janela atual, o
  que é também o que torna seguro guardar a linha de base em disco entre execuções.
- **Texto é medido, nunca posicionado por deslocamento fixo.** `56min` é meia vez mais largo que
  `2h13` e invadia a coluna do relógio. Os algarismos usam `tnum` (`QFont.setFeature`), senão o `1`
  é mais estreito que os outros dígitos e a contagem treme a cada segundo.

E quatro que só aparecem quando o app sai do Windows:

- **O macOS esconde janelas `Qt.Tool` sempre que o aplicativo perde o foco.** Num widget cuja função
  inteira é ficar visível enquanto você trabalha em outra coisa, isso significa nunca estar na tela.
  O `WA_MacAlwaysShowToolWindow` desfaz isso, e não faz nada nos outros dois.
- **O Wayland não dá a uma janela voz sobre a própria posição.** O `move()` é ignorado em silêncio,
  então a posição salva — que é boa parte da graça de um widget flutuante — não pode ser restaurada.
  Não há conserto dentro do protocolo; o `app.prefer_x11()` pede XWayland quando há um servidor X
  alcançável, e sai do caminho se o usuário definiu `QT_QPA_PLATFORM`.
- **O ícone de bandeja é desenhado sobre uma superfície que este app não pinta.** Dígitos quase
  brancos somem numa barra de tarefas, barra de menus ou painel claro, então a tinta segue o tema do
  sistema. No Windows isso quer dizer ler `SystemUsesLightTheme` do registro em vez do
  `colorScheme()` do Qt: o Qt reporta o tema *dos aplicativos*, e um arranjo de apps claros com
  barra escura sairia invertido.
- **No macOS o token não está num arquivo.** O Claude Code o guarda no chaveiro de login, então o
  `credentials.py` chama `security find-generic-password` e mantém o arquivo como plano B. Toda
  forma dessa chamada voltar vazia — sem login, acesso negado, binário inexistente — cai no arquivo
  e produz um erro só para os dois casos.

## Custo

Cada ciclo é um POST que vale um token de saída, a menor requisição que a API aceita. A cada dois
minutos daria algo como 700 por dia, mas o intervalo é um piso e não uma cadência: depois de três
leituras que não se movem, a espera estica até quatro vezes ele, então uma máquina ociosa assenta
perto de 175. Qualquer coisa que mexa no número, qualquer erro e o botão de atualizar põem tudo de
volta na hora. Suba o intervalo no menu se ainda assim incomodar.

## Licença

MIT. Veja [LICENSE](LICENSE).
