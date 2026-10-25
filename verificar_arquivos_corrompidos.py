import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PASTA_SCRIPT = Path(__file__).parent
ARQUIVO_CONFIG_LOCAL = PASTA_SCRIPT / ".config_local.json"
EXTENSOES_AUDIO = {".mp3", ".flac", ".m4a", ".ogg", ".opus", ".wav", ".wma"}


def carregar_caminho_musicas() -> Path:
    if ARQUIVO_CONFIG_LOCAL.exists():
        try:
            with open(ARQUIVO_CONFIG_LOCAL, "r", encoding="utf-8") as f:
                dados = json.load(f)
                caminho = dados.get("caminho_musicas")
                if caminho and Path(caminho).exists():
                    return Path(caminho)
        except Exception:
            pass

    entrada = input("📂 Digite o caminho da sua pasta de músicas: ").strip('\'"')
    caminho = Path(entrada).expanduser().resolve()
    if not caminho.exists():
        print("[❌] Caminho inválido ou inacessível.")
        sys.exit(1)
    return caminho


def testar_integridade_audio(caminho_arquivo: Path) -> tuple[bool, str]:
    """
    Testa se o arquivo pode ser lido e decodificado pelo FFmpeg/FFprobe.
    Retorna (valido, motivo_se_invalido).
    """
    tamanho = caminho_arquivo.stat().st_size
    if tamanho == 0:
        return False, "Arquivo zerado (0 bytes)"
    if tamanho < 1024:
        return False, f"Arquivo truncado (< 1 KB: {tamanho} bytes)"

    # Testa contêiner e metadados com ffprobe
    cmd_probe = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_type",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(caminho_arquivo)
    ]
    res_probe = subprocess.run(cmd_probe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res_probe.returncode != 0:
        erro = res_probe.stderr.strip().splitlines()
        detalhe = erro[-1] if erro else "Cabeçalho corrompido"
        return False, f"FFprobe: {detalhe}"

    # Validação rápida de integridade da trilha de áudio
    cmd_ffmpeg = [
        "ffmpeg",
        "-v", "error",
        "-i", str(caminho_arquivo),
        "-t", "3",
        "-f", "null",
        "-"
    ]
    res_ffmpeg = subprocess.run(cmd_ffmpeg, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res_ffmpeg.returncode != 0:
        erro = res_ffmpeg.stderr.strip().splitlines()
        detalhe = erro[-1] if erro else "Erro na decodificação de stream"
        return False, f"FFmpeg: {detalhe}"

    return True, "OK"


def escanear_biblioteca():
    ferramenta = "ffprobe" if shutil.which("ffprobe") else "ffmpeg"
    if not shutil.which(ferramenta):
        print(f"[❌] Erro: '{ferramenta}' não encontrado no PATH do sistema.")
        sys.exit(1)

    raiz = carregar_caminho_musicas()
    print("\n" + "=" * 60)
    print("🔍 DIAGNÓSTICO DE INTEGRIDADE DA BIBLIOTECA")
    print(f"📁 Pasta: {raiz}")
    print("=" * 60)

    todos_arquivos = sorted([
        f for f in raiz.rglob("*")
        if f.is_file() and f.suffix.lower() in EXTENSOES_AUDIO
    ])
    total = len(todos_arquivos)

    print(f"📊 Arquivos de áudio identificados: {total}\n")

    arquivos_defeituosos: list[tuple[Path, str]] = []

    for idx, arq in enumerate(todos_arquivos, start=1):
        relativo = arq.relative_to(raiz)
        print(f"[{idx}/{total}] Checando: {arq.name[:45]}...", end="\r", flush=True)

        valido, motivo = testar_integridade_audio(arq)
        if not valido:
            arquivos_defeituosos.append((arq, motivo))
            print(f"\n[⚠️ DEFEITUOSO] {relativo}")
            print(f"   ↳ Motivo: {motivo}")

    print("\n" + "=" * 60)
    print("📋 RESUMO DA VERIFICAÇÃO")
    print("=" * 60)
    print(f"Total analisado: {total}")
    print(f"Arquivos válidos: {total - len(arquivos_defeituosos)}")
    print(f"Arquivos corrompidos/zerados: {len(arquivos_defeituosos)}")

    if not arquivos_defeituosos:
        print("✨ Todos os arquivos de áudio estão intactos e reproduzíveis!")
        return

    print("\nLista de itens com problemas:")
    for arq, motivo in arquivos_defeituosos:
        print(f" - {arq.relative_to(raiz)} ({motivo})")

    resposta = input("\nDeseja excluir permanentemente esses arquivos corrompidos? [s/N]: ").strip().lower()
    if resposta in ["s", "sim", "y", "yes"]:
        apagados = 0
        for arq, _ in arquivos_defeituosos:
            try:
                arq.unlink()
                apagados += 1
            except Exception as e:
                print(f"[!] Falha ao apagar {arq.name}: {e}")
        print(f"\n🗑️ {apagados} arquivo(s) corrompido(s) removido(s) com sucesso.")
        print("💡 Ao rodar 'syncmusic', as faixas faltantes serão baixadas novamente do zero.")
    else:
        print("\nNenhum arquivo foi modificado ou excluído.")


if __name__ == "__main__":
    try:
        escanear_biblioteca()
    except KeyboardInterrupt:
        print("\n\n⚠️ Varredura cancelada pelo usuário.")
