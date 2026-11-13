"""
===============================================================================
ARQUIVO: servico_integracao_bookstack.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Ler, gravar e testar a configuração da integração com o BookStack (wiki onde
ficam os manuais), guardando o token de API sempre cifrado.

RESUMO TÉCNICO:
Define os schemas pydantic do PUT (AlteracaoIntegracaoBookstack), da leitura
(LeituraIntegracaoBookstack, que nunca devolve o token) e do teste. obter()
garante a linha única (id=1) da tabela; salvar() cifra o token com
cifrar_segredo e audita sem o valor; tokens() decifra; testar() faz uma
listagem mínima com o ClienteBookstack e mede a latência.

FINALIDADE DE NEGÓCIO:
Permite ao administrador ligar a leitura dos manuais do SGI dentro do
portal, escolhendo quais livros do BookStack aparecem, sem expor a
credencial da conta de serviço.

CONTEXTO NO SISTEMA:
Usado pelas rotas /api/integracao-bookstack (Administração) e pelo
servico_manuais, que lê os livros. Grava no modelo IntegracaoBookstack, usa
app.core.criptografia e registra na auditoria.

===============================================================================
"""

from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.criptografia import ErroDecifrarSegredo, cifrar_segredo, decifrar_segredo
from app.models.integracao_bookstack import IntegracaoBookstack
from app.services.bookstack.cliente_bookstack import ClienteBookstack, ErroBookstack
from app.services.servico_auditoria import auditar


# Schemas pydantic (BaseModel): validam o JSON recebido/enviado pela API e
# aparecem na documentação OpenAPI. Field(...) com "..." = campo obrigatório.
class AlteracaoIntegracaoBookstack(BaseModel):
    """Corpo do `PUT /api/integracao-bookstack`. Token vazio ou ausente preserva o que já está gravado."""

    ativo: bool = Field(..., description="Liga ou desliga a leitura dos manuais pelo portal.")
    url_base: str = Field(..., min_length=8, max_length=300, description="Endereço do BookStack (ex.: `https://instrucoes.spi.sp.gov.br`).")
    token_id: str | None = Field(None, max_length=200, description="ID do token de API da conta de serviço. Vazio preserva o atual.")
    token_segredo: str | None = Field(None, max_length=200, description="Segredo do token de API. Vazio preserva o atual.")
    livros_permitidos: str | None = Field(
        None, max_length=200, pattern=r"^\s*(\d+\s*(,\s*\d+\s*)*)?$",
        description="Ids dos livros exibidos no portal, separados por vírgula (ex.: `147`). Vazio = nenhum livro é exibido. Nulo mantém o atual.")


class LeituraIntegracaoBookstack(BaseModel):
    """Configuração como a API devolve: o token nunca aparece, só se existe."""

    ativo: bool
    url_base: str
    possui_token: bool
    configurada: bool = Field(..., description="Há endereço e token: dá para ler os manuais.")
    livros_permitidos: str = Field(..., description="Ids dos livros exibidos no portal, separados por vírgula (vazio = nenhum).")
    atualizado_em: datetime
    atualizado_por: str


class ResultadoTesteBookstack(BaseModel):
    """Resultado do `POST /api/integracao-bookstack/testar`."""

    sucesso: bool
    mensagem: str
    latencia_ms: int | None = None
    livros_visiveis: int | None = Field(None, description="Quantos livros a conta de serviço enxerga.")


def obter(sessao: Session) -> IntegracaoBookstack:
    """A linha única de configuração (criada vazia se a migração ainda não a trouxe)."""
    config = sessao.get(IntegracaoBookstack, 1)
    # Tabela de uma linha só (id=1). flush insere a linha sem fazer commit, para
    # quem chamou decidir quando gravar de vez.
    if config is None:
        config = IntegracaoBookstack(id=1)
        sessao.add(config)
        sessao.flush()
    return config


def leitura(config: IntegracaoBookstack) -> LeituraIntegracaoBookstack:
    """Converte a configuração gravada na resposta da API, trocando os tokens por "possui_token"."""
    possui = bool(config.token_id_cifrado and config.token_segredo_cifrado)
    return LeituraIntegracaoBookstack(
        ativo=config.ativo, url_base=config.url_base, possui_token=possui, configurada=bool(config.url_base and possui), livros_permitidos=config.livros_permitidos,
        atualizado_em=config.atualizado_em, atualizado_por=config.atualizado_por,
    )


def salvar(sessao: Session, dados: AlteracaoIntegracaoBookstack, autor: str) -> IntegracaoBookstack:
    """Grava a configuração; token em branco mantém o anterior. A auditoria não leva o valor do token."""
    config = obter(sessao)
    config.ativo, config.url_base, config.atualizado_por = dados.ativo, dados.url_base.strip().rstrip("/"), autor
    if dados.token_id:
        config.token_id_cifrado = cifrar_segredo(dados.token_id.strip())
    if dados.token_segredo:
        config.token_segredo_cifrado = cifrar_segredo(dados.token_segredo.strip())
    # Normaliza a lista de livros: tira espaços e itens vazios ("147, ,12" vira "147,12").
    if dados.livros_permitidos is not None:
        config.livros_permitidos = ",".join(parte.strip() for parte in dados.livros_permitidos.split(",") if parte.strip())
    auditar(sessao, autor, "integracao_bookstack.salvar", "Integração BookStack",
            f"ativo={config.ativo} url={config.url_base} livros={config.livros_permitidos or 'todos'} token_novo={bool(dados.token_id or dados.token_segredo)}")
    sessao.commit()
    return config


def tokens(config: IntegracaoBookstack) -> tuple[str, str]:
    """(ID, segredo) decifrados; `ErroBookstack` se a cifra não abre (chave trocada)."""
    try:
        return decifrar_segredo(config.token_id_cifrado), decifrar_segredo(config.token_segredo_cifrado)
    except ErroDecifrarSegredo as erro:
        raise ErroBookstack("O token gravado não pôde ser lido. Informe-o de novo na configuração.") from erro


def testar(config: IntegracaoBookstack, transporte=None) -> ResultadoTesteBookstack:
    """Faz uma listagem mínima no BookStack com a configuração gravada."""
    # Sem endereço ou sem token não há o que testar: responde sem chamar o BookStack.
    if not (config.url_base and config.token_id_cifrado and config.token_segredo_cifrado):
        return ResultadoTesteBookstack(sucesso=False, mensagem="Informe o endereço e o token e salve antes de testar.")
    try:
        token_id, segredo = tokens(config)
        with ClienteBookstack(config.url_base, token_id, segredo, transporte) as bookstack:
            livros = bookstack.testar()
            return ResultadoTesteBookstack(sucesso=True, mensagem="Conexão com o BookStack funcionando.",
                                           latencia_ms=bookstack.latencia_ms, livros_visiveis=livros)
    except ErroBookstack as erro:
        return ResultadoTesteBookstack(sucesso=False, mensagem=erro.mensagem)
