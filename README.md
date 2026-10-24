# 🎵 Music-Sync — Sincronizador Automático de Discografias

Script em Python (compatível com **Linux**, **Windows** e **macOS**) que varre a sua pasta de músicas, identifica as pastas de bandas/artistas, busca toda a discografia oficial no YouTube Music e baixa automaticamente os álbuns que estiverem faltando em **MP3 (320 kbps)** já com metadados completos e **capas de álbum/artista**.

## ✨ Funcionalidades

- **Download Automático de Capas (`cover.jpg` e `artist.jpg`):** Baixa a foto oficial da banda em alta resolução (`artist.jpg`) na pasta do artista, salva a capa oficial (`cover.jpg`) dentro de cada álbum (inclusive nos álbuns que você já tinha!) e embute a capa nos arquivos MP3.
- **Reconhecimento Inteligente de Músicas e Álbuns (*Fuzzy Matching*):** Não importa se os seus álbuns ou músicas atuais estão numerados ou não, ou se têm textos como `[2025]` ou `(Deluxe)` — o script reconhece as faixas que você já tem (em `.mp3`, `.flac`, `.m4a`, etc.) e baixa apenas o que estiver realmente faltando.
- **Suporte Multi-Navegador (Chrome, Firefox, Safari, Brave, Edge):** Autentica via cookies para evitar bloqueios de bot e restrição de idade (+18).
- **Memória Local Inteligente:** Salva seu caminho de músicas e navegador preferido localmente em `.config_local.json` (ignorado pelo Git).
- **Detecção de HD Externo e Montagem:** Verifica se o seu HD externo ou partição secundária está montado antes de iniciar.

## 🛠️ 1. Pré-requisitos (Instalar apenas 1 vez no PC)

- **Linux (Fedora):**

    sudo dnf install python3 python3-virtualenv ffmpeg git

- **Linux (Ubuntu / Debian):**

    sudo apt update && sudo apt install python3 python3-venv ffmpeg git

- **Windows (PowerShell):**

    winget install Python.Python.3.12 Gyan.FFmpeg Git.Git

- **macOS (Homebrew):**

    brew install python ffmpeg git

## 🚀 2. Instalação Passo a Passo (Do Zero)

1. **Baixar o repositório e entrar na pasta:**

    git clone https://github.com/eduardoalbuquerqueribeiro/Music-Sync.git
    cd Music-Sync

2. **Criar o ambiente virtual (venv) e instalar as dependências (Linux / macOS):**

    python3 -m venv venv
    source venv/bin/activate
    pip install -U -r requirements.txt

3. **Criar o ambiente virtual (venv) e instalar as dependências (Windows PowerShell):**

    python -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -U -r requirements.txt

## ▶️ 3. Como Executar no Dia a Dia

1. Crie uma pasta com o nome da banda dentro da sua pasta de músicas (ex: .../music/Rammstein).
2. Abra o terminal na pasta Music-Sync e rode:

- **No Linux / macOS:**

    ./venv/bin/python sincronizar_discografia.py

- **No Windows:**

    .\venv\Scripts\python.exe sincronizar_discografia.py
