"""Configuração da execução: versões de checklist e de formulário de avaliação, e modelos globais."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.contratos import (
    AvaliacaoCompetencia,
    Checklist,
    Competencia,
    Contrato,
    DocumentoMensal,
    FormularioAvaliacao,
    ItemChecklist,
    ModeloGlobal,
)
from app.models.usuario import Usuario
from app.schemas.contratos.execucao import (
    DefinicaoFormulario,
    GravacaoChecklist,
    GravacaoFormulario,
    GravacaoModelo,
    LeituraChecklist,
    LeituraDocumentoChecklist,
    LeituraFormulario,
    LeituraModelo,
)
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado
from app.services.contratos.servico_contratos import exigir_edicao, obter_contrato
from app.services.servico_auditoria import auditar, valor_json

# Etapas em que a competência ainda recebe a nova versão do checklist
ETAPAS_ANTES_DO_CHECKLIST = ("medicao", "avaliacao", "nota_fiscal", "cadin", "checklist")


def _nome(usuario: Usuario) -> str:
    return usuario.nome_completo or usuario.login


# ---------------------------------------------------------------------------------------------
# Checklists
# ---------------------------------------------------------------------------------------------

def leitura_checklist(checklist: Checklist) -> LeituraChecklist:
    return LeituraChecklist(
        id=checklist.id, versao=checklist.versao, nome=checklist.nome, ativo=checklist.ativo,
        itens=[LeituraDocumentoChecklist(id=i.id, ordem=i.ordem, nome=i.nome, observacao=i.observacao, obrigatorio=i.obrigatorio) for i in checklist.itens],
        criado_por_nome=checklist.criado_por_nome, criado_em=checklist.criado_em, ativado_em=checklist.ativado_em,
    )


def _checklists(sessao: Session, contrato_id: uuid.UUID) -> list[Checklist]:
    return list(
        sessao.scalars(
            select(Checklist)
            .where(Checklist.contrato_id == contrato_id, Checklist.excluido_em.is_(None))
            .order_by(Checklist.versao.desc())
        )
    )


def listar_checklists(sessao: Session, contrato_id: uuid.UUID) -> list[LeituraChecklist]:
    obter_contrato(sessao, contrato_id)
    return [leitura_checklist(c) for c in _checklists(sessao, contrato_id)]


def _proxima_versao(sessao: Session, modelo, contrato_id: uuid.UUID) -> int:
    return (sessao.scalar(select(func.max(modelo.versao)).where(modelo.contrato_id == contrato_id)) or 0) + 1


def _obter_checklist(sessao: Session, contrato_id: uuid.UUID, checklist_id: uuid.UUID) -> Checklist:
    checklist = sessao.get(Checklist, checklist_id)
    if checklist is None or checklist.contrato_id != contrato_id or checklist.excluido_em is not None:
        raise RegistroNaoEncontrado("Checklist")
    return checklist


def criar_checklist(sessao: Session, contrato_id: uuid.UUID, dados: GravacaoChecklist, autor: Usuario) -> None:
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    checklist = Checklist(
        contrato_id=contrato.id, versao=_proxima_versao(sessao, Checklist, contrato.id), nome=dados.nome,
        criado_por_id=autor.id, criado_por_nome=_nome(autor),
    )
    checklist.itens = [ItemChecklist(ordem=n, nome=i.nome, observacao=i.observacao, obrigatorio=i.obrigatorio) for n, i in enumerate(dados.itens, start=1)]
    sessao.add(checklist)
    auditar(sessao, autor.login, "contrato.checklist.criar", f"Contrato {contrato.numero}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id, dados={"versao": checklist.versao, "nome": dados.nome, "itens": len(dados.itens)})
    sessao.commit()


def alterar_checklist(sessao: Session, contrato_id: uuid.UUID, checklist_id: uuid.UUID, dados: GravacaoChecklist, autor: Usuario) -> None:
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    checklist = _obter_checklist(sessao, contrato_id, checklist_id)
    if checklist.ativo:
        raise ErroRegraContrato("Um checklist ativo não pode ser editado. Duplique-o para criar uma nova versão.")
    checklist.nome = dados.nome
    checklist.itens.clear()
    sessao.flush()
    checklist.itens.extend(ItemChecklist(ordem=n, nome=i.nome, observacao=i.observacao, obrigatorio=i.obrigatorio) for n, i in enumerate(dados.itens, start=1))
    auditar(sessao, autor.login, "contrato.checklist.alterar", f"Contrato {contrato.numero}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id, dados={"versao": checklist.versao, "nome": dados.nome})
    sessao.commit()


def duplicar_checklist(sessao: Session, contrato_id: uuid.UUID, checklist_id: uuid.UUID, autor: Usuario) -> None:
    origem = _obter_checklist(sessao, contrato_id, checklist_id)
    dados = GravacaoChecklist(nome=origem.nome, itens=[{"nome": i.nome, "observacao": i.observacao, "obrigatorio": i.obrigatorio} for i in origem.itens])
    criar_checklist(sessao, contrato_id, dados, autor)


def excluir_checklist(sessao: Session, contrato_id: uuid.UUID, checklist_id: uuid.UUID, autor: Usuario) -> None:
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    checklist = _obter_checklist(sessao, contrato_id, checklist_id)
    if checklist.ativo:
        raise ErroRegraContrato("Um checklist ativo não pode ser excluído.")
    checklist.excluido_em = agora_utc()
    auditar(sessao, autor.login, "contrato.checklist.excluir", f"Contrato {contrato.numero}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id, dados={"versao": checklist.versao})
    sessao.commit()


def copiar_checklist(competencia: Competencia, checklist: Checklist) -> None:
    """Fotografia do checklist na competência. Documentos já anexados com o mesmo nome são mantidos."""
    anexados = {d.nome.strip().lower(): d for d in competencia.documentos if d.anexo_id}
    competencia.documentos.clear()
    for item in checklist.itens:
        anterior = anexados.get(item.nome.strip().lower())
        competencia.documentos.append(
            DocumentoMensal(
                checklist_id=checklist.id, ordem=item.ordem, nome=item.nome, observacao=item.observacao, obrigatorio=item.obrigatorio,
                anexo_id=anterior.anexo_id if anterior else None,
                enviado_em=anterior.enviado_em if anterior else None,
                enviado_por_id=anterior.enviado_por_id if anterior else None,
            )
        )


def ativar_checklist(sessao: Session, contrato_id: uuid.UUID, checklist_id: uuid.UUID, autor: Usuario) -> int:
    """Ativa a versão e a aplica às competências que ainda não passaram do checklist. Devolve quantas."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    checklist = _obter_checklist(sessao, contrato_id, checklist_id)
    for outro in _checklists(sessao, contrato_id):
        outro.ativo = False
    checklist.ativo, checklist.ativado_em = True, agora_utc()
    abertas = [c for c in contrato.competencias if c.etapa_atual in ETAPAS_ANTES_DO_CHECKLIST]
    for competencia in abertas:
        copiar_checklist(competencia, checklist)
        sessao.flush()
    auditar(sessao, autor.login, "contrato.checklist.ativar", f"Contrato {contrato.numero}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id, dados={"versao": checklist.versao, "competencias_atualizadas": len(abertas)})
    sessao.commit()
    return len(abertas)


def checklist_ativo(contrato: Contrato) -> Checklist | None:
    return next((c for c in contrato.checklists if c.ativo and c.excluido_em is None), None)


# ---------------------------------------------------------------------------------------------
# Formulários de avaliação
# ---------------------------------------------------------------------------------------------

def definicao_com_ids(definicao: DefinicaoFormulario) -> dict[str, Any]:
    """Gera ids estáveis para grupos e itens (as respostas referenciam o id do item)."""
    dados = valor_json(definicao.model_dump())
    for grupo in dados["grupos"]:
        grupo["id"] = grupo.get("id") or uuid.uuid4().hex[:12]
        for item in grupo["itens"]:
            item["id"] = item.get("id") or uuid.uuid4().hex[:12]
    return dados


def leitura_formulario(formulario: FormularioAvaliacao) -> LeituraFormulario:
    return LeituraFormulario(
        id=formulario.id, versao=formulario.versao, nome=formulario.nome, ativo=formulario.ativo, definicao=formulario.definicao,
        criado_por_nome=formulario.criado_por_nome, criado_em=formulario.criado_em, ativado_em=formulario.ativado_em,
    )


def _formularios(sessao: Session, contrato_id: uuid.UUID) -> list[FormularioAvaliacao]:
    return list(
        sessao.scalars(select(FormularioAvaliacao).where(FormularioAvaliacao.contrato_id == contrato_id).order_by(FormularioAvaliacao.versao.desc()))
    )


def listar_formularios(sessao: Session, contrato_id: uuid.UUID) -> list[LeituraFormulario]:
    obter_contrato(sessao, contrato_id)
    return [leitura_formulario(f) for f in _formularios(sessao, contrato_id)]


def _obter_formulario(sessao: Session, contrato_id: uuid.UUID, formulario_id: uuid.UUID) -> FormularioAvaliacao:
    formulario = sessao.get(FormularioAvaliacao, formulario_id)
    if formulario is None or formulario.contrato_id != contrato_id:
        raise RegistroNaoEncontrado("Formulário")
    return formulario


def criar_formulario(sessao: Session, contrato_id: uuid.UUID, dados: GravacaoFormulario, autor: Usuario) -> None:
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    formulario = FormularioAvaliacao(
        contrato_id=contrato.id, versao=_proxima_versao(sessao, FormularioAvaliacao, contrato.id), nome=dados.nome,
        definicao=definicao_com_ids(dados.definicao), criado_por_id=autor.id, criado_por_nome=_nome(autor),
    )
    sessao.add(formulario)
    auditar(sessao, autor.login, "contrato.formulario.criar", f"Contrato {contrato.numero}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id, dados={"versao": formulario.versao, "nome": dados.nome})
    sessao.commit()


def alterar_formulario(sessao: Session, contrato_id: uuid.UUID, formulario_id: uuid.UUID, dados: GravacaoFormulario, autor: Usuario) -> None:
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    formulario = _obter_formulario(sessao, contrato_id, formulario_id)
    if formulario.ativo:
        raise ErroRegraContrato("Um formulário ativo não pode ser editado. Duplique-o para criar uma nova versão.")
    formulario.nome, formulario.definicao = dados.nome, definicao_com_ids(dados.definicao)
    auditar(sessao, autor.login, "contrato.formulario.alterar", f"Contrato {contrato.numero}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id, dados={"versao": formulario.versao, "nome": dados.nome})
    sessao.commit()


def duplicar_formulario(sessao: Session, contrato_id: uuid.UUID, formulario_id: uuid.UUID, autor: Usuario) -> None:
    origem = _obter_formulario(sessao, contrato_id, formulario_id)
    criar_formulario(sessao, contrato_id, GravacaoFormulario(nome=origem.nome, definicao=origem.definicao), autor)


def ativar_formulario(sessao: Session, contrato_id: uuid.UUID, formulario_id: uuid.UUID, autor: Usuario) -> int:
    """Ativa a versão e a aplica às competências ainda na medição (avaliação não iniciada)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    formulario = _obter_formulario(sessao, contrato_id, formulario_id)
    for outro in _formularios(sessao, contrato_id):
        outro.ativo = False
    formulario.ativo, formulario.ativado_em = True, agora_utc()
    aplicadas = 0
    for competencia in contrato.competencias:
        if competencia.etapa_atual != "medicao":
            continue
        avaliacao = sessao.scalar(select(AvaliacaoCompetencia).where(AvaliacaoCompetencia.competencia_id == competencia.id))
        if avaliacao is None:
            sessao.add(AvaliacaoCompetencia(competencia_id=competencia.id, formulario_id=formulario.id, definicao=formulario.definicao))
        elif not avaliacao.respostas_iniciais:
            avaliacao.formulario_id, avaliacao.definicao = formulario.id, formulario.definicao
        else:
            continue
        aplicadas += 1
    auditar(sessao, autor.login, "contrato.formulario.ativar", f"Contrato {contrato.numero}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id, dados={"versao": formulario.versao, "competencias_atualizadas": aplicadas})
    sessao.commit()
    return aplicadas


def formulario_ativo(contrato: Contrato) -> FormularioAvaliacao | None:
    return next((f for f in contrato.formularios if f.ativo), None)


# ---------------------------------------------------------------------------------------------
# Modelos globais (SuperRoot)
# ---------------------------------------------------------------------------------------------

def _conteudo(dados: GravacaoModelo) -> dict[str, Any]:
    if dados.tipo == "checklist":
        return {"itens": [i.model_dump() for i in dados.itens or []]}
    return definicao_com_ids(dados.definicao)


def leitura_modelo(modelo: ModeloGlobal) -> LeituraModelo:
    return LeituraModelo(id=modelo.id, tipo=modelo.tipo, nome=modelo.nome, conteudo=modelo.conteudo, ativo=modelo.ativo, atualizado_em=modelo.atualizado_em)


def listar_modelos(sessao: Session, tipo: str | None, somente_ativos: bool) -> list[LeituraModelo]:
    consulta = select(ModeloGlobal).order_by(ModeloGlobal.tipo, func.lower(ModeloGlobal.nome))
    if tipo:
        consulta = consulta.where(ModeloGlobal.tipo == tipo)
    if somente_ativos:
        consulta = consulta.where(ModeloGlobal.ativo.is_(True))
    return [leitura_modelo(m) for m in sessao.scalars(consulta)]


def _obter_modelo(sessao: Session, modelo_id: uuid.UUID) -> ModeloGlobal:
    modelo = sessao.get(ModeloGlobal, modelo_id)
    if modelo is None:
        raise RegistroNaoEncontrado("Modelo")
    return modelo


def salvar_modelo(sessao: Session, dados: GravacaoModelo, autor: Usuario, modelo_id: uuid.UUID | None = None) -> ModeloGlobal:
    modelo = _obter_modelo(sessao, modelo_id) if modelo_id else ModeloGlobal(tipo=dados.tipo)
    if modelo_id and modelo.tipo != dados.tipo:
        raise ErroRegraContrato("O tipo do modelo não pode ser alterado.")
    modelo.nome, modelo.conteudo, modelo.ativo = dados.nome, _conteudo(dados), dados.ativo
    if modelo_id is None:
        sessao.add(modelo)
    sessao.flush()
    auditar(sessao, autor.login, "contrato.modelo.salvar", f"Modelo {dados.nome}", autor_id=autor.id,
            alvo_tipo="modelo", alvo_id=modelo.id, dados={"tipo": dados.tipo, "nome": dados.nome})
    sessao.commit()
    return modelo


def excluir_modelo(sessao: Session, modelo_id: uuid.UUID, autor: Usuario) -> None:
    modelo = _obter_modelo(sessao, modelo_id)
    auditar(sessao, autor.login, "contrato.modelo.excluir", f"Modelo {modelo.nome}", autor_id=autor.id,
            alvo_tipo="modelo", alvo_id=modelo.id, dados={"tipo": modelo.tipo})
    sessao.delete(modelo)
    sessao.commit()
