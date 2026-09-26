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
from app.services.contratos import calculos, documentos_execucao
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


def eh_financeiro(sessao: Session, usuario: Usuario) -> bool:
    return any(u.id == usuario.id for u in usuarios_financeiro(sessao))


def pode_conferir(sessao: Session, contrato: Contrato, usuario: Usuario) -> bool:
    """SuperRoot, quem edita o contrato (criador/equipe) ou o Financeiro."""
    return usuario.superusuario or pode_editar(sessao, contrato, usuario) or eh_financeiro(sessao, usuario)


# --- Conferências automáticas --------------------------------------------------------------------

def _cnpj(valor: str | None) -> str:
    d = "".join(c for c in (valor or "") if c.isdigit())
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else (d or "não informado")


def conferencias(contrato: Contrato, competencia: Competencia, dados: dict | None, valor_esperado: Decimal | None) -> list[Conferencia]:
    """Conferências de uma nota (dados lidos do XML). `valor_esperado`: valor autorizado, só para a nota principal."""
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
        bruto = Decimal(dados.get("valor_bruto") or "0")
        lista.append(Conferencia(
            "Valor × valor autorizado da medição", "ok" if bruto == valor_esperado else "alerta",
            f"Nota: {documentos_execucao.moeda(bruto)}; autorizado (medido × % da avaliação): {documentos_execucao.moeda(valor_esperado)}"
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
    from app.services.contratos.servico_competencias import percentual_liberado, total_medido

    return calculos.arredondar(total_medido(competencia) * percentual_liberado(competencia) / Decimal(100))


# --- Gravação ------------------------------------------------------------------------------------

def salvar_retencao(sessao: Session, contrato_id: uuid.UUID, competencia_id: uuid.UUID, principal: dict[str, Decimal],
                    adicional: dict[str, Decimal] | None, discriminacao_conferida: bool, autor: Usuario) -> Competencia:
    """Grava as retenções conferidas, gera o PDF da conferência e conclui a etapa (CADIN e checklist correm em paralelo)."""
    from app.services.contratos.servico_competencias import _carregar_competencia, _validar_retencoes, concluir_etapa_paralela, etapas_abertas

    contrato = obter_contrato(sessao, contrato_id)
    if not pode_conferir(sessao, contrato, autor):
        raise SemPermissaoContrato("A retenção de tributos é conferida pelo Financeiro, pela equipe do contrato ou pelo SuperRoot.")
    competencia = _carregar_competencia(sessao, contrato, competencia_id)
    if "retencao" not in etapas_abertas(competencia):
        raise ErroRegraContrato("A retenção de tributos não está aberta nesta competência (já conferida ou a nota fiscal ainda não foi juntada).")
    if not discriminacao_conferida:
        raise ErroRegraContrato("Confirme que a discriminação dos serviços é compatível com o objeto do contrato.")
    _validar_retencoes(principal, competencia.nf_valor_bruto or ZERO, "principal")
    for tributo in TRIBUTOS:
        setattr(competencia, f"nf_retencao_{tributo}", principal.get(tributo, ZERO))
    if competencia.nf_adicional_valor_bruto is not None:
        if adicional is None:
            raise ErroRegraContrato("Informe as retenções da nota fiscal adicional.")
        _validar_retencoes(adicional, competencia.nf_adicional_valor_bruto, "adicional")
        for tributo in TRIBUTOS:
            setattr(competencia, f"nf_adicional_retencao_{tributo}", adicional.get(tributo, ZERO))
    competencia.retencao_discriminacao_conferida = True
    competencia.retencao_por_id, competencia.retencao_por_nome = autor.id, autor.nome_completo or autor.login
    competencia.retencao_concluida_em = agora_utc()
    pdf = documentos_execucao.relatorio_retencao(
        contrato, competencia,
        conferencias(contrato, competencia, competencia.nf_dados_xml, valor_autorizado(competencia)),
        conferencias(contrato, competencia, competencia.nf_adicional_dados_xml, None),
        autor.nome_completo or autor.login,
    )
    competencia.retencao_pdf_anexo = servico_anexos.guardar_pdf_gerado(
        sessao, pdf, f"retencao_{contrato.numero.replace('/', '_')}_{competencia.identificador}.pdf", "contrato-execucao-retencao", autor.id,
        contrato_id=contrato.id,
    )
    # CADIN e checklist correm em paralelo: com os três concluídos, o consolidado é liberado
    concluir_etapa_paralela(competencia, "retencao")
    auditar(
        sessao, autor.login, "contrato.execucao.retencao", f"Contrato {contrato.numero} · {competencia.numero_competencia}", autor_id=autor.id,
        alvo_tipo="contrato", alvo_id=contrato.id,
        dados={"competencia": competencia.competencia, "principal": principal, "adicional": adicional},
    )
    sessao.commit()
    return competencia
