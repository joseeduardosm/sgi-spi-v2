# Criado por José Eduardo Santana Martins
# Este arquivo serve para expor a migração do GLPI pelo botão (Chamados › Parâmetros): conexão, teste, execução em segundo plano e andamento.
"""Rotas `/api/chamados/parametros/migracao-glpi` (só Controle total dos Chamados). Regras em `app/services/chamados/migracao_glpi.py`;
documentação em `docs/endpoints/chamados.md` (Migração do GLPI)."""

from typing import Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.respostas import CONFLITO, INVALIDO, VALIDACAO
from app.api.routes.chamados import SEM_ACESSO, _traduzir, administrador
from app.core.banco import obter_sessao
from app.models.usuario import Usuario
from app.services.chamados import migracao_glpi

roteador = APIRouter(prefix="/chamados/parametros/migracao-glpi", tags=["Chamados"], responses=VALIDACAO)


class ConfiguracaoMigracao(BaseModel):
    ativa: bool = Field(True, description="Desligada, a migração some da tela e as rotas de teste e execução respondem `409 desativada`.")
    host: str = Field("", max_length=200, description="Servidor do MariaDB do GLPI.")
    porta: int = 3306
    banco: str = Field("helpdesk", max_length=100)
    usuario: str = Field("", max_length=100, description="Usuário só de leitura (SELECT), criado pela equipe do GLPI.")
    setor_padrao_id: int | None = Field(None, description="Setor dos chamados sem grupo responsável no GLPI.")
    so_abertos: bool = Field(True, description="Traz só os chamados não solucionados (o histórico de resolvidos fica no GLPI).")


class GravacaoMigracao(ConfiguracaoMigracao):
    senha: str | None = Field(None, max_length=200, description="Vazia mantém a cadastrada. Guardada cifrada; nunca volta na leitura.")


class LeituraMigracao(ConfiguracaoMigracao):
    senha_cadastrada: bool
    ultima_sincronizacao: str | None = Field(None, description="Início da última migração que terminou bem (UTC, ISO).")
    andamento: dict = Field(default_factory=dict, description="A última execução: `modo`, `situacao` (em_andamento/concluido/erro), `etapa`, "
                            "`mensagem`, `percentual`, `chamados_migrados`, `chamados_total`, `resumo`, `iniciado_em`, `atualizado_em`, `autor`.")


class TesteMigracao(BaseModel):
    versao: str
    chamados: int


class PedidoMigracao(BaseModel):
    modo: Literal["novidades", "refazer"] = Field(description="`novidades`: novos + os que mudaram no GLPI. `refazer`: apaga todos os chamados (inclusive os do SGI) e traz tudo.")


def _leitura(sessao: Session) -> LeituraMigracao:
    return LeituraMigracao(**migracao_glpi.configuracao(sessao), andamento=migracao_glpi.andamento())


@roteador.get("", response_model=LeituraMigracao, summary="Migração do GLPI: configuração e andamento", responses=SEM_ACESSO)
def ler(_: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> LeituraMigracao:
    return _leitura(sessao)


@roteador.put("", response_model=LeituraMigracao, summary="Gravar a conexão com o GLPI", responses={**INVALIDO, **SEM_ACESSO},
              description="Servidor, porta, banco, usuário só de leitura, senha (cifrada; vazia mantém a atual), setor padrão e se a migração está ativa.")
def gravar(corpo: GravacaoMigracao, usuario: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> LeituraMigracao:
    with _traduzir(sessao):
        migracao_glpi.gravar_configuracao(sessao, corpo.host, corpo.porta, corpo.banco, corpo.usuario, corpo.senha, corpo.setor_padrao_id, corpo.ativa,
                                          corpo.so_abertos)
        from app.services.servico_auditoria import auditar

        auditar(sessao, usuario.login, "chamados.migracao_glpi.configurar", "Conexão com o GLPI", f"{corpo.usuario}@{corpo.host}:{corpo.porta}/{corpo.banco}",
                autor_id=usuario.id)
        sessao.commit()
    return _leitura(sessao)


@roteador.post("/testar", response_model=TesteMigracao, summary="Testar a conexão com o GLPI", responses={**INVALIDO, **SEM_ACESSO, **CONFLITO},
               description="Conecta só para leitura e devolve a versão do GLPI e quantos chamados há lá. Desativada: `409 desativada`.")
def testar(_: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> TesteMigracao:
    with _traduzir(sessao):
        migracao_glpi.exigir_ativa(sessao)
        return TesteMigracao(**migracao_glpi.testar(sessao))


@roteador.post("/executar", response_model=LeituraMigracao, status_code=status.HTTP_202_ACCEPTED, summary="Migrar do GLPI agora",
               description="Começa em segundo plano e responde na hora; a tela acompanha em `GET` (andamento). `novidades`: traz os novos e regrava os que mudaram "
               "no GLPI desde a última vez (na primeira, tudo). `refazer`: apaga **todos** os chamados (inclusive os abertos no SGI) e traz tudo de novo. Uma por vez (`409 em_andamento`); "
               "desativada: `409 desativada`; sem conexão ou setor padrão: `400 sem_configuracao`.", responses={**INVALIDO, **SEM_ACESSO, **CONFLITO})
def executar(corpo: PedidoMigracao, usuario: Usuario = Depends(administrador), sessao: Session = Depends(obter_sessao)) -> LeituraMigracao:
    with _traduzir(sessao):
        migracao_glpi.iniciar(sessao, corpo.modo, usuario.login)
    return _leitura(sessao)
