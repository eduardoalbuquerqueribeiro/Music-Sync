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
    try:
        with open(ARQUIVO_CONFIG_LOCAL, "w", encoding="utf-8") as f:
            json.dump({"caminho_musicas": caminho_musicas, "navegador_cookies": navegador}, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def escolher_navegador(navegador_salvo: str) -> str:
    print("\n🌐 AUTENTICAÇÃO DO YOUTUBE")
    print("   [1] Google Chrome / Brave / Chromium (Via cookies.txt se houver)")
    print("   [2] Sem navegador (Modo padrão)")
    escolha = input("\nEscolha [1-2] (Padrão: 1): ").strip()
    return "chrome" if escolha != "2" else "nenhum"


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


def normalizar_para_comparacao(texto: str, remover_numeros_faixa: bool = False) -> str:
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join(c for c in texto if not unicodedata.combining(c)).lower()
    if remover_numeros_faixa:
        texto = re.sub(r'^\s*(\d+[\-\.\s_]+)+', '', texto)
    texto = re.sub(r'[\(\[\-\s]*(19\d{2}|20\d{2})[\)\]\-\s]*', ' ', texto)
    for t in ['deluxe edition', 'deluxe version', 'deluxe', 'remastered', 'remaster', 'expanded edition']:
        texto = re.sub(rf'[\(\[\-\s]*{t}[\)\]\-\s]*', ' ', texto)
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9\s]', ' ', texto)).strip()


def encontrar_pasta_album_local(titulo_oficial: str, pastas_locais: list[Path]) -> Path | None:
    alvo_norm = normalizar_para_comparacao(titulo_oficial)
    if not alvo_norm:
        return None
    for pasta in pastas_locais:
        pasta_norm = normalizar_para_comparacao(pasta.name)
        if not pasta_norm:
            continue
        if alvo_norm == pasta_norm or (len(alvo_norm) >= 4 and (alvo_norm in pasta_norm or pasta_norm in alvo_norm)):
            return pasta
        if SequenceMatcher(None, alvo_norm, pasta_norm).ratio() >= 0.82:
            return pasta
    return None


def faixa_ja_existe_na_pasta(titulo_faixa: str, idx: int, arquivos_audio_locais: list[Path]) -> bool:
    alvo_norm = normalizar_para_comparacao(titulo_faixa, remover_numeros_faixa=True)
    for arq in arquivos_audio_locais:
        arq_norm = normalizar_para_comparacao(arq.stem, remover_numeros_faixa=True)
        if not arq_norm:
            continue
        if alvo_norm and (alvo_norm == arq_norm or (len(alvo_norm) >= 4 and (alvo_norm in arq_norm or arq_norm in alvo_norm))):
            return True
        if alvo_norm and SequenceMatcher(None, alvo_norm, arq_norm).ratio() >= 0.82:
            return True
        if re.match(rf'^0?{idx}[\s\.\-_]', arq.stem) and SequenceMatcher(None, alvo_norm, arq_norm).ratio() >= 0.55:
            return True
    return False


def melhorar_url_thumbnail(url: str) -> str:
    if not url:
        return ""
    return re.sub(r'=w\d+-h\d+.*$', '=w1000-h1000-l90-rj', url)


def baixar_imagem(thumbnails: list[dict], destino: Path, descricao: str):
    if destino.exists() or not thumbnails:
        return
    url = melhorar_url_thumbnail(thumbnails[-1].get("url", ""))
    if not url:
        return
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp, open(destino, 'wb') as out_file:
            out_file.write(resp.read())
        print(f"  [🖼️] {descricao} salva em: '{destino.name}'")
    except Exception:
        pass


def obter_dados_e_albuns_artista(ytmusic: YTMusic, nome_artista: str, pasta_artista: Path) -> list[dict]:
    resultados = ytmusic.search(nome_artista, filter="artists", limit=3)
    if not resultados:
        return []
    artista_info = resultados[0]
    browse_id = artista_info.get("browseId")
    nome_oficial = artista_info.get("artist", nome_artista)
    print(f"  -> Artista identificado: {nome_oficial}")

    dados_artista = ytmusic.get_artist(browse_id)
    thumbs = dados_artista.get("thumbnails") or artista_info.get("thumbnails") or []
    caminho_img = pasta_artista / "artist.jpg"
    if not caminho_img.exists() and not (pasta_artista / "folder.jpg").exists():
        baixar_imagem(thumbs, caminho_img, f"Foto de {nome_oficial}")

    secao_albuns = dados_artista.get("albums", {})
    if not secao_albuns:
        return []
    if secao_albuns.get("browseId") and secao_albuns.get("params"):
        return ytmusic.get_artist_albums(secao_albuns["browseId"], secao_albuns["params"])
    return secao_albuns.get("results", [])


def montar_opcoes_ytdlp(caminho_saida: Path, arquivo_historico: Path, nome_artista: str, titulo_album: str, idx: int, total_faixas: int, ano_album: str) -> dict:
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(caminho_saida),
        'download_archive': str(arquivo_historico),
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': True,
        'writethumbnail': True,
        'sleep_interval': 1,
        'max_sleep_interval': 3,
        'postprocessors': [
            {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '320'},
            {'key': 'EmbedThumbnail'},
            {'key': 'FFmpegMetadata', 'add_metadata': True},
        ],
        'postprocessor_args': [
            '-metadata', f'artist={nome_artista}',
            '-metadata', f'album={titulo_album}',
            '-metadata', f'track={idx}/{total_faixas}',
            '-metadata', f'date={ano_album}',
        ],
    }

    if ARQUIVO_COOKIES.exists():
        ydl_opts['cookiefile'] = str(ARQUIVO_COOKIES)

    return ydl_opts


def baixar_album(ytmusic: YTMusic, album_resumo: dict, pasta_album: Path, nome_artista: str):
    browse_id = album_resumo.get("browseId")
    titulo_album = album_resumo.get("title", "Álbum Desconhecido")
    ano_album = album_resumo.get("year", "")
    if not browse_id:
        return

    try:
        detalhes = ytmusic.get_album(browse_id)
    except Exception:
        return

    faixas = detalhes.get("tracks", [])
    if not faixas:
        return

    pasta_album.mkdir(parents=True, exist_ok=True)
    caminho_capa = pasta_album / "cover.jpg"
    if not caminho_capa.exists() and not (pasta_album / "folder.jpg").exists():
        baixar_imagem(detalhes.get("thumbnails") or [], caminho_capa, f"Capa de '{titulo_album}'")

    arquivos_locais = [f for f in pasta_album.iterdir() if f.is_file() and f.suffix.lower() in EXTENSOES_AUDIO]
    faixas_faltantes = [(i, f) for i, f in enumerate(faixas, start=1) if not faixa_ja_existe_na_pasta(f.get("title", ""), i, arquivos_locais)]

    if not faixas_faltantes:
        print(f"    [✓] '{titulo_album}' já completo. Pulando...")
        return

    print(f"    [+] Baixando {len(faixas_faltantes)} faixa(s) de '{titulo_album}' -> {pasta_album.name}")
    arquivo_historico = pasta_album / ".downloaded.txt"

    for idx, faixa in faixas_faltantes:
        titulo_faixa = faixa.get("title", f"Faixa {idx}")
        nome_arq = sanitizar_nome_sistema(f"{idx:02d} - {titulo_faixa}")
        caminho_saida = pasta_album / f"{nome_arq}.%(ext)s"
        
        # Estratégia infalível: Busca textual direta pelo ytsearch do yt-dlp
        termo_busca = f"ytsearch1:{nome_artista} - {titulo_faixa} official audio"
        print(f"      [↓] Baixando: {nome_arq}...")

        ydl_opts = montar_opcoes_ytdlp(caminho_saida, arquivo_historico, nome_artista, titulo_album, idx, len(faixas), ano_album)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([termo_busca])
        except Exception:
            pass


def varrer_biblioteca(caminho_raiz: Path):
    if not verificar_armazenamento(caminho_raiz):
        return

    ytmusic = YTMusic()
    pastas_artistas = sorted([p for p in caminho_raiz.iterdir() if p.is_dir() and not p.name.startswith('.') and p.name.lower() != 'lost+found'])

    print(f"=== Iniciando varredura ({len(pastas_artistas)} artistas encontrados) ===\n")

    for pasta_artista in pastas_artistas:
        nome_artista = pasta_artista.name
        print(f"► Banda/Artista: [{nome_artista}]")
        albuns = obter_dados_e_albuns_artista(ytmusic, nome_artista, pasta_artista)
        if not albuns:
            print()
            continue

        pastas_albuns = [p for p in pasta_artista.iterdir() if p.is_dir() and not p.name.startswith('.')]

        for album in albuns:
            titulo = album.get("title", "").strip()
            ano = album.get("year", "")
            if not titulo:
                continue

            pasta_existente = encontrar_pasta_album_local(titulo, pastas_albuns)
            if pasta_existente:
                print(f"  [✓] Álbum '{titulo}' na pasta: '{pasta_existente.name}'")
                baixar_album(ytmusic, album, pasta_existente, nome_artista)
            else:
                nova_pasta = sanitizar_nome_sistema(f"{ano} - {titulo}" if ano else titulo)
                print(f"  [+] Criando pasta '{nova_pasta}'...")
                baixar_album(ytmusic, album, pasta_artista / nova_pasta, nome_artista)
        print("-" * 60)


if __name__ == "__main__":
    print("=== Sincronizador v4.0 (Smart ytsearch Bypass) ===")
    config = carregar_config_local()
    nav = escolher_navegador(config.get("navegador_cookies", ""))
    caminho = config.get("caminho_musicas", "") or input("\nCaminho da pasta de músicas: ").strip()
    if caminho:
        diretorio = Path(caminho.strip('\'"')).expanduser().resolve()
        salvar_config_local(str(diretorio), nav)
        varrer_biblioteca(diretorio)
