# 🎵 Music-Sync — Sincronizador Automático de Discografias

Script em Python (compatível com **Linux** e **Windows**) que varre a sua pasta de músicas, identifica as pastas de bandas/artistas, busca toda a discografia oficial no YouTube Music e baixa automaticamente os álbuns que estiverem faltando em **MP3 (320 kbps)** já com os metadados (artista, álbum, número da faixa e ano).

## ✨ Funcionalidades

- **Detecção de HD Externo e Montagem:** Verifica automaticamente se o caminho apontado fica em um HD externo, partição secundária ou disco local, avisando caso o disco esteja desconectado ou desmontado.
- **Varredura Inteligente de Álbuns:** Analisa os nomes das pastas que você já tem ignorando anos, símbolos ou termos extras (evitando downloads duplicados).
- **Desbloqueio de Faixas +18:** Suporte integrado a cookies do navegador ou arquivo cookies.txt, além de busca alternativa automática caso o vídeo original esteja bloqueado.
- **Adição Fácil de Novas Bandas:** Basta criar uma pasta vazia com o nome da banda dentro da sua pasta de músicas e rodar o script.

## 🛠️ 1. Pré-requisitos (Instalar apenas 1 vez no PC)

- **Linux (Fedora):**

    sudo dnf install python3 python3-virtualenv ffmpeg git

- **Linux (Ubuntu / Debian):**

    sudo apt update && sudo apt install python3 python3-venv ffmpeg git

- **Windows (PowerShell):**

    winget install Python.Python.3.12 Gyan.FFmpeg Git.Git

## 🚀 2. Instalação Passo a Passo (Do Zero)

1. **Baixar o repositório e entrar na pasta:**

    git clone https://github.com/eduardoalbuquerqueribeiro/Music-Sync.git
    cd Music-Sync

2. **Criar o ambiente virtual (venv) e instalar as dependências (Linux):**

    python3 -m venv venv
    source venv/bin/activate
    pip install -U -r requirements.txt

3. **Criar o ambiente virtual (venv) e instalar as dependências (Windows PowerShell):**

    python -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -U -r requirements.txt

## ▶️ 3. Como Executar no Dia a Dia

1. Crie uma pasta com o nome da banda dentro da sua pasta de músicas (ex: .../music/Rammstein).
2. (Opcional) Se não quiser digitar o caminho toda vez, abra o arquivo sincronizar_discografia.py e troque "DIGITE_AQUI_O_SEU_CAMINHO" na variável CAMINHO_PADRAO pelo endereço da sua pasta.
3. Abra o terminal na pasta Music-Sync e rode:

- **No Linux:**

    ./venv/bin/python sincronizar_discografia.py

- **No Windows:**

    .\venv\Scripts\python.exe sincronizar_discografia.py
