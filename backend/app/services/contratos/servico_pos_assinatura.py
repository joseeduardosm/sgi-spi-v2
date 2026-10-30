# Criado por José Eduardo Santana Martins
# Este arquivo serve para controlar o que vem depois da assinatura da prorrogação: prazo e publicação no PNCP, DOE, garantia e planilhas para a DOF.
"""Pós-assinatura da prorrogação.

A divulgação no PNCP é **condição de eficácia** do aditivo: o prazo é a assinatura + 20 dias úteis (licitação) ou 10 (contratação direta), contados pelo
calendário de feriados do RH, e os dois números são **Parâmetros de Contratos**. Aqui ficam o cálculo do prazo e da situação, o registro das datas e as duas
planilhas de dados de garantia para a DOF (Modelos 9 e 10 da SPI: caução em dinheiro, ou seguro/fiança/títulos).
"""

import io
import uuid
from datetime import date
from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models.contratos import Contrato, Prorrogacao
from app.models.usuario import Usuario
from app.schemas.contratos.alteracoes import GravacaoPosAssinatura
from app.services import calendario_util
from app.services.contratos import extenso, servico_parametros
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado
from app.services.contratos.servico_contratos import exigir_edicao, obter_contrato
from app.services.servico_auditoria import auditar

RECURSOS = Path(__file__).resolve().parents[2] / "recursos" / "prorrogacao"
# Dados que a equipe digita para as planilhas de garantia (chave → rótulo)
CAMPOS_GARANTIA = {
    "responsavel_nome": "Responsável pelas informações: nome completo", "responsavel_email": "Responsável pelas informações: e-mail",
    "responsavel_fone": "Responsável pelas informações: telefone", "ultima_nl": "Nº da última Nota de Lançamento (NL) do SIAFEM",
    "forma_prestacao": "Forma de prestação (caução em dinheiro)", "meio_prestacao": "Meio de prestação (caução em dinheiro)",
    "dare": "Nº de controle do DARE/SP", "valor_complemento": "Valor do complemento da garantia", "data_pagamento": "Data do pagamento (dd/mm/aaaa)",
    "endosso_numero": "Nº do endosso/aditamento da apólice ou fiança", "endosso_valor": "Valor do endosso/aditamento", "endosso_vigencia": "Vigência do endosso/aditamento",
}
MODALIDADES = {"caucao_dinheiro": "I - Caução em dinheiro", "titulos_divida_publica": "II - Caução em títulos da dívida pública", "fianca_bancaria": "III - Fiança bancária",
               "seguro_garantia": "IV - Seguro-garantia", "titulo_capitalizacao": "V - Título de capitalização"}
ROTULO_MODALIDADE = {"licitacao": "Licitação", "dispensa": "Dispensa de licitação", "inexigibilidade": "Inexigibilidade de licitação"}


def prazo_pncp(sessao: Session, contrato: Contrato, assinada_em: date) -> date | None:
    """Último dia para divulgar no PNCP (dias úteis da assinatura); sem modalidade cadastrada, não há como saber."""
    if not contrato.modalidade_contratacao:
        return None
    dias = servico_parametros.valor("pncp_dias_uteis_direta" if contrato.modalidade_contratacao in ("dispensa", "inexigibilidade") else "pncp_dias_uteis_licitacao")
    return calendario_util.somar_uteis(assinada_em, dias, calendario_util.feriados_cadastrados(sessao))


def situacao_pncp(sessao: Session, p: Prorrogacao, hoje: date, feriados: set[date] | None = None) -> tuple[str, int | None]:
    """(situação, dias úteis restantes): `sem_prazo`, `publicado`, `no_prazo` ou `vencido`."""
    if p.pncp_publicado_em:
        return "publicado", None
    if p.pncp_prazo_ate is None:
        return "sem_prazo", None
    if hoje > p.pncp_prazo_ate:
        return "vencido", None
    return "no_prazo", calendario_util.uteis_entre(hoje, p.pncp_prazo_ate, feriados if feriados is not None else calendario_util.feriados_cadastrados(sessao))


def _prorrogacao(contrato: Contrato, prorrogacao_id: uuid.UUID) -> Prorrogacao:
    p = next((x for x in contrato.prorrogacoes if x.id == prorrogacao_id), None)
    if p is None:
        raise RegistroNaoEncontrado("Prorrogação")
    return p


def atualizar(sessao: Session, contrato_id: uuid.UUID, prorrogacao_id: uuid.UUID, dados: GravacaoPosAssinatura, autor: Usuario) -> None:
    """Grava as datas e os dados do pós-assinatura (substitui o que havia)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    p = _prorrogacao(contrato, prorrogacao_id)
    desconhecidos = [k for k in dados.dados_garantia if k not in CAMPOS_GARANTIA]
    if desconhecidos:
        raise ErroRegraContrato("Dado desconhecido nas planilhas de garantia: " + ", ".join(desconhecidos) + ".")
    for campo in ("pncp_publicado_em", "doe_publicado_em", "garantia_comprovada_em", "garantia_enviada_dof_em", "contratos_gov_atualizado_em"):
        valor = getattr(dados, campo)
        if valor is not None and valor < p.assinada_em:
            raise ErroRegraContrato("As datas do pós-assinatura não podem ser anteriores à assinatura do termo aditivo.")
    antes = {c: getattr(p, c) for c in ("pncp_publicado_em", "pncp_numero", "doe_publicado_em", "garantia_comprovada_em", "garantia_enviada_dof_em", "contratos_gov_atualizado_em")}
    for campo in antes:
        setattr(p, campo, getattr(dados, campo))
    p.dados_garantia = {k: v.strip() for k, v in dados.dados_garantia.items() if v.strip()}
    mudou = {c: {"de": str(a), "para": str(getattr(p, c))} for c, a in antes.items() if a != getattr(p, c)}
    auditar(sessao, autor.login, "contrato.prorrogacao.pos_assinatura", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"prorrogacao": str(p.id), "campos": mudou})
    sessao.commit()


# ---------------------------------------------------------------------------------------------
# Planilhas de garantia (DOF)
# ---------------------------------------------------------------------------------------------

def _dinheiro(valor) -> str:
    return extenso.real(valor) if valor is not None else ""


def _anexar(folha, celula: str, texto: str | None) -> None:
    """Escreve depois do rótulo da célula ("Nome Completo:" → "Nome Completo: Fulano"); sem texto, deixa como está."""
    if texto:
        atual = str(folha[celula].value or "").rstrip()
        folha[celula].value = f"{atual} {texto}".strip()


def _trocar(folha, celula: str, texto: str | None) -> None:
    """Troca o conteúdo da célula (os "xxxxx" do modelo); sem texto, deixa como está."""
    if texto:
        folha[celula].value = texto


def planilha_garantia(sessao: Session, contrato_id: uuid.UUID, prorrogacao_id: uuid.UUID) -> tuple[bytes, str]:
    """Planilha de dados de garantia para a DOF, preenchida com o contrato, a prorrogação e o que a equipe digitou."""
    from app.services.contratos import prorrogacao_documentos
    from app.services.contratos.servico_contratos import vigencias

    contrato = obter_contrato(sessao, contrato_id)
    p = _prorrogacao(contrato, prorrogacao_id)
    if not contrato.exige_garantia or not contrato.garantia_modalidade:
        raise ErroRegraContrato("O contrato não está cadastrado com garantia: informe a modalidade da garantia no cadastro do contrato.")
    d = p.dados_garantia or {}
    empresa = contrato.empresa
    original = next(v for v in vigencias(contrato) if not v.retroativa)
    valor_original = prorrogacao_documentos._valor_do_periodo(contrato, original.sequencia, original.inicio, original.fim)  # noqa: SLF001
    sequencia = len(contrato.vigencias_retroativas) + contrato.prorrogacoes.index(p) + 2
    valor_prorrogacao = prorrogacao_documentos._valor_do_periodo(contrato, sequencia, p.data_inicio, p.data_fim)  # noqa: SLF001
    numero = f"SPI nº {contrato.numero}"
    cnpj = prorrogacao_documentos._cnpj(empresa.cnpj)  # noqa: SLF001
    percentual = f"{contrato.garantia_percentual:.2f}%".replace(".", ",") if contrato.garantia_percentual is not None else ""
    periodo = f"{p.data_inicio:%d/%m/%Y} a {p.data_fim:%d/%m/%Y}"
    dinheiro = contrato.garantia_modalidade == "caucao_dinheiro"
    livro = load_workbook(RECURSOS / ("garantia-dinheiro.xlsx" if dinheiro else "garantia-outras-modalidades.xlsx"))
    f = livro.active
    modalidade = ROTULO_MODALIDADE.get(contrato.modalidade_contratacao, "")
    if dinheiro:
        _trocar(f, "D8", MODALIDADES[contrato.garantia_modalidade]); _trocar(f, "D9", d.get("forma_prestacao")); _trocar(f, "D10", d.get("meio_prestacao"))
        _trocar(f, "C14", empresa.razao_social); _trocar(f, "I14", cnpj); _trocar(f, "D15", modalidade); _trocar(f, "D16", _dinheiro(valor_original))
        _trocar(f, "D17", percentual); _trocar(f, "C18", _dinheiro(contrato.garantia_valor)); _trocar(f, "H18", numero)
        _trocar(f, "F21", f"Nº Contrato: {numero}"); _trocar(f, "F22", f"Valor da Prorrogação c/ Reajuste: {_dinheiro(valor_prorrogacao)}" if valor_prorrogacao is not None else None)
        _trocar(f, "F23", f"Período de Vigência: {periodo}"); _trocar(f, "F24", f"Nº {d['ultima_nl']}" if d.get("ultima_nl") else None)
        _trocar(f, "A26", f"Modalidade de Garantia: {MODALIDADES[contrato.garantia_modalidade]}")
        _trocar(f, "F29", f"Nº de Controle DARE/SP: {d['dare']}" if d.get("dare") else None)
        _trocar(f, "F30", f"Valor do Complemento: {d['valor_complemento']}" if d.get("valor_complemento") else None)
        _trocar(f, "F32", f"Data do Pagamento: {d['data_pagamento']}" if d.get("data_pagamento") else None)
        for celula, chave in (("A35", "responsavel_nome"), ("A36", "responsavel_email"), ("A37", "responsavel_fone")):
            _anexar(f, celula, d.get(chave))
    else:
        _anexar(f, "A8", MODALIDADES[contrato.garantia_modalidade])
        # Seguro-garantia: seguradora (linha 9); fiança e demais: instituição financeira (linha 10)
        linha = 9 if contrato.garantia_modalidade == "seguro_garantia" else 10
        _trocar(f, f"D{linha}", contrato.garantia_emissor); _trocar(f, f"H{linha}", f"CNPJ: {prorrogacao_documentos._cnpj(contrato.garantia_cnpj_emissor)}" if contrato.garantia_cnpj_emissor else None)  # noqa: SLF001
        _trocar(f, "C13", empresa.razao_social); _trocar(f, "H13", f"CNPJ: {cnpj}")
        _anexar(f, "A14", modalidade); _anexar(f, "A15", _dinheiro(valor_original)); _anexar(f, "A16", _dinheiro(contrato.garantia_valor))
        _anexar(f, "A19", numero); _anexar(f, "F19", _dinheiro(valor_prorrogacao) if valor_prorrogacao is not None else None)
        _anexar(f, "A20", _dinheiro(valor_original)); _anexar(f, "F20", periodo); _anexar(f, "A21", f"{original.inicio:%d/%m/%Y} a {original.fim:%d/%m/%Y}"); _anexar(f, "F21", d.get("ultima_nl"))
        _anexar(f, "A27", contrato.garantia_apolice); _anexar(f, "F27", d.get("endosso_numero")); _anexar(f, "F28", d.get("endosso_valor")); _anexar(f, "F29", d.get("endosso_vigencia"))
        for celula, chave in (("A32", "responsavel_nome"), ("A33", "responsavel_email"), ("A34", "responsavel_fone")):
            _anexar(f, celula, d.get(chave))
    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue(), f"dados-garantia-{contrato.numero.replace('/', '-')}-prorrogacao-{p.data_inicio:%Y%m%d}.xlsx"
