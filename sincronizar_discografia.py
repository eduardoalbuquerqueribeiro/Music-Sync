import ctypes
import json
import os
import re
import sys
import unicodedata
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path
from ytmusicapi import YTMusic
import yt_dlp

# =====================================================================
# ARQUIVOS DE CONFIGURAÇÃO LOCAL (Ignorados pelo Git)
# =====================================================================

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


def salvar_config_local(caminho_musicas: str, navegador: str):
    dados = {
        "caminho_musicas": caminho_musicas,
        "navegador_cookies": navegador
    }
    try:
        with open(ARQUIVO_CONFIG_LOCAL, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def escolher_navegador(navegador_salvo: str) -> str:
    opcoes = {
        "1": "chrome",
        "2": "firefox",
        "3": "safari",
        "4": "brave",
        "5": "edge",
        "6": "chromium",
        "7": "nenhum"
    }

    print("\n🌐 AUTENTICAÇÃO DO YOUTUBE (Para evitar bloqueio de Bot e músicas +18)")
    print("   Em qual navegador você está logado na sua conta Google/YouTube?")
    print("   [1] Google Chrome   (Linux / Windows / macOS)")
    print("   [2] Mozilla Firefox (Linux / Windows / macOS)")
    print("   [3] Apple Safari    (macOS)")
    print("   [4] Brave Browser   (Linux / Windows / macOS)")
    print("   [5] Microsoft Edge  (Linux / Windows / macOS)")
    print("   [6] Chromium        (Linux / Windows / macOS)")
    print("   [7] Não usar navegador (usar apenas cookies.txt ou sem login)")

    if navegador_salvo:
        escolha = input(f"\nEscolha uma opção [1-7] ou pressione [ENTER] para manter '{navegador_salvo}': ").strip().lower()
        if not escolha:
            return navegador_salvo
    else:
        escolha = input("\nEscolha uma opção [1-7] (Padrão: 1 - Chrome): ").strip().lower()
        if not escolha:
            return "chrome"

    if escolha in opcoes:
        return opcoes[escolha]
    if escolha in opcoes.values():
        return escolha

    return "chrome"


def obter_config_cookies_navegador(navegador: str) -> tuple | None:
    if not navegador or navegador == "nenhum":
        return None

    if sys.platform.startswith("linux"):
        home = Path.home()
        caminhos_linux = {
            "chrome": (
                home / ".config/google-chrome",
                home / ".var/app/com.google.Chrome/config/google-chrome"
            ),
            "firefox": (
                home / ".mozilla/firefox",
                home / ".var/app/org.mozilla.firefox/.mozilla/firefox"
            ),
            "brave": (
                home / ".config/BraveSoftware/Brave-Browser",
                home / ".var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser"
            ),
            "edge": (
                home / ".config/microsoft-edge",
                home / ".var/app/com.microsoft.Edge/config/microsoft-edge"
            ),
            "chromium": (
                home / ".config/chromium",
                home / ".var/app/org.chromium.Chromium/config/chromium"
            ),
        }
        if navegador in caminhos_linux:
            nativo, flatpak = caminhos_linux[navegador]
            if not nativo.exists() and flatpak.exists():
                return (navegador, str(flatpak))

    return (navegador,)


def verificar_armazenamento(caminho_alvo: Path) -> bool:
    print("\n" + "=" * 60)
    print("🔍 DIAGNÓSTICO DE ARMAZENAMENTO")
    print("=" * 60)

    caminho_str = str(caminho_alvo)

    if os.name == "nt":
        drive = caminho_alvo.drive
        if not drive:
            return False
        raiz_drive = f"{drive}\\"
        montado = Path(raiz_drive).exists()
        if not montado:
            return False
    else:
        prefixos_externos = ("/run/media/", "/media/", "/mnt/")
        eh_externo = caminho_str.startswith(prefixos_externos)
        ponto_montagem = None
        for parent in [caminho_alvo] + list(caminho_alvo.parents):
            if parent.exists() and os.path.ismount(parent):
                ponto_montagem = parent
                break
        if eh_externo and not (ponto_montagem and str(ponto_montagem).startswith(prefixos_externos)):
            print("🔌 Status do disco: ❌ DESMONTADO OU DESCONECTADO")
            return False

    if not caminho_alvo.exists():
        print(f"📁 Pasta de música: ❌ A pasta '{caminho_alvo}' não existe.")
        return False

    print(f"📁 Pasta de música: ✅ Encontrada ({caminho_alvo})")
    print("=" * 60 + "\n")
    return True


def sanitizar_nome_sistema(nome: str) -> str:
    nome_limpo = re.sub(r'[<>:"/\\|?*]', '-', nome)
    return nome_limpo.strip('. ')


def normalizar_para_comparacao(texto: str, remover_numeros_faixa: bool = False) -> str:
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join(c for c in texto if not unicodedata.combining(c)).lower()

    if remover_numeros_faixa:
        texto = re.sub(r'^\s*(\d+[\-\.\s_]+)+', '', texto)

    texto = re.sub(r'[\(\[\-\s]*(19\d{2}|20\d{2})[\)\]\-\s]*', ' ', texto)

    termos_ignorar = [
        r'deluxe\s*edition', r'deluxe\s*version', r'deluxe',
        r'remastered', r'remaster', r'expanded\s*edition',
        r'special\s*edition', r'anniversary\s*edition', r'bonus\s*track.*'
    ]
    for termo in termos_ignorar:
        texto = re.sub(rf'[\(\[\-\s]*{termo}[\)\]\-\s]*', ' ', texto)

    texto = re.sub(r'[^a-z0-9\s]', ' ', texto)
    return re.sub(r'\s+', ' ', texto).strip()


def encontrar_pasta_album_local(
    titulo_album_oficial: str,
    pastas_locais: list[Path],
    limiar_similaridade: float = 0.82
) -> Path | None:
    alvo_norm = normalizar_para_comparacao(titulo_album_oficial)
    if not alvo_norm:
        return None

    for pasta in pastas_locais:
        pasta_norm = normalizar_para_comparacao(pasta.name)
        if not pasta_norm:
            continue

        if alvo_norm == pasta_norm:
            return pasta

        if len(alvo_norm) >= 4 and (alvo_norm in pasta_norm or pasta_norm in alvo_norm):
            return pasta

        if SequenceMatcher(None, alvo_norm, pasta_norm).ratio() >= limiar_similaridade:
            return pasta

    return None


def faixa_ja_existe_na_pasta(titulo_faixa: str, idx: int, arquivos_audio_locais: list[Path]) -> bool:
    alvo_norm = normalizar_para_comparacao(titulo_faixa, remover_numeros_faixa=True)

    for arq in arquivos_audio_locais:
        nome_sem_ext = arq.stem
        arq_norm = normalizar_para_comparacao(nome_sem_ext, remover_numeros_faixa=True)

        if not arq_norm:
            continue

        if alvo_norm and alvo_norm == arq_norm:
            return True

        if len(alvo_norm) >= 4 and (alvo_norm in arq_norm or arq_norm in alvo_norm):
            return True

        if alvo_norm and SequenceMatcher(None, alvo_norm, arq_norm).ratio() >= 0.82:
            return True

        if re.match(rf'^0?{idx}[\s\.\-_]', nome_sem_ext) and SequenceMatcher(None, alvo_norm, arq_norm).ratio() >= 0.55:
            return True

    return False


def melhorar_url_thumbnail(url: str) -> str:
    if not url:
        return ""
    return re.sub(r'=w\d+-h\d+.*$', '=w1000-h1000-l90-rj', url)


def baixar_imagem(thumbnails: list[dict], destino: Path, descricao: str):
    if destino.exists() or not thumbnails:
        return
    melhor_thumb = thumbnails[-1].get("url", "")
    url_alta_res = melhorar_url_thumbnail(melhor_thumb)
    if not url_alta_res:
        return

    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url_alta_res, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp, open(destino, 'wb') as out_file:
            out_file.write(resp.read())
        print(f"  [🖼️] {descricao} salva em: '{destino.name}'")
    except Exception:
        pass


def obter_dados_e_albuns_artista(ytmusic: YTMusic, nome_artista: str, pasta_artista: Path) -> list[dict]:
    resultados = ytmusic.search(nome_artista, filter="artists", limit=3)
    if not resultados:
        print(f"  [!] Artista '{nome_artista}' não encontrado no YouTube Music.")
        return []

    artista_info = resultados[0]
    browse_id = artista_info.get("browseId")
    nome_oficial = artista_info.get("artist", nome_artista)
    print(f"  -> Artista identificado: {nome_oficial} (ID: {browse_id})")

    dados_artista = ytmusic.get_artist(browse_id)
    thumbs_artista = dados_artista.get("thumbnails") or artista_info.get("thumbnails") or []
    caminho_img_artista = pasta_artista / "artist.jpg"
    if not caminho_img_artista.exists() and not (pasta_artista / "folder.jpg").exists():
        baixar_imagem(thumbs_artista, caminho_img_artista, f"Foto de {nome_oficial}")

    secao_albuns = dados_artista.get("albums", {})
    if not secao_albuns:
        return []

    if secao_albuns.get("browseId") and secao_albuns.get("params"):
        return ytmusic.get_artist_albums(secao_albuns["browseId"], secao_albuns["params"])
    return secao_albuns.get("results", [])


def montar_opcoes_ytdlp(
    caminho_saida: Path,
    arquivo_historico: Path,
    nome_artista: str,
    titulo_album: str,
    idx: int,
    total_faixas: int,
    ano_album: str,
    navegador_escolhido: str,
    usar_cookies: bool = True
) -> dict:
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(caminho_saida),
        'download_archive': str(arquivo_historico),
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'writethumbnail': True,
        'sleep_interval': 2,
        'max_sleep_interval': 5,
        # Força o cliente web_music otimizado com curl-cffi para evitar bloqueio anti-bot
        'extractor_args': {'youtube': {'player_client': ['web_music', 'web']}},
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            },
            {
                'key': 'EmbedThumbnail',
            },
            {
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            },
        ],
        'postprocessor_args': [
            '-metadata', f'artist={nome_artista}',
            '-metadata', f'album={titulo_album}',
            '-metadata', f'track={idx}/{total_faixas}',
            '-metadata', f'date={ano_album}',
        ],
    }

    if usar_cookies:
        if ARQUIVO_COOKIES.exists():
            ydl_opts['cookiefile'] = str(ARQUIVO_COOKIES)
        else:
            tupla_nav = obter_config_cookies_navegador(navegador_escolhido)
            if tupla_nav:
                ydl_opts['cookiesfrombrowser'] = tupla_nav

    return ydl_opts


def baixar_album(
    ytmusic: YTMusic,
    album_resumo: dict,
    pasta_album: Path,
    nome_artista: str,
    navegador_escolhido: str
):
    browse_id = album_resumo.get("browseId")
    titulo_album = album_resumo.get("title", "Álbum Desconhecido")
    ano_album = album_resumo.get("year", "")

    if not browse_id:
        return

    try:
        detalhes_album = ytmusic.get_album(browse_id)
    except Exception as e:
        print(f"    [Erro] Não foi possível ler as faixas de '{titulo_album}': {e}")
        return

    faixas = detalhes_album.get("tracks", [])
    if not faixas:
        return

    pasta_album.mkdir(parents=True, exist_ok=True)

    thumbs_album = detalhes_album.get("thumbnails") or album_resumo.get("thumbnails") or []
    caminho_capa = pasta_album / "cover.jpg"
    if not caminho_capa.exists() and not (pasta_album / "folder.jpg").exists():
        baixar_imagem(thumbs_album, caminho_capa, f"Capa do álbum '{titulo_album}'")

    arquivos_audio_locais = [
        f for f in pasta_album.iterdir()
        if f.is_file() and f.suffix.lower() in EXTENSOES_AUDIO
    ]

    faixas_faltantes = []
    for idx, faixa in enumerate(faixas, start=1):
        titulo_faixa = faixa.get("title", f"Faixa {idx}")
        if not faixa_ja_existe_na_pasta(titulo_faixa, idx, arquivos_audio_locais):
            faixas_faltantes.append((idx, faixa))

    if not faixas_faltantes:
        print(f"    [✓] Todas as {len(faixas)} faixas de '{titulo_album}' já estão na pasta! Pulando...")
        return

    print(f"    [+] Baixando {len(faixas_faltantes)} faixa(s) faltante(s) de '{titulo_album}' -> {pasta_album.name}")
    arquivo_historico = pasta_album / ".downloaded.txt"

    for idx, faixa in faixas_faltantes:
        video_id = faixa.get("videoId")
        titulo_faixa = faixa.get("title", f"Faixa {idx}")
        if not video_id:
            continue

        numero_faixa = f"{idx:02d}"
        nome_arquivo_limpo = sanitizar_nome_sistema(f"{numero_faixa} - {titulo_faixa}")
        arquivo_mp3_final = pasta_album / f"{nome_arquivo_limpo}.mp3"
        caminho_saida = pasta_album / f"{nome_arquivo_limpo}.%(ext)s"

        url = "https:" + f"//music.youtube.com/watch?v={video_id}"
        print(f"      [↓] Baixando: {nome_arquivo_limpo}...")

        # Tentativa 1: Download direto usando o ID oficial do YouTube Music com cookies e curl-cffi
        ydl_opts = montar_opcoes_ytdlp(
            caminho_saida, arquivo_historico, nome_artista, titulo_album,
            idx, len(faixas), ano_album, navegador_escolhido, usar_cookies=True
        )
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception:
            pass

        # Tentativa 2 (Fallback inteligente): Se falhou, busca outra versão oficial da música via ytmusicapi (evitando busca de texto aberta)
        if not arquivo_mp3_final.exists():
            print(f"      [!] Buscando versão alternativa via catálogo oficial para '{titulo_faixa}'...")
            try:
                resultados_busca = ytmusic.search(f"{nome_artista} {titulo_faixa}", filter="songs", limit=3)
                for res in resultados_busca:
                    vid_alt = res.get("videoId")
                    if vid_alt and vid_alt != video_id:
                        url_alt = f"https://music.youtube.com/watch?v={vid_alt}"
                        ydl_opts_alt = montar_opcoes_ytdlp(
                            caminho_saida, arquivo_historico, nome_artista, titulo_album,
                            idx, len(faixas), ano_album, navegador_escolhido, usar_cookies=True
                        )
                        with yt_dlp.YoutubeDL(ydl_opts_alt) as ydl:
                            ydl.download([url_alt])
                        if arquivo_mp3_final.exists():
                            break
            except Exception:
                pass


def varrer_biblioteca(caminho_raiz: Path, navegador_escolhido: str):
    if not verificar_armazenamento(caminho_raiz):
        return

    ytmusic = YTMusic()

    pastas_artistas = sorted([
        p for p in caminho_raiz.iterdir()
        if p.is_dir() and not p.name.startswith('.') and p.name.lower() != 'lost+found'
    ])

    if not pastas_artistas:
        print(f"[!] Nenhuma pasta de artista encontrada dentro de '{caminho_raiz}'.")
        return

    print(f"=== Iniciando varredura ({len(pastas_artistas)} artistas encontrados) ===\n")

    for pasta_artista in pastas_artistas:
        nome_artista = pasta_artista.name
        print(f"► Banda/Artista: [{nome_artista}]")

        albuns_oficiais = obter_dados_e_albuns_artista(ytmusic, nome_artista, pasta_artista)
        if not albuns_oficiais:
            print()
            continue

        pastas_albuns_locais = [
            p for p in pasta_artista.iterdir()
            if p.is_dir() and not p.name.startswith('.')
        ]

        for album in albuns_oficiais:
            titulo_oficial = album.get("title", "").strip()
            ano = album.get("year", "")
            if not titulo_oficial:
                continue

            pasta_existente = encontrar_pasta_album_local(titulo_oficial, pastas_albuns_locais)

            if pasta_existente:
                print(f"  [✓] Álbum '{titulo_oficial}' identificado na pasta: '{pasta_existente.name}'")
                baixar_album(ytmusic, album, pasta_existente, nome_artista, navegador_escolhido)
            else:
                nome_nova_pasta = sanitizar_nome_sistema(
                    f"{ano} - {titulo_oficial}" if ano else titulo_oficial
                )
                caminho_novo_album = pasta_artista / nome_nova_pasta
                print(f"  [+] Álbum novo: '{titulo_oficial}'. Criando pasta '{nome_nova_pasta}'...")
                baixar_album(ytmusic, album, caminho_novo_album, nome_artista, navegador_escolhido)

        print("-" * 60)


if __name__ == "__main__":
    print("=== Sincronizador de Discografias v3.1 (Anti-Bot & Direct ID) ===")

    config = carregar_config_local()
    caminho_salvo = config.get("caminho_musicas", "")
    navegador_salvo = config.get("navegador_cookies", "")

    navegador_escolhido = escolher_navegador(navegador_salvo)

    print("\n📂 PASTA DE MÚSICAS")
    if caminho_salvo:
        print(f"   Caminho salvo anteriormente: {caminho_salvo}")
        entrada = input("   Pressione [ENTER] para usar o caminho salvo ou digite outro: ").strip()
        caminho_final = entrada if entrada else caminho_salvo
    else:
        caminho_final = input("\n   Caminho da pasta de músicas: ").strip()

    if not caminho_final:
        print("[❌] Nenhum caminho informado. Encerrando.")
    else:
        diretorio_musicas = Path(caminho_final.strip('\'"')).expanduser().resolve()
        salvar_config_local(str(diretorio_musicas), navegador_escolhido)
        varrer_biblioteca(diretorio_musicas, navegador_escolhido)
