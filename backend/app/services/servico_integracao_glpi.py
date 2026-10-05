# Criado por José Eduardo Santana Martins
# Este arquivo serve para ler, gravar e testar a configuração da integração com o GLPI (tokens cifrados).
"""Configuração da integração com o GLPI: leitura sem expor tokens, gravação com cifra e teste de conexão."""

from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.criptografia import ErroDecifrarSegredo, cifrar_segredo, decifrar_segredo
from app.models.integracao_glpi import IntegracaoGlpi
from app.services.glpi.cliente_glpi import ClienteGlpi, ErroGlpi
from app.services.servico_auditoria import auditar


class AlteracaoIntegracaoGlpi(BaseModel):
    """Corpo do `PUT /api/integracao-glpi`. Token vazio ou ausente preserva o que já está gravado."""

    ativo: bool = Field(..., description="Liga ou desliga a abertura de chamados pelo SGI.")
    url_base: str = Field(..., min_length=8, max_length=300, description="Endereço do GLPI, sem `/apirest.php` (ex.: `https://chamados.spi.sp.gov.br`).")
    app_token: str | None = Field(None, max_length=200, description="App-Token do cliente de API. Vazio preserva o atual.")
    user_token: str | None = Field(None, max_length=200, description="`user_token` (chave de acesso remoto) da conta de serviço. Vazio preserva o atual.")
    prefixo_titulo: str | None = Field(None, max_length=80, description="Prefixo do título do chamado (`<prefixo> | <assunto>`). Em branco mantém o atual.")
    grupo_atribuido_id: int | None = Field(None, ge=0, description="Id do grupo do GLPI atribuído ao chamado (0 = nenhum). Nulo mantém o atual.")
    sla_atendimento_id: int | None = Field(None, ge=0, description="Id do SLA de atendimento (0 = nenhum). Nulo mantém o atual.")
    sla_solucao_id: int | None = Field(None, ge=0, description="Id do SLA de solução (0 = nenhum). Nulo mantém o atual.")
    template_id: int | None = Field(None, ge=0, description="Id do modelo de chamado (0 = o padrão). Nulo mantém o atual.")


class LeituraIntegracaoGlpi(BaseModel):
    """Configuração como a API devolve: os tokens nunca aparecem, só se existem."""

    ativo: bool
    url_base: str
    possui_app_token: bool
    possui_user_token: bool
    configurada: bool = Field(..., description="Há endereço e `user_token`: dá para abrir chamados.")
    prefixo_titulo: str
    grupo_atribuido_id: int | None
    sla_atendimento_id: int | None
    sla_solucao_id: int | None
    template_id: int | None
    atualizado_em: datetime
    atualizado_por: str


class ResultadoTesteGlpi(BaseModel):
    """Resultado do `POST /api/integracao-glpi/testar`."""

    sucesso: bool
    mensagem: str
    latencia_ms: int | None = None


def obter(sessao: Session) -> IntegracaoGlpi:
    """A linha única de configuração (criada vazia se a migração ainda não a trouxe)."""
    config = sessao.get(IntegracaoGlpi, 1)
    if config is None:
        config = IntegracaoGlpi(id=1)
        sessao.add(config)
        sessao.flush()
    return config


def leitura(config: IntegracaoGlpi) -> LeituraIntegracaoGlpi:
    return LeituraIntegracaoGlpi(
        ativo=config.ativo, url_base=config.url_base, possui_app_token=bool(config.app_token_cifrado), possui_user_token=bool(config.user_token_cifrado),
        configurada=bool(config.url_base and config.user_token_cifrado), prefixo_titulo=config.prefixo_titulo,
        grupo_atribuido_id=config.grupo_atribuido_id, sla_atendimento_id=config.sla_atendimento_id, sla_solucao_id=config.sla_solucao_id,
        template_id=config.template_id, atualizado_em=config.atualizado_em, atualizado_por=config.atualizado_por,
    )


def salvar(sessao: Session, dados: AlteracaoIntegracaoGlpi, autor: str) -> IntegracaoGlpi:
    """Grava a configuração; token em branco mantém o anterior. A conta de serviço é auditada sem os valores dos tokens."""
    config = obter(sessao)
    config.ativo, config.url_base, config.atualizado_por = dados.ativo, dados.url_base.strip().rstrip("/"), autor
    if dados.app_token:
        config.app_token_cifrado = cifrar_segredo(dados.app_token.strip())
    if dados.user_token:
        config.user_token_cifrado = cifrar_segredo(dados.user_token.strip())
    if dados.prefixo_titulo is not None and dados.prefixo_titulo.strip():
        config.prefixo_titulo = dados.prefixo_titulo.strip()
    # 0 = "nenhum"; nulo no corpo mantém o valor gravado
    for campo in ("grupo_atribuido_id", "sla_atendimento_id", "sla_solucao_id", "template_id"):
        valor = getattr(dados, campo)
        if valor is not None:
            setattr(config, campo, valor or None)
    auditar(sessao, autor, "integracao_glpi.salvar", "Integração GLPI",
            f"ativo={config.ativo} url={config.url_base} token_novo={bool(dados.user_token)} app_token_novo={bool(dados.app_token)}")
    sessao.commit()
    return config


def tokens(config: IntegracaoGlpi) -> tuple[str, str]:
    """(App-Token, user_token) decifrados; `ErroGlpi` se a cifra não abre (chave trocada)."""
    try:
        return (decifrar_segredo(config.app_token_cifrado) if config.app_token_cifrado else "",
                decifrar_segredo(config.user_token_cifrado) if config.user_token_cifrado else "")
    except ErroDecifrarSegredo as erro:
        raise ErroGlpi("Os tokens gravados não puderam ser lidos. Informe-os de novo na configuração.") from erro


def testar(config: IntegracaoGlpi) -> ResultadoTesteGlpi:
    """Abre e encerra uma sessão no GLPI com a configuração gravada."""
    if not (config.url_base and config.user_token_cifrado):
        return ResultadoTesteGlpi(sucesso=False, mensagem="Informe o endereço e o user_token e salve antes de testar.")
    try:
        app_token, user_token = tokens(config)
        with ClienteGlpi(config.url_base, app_token, user_token) as glpi:
            return ResultadoTesteGlpi(sucesso=True, mensagem="Conexão com o GLPI funcionando.", latencia_ms=glpi.latencia_ms)
    except ErroGlpi as erro:
        return ResultadoTesteGlpi(sucesso=False, mensagem=erro.mensagem)
