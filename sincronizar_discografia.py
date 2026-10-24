import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from ytmusicapi import YTMusic

PASTA_SCRIPT = Path(__file__).parent
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


def limpar_arquivos_full_album(caminho_raiz: Path):
    print("🧹 [FASE 1] Varrendo biblioteca em busca de arquivos indesejados 'full album'...")
    removidos = 0
    
    for caminho_arquivo in caminho_raiz.rglob("*"):
        if caminho_arquivo.is_file() and caminho_arquivo.suffix.lower() in EXTENSOES_AUDIO:
            nome_arq_lower = caminho_arquivo.name.lower()
            
            # Critérios para identificar um full album indesejado pelo nome
            padroes_proibidos = ["full album", "full_album", "album completo", "full-album", "fullset", "full set"]
            if any(p in nome_arq_lower for p in padroes_proibidos):
                try:
                    caminho_arquivo.unlink()
                    print(f"  [🗑️ Apagado] {caminho_arquivo.relative_to(caminho_raiz)}")
                    removidos += 1
                    continue
                except Exception as e:
                    print(f"  [!] Erro ao apagar {caminho_arquivo.name}: {e}")

            # Opcional: Se o arquivo for anormalmente grande para uma única música (ex: > 45MB e duração implícita por tamanho),
            # mas o filtro de nome já pega 99% dos casos de full albums baixados por engano.
            
    print(f"🧹 Faxina concluída! Total de arquivos 'full album' removidos: {removidos}\n")


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
        "--match-filter", "duration < 900 & !is_live",  # Rejeita vídeos com mais de 15 minutos ou lives
        "--extractor-args", "youtube:player_client=android",
        "--output", str(caminho_saida),
        "--download-archive", str(arquivo_historico),
    ]

    cmd.extend([
        "--metadata-from-title", "%(artist)s - %(title)s",
        "--add-metadata",
    ])

    cmd.append(termo_busca)

    resultado = subprocess.run(cmd)
    return resultado.returncode == 0


def varrer_biblioteca(caminho_raiz: Path):
    if not verificar_armazenamento(caminho_raiz):
        return

    # Executa a limpeza antes de tudo
    limpar_arquivos_full_album(caminho_raiz)

    try:
        ytmusic = YTMusic()
    except Exception:
        ytmusic = None

    pastas_artistas = sorted([p for p in caminho_raiz.iterdir() if p.is_dir() and not p.name.startswith('.') and p.name.lower() != 'lost+found'])

    total_artistas = len(pastas_artistas)
    total_albuns_geral = sum(len([p for p in art.iterdir() if p.is_dir() and not p.name.startswith('.')]) for art in pastas_artistas)
    
    print(f"=== [FASE 2] Sincronizador v3.4 (Clean & Track-by-Track Engine) ===")
    print(f"📊 Total encontrado: {total_artistas} artistas | {total_albuns_geral} álbuns/pastas.\n")

    album_contador = 0

    for idx_art, pasta_artista in enumerate(pastas_artistas, start=1):
        nome_artista = pasta_artista.name
        print(f"\n[{idx_art}/{total_artistas}] 🎸 Banda/Artista: [{nome_artista}]")

        pastas_albuns = [p for p in pasta_artista.iterdir() if p.is_dir() and not p.name.startswith('.')]
        if not pastas_albuns:
            print("  [!] Nenhuma pasta de álbum encontrada.")
            print("-" * 60)
            continue

        for pasta_album in pastas_albuns:
            album_contador += 1
            titulo_album = pasta_album.name
            
            arquivos_locais = [f for f in pasta_album.iterdir() if f.is_file() and f.suffix.lower() in EXTENSOES_AUDIO]
            
            if len(arquivos_locais) >= 3:
                continue

            print(f"  [{album_contador}/{total_albuns_geral}] 📥 Sincronizando faixas em: {titulo_album} ({len(arquivos_locais)} arquivos locais)")
            arquivo_historico = pasta_album / ".downloaded.txt"

            faixas_baixadas = False
            if ytmusic:
                try:
                    res = ytmusic.search(f"{nome_artista} {titulo_album}", filter="albums", limit=1)
                    if res:
                        browse_id = res[0].get("browseId")
                        detalhes = ytmusic.get_album(browse_id)
                        tracks = detalhes.get("tracks", [])
                        if tracks:
                            print(f"    [i] Tracklist oficial encontrada ({len(tracks)} faixas). Baixando separadamente...")
                            for i, t in enumerate(tracks, start=1):
                                t_nome = t.get("title", "")
                                nome_arq = sanitizar_nome_sistema(f"{i:02d} - {t_nome}")
                                caminho_saida = pasta_album / f"{nome_arq}.%(ext)s"
                                termo_faixa = f"ytsearch1:{nome_artista} {titulo_album} {t_nome} audio -full -album -live"
                                baixar_faixa_cli(termo_faixa, caminho_saida, arquivo_historico, nome_artista, titulo_album)
                            faixas_baixadas = True
                except Exception:
                    pass

            if not faixas_baixadas:
                print(f"    [+] Buscando faixas avulsas para '{titulo_album}'...")
                termo_busca = f"ytsearch12:{nome_artista} {titulo_album} song audio -full -album -live"
                caminho_saida = pasta_album / "%(autonumber)s - %(title)s.%(ext)s"
                baixar_faixa_cli(termo_busca, caminho_saida, arquivo_historico, nome_artista, titulo_album)

        print("-" * 60)

    print("\n✨ Faxina, Varredura e Sincronização concluídas com sucesso!")


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
