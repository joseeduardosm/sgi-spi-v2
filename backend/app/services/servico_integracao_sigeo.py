# Criado por José Eduardo Santana Martins
# Este arquivo serve para ler, gravar e testar a configuração da integração com o SIGEO (senha cifrada).
"""Configuração da integração com o SIGEO: leitura sem expor a senha, gravação com cifra e teste de acesso à análise."""

from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.core.criptografia import ErroDecifrarSegredo, cifrar_segredo, decifrar_segredo
from app.models.integracao_sigeo import IntegracaoSigeo
from app.services.servico_auditoria import auditar
from app.services.sigeo.cliente_obiee import ClienteObiee, ErroSigeo


class AlteracaoIntegracaoSigeo(BaseModel):
    """Corpo do `PUT /api/integracao-sigeo`. Senha vazia ou ausente preserva a gravada."""

    ativo: bool = Field(..., description="Liga ou desliga a conferência diária das ordens bancárias (08:00).")
    url_base: str = Field(..., min_length=8, max_length=300, description="Endereço do `saw.dll` do SIGEO (ex.: `https://www.sigeo.fazenda.sp.gov.br/analytics/saw.dll`).")
    caminho_analise: str = Field(..., min_length=3, max_length=500, description="Caminho da análise salva no catálogo (ex.: `/users/.../PAGO - Execução Contrato - Gestor`).")
    caminho_analise_empenhado: str | None = Field(None, min_length=3, max_length=500, description="Caminho da análise das Notas de Empenho emitidas (padrão `…/EMPENHADO - Execução`). Nulo mantém o atual.")
    usuario: str = Field(..., min_length=1, max_length=100, description="Usuário do SIGEO.")
    senha: str | None = Field(None, max_length=200, description="Senha do SIGEO. Vazio preserva a atual; nunca volta pela API.")
    hora_conferencia: int = Field(8, ge=0, le=23, description="Hora do dia (horário de Brasília) da conferência diária das OBs.")


class LeituraIntegracaoSigeo(BaseModel):
    """Configuração como a API devolve: a senha nunca aparece, só se existe."""

    ativo: bool
    url_base: str
    caminho_analise: str
    caminho_analise_empenhado: str
    usuario: str
    possui_senha: bool
    hora_conferencia: int
    configurada: bool = Field(..., description="Há endereço, análise, usuário e senha.")
    ultima_execucao_em: datetime | None
    ultimo_resultado: dict | None = Field(None, description="Resumo da última conferência: concluídas, pendências e erros.")
    atualizado_em: datetime
    atualizado_por: str


class ResultadoTesteSigeo(BaseModel):
    """Resultado do `POST /api/integracao-sigeo/testar`."""

    sucesso: bool
    mensagem: str
    linhas: int | None = None
    latencia_ms: int | None = None


def obter(sessao: Session) -> IntegracaoSigeo:
    """A linha única de configuração (criada com os padrões se ainda não existir)."""
    config = sessao.get(IntegracaoSigeo, 1)
    if config is None:
        config = IntegracaoSigeo(id=1, atualizado_em=agora_utc())
        sessao.add(config)
        sessao.flush()
    return config


def leitura(config: IntegracaoSigeo) -> LeituraIntegracaoSigeo:
    return LeituraIntegracaoSigeo(
        ativo=config.ativo, url_base=config.url_base, caminho_analise=config.caminho_analise, caminho_analise_empenhado=config.caminho_analise_empenhado, usuario=config.usuario, possui_senha=bool(config.senha_cifrada), hora_conferencia=config.hora_conferencia,
        configurada=bool(config.url_base and config.caminho_analise and config.usuario and config.senha_cifrada),
        ultima_execucao_em=config.ultima_execucao_em, ultimo_resultado=config.ultimo_resultado, atualizado_em=config.atualizado_em, atualizado_por=config.atualizado_por,
    )


def salvar(sessao: Session, dados: AlteracaoIntegracaoSigeo, autor: str) -> IntegracaoSigeo:
    """Grava a configuração; senha em branco mantém a anterior. Auditada sem a senha."""
    config = obter(sessao)
    config.ativo, config.url_base, config.caminho_analise = dados.ativo, dados.url_base.strip().split("?")[0], dados.caminho_analise.strip()
    config.usuario, config.atualizado_por, config.atualizado_em = dados.usuario.strip(), autor, agora_utc()
    config.hora_conferencia = dados.hora_conferencia
    if dados.caminho_analise_empenhado:
        config.caminho_analise_empenhado = dados.caminho_analise_empenhado.strip()
    if dados.senha:
        config.senha_cifrada = cifrar_segredo(dados.senha)
    auditar(sessao, autor, "integracao_sigeo.salvar", "Integração SIGEO", f"ativo={config.ativo} usuario={config.usuario} hora={config.hora_conferencia} senha_nova={bool(dados.senha)}")
    sessao.commit()
    return config


def hora_de_conferir(config: IntegracaoSigeo, agora=None) -> bool:
    """A rotina de hora em hora só confere uma vez por dia, a partir da hora configurada (horário de Brasília)."""
    from zoneinfo import ZoneInfo

    fuso = ZoneInfo("America/Sao_Paulo")
    agora = (agora or agora_utc()).astimezone(fuso)
    if agora.hour < config.hora_conferencia:
        return False
    return config.ultima_execucao_em is None or config.ultima_execucao_em.astimezone(fuso).date() < agora.date()


def credencial(config: IntegracaoSigeo) -> tuple[str, str]:
    """(usuário, senha) decifrados; `ErroSigeo` se faltar ou se a cifra não abre."""
    if not (config.usuario and config.senha_cifrada):
        raise ErroSigeo("Informe o usuário e a senha do SIGEO em Administração > Integração SIGEO.")
    try:
        return config.usuario, decifrar_segredo(config.senha_cifrada)
    except ErroDecifrarSegredo as erro:
        raise ErroSigeo("A senha gravada não pôde ser lida. Informe-a de novo na configuração.") from erro


def baixar_pagamentos(config: IntegracaoSigeo) -> list[dict[str, str]]:
    """Executa a análise configurada e devolve as linhas (cada uma, uma OB)."""
    usuario, senha = credencial(config)
    with ClienteObiee(config.url_base, usuario, senha) as cliente:
        return cliente.executar_analise(config.caminho_analise)


def baixar_empenhos(config: IntegracaoSigeo) -> list[dict[str, str]]:
    """Executa a análise de empenhos (NEs e cancelamentos emitidos) e devolve as linhas."""
    usuario, senha = credencial(config)
    with ClienteObiee(config.url_base, usuario, senha) as cliente:
        return cliente.executar_analise(config.caminho_analise_empenhado)


def testar(config: IntegracaoSigeo) -> ResultadoTesteSigeo:
    """Entra no SIGEO, executa a análise e informa quantas OBs vieram."""
    try:
        usuario, senha = credencial(config)
        with ClienteObiee(config.url_base, usuario, senha) as cliente:
            linhas = cliente.executar_analise(config.caminho_analise)
            latencia = cliente.latencia_ms
    except ErroSigeo as erro:
        return ResultadoTesteSigeo(sucesso=False, mensagem=erro.mensagem)
    faltam = [c for c in ("COD_PROCESSO", "COD_DOCUMENTO", "DATA_LANCAMENTO", "DESCRICAO_DOCUMENTO", "VALOR_DOCUMENTO") if linhas and c not in linhas[0]]
    if faltam:
        return ResultadoTesteSigeo(sucesso=False, mensagem=f"A análise não tem as colunas {', '.join(faltam)}.", linhas=len(linhas), latencia_ms=latencia)
    return ResultadoTesteSigeo(sucesso=True, mensagem=f"Acesso ao SIGEO funcionando: {len(linhas)} ordem(ns) bancária(s) na análise.", linhas=len(linhas), latencia_ms=latencia)
