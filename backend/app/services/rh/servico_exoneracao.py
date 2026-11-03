# Criado por José Eduardo Santana Martins
# Este arquivo serve para abrir os chamados da exoneração: o inverso da nomeação (desativar a rede, recolher o crachá e assim por diante).
"""Chamados da exoneração.

Quando o RH registra a exoneração (vagar o cargo com o motivo `exoneracao`), esta tela pede às equipes que desfaçam o que a nomeação pediu:
"Criar usuário de rede" vira "Desativar usuário de rede", "Solicitar crachá" vira "Recolher crachá" e assim por diante.
- **Sugestão:** vêm marcados os serviços pedidos na nomeação da pessoa (admissão do SGI). Sem admissão registrada, todos vêm marcados.
- Só depois da virada (Parâmetros dos Chamados > RH, destino `chamados`); antes disso o RH segue pelo formulário de Exoneração do GLPI.
- Uma vez só por exoneração (409 na segunda).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chamados import Chamado
from app.models.rh_admissao import Admissao
from app.models.rh_cargos import Ocupacao
from app.models.rh_pre_cadastro import PreCadastro
from app.models.setor import Setor
from app.models.usuario import Usuario
from app.services.chamados import rh as chamados_rh
from app.services.chamados.parametros import ErroParametro
from app.services.chamados.servico import ErroChamado
from app.services.rh.servico_cargos import CargoNaoEncontrado, ErroRegraCargo
from app.services.servico_auditoria import auditar


def _ocupacao(sessao: Session, ocupacao_id: int) -> Ocupacao:
    ocupacao = sessao.get(Ocupacao, ocupacao_id)
    if ocupacao is None:
        raise CargoNaoEncontrado("Exoneração")
    if ocupacao.motivo_fim != "exoneracao":
        raise ErroRegraCargo("Esta saída do cargo não foi registrada como exoneração.", conflito=True)
    return ocupacao


def sugestao(sessao: Session, usuario_id: int) -> tuple[dict[str, bool], bool]:
    """Os serviços pedidos na nomeação da pessoa (e `True`); sem admissão registrada no SGI, todos (e `False`)."""
    admissao = sessao.scalar(select(Admissao).join(PreCadastro, PreCadastro.id == Admissao.pre_cadastro_id)
                             .where(PreCadastro.usuario_id == usuario_id).order_by(Admissao.id.desc()))
    pedidos = (admissao.solicitacoes or {}) if admissao is not None else {}
    if not any(pedidos.values()):
        return {chave: True for chave in chamados_rh.SERVICOS_EXONERACAO}, False
    return {chave: bool(pedidos.get(chave)) for chave in chamados_rh.SERVICOS_EXONERACAO}, True


def leitura(sessao: Session, ocupacao_id: int) -> dict:
    ocupacao = _ocupacao(sessao, ocupacao_id)
    pessoa = sessao.get(Usuario, ocupacao.usuario_id)
    setor = sessao.get(Setor, ocupacao.cargo.setor_id)
    marcados, da_nomeacao = sugestao(sessao, ocupacao.usuario_id)
    return {
        "ocupacao_id": ocupacao.id, "usuario_id": ocupacao.usuario_id, "nome": (pessoa.nome_completo or pessoa.login) if pessoa else "",
        "login": pessoa.login if pessoa else "", "cargo_rotulo": ocupacao.cargo.rotulo, "setor_nome": setor.nome if setor else "",
        "fim": ocupacao.fim, "ato_fim": ocupacao.ato_fim, "destino": chamados_rh.destino(sessao),
        "servicos": chamados_rh.SERVICOS_EXONERACAO, "sugestao": marcados, "sugestao_da_nomeacao": da_nomeacao,
        "chamados": chamados_rh.chamados_da_exoneracao(sessao, ocupacao.id),
    }


def abrir(sessao: Session, ocupacao_id: int, solicitacoes: dict[str, bool], observacoes: str, autor: Usuario) -> dict:
    """Abre um chamado por serviço marcado. Sem commit (a rota grava)."""
    ocupacao = _ocupacao(sessao, ocupacao_id)
    if chamados_rh.destino(sessao) != "chamados":
        raise ErroRegraCargo("Enquanto os chamados do RH forem para o GLPI, a exoneração segue pelo formulário de Exoneração do GLPI.", conflito=True)
    if sessao.scalar(select(Chamado.id).where(Chamado.rh_ocupacao_id == ocupacao.id).limit(1)) is not None:
        raise ErroRegraCargo("Os chamados desta exoneração já foram abertos.", conflito=True)
    desconhecidas = set(solicitacoes) - set(chamados_rh.SERVICOS_EXONERACAO)
    if desconhecidas:
        raise ErroRegraCargo("Serviço desconhecido: " + ", ".join(sorted(desconhecidas)) + ".")
    pedidos = {k: rotulo for k, rotulo in chamados_rh.SERVICOS_EXONERACAO.items() if solicitacoes.get(k)}
    if not pedidos:
        raise ErroRegraCargo("Marque pelo menos um serviço para pedir.")
    pessoa = sessao.get(Usuario, ocupacao.usuario_id)
    setor = sessao.get(Setor, ocupacao.cargo.setor_id)
    dados = chamados_rh.DadosExoneracao(
        nome=(pessoa.nome_completo or pessoa.login) if pessoa else "", login=pessoa.login if pessoa else "", cargo=ocupacao.cargo.rotulo,
        lotacao=setor.nome if setor else "", saida=ocupacao.fim.strftime("%d/%m/%Y") if ocupacao.fim else "", ato=ocupacao.ato_fim or "", observacoes=observacoes,
    )
    try:
        criados = chamados_rh.abrir_exoneracao(sessao, ocupacao.id, pedidos, dados, autor)
    except (ErroParametro, ErroChamado) as erro:
        sessao.rollback()
        raise ErroRegraCargo(str(erro), conflito=getattr(erro, "status", 400) == 409) from erro
    auditar(sessao, autor.login, "rh.exoneracao.chamados", dados.nome, f"{len(criados)} chamado(s): " + ", ".join(str(c.numero) for c in criados),
            autor_id=autor.id, dados={"ocupacao_id": ocupacao.id})
    return leitura(sessao, ocupacao.id)
