# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras da etapa "Retenção de Tributos": Financeiro, conferências e gravação.
"""Etapa 4 da competência: retenção de tributos.

Depois que a equipe junta a nota fiscal (PDF + XML), o Financeiro — usuários do setor `SETOR_FINANCEIRO`
("Diretoria de Orçamento e Finanças") e dos setores filhos, por participação no setor ou pelo Departamento do
perfil — confere a nota lida do XML, confirma as retenções (IR, INSS, ISS, PIS, COFINS e CSLL) e registra a
conferência. A equipe do contrato e o SuperRoot também podem fazer a etapa.

Conferências automáticas (✓/⚠) ajudam o Financeiro: emitente = contratada do contrato, tomador = SPI, nota
autorizada, valor × valor autorizado da medição, competência e código do serviço. A compatibilidade da
discriminação com o objeto é confirmada manualmente (obrigatória para salvar).
"""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.core.configuracao import obter_configuracao
from app.models.contratos import Competencia, Contrato
from app.models.setor import MembroSetor, Setor
from app.models.usuario import Usuario
from app.services import servico_anexos
from app.services.contratos import documentos_execucao
from app.services.contratos.erros import ErroRegraContrato, SemPermissaoContrato
from app.services.contratos.servico_contratos import obter_contrato, pode_editar
from app.services.servico_auditoria import auditar

ZERO = Decimal(0)
TRIBUTOS = ("ir", "inss", "iss", "pis", "cofins", "csll")
ROTULOS_TRIBUTO = {"ir": "IR", "inss": "INSS", "iss": "ISS", "pis": "PIS", "cofins": "COFINS", "csll": "CSLL"}


@dataclass(frozen=True)
class Conferencia:
    """Resultado de uma conferência da nota: `ok`, `alerta` (conferir) ou `info` (sem como verificar)."""
    descricao: str
    situacao: str
    detalhe: str


# --- Financeiro ----------------------------------------------------------------------------------

def setores_financeiro(sessao: Session) -> list[Setor]:
    """O setor do Financeiro (pelo nome configurado) e todos os seus descendentes."""
    nome = obter_configuracao().setor_financeiro.strip().lower()
    todos = list(sessao.scalars(select(Setor)))
    raiz = [s for s in todos if s.nome.strip().lower() == nome]
    resultado, fila = list(raiz), [s.id for s in raiz]
    while fila:
        pai = fila.pop()
        for filho in (s for s in todos if s.setor_pai_id == pai):
            resultado.append(filho)
            fila.append(filho.id)
    return resultado


def usuarios_financeiro(sessao: Session) -> list[Usuario]:
    """Usuários ativos do Financeiro: membros dos setores ou com um deles como Departamento do perfil."""
    setores = setores_financeiro(sessao)
    if not setores:
        return []
    ids = [s.id for s in setores]
    nomes = [s.nome.strip().lower() for s in setores]
    membros = select(MembroSetor.usuario_id).where(MembroSetor.setor_id.in_(ids))
    return list(sessao.scalars(
        select(Usuario).where(Usuario.ativo.is_(True), Usuario.id.in_(membros) | func.lower(func.trim(Usuario.departamento)).in_(nomes))
    ))


def grupos_financeiro(sessao: Session) -> list[dict]:
    """Usuários ativos com e-mail do Financeiro, agrupados por setor (raiz e subsetores), com o caminho `DOF › Subsetor`."""
    setores = setores_financeiro(sessao)
    por_id = {s.id: s for s in setores}

    def caminho(setor: Setor) -> str:
        partes, atual = [setor.nome], setor
        while atual.setor_pai_id in por_id:
            atual = por_id[atual.setor_pai_id]
            partes.append(atual.nome)
        return " › ".join(reversed(partes))

    grupos = []
    for setor in setores:
        membros = select(MembroSetor.usuario_id).where(MembroSetor.setor_id == setor.id)
        usuarios = sessao.scalars(select(Usuario).where(Usuario.ativo.is_(True), Usuario.email != "",
                                                        Usuario.id.in_(membros) | (func.lower(func.trim(Usuario.departamento)) == setor.nome.strip().lower())).order_by(Usuario.nome_completo))
        lista = [{"id": u.id, "nome": u.nome_completo or u.login, "email": u.email, "cargo": u.cargo or ""} for u in usuarios]
        if lista:
            grupos.append({"setor_id": setor.id, "setor": caminho(setor), "usuarios": lista})
    return sorted(grupos, key=lambda g: g["setor"])


def eh_financeiro(sessao: Session, usuario: Usuario) -> bool:
    return any(u.id == usuario.id for u in usuarios_financeiro(sessao))


def pode_conferir(sessao: Session, contrato: Contrato, usuario: Usuario) -> bool:
    """SuperRoot, quem edita o contrato (criador/equipe) ou o Financeiro."""
    return usuario.superusuario or pode_editar(sessao, contrato, usuario) or eh_financeiro(sessao, usuario)


# --- Conferências automáticas --------------------------------------------------------------------

def _cnpj(valor: str | None) -> str:
    d = "".join(c for c in (valor or "") if c.isdigit())
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else (d or "não informado")


def conferencias(contrato: Contrato, competencia: Competencia, dados: dict | None, valor_esperado: Decimal | None,
                 valor_total: Decimal | None = None) -> list[Conferencia]:
    """Conferências de uma nota (dados lidos do XML).

    `valor_esperado`: valor autorizado, só para a primeira nota. Ele é comparado com `valor_total` (a soma de todas as
    notas da competência) ou, sem ele, com o bruto desta nota.
    """
    if not dados:
        return []
    lista = []
    emitente, tomador = dados.get("emitente") or {}, dados.get("tomador") or {}
    contratada = "".join(c for c in contrato.empresa.cnpj if c.isdigit())
    lista.append(Conferencia(
        "Emitente = empresa contratada", "ok" if emitente.get("cnpj") == contratada else "alerta",
        f"{emitente.get('razao_social') or '—'} ({_cnpj(emitente.get('cnpj'))}); contratada: {contrato.empresa.razao_social} ({_cnpj(contratada)})",
    ))
    tomador_esperado = obter_configuracao().tomador_cnpj
    lista.append(Conferencia(
        "Tomador = SPI", "ok" if tomador.get("cnpj") == tomador_esperado else "alerta",
        f"{tomador.get('razao_social') or '—'} ({_cnpj(tomador.get('cnpj'))}); esperado {_cnpj(tomador_esperado)}",
    ))
    autorizada = dados.get("autorizada")
    lista.append(Conferencia(
        "Nota autorizada", "ok" if autorizada else ("alerta" if autorizada is False else "info"),
        dados.get("situacao") or ("Sem protocolo de autorização no XML" if autorizada is None else ""),
    ))
    if valor_esperado is not None:
        bruto = valor_total if valor_total is not None else Decimal(dados.get("valor_bruto") or "0")
        lista.append(Conferencia(
            "Valor × valor autorizado da medição", "ok" if bruto == valor_esperado else "alerta",
            f"{'Notas' if valor_total is not None else 'Nota'}: {documentos_execucao.moeda(bruto)}; autorizado (medido × % da avaliação): {documentos_execucao.moeda(valor_esperado)}"
            + (f"; diferença {documentos_execucao.moeda(bruto - valor_esperado)}" if bruto != valor_esperado else ""),
        ))
    competencia_nota = dados.get("competencia")
    if competencia_nota:
        mesmo = date.fromisoformat(competencia_nota).strftime("%Y-%m") == competencia.competencia.strftime("%Y-%m")
        lista.append(Conferencia("Competência", "ok" if mesmo else "alerta",
                                 f"Nota: {date.fromisoformat(competencia_nota):%m/%Y}; execução: {competencia.competencia:%m/%Y}"))
    else:
        emissao = f"; emissão em {date.fromisoformat(dados['emissao']):%d/%m/%Y}" if dados.get("emissao") else ""
        lista.append(Conferencia("Competência", "info", f"Não informada na nota ({dados.get('modelo_rotulo')}){emissao}"))
    codigo = dados.get("codigo_servico")
    lista.append(Conferencia("Código do serviço (guia de ISS)", "ok" if codigo else "info",
                             codigo or f"Não informado na nota ({dados.get('modelo_rotulo')})"))
    lista.append(Conferencia("Discriminação compatível com o objeto", "info", "Conferência manual: marque a confirmação ao salvar."))
    return lista


def valor_autorizado(competencia: Competencia) -> Decimal:
    """Medido × % liberado − desconto de reajuste (a regra fica em `servico_competencias`)."""
    from app.services.contratos.servico_competencias import valor_autorizado as calcular

    return calcular(competencia)


# --- Gravação ------------------------------------------------------------------------------------

def salvar_retencao(sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, retencoes: dict[uuid.UUID, dict[str, Decimal]],
                    discriminacao_conferida: bool, autor: Usuario) -> Competencia:
    """Grava as retenções conferidas de cada nota, gera o PDF da conferência e conclui a etapa (CADIN e checklist correm em paralelo)."""
    from app.services.contratos.servico_competencias import _carregar_competencia, _validar_retencoes, concluir_etapa_paralela, etapas_abertas, total_bruto_notas

    contrato = obter_contrato(sessao, contrato_id)
    if not pode_conferir(sessao, contrato, autor):
        raise SemPermissaoContrato("A retenção de tributos é conferida pelo Financeiro, pela equipe do contrato ou pelo SuperRoot.")
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    if "retencao" not in etapas_abertas(competencia):
        raise ErroRegraContrato("A retenção de tributos não está aberta nesta competência (já conferida ou a nota fiscal ainda não foi juntada).")
    if not discriminacao_conferida:
        raise ErroRegraContrato("Confirme que a discriminação dos serviços é compatível com o objeto do contrato.")
    notas = {n.id: n for n in competencia.notas_fiscais}
    if set(retencoes) - set(notas):
        raise ErroRegraContrato("Há retenções de uma nota que não pertence a esta competência.")
    for nota in notas.values():
        if nota.id not in retencoes:
            raise ErroRegraContrato(f"Informe as retenções da {nota.rotulo}.")
        _validar_retencoes(retencoes[nota.id], nota.valor_bruto or ZERO, nota.rotulo)
    for nota in notas.values():
        for tributo in TRIBUTOS:
            setattr(nota, f"retencao_{tributo}", retencoes[nota.id].get(tributo, ZERO))
    competencia.retencao_discriminacao_conferida = True
    competencia.retencao_por_id, competencia.retencao_por_nome = autor.id, autor.nome_completo or autor.login
    competencia.retencao_concluida_em = agora_utc()
    total, esperado = total_bruto_notas(competencia), valor_autorizado(competencia)
    pdf = documentos_execucao.relatorio_retencao(
        contrato, competencia,
        [conferencias(contrato, competencia, n.dados_xml, esperado if i == 0 else None, total) for i, n in enumerate(competencia.notas_fiscais)],
        autor.nome_completo or autor.login,
    )
    competencia.retencao_pdf_anexo = servico_anexos.guardar_pdf_gerado(
        sessao, pdf, f"retencao_{contrato.numero.replace('/', '_')}_{competencia.identificador}.pdf", "contrato-execucao-retencao", autor.id,
        contrato_id=contrato.id,
    )
    # CADIN e checklist correm em paralelo: com os três concluídos, o consolidado é liberado
    concluir_etapa_paralela(competencia, "retencao")
    from app.services.contratos import avisos
    avisos.retencao_conferida(sessao, contrato, competencia, autor)
    auditar(
        sessao, autor.login, "contrato.execucao.retencao", f"Contrato {contrato.numero} · {competencia.numero_competencia}", autor_id=autor.id,
        alvo_tipo="contrato", alvo_id=contrato.id,
        dados={"competencia": competencia.competencia, "notas": {nota.rotulo: retencoes[nota.id] for nota in competencia.notas_fiscais}},
    )
    from app.services.contratos.servico_competencias import sincronizar_tarefas
    sincronizar_tarefas(sessao, competencia, autor)
    sessao.commit()
    return competencia


def recusar_nota(sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, justificativa: str, autor: Usuario):
    """O Financeiro recusa a(s) nota(s) fiscal(is) na etapa de retenção, com justificativa.

    Guarda o retrato das notas e o PDF da recusa; a competência volta para a etapa da nota fiscal (que fica aberta para juntar outra nota,
    sem limite de ciclos). O CADIN e o checklist já feitos são mantidos: só a retenção precisa ser refeita. Devolve a `RecusaNota`.
    """
    from app.models.contratos.execucao import RecusaNota
    from app.services.contratos import avisos
    from app.services.contratos.servico_competencias import _carregar_competencia, etapas_abertas

    contrato = obter_contrato(sessao, contrato_id)
    if not pode_conferir(sessao, contrato, autor):
        raise SemPermissaoContrato("A nota fiscal é recusada pelo Financeiro, pela equipe do contrato ou pelo SuperRoot.")
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    if "retencao" not in etapas_abertas(competencia):
        raise ErroRegraContrato("A nota só pode ser recusada com a retenção de tributos aberta (nota juntada e ainda não conferida).")
    justificativa = (justificativa or "").strip()
    if len(justificativa) < 10:
        raise ErroRegraContrato("Informe a justificativa da recusa (pelo menos 10 caracteres).")
    nome = autor.nome_completo or autor.login
    recusa = RecusaNota(
        competencia_id=competencia.id, ordem=len(competencia.recusas) + 1, justificativa=justificativa, recusada_por_id=autor.id,
        recusada_por_nome=nome, recusada_em=agora_utc(),
        notas=[{"rotulo": n.rotulo, "numero": n.numero, "valor_bruto": str(n.valor_bruto) if n.valor_bruto is not None else None, "chave": n.chave,
                "anexo_id": str(n.anexo_id) if n.anexo_id else None, "xml_anexo_id": str(n.xml_anexo_id) if n.xml_anexo_id else None}
               for n in competencia.notas_fiscais],
    )
    competencia.recusas.append(recusa)
    sessao.flush()
    pdf = documentos_execucao.relatorio_recusa(contrato, competencia, recusa, nome)
    recusa.pdf_anexo = servico_anexos.guardar_pdf_gerado(
        sessao, pdf, f"recusa{recusa.ordem}_{contrato.numero.replace('/', '_')}_{competencia.identificador}.pdf", "contrato-execucao-recusa", autor.id,
        contrato_id=contrato.id,
    )
    # A nota recusada sai da competência; a etapa da nota fiscal reabre. CADIN, checklist e seus anexos ficam como estavam.
    competencia.notas_fiscais.clear()
    competencia.nf_concluida_em = competencia.origem_valor_nf = None
    competencia.retencao_concluida_em, competencia.retencao_pdf_anexo_id = None, None
    competencia.retencao_por_id, competencia.retencao_por_nome, competencia.retencao_discriminacao_conferida = None, "", False
    competencia.etapa_atual = "nota_fiscal"
    avisos.nota_recusada(sessao, contrato, competencia, recusa, autor)
    auditar(
        sessao, autor.login, "contrato.execucao.retencao.recusar", f"Contrato {contrato.numero} · {competencia.numero_competencia}", autor_id=autor.id,
        alvo_tipo="contrato", alvo_id=contrato.id, dados={"competencia": competencia.competencia, "recusa": recusa.ordem, "justificativa": justificativa},
    )
    from app.services.contratos.servico_competencias import sincronizar_tarefas
    sincronizar_tarefas(sessao, competencia, autor)
    sessao.commit()
    return recusa
