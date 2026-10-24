# 🎵 Music-Sync — Sincronizador Automático de Discografias

Script em Python (compatível com **Linux**, **Windows** e **macOS**) que varre a sua pasta de músicas, identifica as pastas de bandas/artistas, busca toda a discografia oficial no YouTube Music e baixa automaticamente os álbuns que estiverem faltando em **MP3 (320 kbps)** já com os metadados (artista, álbum, número da faixa e ano).

## ✨ Funcionalidades

- **Suporte Multi-Navegador (Chrome, Firefox, Safari, Brave, Edge):** Pergunta em qual navegador você está logado no YouTube para autenticar automaticamente e evitar bloqueios de bot (`Sign in to confirm you're not a bot`) ou restrição de idade (+18). Detecta inclusive navegadores instalados via Flatpak no Linux.
- **Memória Local Inteligente:** Salva o caminho da sua pasta de músicas e o seu navegador preferido localmente (em `.config_local.json`, ignorado pelo Git) para que nas próximas execuções você só precise apertar ENTER.
- **Detecção de HD Externo e Montagem:** Verifica automaticamente se o caminho apontado fica em um HD externo, partição secundária ou disco local, avisando caso o disco esteja desconectado ou desmontado.
- **Varredura Inteligente de Álbuns:** Analisa os nomes das pastas que você já tem ignorando anos, símbolos ou termos extras (evitando downloads duplicados).

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

1. Certifique-se de estar logado na sua conta do YouTube no seu navegador (Chrome, Firefox, Safari, etc.).
2. Crie uma pasta com o nome da banda dentro da sua pasta de músicas (ex: .../music/Rammstein).
3. Abra o terminal na pasta Music-Sync e rode:

- **No Linux / macOS:**

    ./venv/bin/python sincronizar_discografia.py

- **No Windows:**

    .\venv\Scripts\python.exe sincronizar_discografia.py
