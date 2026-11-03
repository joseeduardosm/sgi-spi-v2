# Criado por José Eduardo Santana Martins
# Este arquivo serve para a migração do GLPI pelo botão (Chamados › Parâmetros): lê o banco do GLPI só com SELECT e traz os chamados,
# em segundo plano, com o andamento para a tela.
"""Migração do GLPI pelo botão.

- **Só leitura no GLPI:** conecta no MariaDB com um usuário que só tem SELECT (criado pela equipe do GLPI) e lê as mesmas tabelas que o
  importador lê do dump. Nada é gravado lá.
- **Dois modos:**
  - `novidades`: traz os chamados novos e regrava os que **mudaram no GLPI** desde a última sincronização (campos e filhos). Na primeira
    vez, traz tudo. Pode rodar quantas vezes quiser.
  - `refazer`: apaga **todos** os chamados, inclusive os abertos no próprio SGI (a base volta a ser só o GLPI), e traz tudo de novo.
- **Só os não solucionados** (padrão, `glpi_so_abertos`): chamado novo já resolvido ou excluído no GLPI não vem; o que já veio continua sendo
  atualizado. Desmarcado, traz também o histórico (resolvidos como somente leitura).
- **Pessoas, grupos e etiquetas** casam sozinhos (login/e-mail, nome do setor, nome da pessoa), como as sugestões do script.
- **Categorias do GLPI** viram **categorias ITIL**; o assunto dos importados é o "Importados do GLPI".
- **Anexos** ficam de fora (estão nas pastas do servidor do GLPI, não no banco).
- Roda **em segundo plano**; o andamento vai para um arquivo JSON que os dois workers da API leem (como o Backup geral). Uma por vez.
- **Desligável:** com `glpi_migracao_ativa` = falso, as rotas recusam (`409 desativada`) e a tela esconde a aba.
"""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.banco import FabricaSessao, agora_utc
from app.core.configuracao import obter_configuracao
from app.core.criptografia import ErroDecifrarSegredo, cifrar_segredo, decifrar_segredo
from app.models.setor import Setor
from app.services.chamados import importacao_glpi, parametros
from app.services.chamados.parametros import ErroParametro

log = logging.getLogger(__name__)

# Configuração nos Parâmetros dos Chamados (a senha, cifrada)
parametros.PADROES.update({
    "glpi_host": "", "glpi_porta": "3306", "glpi_banco": "helpdesk", "glpi_usuario": "", "glpi_senha": "", "glpi_setor_padrao_id": "",
    "glpi_migracao_ativa": "true", "glpi_ultima_sincronizacao": "", "glpi_so_abertos": "true",
})
ANDAMENTO = "andamento.json"
MODOS = ("novidades", "refazer")
# Etapas na ordem em que a tela mostra na trilha
ETAPAS = ("conexao", "leitura", "limpeza", "categorias", "chamados", "detalhes", "concluido")
_trava = threading.Lock()


# ---------------------------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------------------------

def ativa(sessao: Session) -> bool:
    return parametros.obter(sessao, "glpi_migracao_ativa") == "true"


def exigir_ativa(sessao: Session) -> None:
    if not ativa(sessao):
        raise ErroParametro("A migração do GLPI está desativada nos Parâmetros.", 409, "desativada")


def configuracao(sessao: Session) -> dict:
    """O que a tela mostra (a senha nunca volta: só se está cadastrada)."""
    setor = parametros.obter(sessao, "glpi_setor_padrao_id")
    return {
        "ativa": ativa(sessao), "host": parametros.obter(sessao, "glpi_host"), "porta": int(parametros.obter(sessao, "glpi_porta") or 3306),
        "banco": parametros.obter(sessao, "glpi_banco"), "usuario": parametros.obter(sessao, "glpi_usuario"),
        "senha_cadastrada": bool(parametros.obter(sessao, "glpi_senha")), "setor_padrao_id": int(setor) if setor else None,
        "ultima_sincronizacao": parametros.obter(sessao, "glpi_ultima_sincronizacao") or None,
        "so_abertos": parametros.obter(sessao, "glpi_so_abertos") == "true",
    }


def gravar_configuracao(sessao: Session, host: str, porta: int, banco: str, usuario: str, senha: str | None, setor_padrao_id: int | None,
                        ativa_: bool, so_abertos: bool = True) -> None:
    """Grava a conexão. `senha` vazia ou nula mantém a cadastrada. Sem commit."""
    if not 1 <= porta <= 65535:
        raise ErroParametro("Porta inválida.")
    if setor_padrao_id is not None:
        setor = sessao.get(Setor, setor_padrao_id)
        if setor is None or not setor.ativo:
            raise ErroParametro("Escolha um setor ativo como padrão.")
    for chave, valor in (("glpi_host", host.strip()), ("glpi_porta", str(porta)), ("glpi_banco", banco.strip() or "helpdesk"),
                         ("glpi_usuario", usuario.strip()), ("glpi_setor_padrao_id", str(setor_padrao_id or "")),
                         ("glpi_migracao_ativa", "true" if ativa_ else "false"), ("glpi_so_abertos", "true" if so_abertos else "false")):
        parametros.gravar(sessao, chave, valor)
    if senha:
        parametros.gravar(sessao, "glpi_senha", cifrar_segredo(senha))


def _conectar(sessao: Session):
    """Conexão só de leitura com o MariaDB do GLPI (a sessão também é marcada READ ONLY)."""
    import pymysql

    cfg = configuracao(sessao)
    if not cfg["host"] or not cfg["usuario"] or not cfg["senha_cadastrada"]:
        raise ErroParametro("Cadastre o servidor, o usuário e a senha do banco do GLPI antes.", 400, "sem_configuracao")
    try:
        senha = decifrar_segredo(parametros.obter(sessao, "glpi_senha"))
    except ErroDecifrarSegredo as erro:
        raise ErroParametro("Não foi possível ler a senha cadastrada; cadastre de novo.", 400, "senha_invalida") from erro
    try:
        conexao = pymysql.connect(host=cfg["host"], port=cfg["porta"], user=cfg["usuario"], password=senha, database=cfg["banco"],
                                  charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor, connect_timeout=10, read_timeout=300)
    except pymysql.MySQLError as erro:
        raise ErroParametro(f"Não foi possível conectar no banco do GLPI: {erro.args[-1] if erro.args else erro}", 400, "sem_conexao") from erro
    with conexao.cursor() as cursor:
        cursor.execute("SET SESSION TRANSACTION READ ONLY")
    return conexao


def testar(sessao: Session) -> dict:
    """Conecta e conta os chamados, sem trazer nada."""
    conexao = _conectar(sessao)
    try:
        with conexao.cursor() as cursor:
            cursor.execute("SELECT value FROM glpi_configs WHERE context = 'core' AND name = 'version'")
            versao = (cursor.fetchone() or {}).get("value", "")
            cursor.execute("SELECT COUNT(*) AS total FROM glpi_tickets")
            total = cursor.fetchone()["total"]
    finally:
        conexao.close()
    return {"versao": versao, "chamados": total}


def ler_banco(conexao, avisar=None) -> dict[str, list[dict]]:
    """As mesmas tabelas do importador, lidas com SELECT (tabela que não existe na versão do GLPI fica vazia, como no dump)."""
    avisar = avisar or (lambda *_: None)
    dados: dict[str, list[dict]] = {}
    tabelas = sorted(importacao_glpi.TABELAS)
    with conexao.cursor() as cursor:
        cursor.execute("SHOW TABLES")
        existentes = {list(linha.values())[0] for linha in cursor.fetchall()}
        for n, tabela in enumerate(tabelas, 1):
            avisar("leitura", f"Lendo {tabela} do GLPI…", n / len(tabelas))
            if tabela not in existentes:
                dados[tabela] = []
                continue
            cursor.execute(f"SELECT * FROM `{tabela}`")  # noqa: S608 — nome vem da lista fixa do importador
            dados[tabela] = [_normalizar_linha(x) for x in cursor.fetchall()]
    return dados


def _normalizar_linha(linha: dict) -> dict:
    """Valores do MariaDB no formato do dump: datas como texto "AAAA-MM-DD hh:mm:ss" (o importador converte), decimais como float."""
    from decimal import Decimal

    saida = {}
    for k, v in linha.items():
        if isinstance(v, datetime):
            saida[k] = v.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(v, Decimal):
            saida[k] = float(v)
        elif isinstance(v, bytes):
            saida[k] = v.decode("utf-8", "replace")
        else:
            saida[k] = v
    return saida


# ---------------------------------------------------------------------------------------------
# Andamento (arquivo lido pelos dois workers)
# ---------------------------------------------------------------------------------------------

def _pasta() -> Path:
    destino = obter_configuracao().backups_diretorio.parent / "migracao-glpi"
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def andamento() -> dict:
    """{"modo", "situacao": em_andamento|concluido|erro, "etapa", "mensagem", "percentual", "chamados_migrados", "chamados_total", "resumo",
    "iniciado_em", "atualizado_em", "autor"}"""
    try:
        return json.loads((_pasta() / ANDAMENTO).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _registrar(**dados) -> None:
    atual = andamento()
    atual.update(dados, atualizado_em=agora_utc().isoformat())
    if atual.get("percentual") is not None:
        atual["percentual"] = round(min(max(float(atual["percentual"]), 0), 100), 1)
    temporario = _pasta() / (ANDAMENTO + ".tmp")
    temporario.write_text(json.dumps(atual, ensure_ascii=False))
    temporario.replace(_pasta() / ANDAMENTO)


def ocupado() -> bool:
    return andamento().get("situacao") == "em_andamento"


# ---------------------------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------------------------

# Peso de cada etapa na barra (somam 100)
_PESOS = {"conexao": (0, 3), "leitura": (3, 20), "limpeza": (20, 25), "categorias": (25, 28), "chamados": (28, 85), "detalhes": (85, 99)}


def iniciar(sessao: Session, modo: str, autor_login: str) -> None:
    """Confere e dispara em segundo plano. Uma migração por vez (inclusive entre os workers, pelo arquivo de andamento)."""
    exigir_ativa(sessao)
    if modo not in MODOS:
        raise ErroParametro("Modo inválido (novidades ou refazer).")
    cfg = configuracao(sessao)
    if not cfg["setor_padrao_id"]:
        raise ErroParametro("Escolha o setor padrão (o dos chamados sem grupo responsável no GLPI).", 400, "sem_configuracao")
    # O arquivo de andamento vale entre os workers; a trava, dentro deste processo (dois cliques seguidos)
    if ocupado() or not _trava.acquire(blocking=False):
        raise ErroParametro("Já há uma migração do GLPI em andamento. Aguarde terminar.", 409, "em_andamento")
    _registrar(modo=modo, situacao="em_andamento", etapa="conexao", mensagem="Conectando no banco do GLPI…", percentual=0, chamados_migrados=0,
               chamados_total=None, resumo=None, iniciado_em=agora_utc().isoformat(), autor=autor_login)
    threading.Thread(target=_executar, args=(modo, autor_login), daemon=True).start()


def _executar(modo: str, autor_login: str) -> None:
    """Roda numa sessão própria. Tudo numa transação só: se der erro, nada fica pela metade."""
    inicio = agora_utc()
    try:
        with FabricaSessao() as sessao:
            def avisar(etapa: str, mensagem: str, fracao: float) -> None:
                de, ate = _PESOS.get(etapa, (0, 100))
                extra = {}
                if etapa == "chamados" and "de" in mensagem:
                    feitos, _, resto = mensagem.partition(" de ")
                    if feitos.isdigit():
                        extra = {"chamados_migrados": int(feitos), "chamados_total": int(resto.split(" ")[0])}
                _registrar(etapa=etapa, mensagem=mensagem, percentual=de + (ate - de) * fracao, **extra)

            conexao = _conectar(sessao)
            try:
                avisar("leitura", "Lendo o banco do GLPI…", 0)
                dados = ler_banco(conexao, avisar)
            finally:
                conexao.close()
            if modo == "refazer":
                avisar("limpeza", "Apagando todos os chamados (os do GLPI e os abertos no SGI)…", 0)
                apagados = importacao_glpi.apagar_chamados(sessao)
                avisar("limpeza", f"{apagados} chamado(s) apagado(s).", 1)
            ultima = parametros.obter(sessao, "glpi_ultima_sincronizacao")
            desde = datetime.fromisoformat(ultima) if (modo == "novidades" and ultima) else None
            setor = int(parametros.obter(sessao, "glpi_setor_padrao_id"))
            mapas = importacao_glpi.mapas_automaticos(sessao, dados)
            so_abertos = parametros.obter(sessao, "glpi_so_abertos") == "true"
            rel = importacao_glpi.carregar(sessao, dados, mapas, setor, None, atualizar=True, desde=desde, avisar=avisar, so_abertos=so_abertos)
            parametros.gravar(sessao, "glpi_ultima_sincronizacao", inicio.isoformat())
            from app.services.servico_auditoria import auditar

            auditar(sessao, autor_login, "chamados.migracao_glpi", f"Migração do GLPI ({modo})",
                    f"{rel.destino['chamados']} novo(s), {rel.destino['chamados atualizados']} atualizado(s)")
            sessao.commit()
        resumo = {
            "versao": rel.versao, "novos": rel.destino["chamados"], "atualizados": rel.destino["chamados atualizados"], "sem_mudanca": rel.pulados["chamados"],
            "categorias_itil": rel.destino["categorias ITIL"], "trabalhados_sgi": rel.pulados["trabalhados no SGI"],
            "resolvidos_nao_migrados": rel.pulados["resolvidos no GLPI (não migrados)"], "acompanhamentos": rel.destino["acompanhamentos"], "solucoes": rel.destino["soluções"],
            "avisos": rel.avisos[:50], "total_avisos": len(rel.avisos),
        }
        migrados = resumo["novos"] + resumo["atualizados"]
        _registrar(situacao="concluido", etapa="concluido", percentual=100, resumo=resumo, chamados_migrados=migrados,
                   mensagem=f"Pronto: {resumo['novos']} chamado(s) novo(s) e {resumo['atualizados']} atualizado(s); {resumo['sem_mudanca']} sem mudança.")
    except Exception as erro:  # noqa: BLE001 — qualquer falha vai para a tela; a transação foi desfeita
        log.exception("Migração do GLPI falhou")
        # Só a primeira linha e sem o SQL (o detalhe completo fica no log da API)
        texto = str(getattr(erro, "orig", None) or erro).split("\n")[0][:400]
        mensagem = str(erro) if isinstance(erro, ErroParametro) else f"A migração parou e nada foi gravado: {texto}"
        _registrar(situacao="erro", mensagem=mensagem)
    finally:
        try:
            _trava.release()
        except RuntimeError:
            pass
