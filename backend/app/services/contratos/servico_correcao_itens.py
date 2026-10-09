# Criado por José Eduardo Santana Martins
# Este arquivo serve para as regras da correção de itens do contrato (proposta, prévia, confirmação por outra pessoa e sincronização das competências abertas).
"""Correção de erro de cadastro dos itens depois de geradas as competências.

Princípio: as competências **abertas** (medição não concluída) acompanham o cadastro; as **concluídas** são histórico e nunca mudam. A
correção é **proposta** pelo gestor titular (ou SuperRoot) e só vale depois que **outra pessoa** com permissão de edição confirma.
Preço de item já reajustado e quantidade de item já aditado/suprimido não são corrigidos aqui (seguem o reajuste e o aditamento).
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.contratos import Contrato, CorrecaoItens, HistoricoItemContrato, ItemContrato
from app.models.usuario import Usuario
from app.schemas.contratos.correcoes import GravacaoCorrecao
from app.services import servico_mensagens
from app.services.contratos import calculos, valores
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado, SemPermissaoContrato
from app.services.contratos.servico_competencias import _periodos_por_inicio, competencias_abertas, sincronizar_abertas, sincronizar_competencia
from app.services.contratos.servico_contratos import designacoes_vigentes, eh_administrador, obter_contrato, pode_editar
from app.services.servico_auditoria import auditar

CAMPOS = ("valor_unitario", "quantidade_mensal", "quantidade_total", "unidade_fornecimento", "codigo_classe", "codigo_natureza_despesa", "codigo_siafisico",
          "codigo_catmat_catser")
DECIMAIS = ("valor_unitario", "quantidade_mensal", "quantidade_total")
ZERO = Decimal(0)


def _nome(usuario: Usuario) -> str:
    return usuario.nome_completo or usuario.login


def _texto(valor: Any) -> str:
    return str(valor) if not isinstance(valor, Decimal) else format(valor.normalize(), "f")


def eh_gestor(contrato: Contrato, usuario: Usuario) -> bool:
    return any(d.usuario_id == usuario.id and d.papel == "gestor" for d in designacoes_vigentes(contrato))


def pode_propor(sessao: Session, contrato: Contrato, usuario: Usuario) -> bool:
    """Gestor titular vigente, controle total em Contratos ou SuperRoot."""
    return eh_administrador(sessao, usuario) or eh_gestor(contrato, usuario)


def pode_decidir(sessao: Session, contrato: Contrato, correcao: CorrecaoItens, usuario: Usuario) -> bool:
    """Dois olhos: outra pessoa que não o autor, com permissão de edição no contrato."""
    return correcao.situacao == "pendente" and correcao.autor_id != usuario.id and pode_editar(sessao, contrato, usuario)


def _item_ou_erro(contrato: Contrato, item_id: uuid.UUID) -> ItemContrato:
    item = next((i for i in contrato.itens if i.id == item_id), None)
    if item is None:
        raise ErroRegraContrato("Um dos itens não pertence a este contrato.")
    return item


def _itens_com_reajuste(contrato: Contrato) -> set[uuid.UUID]:
    return {linha.item_id for r in valores._reajustes(contrato) for linha in r.itens}


def _itens_com_alteracao(contrato: Contrato) -> set[uuid.UUID]:
    return {linha.item_id for a in valores._alteracoes(contrato) for linha in a.itens}


def montar_mudancas(contrato: Contrato, dados: GravacaoCorrecao) -> list[dict]:
    """Compara os valores propostos com o cadastro e valida as regras; devolve só o que muda."""
    reajustados, aditados = _itens_com_reajuste(contrato), _itens_com_alteracao(contrato)
    mudancas = []
    for proposto in dados.itens:
        item = _item_ou_erro(contrato, proposto.id)
        campos: dict[str, dict] = {}
        for campo in CAMPOS:
            novo = getattr(proposto, campo)
            if novo is None:
                continue
            atual = getattr(item, campo)
            if (Decimal(novo) != Decimal(atual)) if campo in DECIMAIS else (str(novo).strip() != str(atual)):
                campos[campo] = {"de": _texto(atual), "para": _texto(novo).strip()}
        if not campos:
            continue
        if "valor_unitario" in campos and item.id in reajustados:
            raise ErroRegraContrato(f"O preço de \"{item.descricao}\" já foi reajustado: use o reajuste (ou a repactuação) para mudá-lo.")
        if ("quantidade_mensal" in campos or "quantidade_total" in campos) and item.id in aditados:
            raise ErroRegraContrato(f"A quantidade de \"{item.descricao}\" já foi aditada ou suprimida: use um novo aditamento ou supressão.")
        if "quantidade_total" in campos and item.tipo != "sob_demanda":
            raise ErroRegraContrato(f"\"{item.descricao}\" é contínuo: a quantidade total é calculada (mensal × meses).")
        novo_mensal = Decimal(campos["quantidade_mensal"]["para"]) if "quantidade_mensal" in campos else item.quantidade_mensal
        novo_total = Decimal(campos["quantidade_total"]["para"]) if "quantidade_total" in campos else item.quantidade_total
        if item.tipo == "continuo" and novo_mensal <= 0:
            raise ErroRegraContrato(f"\"{item.descricao}\": item contínuo exige quantidade mensal maior que zero.")
        if item.tipo == "sob_demanda" and novo_total <= 0:
            raise ErroRegraContrato(f"\"{item.descricao}\": item sob demanda exige quantidade total maior que zero.")
        mudancas.append({"item_id": str(item.id), "descricao": item.descricao, "campos": campos})
    if not mudancas:
        raise ErroRegraContrato("Nenhum valor mudou em relação ao cadastro atual.")
    return mudancas


def _copias(contrato: Contrato, mudancas: list[dict]) -> list[ItemContrato]:
    """Itens do contrato com os valores propostos, sem tocar no cadastro (transientes)."""
    por_item = {m["item_id"]: m["campos"] for m in mudancas}
    saida = []
    for item in contrato.itens:
        copia = ItemContrato(**{c.key: getattr(item, c.key) for c in ItemContrato.__mapper__.column_attrs})
        for campo, par in por_item.get(str(item.id), {}).items():
            setattr(copia, campo, Decimal(par["para"]) if campo in DECIMAIS else par["para"])
        saida.append(copia)
    return saida


def previa(contrato: Contrato, mudancas: list[dict]) -> dict:
    """Competências abertas que mudariam e a variação do valor previsto. Não grava nada."""
    copias = _copias(contrato, mudancas)
    periodos = _periodos_por_inicio(contrato)
    linhas, total, fora = [], ZERO, 0
    for c in competencias_abertas(contrato):
        r = sincronizar_competencia(contrato, c, periodos, copias, aplicar=False)
        if r is None:
            fora += 1
            continue
        if not (r["alteradas"] or r["incluidas"] or r["removidas"]):
            continue
        variacao = calculos.arredondar(r["valor_depois"] - r["valor_antes"])
        total += variacao
        linhas.append({"competencia": c.numero_competencia, "identificador": c.identificador, "itens_alterados": r["alteradas"], "itens_incluidos": r["incluidas"],
                       "itens_removidos": r["removidas"], "valor_antes": str(calculos.arredondar(r["valor_antes"])), "valor_depois": str(calculos.arredondar(r["valor_depois"])),
                       "variacao": str(variacao), "medicao_iniciada": c.medicao_iniciada_em is not None, "ciencias_invalidadas": bool(c.ciencias)})
    congeladas = sum(1 for c in contrato.competencias if c.tipo == "regular" and c.medicao_concluida_em is not None)
    avisos = []
    if congeladas:
        avisos.append(f"{congeladas} competência(s) com medição concluída não mudam. Se o preço delas estava errado, use a repactuação ou o ajuste de competência concluída.")
    if fora:
        avisos.append(f"{fora} competência(s) aberta(s) não seguem o calendário atual do contrato e não serão atualizadas.")
    if any(l["ciencias_invalidadas"] for l in linhas):
        avisos.append("As ciências já dadas nas competências afetadas serão invalidadas e a equipe será avisada.")
    return {"competencias_abertas": linhas, "variacao_total": str(calculos.arredondar(total)), "congeladas": congeladas, "fora_do_calendario": fora, "avisos": avisos}


def _equipe_ids(contrato: Contrato) -> set[int]:
    return {d.usuario_id for d in designacoes_vigentes(contrato)} | ({contrato.criador_id} - {None})


def _avisar(sessao: Session, contrato: Contrato, correcao: CorrecaoItens, assunto: str, corpo: str, evento: str, autor: Usuario, extra_ids: set[int] | None = None) -> None:
    servico_mensagens.notificar(
        sessao, sorted(_equipe_ids(contrato) | (extra_ids or set())), assunto, corpo, chave=f"correcao-itens:{correcao.id}:{evento}",
        link=f"/contratos/{contrato.id}?aba=correcoes", contrato_id=contrato.id, email=True, autor=autor)


def listar(sessao: Session, contrato_id: uuid.UUID) -> list[CorrecaoItens]:
    return list(sessao.scalars(select(CorrecaoItens).where(CorrecaoItens.contrato_id == contrato_id).order_by(CorrecaoItens.criado_em.desc())))


def obter_correcao(sessao: Session, contrato_id: uuid.UUID, correcao_id: uuid.UUID) -> CorrecaoItens:
    correcao = sessao.get(CorrecaoItens, correcao_id)
    if correcao is None or correcao.contrato_id != contrato_id:
        raise RegistroNaoEncontrado("Correção")
    return correcao


def calcular_previa(sessao: Session, contrato_id: uuid.UUID, dados: GravacaoCorrecao, autor: Usuario) -> dict:
    contrato = obter_contrato(sessao, contrato_id)
    if not pode_propor(sessao, contrato, autor):
        raise SemPermissaoContrato("Só o gestor titular do contrato ou o SuperRoot propõem correções dos itens.")
    return previa(contrato, montar_mudancas(contrato, dados))


def propor(sessao: Session, contrato_id: uuid.UUID, dados: GravacaoCorrecao, autor: Usuario) -> CorrecaoItens:
    """Registra a proposta (pendente) e avisa a equipe: outra pessoa precisa confirmar."""
    contrato = obter_contrato(sessao, contrato_id)
    if not pode_propor(sessao, contrato, autor):
        raise SemPermissaoContrato("Só o gestor titular do contrato ou o SuperRoot propõem correções dos itens.")
    mudancas = montar_mudancas(contrato, dados)
    correcao = CorrecaoItens(contrato_id=contrato.id, autor_id=autor.id, autor_nome=_nome(autor), justificativa=dados.justificativa.strip(),
                             mudancas=mudancas, previa=previa(contrato, mudancas))
    sessao.add(correcao)
    sessao.flush()
    _avisar(sessao, contrato, correcao, f"Correção de itens para confirmar: contrato {contrato.numero}",
            f"{_nome(autor)} propôs corrigir {len(mudancas)} item(ns) do contrato {contrato.numero}.\n\nJustificativa: {correcao.justificativa}\n\n"
            "Abra a aba Correções do contrato para conferir a prévia e confirmar ou recusar. Quem propõe não pode confirmar a própria correção.", "proposta", autor)
    auditar(sessao, autor.login, "contrato.itens.correcao.propor", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"correcao": str(correcao.id), "itens": len(mudancas)})
    sessao.commit()
    return correcao


def _pendente(sessao: Session, contrato_id: uuid.UUID, correcao_id: uuid.UUID) -> tuple[Contrato, CorrecaoItens]:
    contrato = obter_contrato(sessao, contrato_id)
    correcao = obter_correcao(sessao, contrato_id, correcao_id)
    if correcao.situacao != "pendente":
        raise ErroRegraContrato("Esta correção já foi decidida.", conflito=True)
    return contrato, correcao


def confirmar(sessao: Session, contrato_id: uuid.UUID, correcao_id: uuid.UUID, aprovador: Usuario) -> CorrecaoItens:
    """Segundo par de olhos: grava o cadastro, sobe a versão, registra o histórico e sincroniza as competências abertas."""
    contrato, correcao = _pendente(sessao, contrato_id, correcao_id)
    if correcao.autor_id == aprovador.id:
        raise SemPermissaoContrato("Quem propôs a correção não pode confirmá-la: peça a outra pessoa da equipe.")
    if not pode_decidir(sessao, contrato, correcao, aprovador):
        raise SemPermissaoContrato("Somente integrantes da equipe com permissão de edição, ou o SuperRoot, confirmam a correção.")
    # O cadastro pode ter mudado desde a proposta: cada "de" precisa ser o valor atual
    for m in correcao.mudancas:
        item = _item_ou_erro(contrato, uuid.UUID(m["item_id"]))
        for campo, par in m["campos"].items():
            if _texto(getattr(item, campo)) != par["de"]:
                raise ErroRegraContrato(f"O cadastro de \"{item.descricao}\" mudou depois da proposta. Recuse esta correção e proponha de novo.", conflito=True)
    contrato.versao_cadastro += 1
    for m in correcao.mudancas:
        item = _item_ou_erro(contrato, uuid.UUID(m["item_id"]))
        for campo, par in m["campos"].items():
            setattr(item, campo, Decimal(par["para"]) if campo in DECIMAIS else par["para"])
        sessao.add(HistoricoItemContrato(contrato_id=contrato.id, item_id=item.id, descricao_item=item.descricao, versao_cadastro=contrato.versao_cadastro,
                                         correcao_id=correcao.id, autor_id=correcao.autor_id, autor_nome=correcao.autor_nome, motivo=correcao.justificativa,
                                         campos=m["campos"]))
    correcao.situacao, correcao.decidido_por_id, correcao.decidido_por_nome = "aplicada", aprovador.id, _nome(aprovador)
    correcao.decidido_em, correcao.versao_cadastro = agora_utc(), contrato.versao_cadastro
    sessao.flush()
    mudadas = sincronizar_abertas(contrato)
    invalidadas = [c.numero_competencia for c, r in mudadas if r.get("ciencias_invalidadas")]
    corpo = (f"{_nome(aprovador)} confirmou a correção de itens proposta por {correcao.autor_nome} no contrato {contrato.numero}. "
             f"{len(mudadas)} competência(s) aberta(s) foram atualizadas.")
    if invalidadas:
        corpo += f" As ciências da medição foram invalidadas em: {', '.join(invalidadas)}. Confira os valores e registre a ciência de novo."
    _avisar(sessao, contrato, correcao, f"Correção de itens aplicada: contrato {contrato.numero}", corpo, "aplicada", aprovador, {correcao.autor_id} - {None})
    auditar(sessao, aprovador.login, "contrato.itens.correcao.confirmar", f"Contrato {contrato.numero}", autor_id=aprovador.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"correcao": str(correcao.id), "competencias_atualizadas": len(mudadas), "ciencias_invalidadas": invalidadas})
    sessao.commit()
    return correcao


def recusar(sessao: Session, contrato_id: uuid.UUID, correcao_id: uuid.UUID, usuario: Usuario, motivo: str) -> CorrecaoItens:
    contrato, correcao = _pendente(sessao, contrato_id, correcao_id)
    if not pode_decidir(sessao, contrato, correcao, usuario):
        raise SemPermissaoContrato("Somente outra pessoa da equipe com permissão de edição, ou o SuperRoot, recusa a correção.")
    correcao.situacao, correcao.decidido_por_id, correcao.decidido_por_nome = "recusada", usuario.id, _nome(usuario)
    correcao.decidido_em, correcao.motivo_decisao = agora_utc(), motivo.strip()
    _avisar(sessao, contrato, correcao, f"Correção de itens recusada: contrato {contrato.numero}",
            f"{_nome(usuario)} recusou a correção proposta por {correcao.autor_nome}.\n\nMotivo: {correcao.motivo_decisao}", "recusada", usuario, {correcao.autor_id} - {None})
    auditar(sessao, usuario.login, "contrato.itens.correcao.recusar", f"Contrato {contrato.numero}", autor_id=usuario.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"correcao": str(correcao.id), "motivo": correcao.motivo_decisao})
    sessao.commit()
    return correcao


def cancelar(sessao: Session, contrato_id: uuid.UUID, correcao_id: uuid.UUID, usuario: Usuario) -> CorrecaoItens:
    contrato, correcao = _pendente(sessao, contrato_id, correcao_id)
    if correcao.autor_id != usuario.id and not eh_administrador(sessao, usuario):
        raise SemPermissaoContrato("Só quem propôs, o SuperRoot ou quem tem controle total em Contratos cancela a proposta.")
    correcao.situacao, correcao.decidido_por_id, correcao.decidido_por_nome, correcao.decidido_em = "cancelada", usuario.id, _nome(usuario), agora_utc()
    auditar(sessao, usuario.login, "contrato.itens.correcao.cancelar", f"Contrato {contrato.numero}", autor_id=usuario.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"correcao": str(correcao.id)})
    sessao.commit()
    return correcao


def historico(sessao: Session, contrato_id: uuid.UUID) -> list[HistoricoItemContrato]:
    obter_contrato(sessao, contrato_id)
    return list(sessao.scalars(select(HistoricoItemContrato).where(HistoricoItemContrato.contrato_id == contrato_id).order_by(HistoricoItemContrato.criado_em.desc())))
