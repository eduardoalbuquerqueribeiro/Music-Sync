import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.request
from pathlib import Path
from ytmusicapi import YTMusic

PASTA_SCRIPT = Path(__file__).parent
ARQUIVO_CONFIG_LOCAL = PASTA_SCRIPT / ".config_local.json"
EXTENSOES_AUDIO = {".mp3", ".flac", ".m4a", ".ogg", ".opus", ".wav", ".wma"}

# Expressão regular para identificar e purgar arquivos de karaokê, covers amadores e lixo sonoro
REGEX_LIXO_SONORO = re.compile(
    r'(?i)(full[\s_-]?album|album[\s_-]?completo|fullset|full[\s_-]?set|karaoke|in the style of|'
    r'tribute|backing track|vocal demo|lead vocal|drum cover|guitar cover|bass cover|'
    r'piano cover|acoustic cover|\bcover\b|slowed|reverb|nightcore|reaction|tutorial|how to play)'
)


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
    for cmd in ["yt-dlp", "ffmpeg", "curl"]:
        if not shutil.which(cmd):
            print(f"[❌] Erro crítico: A ferramenta '{cmd}' não foi encontrada no PATH do sistema.")
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


def limpar_arquivos_indesejados(caminho_raiz: Path):
    print("🧹 [FASE 1] Faxina geral: Procurando full albums, karaokês, covers e tributos...")
    removidos = 0
    for caminho_arquivo in caminho_raiz.rglob("*"):
        if caminho_arquivo.is_file() and (caminho_arquivo.suffix.lower() in EXTENSOES_AUDIO or caminho_arquivo.suffix.lower() == ".lrc"):
            nome_arq = caminho_arquivo.name
            
            if REGEX_LIXO_SONORO.search(nome_arq):
                try:
                    caminho_arquivo.unlink()
                    # Apaga também o .lrc se existir
                    lrc_par = caminho_arquivo.with_suffix(".lrc")
                    if lrc_par.exists():
                        lrc_par.unlink()
                    print(f"  [🗑️ Apagado lixo] {caminho_arquivo.relative_to(caminho_raiz)}")
                    removidos += 1
                except Exception:
                    pass
    print(f"🧹 Faxina concluída! Total de arquivos indesejados removidos: {removidos}\n")


def baixar_capa_album(thumbnails: list[dict], pasta_album: Path):
    caminho_capa = pasta_album / "cover.jpg"
    caminho_folder = pasta_album / "folder.jpg"
    if caminho_capa.exists() or caminho_folder.exists() or not thumbnails:
        return

    url = thumbnails[-1].get("url", "")
    if not url:
        return

    url = re.sub(r'=w\d+-h\d+.*$', '=w1200-h1200-l90-rj', url)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp, open(caminho_capa, 'wb') as f:
            f.write(resp.read())
        print(f"    [🖼️ Capa salva] cover.jpg")
    except Exception:
        pass


def baixar_letra_lrc(caminho_musica: Path, artista: str, titulo: str, album: str = ""):
    caminho_lrc = caminho_musica.with_suffix(".lrc")
    if caminho_lrc.exists():
        return

    titulo_limpo = re.sub(r'^\d+[\s\.\-_]+', '', titulo).strip()
    titulo_limpo = re.sub(r'[\(\[\-].*?(feat|ft|remaster|version|edition).*?[\)\]]', '', titulo_limpo, flags=re.IGNORECASE).strip()

    cmd = [
        "curl", "-s", "--max-time", "6",
        "-H", "User-Agent: MusicSync/3.8",
        "-G", "https://lrclib.net/api/get",
        "--data-urlencode", f"artist_name={artista}",
        "--data-urlencode", f"track_name={titulo_limpo}",
    ]
    if album:
        cmd.extend(["--data-urlencode", f"album_name={album}"])

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    conteudo_letra = ""

    if res.returncode == 0 and res.stdout.strip():
        try:
            dados = json.loads(res.stdout)
            conteudo_letra = dados.get("syncedLyrics") or dados.get("plainLyrics") or ""
        except Exception:
            pass

    if not conteudo_letra:
        cmd_search = [
            "curl", "-s", "--max-time", "6",
            "-H", "User-Agent: MusicSync/3.8",
            "-G", "https://lrclib.net/api/search",
            "--data-urlencode", f"q={artista} {titulo_limpo}",
        ]
        res_search = subprocess.run(cmd_search, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        if res_search.returncode == 0 and res_search.stdout.strip():
            try:
                resultados = json.loads(res_search.stdout)
                if isinstance(resultados, list) and resultados:
                    conteudo_letra = resultados[0].get("syncedLyrics") or resultados[0].get("plainLyrics") or ""
            except Exception:
                pass

    if conteudo_letra:
        try:
            with open(caminho_lrc, "w", encoding="utf-8") as f_lrc:
                f_lrc.write(conteudo_letra.strip() + "\n")
            print(f"      [📝 Letra salva] {caminho_lrc.name}")
        except Exception:
            pass


def baixar_faixa_cli(termo_busca: str, caminho_saida: Path, arquivo_historico: Path, nome_artista: str, titulo_album: str) -> bool:
    # Filtro anti-lixo severo: bloqueia karaokê, covers, tributos, tutorias e lives
    filtro_match = (
        "duration < 900 & !is_live & "
        "title !~* '(?i)(karaoke|in the style of|tribute|cover|instrumental|backing track|lesson|tutorial|reaction|parody|slowed|reverb|nightcore)'"
    )

    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "320K",
        "--embed-thumbnail",
        "--add-metadata",
        "--force-ipv4",
        "--no-playlist",
        "--match-filter", filtro_match,
        "--extractor-args", "youtube:player_client=android",
        "--output", str(caminho_saida),
        "--download-archive", str(arquivo_historico),
    ]

    # Injeção direta de artista e álbum nas tags sem quebrar caso o título venha sem hífen
    cmd.extend([
        "--parse-metadata", f":(?P<artist>{nome_artista})",
        "--parse-metadata", f":(?P<album>{titulo_album})",
    ])

    cmd.append(termo_busca)

    resultado = subprocess.run(cmd)
    return resultado.returncode == 0


def obter_todos_lancamentos_artista(ytmusic: YTMusic, browse_id: str) -> list[dict]:
    dados_artista = ytmusic.get_artist(browse_id)
    lancamentos = []

    for secao_key in ["albums", "singles"]:
        secao = dados_artista.get(secao_key, {})
        if secao.get("browseId") and secao.get("params"):
            try:
                itens = ytmusic.get_artist_albums(secao["browseId"], secao["params"])
                lancamentos.extend(itens)
            except Exception:
                lancamentos.extend(secao.get("results", []))
        else:
            lancamentos.extend(secao.get("results", []))

    return lancamentos


def sincronizar_letras_pasta(pasta_album: Path, nome_artista: str, titulo_album: str):
    for arq in pasta_album.iterdir():
        if arq.is_file() and arq.suffix.lower() in EXTENSOES_AUDIO:
            if not arq.with_suffix(".lrc").exists():
                nome_faixa = re.sub(r'^\d+[\s\.\-_]+', '', arq.stem)
                baixar_letra_lrc(arq, nome_artista, nome_faixa, titulo_album)


def varrer_biblioteca(caminho_raiz: Path):
    if not verificar_armazenamento(caminho_raiz):
        return

    # Executa a limpeza retroativa antes de qualquer download
    limpar_arquivos_indesejados(caminho_raiz)

    try:
        ytmusic = YTMusic()
    except Exception:
        ytmusic = None

    pastas_artistas = sorted([p for p in caminho_raiz.iterdir() if p.is_dir() and not p.name.startswith('.') and p.name.lower() != 'lost+found'])

    total_artistas = len(pastas_artistas)
    print(f"=== [FASE 2] Sincronizador v3.8 (Original Masters Only & Anti-Karaoke) ===")
    print(f"📊 Total de artistas encontrados: {total_artistas}\n")

    for idx_art, pasta_artista in enumerate(pastas_artistas, start=1):
        nome_artista = pasta_artista.name
        print(f"\n[{idx_art}/{total_artistas}] 🎸 Banda/Artista: [{nome_artista}]")

        pastas_albuns = [p for p in pasta_artista.iterdir() if p.is_dir() and not p.name.startswith('.')]

        if not pastas_albuns and ytmusic:
            print(f"  [+] Artista sem pastas. Buscando discografia (Álbuns, EPs e Singles) de '{nome_artista}'...")
            try:
                res = ytmusic.search(nome_artista, filter="artists", limit=1)
                if res:
                    browse_id = res[0].get("browseId")
                    lancamentos = obter_todos_lancamentos_artista(ytmusic, browse_id)

                    for item in lancamentos:
                        t_item = item.get("title", "Lançamento")
                        ano_item = item.get("year", "")
                        nome_pasta = f"[{ano_item}] {t_item}" if ano_item else t_item
                        nova_pasta = pasta_artista / sanitizar_nome_sistema(nome_pasta)
                        nova_pasta.mkdir(parents=True, exist_ok=True)
                        print(f"    [📁 Criada] {nova_pasta.name}")

                    pastas_albuns = [p for p in pasta_artista.iterdir() if p.is_dir() and not p.name.startswith('.')]
            except Exception as e:
                print(f"    [!] Erro ao buscar discografia automática: {e}")

        if not pastas_albuns:
            print("  [!] Nenhuma pasta de álbum/single disponível para processar.")
            print("-" * 60)
            continue

        for pasta_album in pastas_albuns:
            titulo_album = pasta_album.name
            arquivos_locais = [f for f in pasta_album.iterdir() if f.is_file() and f.suffix.lower() in EXTENSOES_AUDIO]
            
            if len(arquivos_locais) >= 3:
                sincronizar_letras_pasta(pasta_album, nome_artista, titulo_album)
                continue

            print(f"  📥 Sincronizando faixas em: {titulo_album} ({len(arquivos_locais)} arquivos locais)")
            arquivo_historico = pasta_album / ".downloaded.txt"

            faixas_baixadas = False
            if ytmusic:
                try:
                    res = ytmusic.search(f"{nome_artista} {titulo_album}", filter="albums", limit=1)
                    if res:
                        browse_id = res[0].get("browseId")
                        detalhes = ytmusic.get_album(browse_id)
                        
                        baixar_capa_album(detalhes.get("thumbnails", []), pasta_album)

                        tracks = detalhes.get("tracks", [])
                        if tracks:
                            print(f"    [i] Tracklist oficial encontrada ({len(tracks)} faixas). Baixando estúdio oficial...")
                            for i, t in enumerate(tracks, start=1):
                                t_nome = t.get("title", "")
                                nome_arq = sanitizar_nome_sistema(f"{i:02d} - {t_nome}")
                                caminho_saida = pasta_album / f"{nome_arq}.%(ext)s"
                                
                                # Busca direcionada para a master oficial do artista (Topic channel)
                                termo_faixa = f"ytsearch2:\"{nome_artista} - Topic\" \"{t_nome}\" audio -karaoke -cover -tribute"
                                
                                baixar_faixa_cli(termo_faixa, caminho_saida, arquivo_historico, nome_artista, titulo_album)
                                
                                for extensao in EXTENSOES_AUDIO:
                                    arq_gerado = pasta_album / f"{nome_arq}{extensao}"
                                    if arq_gerado.exists():
                                        baixar_letra_lrc(arq_gerado, nome_artista, t_nome, titulo_album)
                                        break
                                        
                            faixas_baixadas = True
                except Exception:
                    pass

            if not faixas_baixadas:
                print(f"    [+] Buscando masters originais para '{titulo_album}'...")
                # Força a busca por canais Topic oficiais ou áudios com selo da gravadora
                termo_busca = f"ytsearch10:\"{nome_artista}\" \"{titulo_album}\" \"Provided to YouTube\" -karaoke -cover -tribute"
                caminho_saida = pasta_album / "%(autonumber)s - %(title)s.%(ext)s"
                baixar_faixa_cli(termo_busca, caminho_saida, arquivo_historico, nome_artista, titulo_album)

            sincronizar_letras_pasta(pasta_album, nome_artista, titulo_album)

        print("-" * 60)

    print("\n✨ Varredura concluída! Somente masters originais de estúdio na biblioteca!")


if __name__ == "__main__":
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
