#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para executar a atualização do SGI pedida na tela Administração › Versões (roda na unidade sgi-spi-atualizar, fora da API).
"""Atualização do SGI SPI para a versão pedida em `dados/atualizacao/pedido.json` (regras em app/services/servico_versoes.py).

Etapas (gravadas em `dados/atualizacao/andamento.json`, que a tela acompanha):
  conferir → backup (backup geral "antes-da-atualizacao") → codigo (git checkout da versão) → dependencias (pip e npm) →
  migracoes (alembic) → build (Angular numa pasta ao lado, trocada de uma vez) → reiniciar (espera /api/saude com a versão nova).

Se falhar a partir de "codigo", **volta sozinho** (decisão do usuário): devolve o código anterior, as dependências e o build e, se as
migrações já tinham rodado, restaura o banco do backup da etapa 2. Os anexos não mudam numa atualização. A saída de cada comando vai
para `dados/atualizacao/ultima-atualizacao.log`.

Uso: a unidade roda `.venv/bin/python ../scripts/atualizar-versao.py` na pasta backend. `--ensaio` faz conferir, código e volta
(sem backup, dependências, migrações, build nem reinício), para testar num clone.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "backend"))

from app.core.banco import FabricaSessao  # noqa: E402
from app.core.configuracao import obter_configuracao  # noqa: E402
from app.services import servico_backup, servico_versoes  # noqa: E402
from app.services.servico_auditoria import auditar  # noqa: E402

BACKEND, FRONTEND = RAIZ / "backend", RAIZ / "frontend"
PYTHON = BACKEND / ".venv" / "bin" / "python"
# Pasta do build servida pelo Nginx (root …/frontend/dist/sgi-spi/browser)
DIST = FRONTEND / "dist" / "sgi-spi"
# Faixa do percentual de cada etapa na barra da tela
FAIXAS = {"conferir": (0, 2), "backup": (2, 40), "codigo": (40, 45), "dependencias": (45, 65), "migracoes": (65, 70), "build": (70, 92), "reiniciar": (92, 100)}


class Falha(Exception):
    """Uma etapa falhou (a mensagem vai para a tela)."""


def andamento(etapa: str, mensagem: str, fracao: float = 0.0, situacao: str = "em_andamento") -> None:
    inicio, fim = FAIXAS[etapa]
    servico_versoes.registrar_andamento(situacao, mensagem, etapa=etapa, percentual=inicio + (fim - inicio) * fracao)


def rodar(comando: list[str], pasta: Path, etapa: str, tempo: int = 1800) -> None:
    """Roda o comando, anexa a saída ao log e transforma erro em `Falha` com o final da saída."""
    with open(servico_versoes.pasta() / servico_versoes.LOG, "a", encoding="utf-8") as registro:
        registro.write(f"\n$ ({pasta.name}) {' '.join(comando)}\n")
        registro.flush()
        try:
            r = subprocess.run(comando, cwd=pasta, stdout=registro, stderr=subprocess.STDOUT, timeout=tempo)
        except (OSError, subprocess.SubprocessError) as erro:
            raise Falha(f"{etapa}: não foi possível executar {comando[0]} ({erro}).") from erro
    if r.returncode != 0:
        raise Falha(f"{etapa}: o comando \"{' '.join(comando[:3])}\" falhou (código {r.returncode}). Veja o log.")


def dependencias() -> None:
    rodar([str(PYTHON), "-m", "pip", "install", "-q", "-r", "requirements.txt"], BACKEND, "dependencias")
    rodar(["npm", "ci", "--no-audit", "--no-fund"], FRONTEND, "dependencias")


def migrar() -> None:
    rodar([str(PYTHON), "-m", "alembic", "upgrade", "head"], BACKEND, "migracoes")


def construir() -> None:
    """Build numa pasta ao lado e troca de uma vez: o site não fica fora do ar enquanto compila."""
    nova = FRONTEND / "dist-nova"
    shutil.rmtree(nova, ignore_errors=True)
    rodar(["npx", "ng", "build", "--configuration", "production", "--output-path", str(nova / "sgi-spi")], FRONTEND, "build")
    anterior = FRONTEND / "dist" / "sgi-spi.anterior"
    shutil.rmtree(anterior, ignore_errors=True)
    DIST.parent.mkdir(parents=True, exist_ok=True)
    if DIST.exists():
        DIST.rename(anterior)
    (nova / "sgi-spi").rename(DIST)
    shutil.rmtree(anterior, ignore_errors=True)
    shutil.rmtree(nova, ignore_errors=True)


def reiniciar(versao_esperada: str) -> None:
    """Reinicia a API e espera até 90 s o /api/saude responder com a versão esperada."""
    rodar(["sudo", "-n", "systemctl", "restart", "sgi-spi-api.service"], BACKEND, "reiniciar", tempo=120)
    for _ in range(45):
        time.sleep(2)
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/api/saude", timeout=5) as resposta:
                if json.loads(resposta.read()).get("versao") == versao_esperada:
                    return
        except (OSError, ValueError):
            continue
    raise Falha(f"reiniciar: a API não voltou com a versão {versao_esperada} em 90 s.")


def restaurar_banco(backup: Path) -> None:
    """Restaura só o banco do backup geral (a atualização não mexe nos anexos)."""
    with tempfile.TemporaryDirectory(dir=servico_versoes.pasta()) as temporaria:
        with zipfile.ZipFile(backup) as z:
            z.extract(servico_backup.DUMP, temporaria)
        servico_backup.restaurar_banco(Path(temporaria) / servico_backup.DUMP)


def auditar_resultado(pedido: dict, acao_resultado: str, dados: dict) -> None:
    try:
        with FabricaSessao() as sessao:
            auditar(sessao, pedido["pedido_por"], "sistema.versao.atualizar", f"{pedido['de']} → {pedido['alvo']}", autor_id=pedido.get("pedido_por_id"),
                    alvo_tipo="versao", dados={"resultado": acao_resultado, **dados})
            sessao.commit()
    except Exception:  # noqa: BLE001 - auditoria não pode derrubar a atualização
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Executa a atualização pedida na tela Administração › Versões.")
    parser.add_argument("--ensaio", action="store_true", help="Só confere, troca o código e volta (sem backup, build nem reinício).")
    args = parser.parse_args()
    (servico_versoes.pasta() / servico_versoes.LOG).write_text("", encoding="utf-8")
    try:
        pedido = json.loads((servico_versoes.pasta() / servico_versoes.PEDIDO).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        servico_versoes.registrar_andamento("erro", "Não há pedido de atualização.", etapa="conferir")
        return 1

    etapa, backup, migrou, trocou_codigo = "conferir", None, False, False
    try:
        andamento("conferir", "Conferindo o código e a versão pedida…")
        if not servico_versoes.arvore_limpa():
            raise Falha("conferir: há alterações locais não commitadas neste servidor.")
        if servico_versoes.git("rev-parse", "HEAD") != pedido["de_commit"]:
            raise Falha("conferir: o código mudou depois do pedido. Peça a atualização de novo.")
        servico_versoes.git("rev-parse", "--verify", pedido["ref"] + "^{commit}")

        if not args.ensaio:
            etapa = "backup"
            andamento("backup", "Gerando o backup geral antes de atualizar…")
            backup = servico_backup._gerar_arquivo(pedido["pedido_por"], "antes-da-atualizacao",
                                                   lambda _e, mensagem, fracao: andamento("backup", mensagem, fracao))

        etapa = "codigo"
        andamento("codigo", f"Trocando o código para {pedido['alvo']}…")
        trocou_codigo = True
        servico_versoes.git("checkout", "--detach", pedido["ref"])
        versao_nova = servico_versoes.versao_atual()
        if args.ensaio:
            raise Falha("ensaio: código trocado; voltando (nada mais é feito no ensaio).")

        etapa = "dependencias"
        andamento("dependencias", "Instalando as dependências do backend e do frontend…")
        dependencias()
        etapa = "migracoes"
        andamento("migracoes", "Aplicando as migrações do banco…")
        migrou = True
        migrar()
        etapa = "build"
        andamento("build", "Compilando as telas (o site continua no ar até a troca)…")
        construir()
        etapa = "reiniciar"
        servico_versoes.registrar_andamento("reiniciando", "Reiniciando a API com a versão nova…", etapa="reiniciar", percentual=94)
        reiniciar(versao_nova)
        servico_versoes.registrar_andamento("concluido", f"Atualizado para {versao_nova}. Backup do estado anterior: {backup.name if backup else '—'}.",
                                            etapa="reiniciar", percentual=100)
        auditar_resultado(pedido, "concluido", {"backup": backup.name if backup else None})
        return 0
    except Exception as erro:  # noqa: BLE001 - qualquer falha dispara a volta automática
        motivo = str(erro)
        if not trocou_codigo:
            servico_versoes.registrar_andamento("erro", f"Falhou antes de trocar o código ({etapa}): {motivo}. Nada mudou.", etapa=etapa)
            auditar_resultado(pedido, "erro", {"etapa": etapa, "erro": motivo})
            return 1
        return voltar(pedido, etapa, motivo, backup, migrou, args.ensaio)


def voltar(pedido: dict, etapa: str, motivo: str, backup: Path | None, migrou: bool, ensaio: bool) -> int:
    """Volta automática: código anterior, dependências, banco do backup (se migrou), build e reinício."""
    servico_versoes.registrar_andamento("em_andamento", f"Falhou em {etapa}: {motivo} Voltando para {pedido['de']}…", etapa=etapa)
    try:
        servico_versoes.git("checkout", "--force", pedido["de_commit"])
        if not ensaio:
            dependencias()
            if migrou and backup is not None:
                restaurar_banco(backup)
            construir()
            reiniciar(servico_versoes.versao_atual())
    except Exception as erro_volta:  # noqa: BLE001
        mensagem = (f"Falhou em {etapa}: {motivo} A volta automática também falhou ({erro_volta}). Restaure pelo backup "
                    f"{backup.name if backup else '(sem backup)'} em Backup geral e veja o log.")
        servico_versoes.registrar_andamento("erro", mensagem, etapa=etapa, voltou=False)
        auditar_resultado(pedido, "erro_sem_volta", {"etapa": etapa, "erro": motivo, "erro_volta": str(erro_volta)})
        return 1
    servico_versoes.registrar_andamento("erro", f"Falhou em {etapa}: {motivo} Voltamos para {pedido['de']}"
                                        + (" (banco restaurado do backup)." if migrou and backup else "."), etapa=etapa, voltou=True)
    auditar_resultado(pedido, "erro_com_volta", {"etapa": etapa, "erro": motivo, "banco_restaurado": bool(migrou and backup)})
    return 1


if __name__ == "__main__":
    sys.exit(main())
