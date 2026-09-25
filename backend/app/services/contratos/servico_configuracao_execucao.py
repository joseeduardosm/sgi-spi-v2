# Criado por José Eduardo Santana Martins
# Este arquivo serve para gerenciar versões de checklist e de formulário de avaliação e os modelos globais.
"""Configuração da execução: versões de checklist e de formulário de avaliação, e modelos globais.

Checklists e formulários funcionam por versões: só uma de cada fica ativa, e versões ativas
não são editadas (duplica-se para criar a próxima). Ao gerar as competências, a versão ativa
é copiada para cada uma; ao ativar uma nova, ela substitui a cópia nas competências que ainda
não passaram daquela etapa.
"""

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
    """Nome de exibição do usuário (nome completo ou, na falta, o login)."""
    return usuario.nome_completo or usuario.login


# ---------------------------------------------------------------------------------------------
# Checklists
# ---------------------------------------------------------------------------------------------

def leitura_checklist(checklist: Checklist) -> LeituraChecklist:
    """Converte o checklist do banco para o formato da API."""
    return LeituraChecklist(
        id=checklist.id, versao=checklist.versao, nome=checklist.nome, ativo=checklist.ativo,
        itens=[LeituraDocumentoChecklist(id=i.id, ordem=i.ordem, nome=i.nome, observacao=i.observacao, obrigatorio=i.obrigatorio) for i in checklist.itens],
        criado_por_nome=checklist.criado_por_nome, criado_em=checklist.criado_em, ativado_em=checklist.ativado_em,
    )


def _checklists(sessao: Session, contrato_id: uuid.UUID) -> list[Checklist]:
    """Versões do checklist do contrato (exceto as excluídas), da mais nova para a mais antiga."""
    return list(
        sessao.scalars(
            select(Checklist)
            .where(Checklist.contrato_id == contrato_id, Checklist.excluido_em.is_(None))
            .order_by(Checklist.versao.desc())
        )
    )


def listar_checklists(sessao: Session, contrato_id: uuid.UUID) -> list[LeituraChecklist]:
    """Versões do checklist do contrato para a aba Checklists."""
    obter_contrato(sessao, contrato_id)
    return [leitura_checklist(c) for c in _checklists(sessao, contrato_id)]


def _proxima_versao(sessao: Session, modelo, contrato_id: uuid.UUID) -> int:
    """Próximo número de versão para checklist ou formulário (maior versão do contrato + 1)."""
    return (sessao.scalar(select(func.max(modelo.versao)).where(modelo.contrato_id == contrato_id)) or 0) + 1


def _obter_checklist(sessao: Session, contrato_id: uuid.UUID, checklist_id: uuid.UUID) -> Checklist:
    """Checklist pelo id, desde que seja do contrato e não esteja excluído."""
    checklist = sessao.get(Checklist, checklist_id)
    if checklist is None or checklist.contrato_id != contrato_id or checklist.excluido_em is not None:
        raise RegistroNaoEncontrado("Checklist")
    return checklist


def criar_checklist(sessao: Session, contrato_id: uuid.UUID, dados: GravacaoChecklist, autor: Usuario) -> None:
    """Cria uma nova versão (inativa) do checklist, com os documentos na ordem enviada."""
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
    """Edita uma versão inativa: substitui nome e lista de documentos."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    checklist = _obter_checklist(sessao, contrato_id, checklist_id)
    if checklist.ativo:
        raise ErroRegraContrato("Um checklist ativo não pode ser editado. Duplique-o para criar uma nova versão.")
    checklist.nome = dados.nome
    # Limpa os documentos antigos (flush grava a remoção) antes de inserir a nova lista
    checklist.itens.clear()
    sessao.flush()
    checklist.itens.extend(ItemChecklist(ordem=n, nome=i.nome, observacao=i.observacao, obrigatorio=i.obrigatorio) for n, i in enumerate(dados.itens, start=1))
    auditar(sessao, autor.login, "contrato.checklist.alterar", f"Contrato {contrato.numero}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id, dados={"versao": checklist.versao, "nome": dados.nome})
    sessao.commit()


def duplicar_checklist(sessao: Session, contrato_id: uuid.UUID, checklist_id: uuid.UUID, autor: Usuario) -> None:
    """Cria uma nova versão com o mesmo conteúdo da versão de origem."""
    origem = _obter_checklist(sessao, contrato_id, checklist_id)
    dados = GravacaoChecklist(nome=origem.nome, itens=[{"nome": i.nome, "observacao": i.observacao, "obrigatorio": i.obrigatorio} for i in origem.itens])
    criar_checklist(sessao, contrato_id, dados, autor)


def excluir_checklist(sessao: Session, contrato_id: uuid.UUID, checklist_id: uuid.UUID, autor: Usuario) -> None:
    """Exclusão lógica de uma versão inativa (ela some da lista, mas fica no banco)."""
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
    # Documentos já anexados na competência, indexados pelo nome (sem diferenciar maiúsculas/espaços)
    anexados = {d.nome.strip().lower(): d for d in competencia.documentos if d.anexo_id}
    competencia.documentos.clear()
    # Recria a lista a partir do checklist, reaproveitando o anexo de um documento com o mesmo nome
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
    # Só uma versão ativa por vez
    for outro in _checklists(sessao, contrato_id):
        outro.ativo = False
    checklist.ativo, checklist.ativado_em = True, agora_utc()
    # Competências que ainda não passaram da etapa do checklist recebem a nova versão
    abertas = [c for c in contrato.competencias if c.etapa_atual in ETAPAS_ANTES_DO_CHECKLIST]
    for competencia in abertas:
        copiar_checklist(competencia, checklist)
        sessao.flush()
    auditar(sessao, autor.login, "contrato.checklist.ativar", f"Contrato {contrato.numero}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id, dados={"versao": checklist.versao, "competencias_atualizadas": len(abertas)})
    sessao.commit()
    return len(abertas)


def checklist_ativo(contrato: Contrato) -> Checklist | None:
    """A versão ativa do checklist do contrato, se houver."""
    return next((c for c in contrato.checklists if c.ativo and c.excluido_em is None), None)


# ---------------------------------------------------------------------------------------------
# Formulários de avaliação
# ---------------------------------------------------------------------------------------------

def definicao_com_ids(definicao: DefinicaoFormulario) -> dict[str, Any]:
    """Gera ids estáveis para grupos e itens (as respostas referenciam o id do item)."""
    # Grupos e itens sem id recebem um identificador curto e aleatório; os que já têm, mantêm
    dados = valor_json(definicao.model_dump())
    for grupo in dados["grupos"]:
        grupo["id"] = grupo.get("id") or uuid.uuid4().hex[:12]
        for item in grupo["itens"]:
            item["id"] = item.get("id") or uuid.uuid4().hex[:12]
    return dados


def leitura_formulario(formulario: FormularioAvaliacao) -> LeituraFormulario:
    """Converte o formulário do banco para o formato da API."""
    return LeituraFormulario(
        id=formulario.id, versao=formulario.versao, nome=formulario.nome, ativo=formulario.ativo, definicao=formulario.definicao,
        criado_por_nome=formulario.criado_por_nome, criado_em=formulario.criado_em, ativado_em=formulario.ativado_em,
    )


def _formularios(sessao: Session, contrato_id: uuid.UUID) -> list[FormularioAvaliacao]:
    """Versões do formulário do contrato, da mais nova para a mais antiga."""
    return list(
        sessao.scalars(select(FormularioAvaliacao).where(FormularioAvaliacao.contrato_id == contrato_id).order_by(FormularioAvaliacao.versao.desc()))
    )


def listar_formularios(sessao: Session, contrato_id: uuid.UUID) -> list[LeituraFormulario]:
    """Versões do formulário para a aba Formulários."""
    obter_contrato(sessao, contrato_id)
    return [leitura_formulario(f) for f in _formularios(sessao, contrato_id)]


def _obter_formulario(sessao: Session, contrato_id: uuid.UUID, formulario_id: uuid.UUID) -> FormularioAvaliacao:
    """Formulário pelo id, desde que seja do contrato."""
    formulario = sessao.get(FormularioAvaliacao, formulario_id)
    if formulario is None or formulario.contrato_id != contrato_id:
        raise RegistroNaoEncontrado("Formulário")
    return formulario


def criar_formulario(sessao: Session, contrato_id: uuid.UUID, dados: GravacaoFormulario, autor: Usuario) -> None:
    """Cria uma nova versão (inativa) do formulário de avaliação."""
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
    """Edita uma versão inativa do formulário."""
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
    """Cria uma nova versão com a mesma definição da versão de origem."""
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
    # Aplica a nova versão só às competências ainda na medição
    aplicadas = 0
    for competencia in contrato.competencias:
        if competencia.etapa_atual != "medicao":
            continue
        # Sem avaliação: cria com a nova definição; com avaliação ainda sem respostas: troca a definição;
        # com respostas: mantém a versão antiga (a avaliação já começou)
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
    """A versão ativa do formulário do contrato, se houver."""
    return next((f for f in contrato.formularios if f.ativo), None)


# ---------------------------------------------------------------------------------------------
# Modelos globais (SuperRoot)
# ---------------------------------------------------------------------------------------------

def _conteudo(dados: GravacaoModelo) -> dict[str, Any]:
    """Conteúdo JSON do modelo: lista de documentos (checklist) ou definição com ids (formulário)."""
    if dados.tipo == "checklist":
        return {"itens": [i.model_dump() for i in dados.itens or []]}
    return definicao_com_ids(dados.definicao)


def leitura_modelo(modelo: ModeloGlobal) -> LeituraModelo:
    """Converte o modelo global para o formato da API."""
    return LeituraModelo(id=modelo.id, tipo=modelo.tipo, nome=modelo.nome, conteudo=modelo.conteudo, ativo=modelo.ativo, atualizado_em=modelo.atualizado_em)


def listar_modelos(sessao: Session, tipo: str | None, somente_ativos: bool) -> list[LeituraModelo]:
    """Modelos globais, opcionalmente filtrados por tipo e só os ativos."""
    consulta = select(ModeloGlobal).order_by(ModeloGlobal.tipo, func.lower(ModeloGlobal.nome))
    if tipo:
        consulta = consulta.where(ModeloGlobal.tipo == tipo)
    if somente_ativos:
        consulta = consulta.where(ModeloGlobal.ativo.is_(True))
    return [leitura_modelo(m) for m in sessao.scalars(consulta)]


def _obter_modelo(sessao: Session, modelo_id: uuid.UUID) -> ModeloGlobal:
    """Modelo pelo id, ou `RegistroNaoEncontrado`."""
    modelo = sessao.get(ModeloGlobal, modelo_id)
    if modelo is None:
        raise RegistroNaoEncontrado("Modelo")
    return modelo


def salvar_modelo(sessao: Session, dados: GravacaoModelo, autor: Usuario, modelo_id: uuid.UUID | None = None) -> ModeloGlobal:
    """Cria (sem `modelo_id`) ou altera um modelo global; o tipo não pode mudar."""
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
    """Exclui o modelo global (as cópias já feitas nos contratos continuam)."""
    modelo = _obter_modelo(sessao, modelo_id)
    auditar(sessao, autor.login, "contrato.modelo.excluir", f"Modelo {modelo.nome}", autor_id=autor.id,
            alvo_tipo="modelo", alvo_id=modelo.id, dados={"tipo": modelo.tipo})
    sessao.delete(modelo)
    sessao.commit()
