"""
===============================================================================
ARQUIVO: servico_backup.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Gerar e importar o backup geral do SGI SPI: um .zip com o banco inteiro e
todos os anexos, operado pelo SuperRoot (papel administrativo máximo).

RESUMO TÉCNICO:
O .zip traz manifesto.json (data, servidor, ambiente, versão do sistema,
revisão do banco no Alembic, quem gerou e o motivo), banco.dump (pg_dump no
formato custom) e a pasta anexos/ com o mesmo caminho relativo. Gerar e
importar demoram mais que uma requisição: rodam numa thread e gravam o
andamento em dados/backups/andamento.json, que a tela consulta. Importar
primeiro faz um backup automático ("antes-da-importacao"), restaura o banco
numa transação só (pg_restore --single-transaction), troca a pasta de anexos,
aplica as migrações e reinicia a API.

FINALIDADE DE NEGÓCIO:
Permite guardar uma cópia completa do sistema (configurações, ACL, SMTP,
LDAP, contratos, RH...) e recuperá-la ou levá-la a outro servidor sem
depender da equipe de infraestrutura. Atenção: as senhas do LDAP e do SMTP
vão cifradas com CHAVE_CIFRA_LDAP; restaurar em outro servidor exige a mesma
chave no .env.

CONTEXTO NO SISTEMA:
Chamado pelas rotas de Administração (backup). Usa FabricaSessao e a
configuração (app.core), a auditoria (servico_auditoria), as ferramentas
pg_dump/pg_restore, o Alembic e o systemd (reinício de sgi-spi-api.service).
Nos testes (SQLite) as funções das ferramentas do PostgreSQL são substituídas.

===============================================================================
"""

import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.core.banco import FabricaSessao, agora_utc
from app.core.configuracao import DIRETORIO_BACKEND, obter_configuracao
from app.models.usuario import Usuario
from app.services.servico_auditoria import auditar

log = logging.getLogger(__name__)

# Nomes fixos dos itens dentro do .zip e do arquivo de andamento lido pela tela.
SISTEMA = "SGI SPI"
MANIFESTO = "manifesto.json"
DUMP = "banco.dump"
PASTA_ANEXOS = "anexos/"
ANDAMENTO = "andamento.json"
# Só um backup ou importação por vez (no mesmo processo; o arquivo de andamento cobre os demais workers)
_trava = threading.Lock()


class ErroBackup(Exception):
    """Regra do backup violada ou falha das ferramentas do PostgreSQL (vira 400 com a mensagem)."""


# ---------------------------------------------------------------------------------------------
# Pastas e andamento
# ---------------------------------------------------------------------------------------------

def pasta() -> Path:
    """Pasta onde os backups ficam guardados (criada na hora se ainda não existir)."""
    destino = obter_configuracao().backups_diretorio
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def andamento() -> dict:
    """Situação da última operação: {"operacao", "situacao": em_andamento|concluido|erro|reiniciando, "mensagem", "arquivo",
    "etapa", "percentual", "atualizado_em"}. A tela mostra `etapa` na trilha e `percentual` na barra do modal de andamento."""
    try:
        return json.loads((pasta() / ANDAMENTO).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _registrar_andamento(operacao: str, situacao: str, mensagem: str, arquivo: str | None = None, etapa: str | None = None,
                         percentual: float | None = None) -> None:
    """Grava o andamento num arquivo temporário e troca de uma vez (a tela nunca lê um JSON pela metade)."""
    dados = {"operacao": operacao, "situacao": situacao, "mensagem": mensagem, "arquivo": arquivo, "etapa": etapa,
             "percentual": None if percentual is None else round(min(max(percentual, 0), 100), 1), "atualizado_em": agora_utc().isoformat()}
    temporario = pasta() / (ANDAMENTO + ".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False))
    temporario.replace(pasta() / ANDAMENTO)


def _mb(quantidade: int) -> str:
    """Bytes em MB ou GB, para as mensagens de andamento (ex.: "1,4 GB")."""
    if quantidade >= 1024 ** 3:
        return f"{quantidade / 1024 ** 3:.1f} GB".replace(".", ",")
    return f"{quantidade / 1024 ** 2:.0f} MB"


def ocupado() -> bool:
    """True se há um backup ou importação marcado como em andamento no arquivo de andamento."""
    return andamento().get("situacao") == "em_andamento"


def listar() -> list[dict]:
    """Backups guardados no servidor, do mais recente para o mais antigo."""
    itens = []
    for arquivo in sorted(pasta().glob("*.zip"), key=lambda a: a.stat().st_mtime, reverse=True):
        itens.append({"nome": arquivo.name, "tamanho": arquivo.stat().st_size,
                      "criado_em": datetime.fromtimestamp(arquivo.stat().st_mtime).astimezone(),
                      "antes_da_importacao": "antes-da-importacao" in arquivo.name})
    return itens


def caminho_do_backup(nome: str) -> Path:
    """Caminho de um backup pelo nome, sem deixar sair da pasta (nome com barra ou `..` é recusado)."""
    # Proteção contra "path traversal": um nome como "../../etc/passwd" faria o
    # download sair da pasta dos backups. Só aceita nome simples terminado em .zip.
    if "/" in nome or "\\" in nome or nome.startswith(".") or not nome.endswith(".zip"):
        raise ErroBackup("Nome de backup inválido.")
    caminho = pasta() / nome
    if not caminho.is_file():
        raise ErroBackup("Backup não encontrado.")
    return caminho


# ---------------------------------------------------------------------------------------------
# Ferramentas do PostgreSQL (isoladas: os testes, em SQLite, as substituem)
# ---------------------------------------------------------------------------------------------

def _conexao_libpq() -> tuple[str, dict]:
    """Endereço do banco para as ferramentas do PostgreSQL e o ambiente com a senha (a senha nunca vai na linha de comando)."""
    url = make_url(obter_configuracao().url_banco_dados)
    # make_url (SQLAlchemy) quebra a URL do banco em usuário, senha, host, porta e base.
    if not url.drivername.startswith("postgresql"):
        raise ErroBackup("O backup geral só funciona com o banco PostgreSQL.")
    # A senha vai na variável de ambiente PGPASSWORD, lida pelo pg_dump/pg_restore,
    # para não aparecer na lista de processos do servidor.
    ambiente = {**os.environ, "PGPASSWORD": url.password or ""}
    return f"postgresql://{url.username}@{url.host or 'localhost'}:{url.port or 5432}/{url.database}", ambiente


def despejar_banco(destino: Path) -> None:
    """`pg_dump` do banco inteiro (formato custom, sem dono nem permissões, para restaurar em outro servidor)."""
    endereco, ambiente = _conexao_libpq()
    # subprocess.run executa o programa externo e espera terminar; capture_output
    # guarda a saída de erro para montar a mensagem caso falhe.
    r = subprocess.run(["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--dbname", endereco, "--file", str(destino)],
                       env=ambiente, capture_output=True, text=True)
    if r.returncode != 0:
        raise ErroBackup(f"Falha ao copiar o banco (pg_dump): {r.stderr.strip()[:500]}")


def restaurar_banco(origem: Path) -> None:
    """Substitui o banco pelo do backup numa transação só: se algo falhar, nada muda.

    Antes, encerra as outras conexões ao banco (os workers da API), que segurariam as tabelas."""
    endereco, ambiente = _conexao_libpq()
    # pg_terminate_backend derruba as outras conexões (de outros workers da API);
    # sem isso o pg_restore ficaria bloqueado esperando as tabelas serem liberadas.
    with FabricaSessao() as sessao:
        sessao.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid()"))
        sessao.commit()
    r = subprocess.run(["pg_restore", "--clean", "--if-exists", "--no-owner", "--no-acl", "--single-transaction", "--exit-on-error",
                        "--dbname", endereco, str(origem)], env=ambiente, capture_output=True, text=True)
    if r.returncode != 0:
        raise ErroBackup(f"Falha ao restaurar o banco (pg_restore); o banco continua como estava: {r.stderr.strip()[:500]}")


def migrar() -> None:
    """Leva o banco restaurado à versão atual do sistema (backup de versão anterior)."""
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=DIRETORIO_BACKEND, capture_output=True, text=True)
    if r.returncode != 0:
        raise ErroBackup(f"O banco foi restaurado, mas as migrações falharam: {r.stderr.strip()[-500:]}")


def reiniciar_api() -> None:
    """Reinicia a API logo depois de responder (o sudoers do instalador libera só este comando)."""
    # Popen (sem esperar) com start_new_session: o comando sobrevive mesmo quando a
    # própria API é derrubada pelo restart. O "sleep 3" dá tempo de a resposta HTTP sair.
    subprocess.Popen(["sh", "-c", "sleep 3; sudo -n systemctl restart sgi-spi-api.service"], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def em_segundo_plano(funcao, *args) -> None:
    """Roda a operação numa thread (os testes trocam por execução direta)."""
    threading.Thread(target=funcao, args=args, daemon=True).start()


def _revisoes_conhecidas() -> set[str]:
    """Conjunto de todas as revisões de migração que esta versão do código conhece.

    Usado para recusar backups gerados por uma versão mais nova do sistema.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    return {r.revision for r in ScriptDirectory.from_config(Config(str(DIRETORIO_BACKEND / "alembic.ini"))).walk_revisions()}


def _revisao_atual() -> str:
    """Revisão do Alembic gravada no banco atual (vazia se a tabela não existir)."""
    with FabricaSessao() as sessao:
        try:
            return sessao.scalar(text("SELECT version_num FROM alembic_version")) or ""
        except Exception:  # noqa: BLE001 - banco sem a tabela do Alembic (ex.: testes)
            return ""


# ---------------------------------------------------------------------------------------------
# Gerar
# ---------------------------------------------------------------------------------------------

def _gerar_arquivo(gerado_por: str, motivo: str, avisar=None) -> Path:
    """Monta o .zip (banco + anexos + manifesto) na pasta dos backups e devolve o caminho.

    `avisar(etapa, mensagem, fracao)` recebe o andamento: etapa `banco` (cópia do banco), `anexos` (um a um, pelo tamanho)
    e `finalizar`; `fracao` vai de 0 a 1 dentro da geração inteira. Os anexos avisam no máximo uma vez por segundo."""
    # Quando ninguém quer acompanhar o andamento, usa uma função que não faz nada.
    avisar = avisar or (lambda etapa, mensagem, fracao: None)
    config = obter_configuracao()
    momento = datetime.now().astimezone()
    # Nome com data e hora; o sufixo do motivo (ex.: "-antes-da-importacao") só
    # aparece quando não é um backup manual.
    nome = f"backup-sgi-spi-{momento:%Y%m%d-%H%M%S}{'-' + motivo if motivo != 'manual' else ''}.zip"
    destino = pasta() / nome
    # O .zip é montado com extensão ".parcial" e só renomeado no fim: assim a lista
    # de backups nunca mostra um arquivo incompleto.
    parcial = destino.with_suffix(".zip.parcial")
    anexos = config.anexos_diretorio
    # TemporaryDirectory cria uma pasta temporária e a apaga sozinha ao sair do "with".
    with tempfile.TemporaryDirectory(dir=pasta()) as temporaria:
        dump = Path(temporaria) / DUMP
        avisar("banco", "Copiando o banco de dados (configurações, controle de acesso, SMTP, LDAP, contratos, RH…)", 0.02)
        despejar_banco(dump)
        arquivos = [a for a in anexos.rglob("*") if a.is_file()] if anexos.is_dir() else []
        total_bytes = sum(a.stat().st_size for a in arquivos)
        manifesto = {
            "sistema": SISTEMA, "gerado_em": momento.isoformat(), "servidor": socket.gethostname(), "ambiente": config.ambiente,
            "homologacao": config.modo_homologacao, "versao": config.versao_aplicacao, "revisao_banco": _revisao_atual(),
            "gerado_por": gerado_por, "motivo": motivo, "anexos": len(arquivos), "bytes_anexos": total_bytes,
        }
        with zipfile.ZipFile(parcial, "w", allowZip64=True) as z:
            z.writestr(MANIFESTO, json.dumps(manifesto, ensure_ascii=False, indent=2), compress_type=zipfile.ZIP_DEFLATED)
            avisar("banco", f"Compactando a cópia do banco ({_mb(dump.stat().st_size)})…", 0.2)
            z.write(dump, DUMP, compress_type=zipfile.ZIP_DEFLATED)
            avisar("anexos", f"Juntando os anexos: 0 de {len(arquivos)}…", 0.3)
            # PDFs e imagens já vêm comprimidos: guardar sem recomprimir economiza muito tempo de CPU
            feitos, ultimo_aviso = 0, time.monotonic()
            for i, arquivo in enumerate(arquivos, start=1):
                z.write(arquivo, PASTA_ANEXOS + arquivo.relative_to(anexos).as_posix(), compress_type=zipfile.ZIP_STORED)
                feitos += arquivo.stat().st_size
                if time.monotonic() - ultimo_aviso >= 1:
                    ultimo_aviso = time.monotonic()
                    avisar("anexos", f"Juntando os anexos: {i} de {len(arquivos)} ({_mb(feitos)} de {_mb(total_bytes)})…",
                           0.3 + 0.65 * (feitos / total_bytes if total_bytes else 1))
            avisar("finalizar", "Finalizando o arquivo .zip…", 0.97)
    parcial.rename(destino)
    return destino


def _executar_geracao(usuario_login: str, usuario_id: int) -> None:
    """Corpo da geração em segundo plano: gera, audita e grava o resultado no andamento.

    Sempre libera a trava no fim (finally), dando certo ou não.
    """
    try:
        destino = _gerar_arquivo(usuario_login, "manual",
                                 lambda etapa, mensagem, fracao: _registrar_andamento("gerar", "em_andamento", mensagem, etapa=etapa, percentual=100 * fracao))
        # Registra na auditoria quem gerou o backup (commit grava de fato no banco).
        with FabricaSessao() as sessao:
            auditar(sessao, usuario_login, "sistema.backup.gerar", destino.name, autor_id=usuario_id, alvo_tipo="backup",
                    dados={"tamanho": destino.stat().st_size})
            sessao.commit()
        _registrar_andamento("gerar", "concluido", f"Backup {destino.name} gerado ({_mb(destino.stat().st_size)}).", destino.name,
                             etapa="finalizar", percentual=100)
    except Exception as erro:  # noqa: BLE001 - a falha vira mensagem para a tela
        log.exception("Falha ao gerar o backup")
        etapa = andamento().get("etapa")
        _registrar_andamento("gerar", "erro", str(erro), etapa=etapa)
    finally:
        _trava.release()


def iniciar_geracao(autor: Usuario) -> None:
    """Começa a gerar o backup em segundo plano (um por vez)."""
    # Duas proteções: o arquivo de andamento (vale entre processos/workers) e a
    # trava da thread (vale dentro deste processo). acquire(blocking=False) não espera.
    if ocupado() or not _trava.acquire(blocking=False):
        raise ErroBackup("Já há um backup ou uma importação em andamento. Aguarde terminar.")
    _registrar_andamento("gerar", "em_andamento", "Preparando o backup…", etapa="banco", percentual=0)
    em_segundo_plano(_executar_geracao, autor.login, autor.id)


# ---------------------------------------------------------------------------------------------
# Importar
# ---------------------------------------------------------------------------------------------

def conferir(arquivo: Path) -> dict:
    """Confere o .zip antes de mexer em qualquer coisa e devolve o manifesto."""
    try:
        with zipfile.ZipFile(arquivo) as z:
            nomes = set(z.namelist())
            if MANIFESTO not in nomes or DUMP not in nomes:
                raise ErroBackup("O arquivo não é um backup do SGI SPI (faltam o manifesto ou o banco).")
            manifesto = json.loads(z.read(MANIFESTO))
            # Nenhum caminho pode sair da pasta dos anexos ao extrair
            if any(n.startswith("/") or ".." in Path(n).parts for n in nomes):
                raise ErroBackup("O backup tem caminhos inválidos.")
    except zipfile.BadZipFile as erro:
        raise ErroBackup("O arquivo não é um .zip válido.") from erro
    if manifesto.get("sistema") != SISTEMA:
        raise ErroBackup("O arquivo não é um backup do SGI SPI.")
    revisao = manifesto.get("revisao_banco") or ""
    # Backup de versão mais nova traria tabelas/colunas que este código não conhece;
    # o contrário (backup mais antigo) é aceito porque as migrações o atualizam.
    if revisao and revisao not in _revisoes_conhecidas():
        raise ErroBackup("O backup é de uma versão do sistema mais nova que esta. Atualize o sistema antes de importar.")
    return manifesto


def _trocar_anexos(arquivo: Path, avisar=None) -> int:
    """Substitui a pasta de anexos pelos arquivos do backup (extrai ao lado e troca no fim, para não ficar pela metade).

    `avisar(feitos, total)` recebe o andamento, no máximo uma vez por segundo."""
    anexos = obter_configuracao().anexos_diretorio
    # Extrai numa pasta ".importando" e só no fim troca pelo nome oficial, para a
    # pasta de anexos nunca ficar pela metade se a extração falhar.
    nova = anexos.with_name(anexos.name + ".importando")
    velha = anexos.with_name(anexos.name + ".anterior")
    shutil.rmtree(nova, ignore_errors=True)
    nova.mkdir(parents=True)
    quantidade, ultimo_aviso = 0, time.monotonic()
    with zipfile.ZipFile(arquivo) as z:
        itens = [i for i in z.infolist() if i.filename.startswith(PASTA_ANEXOS) and not i.is_dir()]
        for info in itens:
            alvo = nova / info.filename[len(PASTA_ANEXOS):]
            alvo.parent.mkdir(parents=True, exist_ok=True)
            # copyfileobj copia em blocos de 1 MB, sem carregar o arquivo inteiro na memória.
            with z.open(info) as origem, open(alvo, "wb") as saida:
                shutil.copyfileobj(origem, saida, 1024 * 1024)
            quantidade += 1
            if avisar and time.monotonic() - ultimo_aviso >= 1:
                ultimo_aviso = time.monotonic()
                avisar(quantidade, len(itens))
    shutil.rmtree(velha, ignore_errors=True)
    if anexos.exists():
        anexos.rename(velha)
    nova.rename(anexos)
    # A pasta antiga já está no backup automático feito antes da importação
    shutil.rmtree(velha, ignore_errors=True)
    return quantidade


def _executar_importacao(arquivo: Path, usuario_login: str, usuario_id: int) -> None:
    """Corpo da importação em segundo plano, com o andamento em percentuais.

    Ordem: backup do estado atual (0-35%), restauração do banco (35-60%), troca
    dos anexos (60-90%), migrações (90%) e reinício da API (100%). O arquivo
    enviado é apagado no fim, e a trava é liberada mesmo em caso de erro.
    """
    try:
        # Função auxiliar só para encurtar as chamadas de registro do andamento.
        def passo(etapa: str, mensagem: str, percentual: float, arquivo_anterior: str | None = None) -> None:
            _registrar_andamento("importar", "em_andamento", mensagem, arquivo_anterior, etapa=etapa, percentual=percentual)

        anterior = _gerar_arquivo(usuario_login, "antes-da-importacao",
                                  lambda _etapa, mensagem, fracao: passo("guardar", f"Backup do estado atual: {mensagem[0].lower()}{mensagem[1:]}", 35 * fracao))
        passo("banco", "Restaurando o banco do backup (numa transação só: se falhar, nada muda)…", 35, anterior.name)
        with tempfile.TemporaryDirectory(dir=pasta()) as temporaria, zipfile.ZipFile(arquivo) as z:
            dump = Path(z.extract(DUMP, temporaria))
            restaurar_banco(dump)
        passo("anexos", "Copiando os anexos do backup…", 60, anterior.name)
        quantidade = _trocar_anexos(arquivo, lambda feitos, total: passo("anexos", f"Copiando os anexos do backup: {feitos} de {total}…",
                                                                            60 + 30 * (feitos / total if total else 1), anterior.name))
        passo("migracoes", "Atualizando o banco para a versão deste sistema (migrações)…", 90, anterior.name)
        migrar()
        # A auditoria vai para o banco já restaurado
        with FabricaSessao() as sessao:
            # autor_id=None porque o usuário (id) pode nem existir no banco restaurado;
            # o id de quem importou vai nos dados da auditoria.
            auditar(sessao, usuario_login, "sistema.backup.importar", arquivo.name, autor_id=None, alvo_tipo="backup",
                    dados={"backup_anterior": anterior.name, "anexos": quantidade, "importado_por_id": usuario_id})
            sessao.commit()
        _registrar_andamento("importar", "reiniciando", f"Backup importado ({quantidade} anexo(s)). O estado anterior ficou em {anterior.name}. "
                             "Reiniciando o sistema…", anterior.name, etapa="reiniciar", percentual=100)
        reiniciar_api()
    except Exception as erro:  # noqa: BLE001 - a falha vira mensagem para a tela
        log.exception("Falha ao importar o backup")
        _registrar_andamento("importar", "erro", str(erro), etapa=andamento().get("etapa"))
    finally:
        arquivo.unlink(missing_ok=True)
        _trava.release()


def iniciar_importacao(arquivo: Path, confirmacao: str, autor: Usuario) -> dict:
    """Confere o .zip e começa a importação em segundo plano. Exige a confirmação digitada "SUBSTITUIR"."""
    # Confirmação digitada evita importar por engano (a importação apaga tudo).
    # Em todo caminho de erro o arquivo enviado é apagado para não ocupar disco.
    if confirmacao.strip() != "SUBSTITUIR":
        arquivo.unlink(missing_ok=True)
        raise ErroBackup('Para importar, digite SUBSTITUIR na confirmação.')
    try:
        manifesto = conferir(arquivo)
    except ErroBackup:
        arquivo.unlink(missing_ok=True)
        raise
    if ocupado() or not _trava.acquire(blocking=False):
        arquivo.unlink(missing_ok=True)
        raise ErroBackup("Já há um backup ou uma importação em andamento. Aguarde terminar.")
    _registrar_andamento("importar", "em_andamento", "Importação iniciada…", etapa="guardar", percentual=0)
    em_segundo_plano(_executar_importacao, arquivo, autor.login, autor.id)
    return manifesto


def receber_envio(origem, nome: str) -> Path:
    """Grava o .zip enviado na pasta dos backups (em pedaços, sem carregar na memória)."""
    destino = pasta() / f"importando-{datetime.now():%Y%m%d-%H%M%S}.upload"
    with open(destino, "wb") as saida:
        shutil.copyfileobj(origem, saida, 1024 * 1024)
    return destino
