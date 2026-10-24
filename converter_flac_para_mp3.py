import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PASTA_SCRIPT = Path(__file__).parent
ARQUIVO_CONFIG_LOCAL = PASTA_SCRIPT / ".config_local.json"


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


def formatar_tamanho(bytes_qtd: int) -> str:
    for unidade in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_qtd < 1024:
            return f"{bytes_qtd:.2f} {unidade}"
        bytes_qtd /= 1024
    return f"{bytes_qtd:.2f} PB"


def converter_flac(caminho_flac: Path) -> tuple[bool, int]:
    """
    Converte um FLAC para MP3 320k mantendo tags e metadados.
    Retorna (sucesso, bytes_economizados).
    """
    caminho_mp3 = caminho_flac.with_suffix(".mp3")
    tamanho_flac = caminho_flac.stat().st_size

    cmd = [
        "ffmpeg",
        "-y",
        "-v", "error",
        "-i", str(caminho_flac),
        "-codec:a", "libmp3lame",
        "-b:a", "320k",
        "-map_metadata", "0",
        "-id3v2_version", "3",
        str(caminho_mp3)
    ]

    resultado = subprocess.run(cmd)

    # Verificação estrita de segurança antes de apagar o original
    if resultado.returncode == 0 and caminho_mp3.exists() and caminho_mp3.stat().st_size > 1024:
        tamanho_mp3 = caminho_mp3.stat().st_size
        caminho_flac.unlink()
        bytes_economizados = max(0, tamanho_flac - tamanho_mp3)
        return True, bytes_economizados

    # Se falhou, remove o MP3 defeituoso se tiver sido criado
    if caminho_mp3.exists() and caminho_mp3.stat().st_size <= 1024:
        caminho_mp3.unlink()
    return False, 0


def executar_conversao_em_massa():
    if not shutil.which("ffmpeg"):
        print("[❌] Erro: FFmpeg não encontrado no PATH do sistema.")
        sys.exit(1)

    raiz = carregar_caminho_musicas()
    print(f"\n📁 Pasta selecionada: {raiz}")
    print("🔍 Mapeando arquivos .flac na biblioteca...")

    arquivos_flac = sorted([f for f in raiz.rglob("*") if f.is_file() and f.suffix.lower() == ".flac"])
    total = len(arquivos_flac)

    if total == 0:
        print("✨ Nenhum arquivo .flac encontrado. Sua biblioteca já está 100% compacta!")
        return

    tamanho_total_flac = sum(f.stat().st_size for f in arquivos_flac)
    print(f"\n📊 Total encontrado: {total} arquivos FLAC ({formatar_tamanho(tamanho_total_flac)})")
    print("⚡ Todos serão convertidos para MP3 320 kbps (CBR) com tags preservadas.")
    print("⚠️  Os arquivos .flac originais serão removidos apenas após a conversão bem-sucedida.")

    confirma = input("\nDeseja iniciar a conversão agora? [s/N]: ").strip().lower()
    if confirma not in ["s", "sim", "y", "yes"]:
        print("Operação cancelada.")
        return

    print("\n" + "=" * 60)
    print("🚀 INICIANDO CONVERSÃO")
    print("=" * 60)

    sucessos = 0
    falhas = 0
    total_economizado = 0

    try:
        for idx, flac in enumerate(arquivos_flac, start=1):
            nome_amigavel = f"{flac.parent.name}/{flac.name}"
            print(f"[{idx}/{total}] 🔄 Convertendo: {nome_amigavel}...", end="\r", flush=True)

            ok, economizado = converter_flac(flac)
            if ok:
                sucessos += 1
                total_economizado += economizado
                print(f"[{idx}/{total}] ✅ Convertido: {flac.stem}.mp3 (-{formatar_tamanho(economizado)})")
            else:
                falhas += 1
                print(f"[{idx}/{total}] ❌ Falha: {flac.name} (mantido em .flac)")

    except KeyboardInterrupt:
        print("\n\n⚠️ Processo interrompido pelo usuário. O que já foi convertido está salvo e seguro.")

    print("\n" + "=" * 60)
    print("🎉 RESUMO DA OPERAÇÃO")
    print(f"✅ Convertidos com sucesso: {sucessos}")
    if falhas > 0:
        print(f"❌ Falhas: {falhas}")
    print(f"💾 Espaço em disco recuperado: {formatar_tamanho(total_economizado)}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    executar_conversao_em_massa()
