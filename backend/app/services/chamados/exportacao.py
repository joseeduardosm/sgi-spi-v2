# Criado por José Eduardo Santana Martins
# Este arquivo serve para exportar a lista de chamados do período (PDF paisagem ou XLSX), a partir da tela de Relatórios.
"""Exportação dos chamados (Chamados › Relatórios › Exportar).

Entram os chamados **abertos no período** (dia inicial e final inclusos, horário de Brasília), dos setores do escopo do relatório
(`qualidade.escopo`: o setor escolhido e os de baixo, ou tudo o que a pessoa atende). O histórico importado do GLPI também entra.

Colunas: Nº, título, descrição (texto sem formatação), solicitante, setor responsável, responsável e status (o nome dos Parâmetros).
Com `com_solucao`, mais a solução vigente. Título: "Chamados {setor} - {início} a {fim}". Notas privadas nunca entram.
"""

from dataclasses import dataclass
from datetime import date
from html import unescape

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import hoje_sao_paulo
from app.models.chamados import Chamado
from app.models.usuario import Usuario
from app.services.chamados import configuracao
from app.services.chamados.qualidade import MAXIMO_DIAS_RELATORIO, _limites
from app.services.chamados.servico import ErroChamado
from app.services.noticias.sanitizacao import texto_puro

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FORMATOS = ("pdf", "xlsx")
# No PDF a descrição e a solução longas são cortadas (a planilha leva o texto inteiro, até o limite da célula do Excel)
LIMITE_PDF = 1500
LIMITE_CELULA = 32000


@dataclass
class Arquivo:
    conteudo: bytes
    nome: str
    tipo: str


def _texto(html: str, limite: int) -> str:
    texto = unescape(texto_puro(html))
    return texto if len(texto) <= limite else texto[: limite - 1].rstrip() + "…"


def _nome(u: Usuario | None) -> str:
    return (u.nome_completo or u.login) if u else ""


def exportar(sessao: Session, setores: set[int] | None, area: str, inicio: date, fim: date, com_solucao: bool, formato: str, autor: Usuario) -> Arquivo:
    if formato not in FORMATOS:
        raise ErroChamado("Formato inválido (pdf ou xlsx).")
    if inicio > fim:
        raise ErroChamado("A data inicial vem depois da final.")
    if (fim - inicio).days >= MAXIMO_DIAS_RELATORIO:
        raise ErroChamado("Escolha um período de até 1 ano.")
    de, ate = _limites(inicio, fim)
    consulta = (select(Chamado).options(selectinload(Chamado.solucoes))
                .where(Chamado.excluido_em.is_(None), Chamado.aberto_em >= de, Chamado.aberto_em < ate).order_by(Chamado.numero))
    if setores is not None:
        consulta = consulta.where(Chamado.setor_id.in_(setores or {-1}))
    chamados = list(sessao.scalars(consulta))
    # Nomes das pessoas numa consulta só (solicitantes e responsáveis)
    ids = {i for c in chamados for i in (c.solicitante_id, c.responsavel_id) if i}
    pessoas = {u.id: u for u in sessao.scalars(select(Usuario).where(Usuario.id.in_(ids)))} if ids else {}
    status = configuracao.apresentacao(sessao)

    limite = LIMITE_CELULA if formato == "xlsx" else LIMITE_PDF
    linhas = []
    for c in chamados:
        solicitante = _nome(pessoas.get(c.solicitante_id)) or (c.solicitante_externo or "")
        linha = [c.numero, c.titulo, _texto(c.descricao, limite), solicitante, c.setor_nome, _nome(pessoas.get(c.responsavel_id)) or "—",
                 status[c.status_base][0]]
        if com_solucao:
            vigente = next((s for s in reversed(c.solucoes) if s.status == "vigente"), None)
            linha.append(_texto(vigente.texto, limite) if vigente else "—")
        linhas.append(linha)

    periodo = f"{inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}"
    titulo = f"Chamados {area} - {periodo}"
    nome_arquivo = f"chamados-{inicio.isoformat()}-a-{fim.isoformat()}.{formato}"
    cabecalho = ["Nº", "Título", "Descrição", "Solicitante", "Setor responsável", "Responsável", "Status"] + (["Solução"] if com_solucao else [])

    if formato == "xlsx":
        from app.services.documentos.planilha import Aba, Coluna, gerar_planilha

        larguras = [8, 40, 70, 28, 28, 28, 16] + ([70] if com_solucao else [])
        colunas = [Coluna(t, "0" if i == 0 else "", w) for i, (t, w) in enumerate(zip(cabecalho, larguras))]
        conteudo = gerar_planilha([Aba("Chamados", colunas, linhas, titulo=titulo, observacoes=[
            f"Chamados abertos de {periodo}. Gerado em {hoje_sao_paulo().strftime('%d/%m/%Y')} por {_nome(autor)}."])])
        return Arquivo(conteudo, nome_arquivo, XLSX)

    from app.services.documentos.pdf import DocumentoPdf

    documento = DocumentoPdf(titulo, f"{len(linhas)} chamado(s) aberto(s) no período", paisagem=True, autor=_nome(autor))
    if linhas:
        larguras = [0.5, 2, 3.6, 1.5, 1.5, 1.5, 1] + ([3.6] if com_solucao else [])
        documento.tabela(cabecalho, [[str(l[0]), *l[1:]] for l in linhas], larguras=larguras, alinhar_direita=[0])
    else:
        documento.paragrafo("Nenhum chamado aberto no período.")
    return Arquivo(documento.gerar(), nome_arquivo, "application/pdf")
