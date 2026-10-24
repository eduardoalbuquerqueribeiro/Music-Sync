import json
import os
import re
import subprocess
import sys
import unicodedata
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path
from ytmusicapi import YTMusic

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
    """Garante que ferramentas essenciais do sistema estão instaladas."""
    for cmd in ["yt-dlp", "ffmpeg"]:
        if subprocess.run(["which", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
            print(f"[❌] Erro crítico: A ferramenta '{cmd}' não foi encontrada no sistema.")
            print(f"     Instale com: sudo dnf install {cmd} (ou equivalente)")
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
        with urllib.request.urlopen(req, timeout=10) as resp, open(destino, 'wb') as out_file:
            out_file.write(resp.read())
        print(f"  [🖼️] {descricao} salva em: '{destino.name}'")
    except Exception:
        pass


def obter_dados_e_albuns_artista(ytmusic: YTMusic, nome_artista: str, pasta_artista: Path) -> list[dict]:
    try:
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
    except Exception as e:
        print(f"  [!] Erro ao buscar artista '{nome_artista}': {e}")
        return []


def baixar_faixa_via_cli(alvo: str, caminho_saida: Path, arquivo_historico: Path, metadata: dict) -> bool:
    """Executa o yt-dlp diretamente via terminal (subprocesso CLI), eliminando conflitos de socket Python."""
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

    # Metadados injetados via CLI
    cmd.extend([
        "--parse-metadata", f":(?P<artist>{metadata['artist']})",
        "--parse-metadata", f":(?P<album>{metadata['album']})",
        "--parse-metadata", f":(?P<date>{metadata['year']})",
    ])

    cmd.append(alvo)

    resultado = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return resultado.returncode == 0


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

    metadata = {
        "artist": nome_artista,
        "album": titulo_album,
        "year": str(ano_album)
    }

    for idx, faixa in faixas_faltantes:
        titulo_faixa = faixa.get("title", f"Faixa {idx}")
        nome_arq = sanitizar_nome_sistema(f"{idx:02d} - {titulo_faixa}")
        caminho_saida = pasta_album / f"{nome_arq}.%(ext)s"

        video_id = faixa.get("videoId")
        print(f"      [↓] Baixando: {nome_arq}...")

        sucesso = False
        # Tentativa 1: Link direto do YouTube Music
        if video_id:
            alvo_direto = f"https://music.youtube.com/watch?v={video_id}"
            sucesso = baixar_faixa_via_cli(alvo_direto, caminho_saida, arquivo_historico, metadata)

        # Tentativa 2 (Fallback): Busca textual limpa no YouTube se a tentativa 1 falhou
        if not sucesso:
            alvo_busca = f"ytsearch1:{nome_artista} - {titulo_faixa} audio"
            sucesso = baixar_faixa_via_cli(alvo_busca, caminho_saida, arquivo_historico, metadata)

        if not sucesso:
            print(f"      [❌] Falha ao baixar a faixa '{titulo_faixa}'.")


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
    print("=== Sincronizador v1.7 (Punk Subprocess CLI Engine) ===")
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
