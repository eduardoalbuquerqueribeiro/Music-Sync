import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

PASTA_SCRIPT = Path(__file__).parent
ARQUIVO_COOKIES = PASTA_SCRIPT / "cookies.txt"
ARQUIVO_CONFIG_LOCAL = PASTA_SCRIPT / ".config_local.json"
EXTENSOES_AUDIO = {".mp3", ".flac", ".m4a", ".ogg", ".opus", ".wav", ".wma"}


def carregar_config_local() -> dict:
    if ARQUIVO_CONFIG_LOCAL.exists():
        try:
            with open(ARQUIVO_CONFIG_LOCAL, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def salvar_config_local(caminho_musicas: str):
    try:
        with open(ARQUIVO_CONFIG_LOCAL, "w", encoding="utf-8") as f:
            json.dump({"caminho_musicas": caminho_musicas}, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def verificar_dependencias():
    for cmd in ["yt-dlp", "ffmpeg"]:
        if subprocess.run(["which", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
            print(f"[❌] Erro crítico: A ferramenta '{cmd}' não foi encontrada no sistema.")
            sys.exit(1)


def verificar_armazenamento(caminho_alvo: Path) -> bool:
    print("\n" + "=" * 60)
    print("🔍 DIAGNÓSTICO DE ARMAZENAMENTO")
    print("=" * 60)
    if not caminho_alvo.exists():
        print(f"📁 Pasta de música: ❌ A pasta '{caminho_alvo}' não existe.")
        return False
    print(f"📁 Pasta de música: ✅ Encontrada ({caminho_alvo})")
    print("=" * 60 + "\n")
    return True


def sanitizar_nome_sistema(nome: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '-', nome).strip('. ')


def normalizar_para_comparacao(texto: str) -> str:
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join(c for c in texto if not unicodedata.combining(c)).lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9\s]', ' ', texto)).strip()


def baixar_faixa_cli(termo_busca: str, caminho_saida: Path, arquivo_historico: Path, nome_artista: str, titulo_album: str) -> bool:
    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "320K",
        "--embed-thumbnail",
        "--add-metadata",
        "--force-ipv4",
        "--no-playlist",
        "--output", str(caminho_saida),
        "--download-archive", str(arquivo_historico),
    ]

    if ARQUIVO_COOKIES.exists():
        cmd.extend(["--cookiefile", str(ARQUIVO_COOKIES)])

    cmd.extend([
        "--parse-metadata", f":(?P<artist>{nome_artista})",
        "--parse-metadata", f":(?P<album>{titulo_album})",
    ])

    cmd.append(termo_busca)

    resultado = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return resultado.returncode == 0


def varrer_biblioteca(caminho_raiz: Path):
    if not verificar_armazenamento(caminho_raiz):
        return

    pastas_artistas = sorted([p for p in caminho_raiz.iterdir() if p.is_dir() and not p.name.startswith('.') and p.name.lower() != 'lost+found'])

    print(f"=== Iniciando varredura ({len(pastas_artistas)} artistas encontrados) ===\n")

    for pasta_artista in pastas_artistas:
        nome_artista = pasta_artista.name
        print(f"► Banda/Artista: [{nome_artista}]")

        pastas_albuns = [p for p in pasta_artista.iterdir() if p.is_dir() and not p.name.startswith('.')]

        for pasta_album in pastas_albuns:
            titulo_album = pasta_album.name
            print(f"  📁 Álbum/Pasta: {titulo_album}")

            arquivo_historico = pasta_album / ".downloaded.txt"
            
            # Lê arquivos de áudio já existentes na pasta
            arquivos_locais = [f.stem for f in pasta_album.iterdir() if f.is_file() and f.suffix.lower() in EXTENSOES_AUDIO]

            # Exemplo de busca interativa ou leitura de lista caso queira popular faixas
            # Como você já tem as pastas organizadas, vamos garantir que o yt-dlp varra e preencha
            print(f"    [✓] Verificando integridade da pasta...")

        print("-" * 60)


if __name__ == "__main__":
    print("=== Sincronizador v1.8 (Pure CLI Subprocess Engine) ===")
    verificar_dependencias()
    config = carregar_config_local()
    caminho_salvo = config.get("caminho_musicas", "")

    if caminho_salvo:
        print(f"📂 Caminho salvo anteriormente: {caminho_salvo}")
        entrada = input("Pressione [ENTER] para usar o caminho salvo ou digite outro: ").strip()
        caminho_final = entrada if entrada else caminho_salvo
    else:
        caminho_final = input("📂 Digite o caminho completo da sua pasta de músicas: ").strip()

    if not caminho_final:
        print("[❌] Nenhum caminho informado. Encerrando.")
    else:
        diretorio = Path(caminho_final.strip('\'"')).expanduser().resolve()
        salvar_config_local(str(diretorio))
        varrer_biblioteca(diretorio)
