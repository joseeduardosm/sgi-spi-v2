"""Importação do Módulo de Contratos do SGI SPI pela tela (botão do SuperRoot em /contratos).

O SuperRoot digita duas senhas: a do usuário do SGI (origem, `MIGRACAO_SGI_*`) e a deste servidor
(destino, `MIGRACAO_LOCAL_*`). As duas são conferidas por SSH antes de começar; a de origem também precisa
servir para o `sudo` de lá (a extração lê o banco como `postgres`). Nenhuma senha é gravada: a de origem
passa ao processo de extração só pela variável de ambiente dele.

A execução roda num processo à parte (a extração leva minutos), que registra o andamento em
`MIGRACAO_DIRETORIO/estado.json`; a API tem mais de um worker, por isso o estado fica em arquivo.
Etapas: extração somente leitura (`scripts/extrair-contratos-sgi.py`) e carga com substituição
(`scripts/migrar-contratos-sgi.py --gravar --substituir`). Ver docs/migracao-sgi.md.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import paramiko

from app.core.banco import FabricaSessao, agora_utc
from app.core.configuracao import obter_configuracao
from app.models.usuario import Usuario
from app.services.servico_auditoria import auditar

RAIZ_PROJETO = Path(__file__).resolve().parents[4]
SCRIPT_EXTRACAO = RAIZ_PROJETO / "scripts" / "extrair-contratos-sgi.py"
SCRIPT_CARGA = RAIZ_PROJETO / "scripts" / "migrar-contratos-sgi.py"
LINHAS_DE_LOG = 40


class ErroMigracao(Exception):
    def __init__(self, mensagem: str, codigo: str, status_code: int = 400) -> None:
        super().__init__(mensagem)
        self.codigo, self.status_code = codigo, status_code


def _diretorio() -> Path:
    pasta = Path(obter_configuracao().migracao_diretorio)
    pasta.mkdir(parents=True, exist_ok=True)
    os.chmod(pasta, 0o700)
    return pasta


def _arquivo_estado() -> Path:
    return _diretorio() / "estado.json"


def _arquivo_log() -> Path:
    return _diretorio() / "execucao.log"


def _ler_bruto() -> dict[str, Any]:
    try:
        return json.loads(_arquivo_estado().read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"situacao": "ociosa"}


def _gravar_estado(**campos: Any) -> dict[str, Any]:
    estado = {**_ler_bruto(), **campos}
    temporario = _arquivo_estado().with_suffix(".tmp")
    temporario.write_text(json.dumps(estado, ensure_ascii=False, default=str))
    temporario.replace(_arquivo_estado())
    return estado


def _processo_vivo(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def ler_estado() -> dict[str, Any]:
    """Estado da última importação, com o fim do log. Execução sem processo vivo vira erro (interrompida)."""
    estado = _ler_bruto()
    if estado.get("situacao") == "executando" and not _processo_vivo(estado.get("pid")):
        estado = _gravar_estado(situacao="erro", mensagem="A importação foi interrompida (o serviço foi reiniciado?).", concluida_em=agora_utc())
    try:
        estado["log"] = _arquivo_log().read_text(errors="replace").splitlines()[-LINHAS_DE_LOG:]
    except FileNotFoundError:
        estado["log"] = []
    configuracao = obter_configuracao()
    estado["origem"] = f"{configuracao.migracao_sgi_usuario}@{configuracao.migracao_sgi_host}"
    estado["destino"] = f"{configuracao.migracao_local_usuario}@{configuracao.migracao_local_host}"
    return estado


def _conectar(host: str, usuario: str, senha: str, rotulo: str) -> paramiko.SSHClient:
    cliente = paramiko.SSHClient()
    cliente.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        cliente.connect(host, username=usuario, password=senha, timeout=10, allow_agent=False, look_for_keys=False)
    except paramiko.AuthenticationException as erro:
        raise ErroMigracao(f"Senha incorreta para {usuario}@{host} ({rotulo}).", "senha_invalida") from erro
    except (OSError, paramiko.SSHException) as erro:
        raise ErroMigracao(f"Não foi possível conectar a {host} ({rotulo}): {erro}", "servidor_inacessivel", 502) from erro
    return cliente


def validar_senhas(senha_origem: str, senha_destino: str) -> None:
    configuracao = obter_configuracao()
    origem = _conectar(configuracao.migracao_sgi_host, configuracao.migracao_sgi_usuario, senha_origem, "origem")
    try:
        # A extração lê o banco do SGI como postgres: a senha precisa valer também no sudo de lá
        entrada, saida, _ = origem.exec_command("sudo -S -p '' -v", timeout=15)
        entrada.write(senha_origem + "\n")
        entrada.channel.shutdown_write()
        if saida.channel.recv_exit_status() != 0:
            raise ErroMigracao(
                f"A senha de {configuracao.migracao_sgi_usuario} não foi aceita pelo sudo em {configuracao.migracao_sgi_host}.", "senha_invalida"
            )
    finally:
        origem.close()
    _conectar(configuracao.migracao_local_host, configuracao.migracao_local_usuario, senha_destino, "destino").close()


def iniciar(senha_origem: str, senha_destino: str, autor: Usuario) -> dict[str, Any]:
    if ler_estado().get("situacao") == "executando":
        raise ErroMigracao("Já existe uma importação em andamento.", "conflito", 409)
    validar_senhas(senha_origem, senha_destino)
    configuracao = obter_configuracao()
    _arquivo_log().write_text("")
    _gravar_estado(situacao="executando", etapa="iniciando", mensagem="Iniciando a importação.", iniciada_em=agora_utc(),
                   concluida_em=None, iniciada_por=autor.nome_completo or autor.login, resultado=None, avisos=[], pid=None)
    ambiente = {**os.environ, "SGI_SENHA": senha_origem, "SGI_HOST": configuracao.migracao_sgi_host,
                "SGI_USUARIO": configuracao.migracao_sgi_usuario}
    processo = subprocess.Popen(
        [sys.executable, "-m", "app.services.contratos.servico_migracao_sgi", str(autor.id), autor.login],
        cwd=RAIZ_PROJETO / "backend", env=ambiente, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    _gravar_estado(pid=processo.pid)
    with FabricaSessao() as sessao:
        auditar(sessao, autor.login, "contrato.migracao_sgi.iniciar", f"SGI {configuracao.migracao_sgi_host}", autor_id=autor.id,
                alvo_tipo="migracao", alvo_id="sgi")
        sessao.commit()
    return ler_estado()


# --- Processo à parte ----------------------------------------------------------------------------

def _rodar(etapa: str, mensagem: str, comando: list[str], ambiente: dict[str, str]) -> str:
    _gravar_estado(etapa=etapa, mensagem=mensagem)
    with open(_arquivo_log(), "a") as log:
        log.write(f"==> {mensagem}\n")
        log.flush()
        resultado = subprocess.run(comando, cwd=RAIZ_PROJETO / "backend", env=ambiente, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)
        # Avisos internos do SQLAlchemy não interessam a quem acompanha pela tela
        saida = "\n".join(linha for linha in resultado.stdout.splitlines() if "Warning" not in linha and not linha.startswith("  sessao."))
        log.write(saida + "\n")
    if resultado.returncode != 0:
        ultima = next((linha for linha in reversed(saida.splitlines()) if linha.strip()), "sem detalhes")
        raise RuntimeError(f"Falha na etapa '{etapa}': {ultima}")
    return saida


def executar(autor_id: int, autor_login: str) -> None:
    ambiente = {**os.environ}
    pacote = _diretorio() / f"pacote-{datetime.now():%Y%m%d-%H%M%S}"
    acao, dados = "contrato.migracao_sgi.falhar", None
    try:
        _rodar("extraindo", "Extraindo os dados do SGI (somente leitura)…", [sys.executable, str(SCRIPT_EXTRACAO), str(pacote)], ambiente)
        ambiente.pop("SGI_SENHA", None)
        saida = _rodar("carregando", "Carregando e conferindo os dados neste servidor…",
                       [sys.executable, str(SCRIPT_CARGA), str(pacote), "--gravar", "--substituir"], ambiente)
        carga = re.search(r"^Carga: (\{.*\})$", saida, re.M)
        resultado = json.loads(carga.group(1)) if carga else None
        avisos = [linha.strip().removeprefix("aviso:").strip() for linha in saida.splitlines() if linha.strip().startswith("aviso:")]
        _gravar_estado(situacao="concluida", etapa="concluida", mensagem="Importação concluída.", resultado=resultado, avisos=avisos,
                       concluida_em=agora_utc())
        acao, dados = "contrato.migracao_sgi.concluir", resultado
    except Exception as erro:  # noqa: BLE001 - qualquer falha precisa chegar à tela
        _gravar_estado(situacao="erro", mensagem=str(erro), concluida_em=agora_utc())
        dados = {"erro": str(erro)}
    finally:
        # O pacote tem dados pessoais e documentos contratuais: não fica no disco
        shutil.rmtree(pacote, ignore_errors=True)
    with FabricaSessao() as sessao:
        auditar(sessao, autor_login, acao, "SGI", autor_id=autor_id, alvo_tipo="migracao", alvo_id="sgi", dados=dados)
        sessao.commit()


if __name__ == "__main__":
    executar(int(sys.argv[1]), sys.argv[2])
