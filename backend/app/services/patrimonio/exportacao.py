# Criado por José Eduardo Santana Martins
# Este arquivo serve para exportar o Patrimônio em Excel e PDF: bens, bens fora de garantia, painel por grupo e movimentações.
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.banco import hoje_sao_paulo
from app.models.usuario import Usuario
from app.services.documentos.pdf import DocumentoPdf
from app.services.documentos.planilha import FORMATO_DATA, FORMATO_MOEDA, Aba, Coluna, gerar_planilha
from app.services.patrimonio import servico_bens, servico_movimentacoes, servico_paineis
from app.services.patrimonio.base import ErroPatrimonio, nome_do_autor
from app.services.patrimonio.servico_localizacoes import rotulo_curto

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ROTULOS_SITUACAO = {"ativo": "Ativo", "em_manutencao": "Em manutenção", "inservivel": "Inservível", "extraviado": "Extraviado", "baixado": "Baixado"}
ROTULOS_GARANTIA = {"indefinida": "Indefinida", "vigente": "Vigente", "vencida": "Vencida"}
ROTULOS_STATUS_MOV = {"pendente": "Pendente", "autorizada": "Autorizada", "concluida": "Concluída", "recusada": "Recusada", "cancelada": "Cancelada"}


def _data(valor: datetime | None) -> str:
    return valor.astimezone().strftime("%d/%m/%Y %H:%M") if valor else ""


def _real(valor) -> str:
    return "—" if valor is None else f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _saida(formato: str, titulo: str, nome: str, colunas: list[Coluna], linhas: list[list], autor: Usuario, subtitulo: str = "", larguras_pdf: list[float] | None = None):
    sufixo = hoje_sao_paulo().strftime("%Y-%m-%d")
    if formato == "xlsx":
        return gerar_planilha([Aba(nome=nome[:31], colunas=colunas, linhas=linhas, titulo=titulo)]), f"{nome}-{sufixo}.xlsx", XLSX
    documento = DocumentoPdf(titulo=titulo, subtitulo=subtitulo or f"{len(linhas)} registro(s)", autor=nome_do_autor(autor))
    texto = [[("" if c is None else (c.strftime("%d/%m/%Y") if hasattr(c, "strftime") else _real(c) if not isinstance(c, (str, int)) else str(c))) for c in linha] for linha in linhas]
    documento.tabela([c.titulo for c in colunas], texto, larguras=larguras_pdf)
    return documento.gerar(), f"{nome}-{sufixo}.pdf", "application/pdf"


def exportar_bens(sessao: Session, formato: str, autor: Usuario, **filtros) -> tuple[bytes, str, str]:
    if formato not in ("xlsx", "pdf"):
        raise ErroPatrimonio("O formato é xlsx ou pdf.")
    bens, _ = servico_bens.listar(sessao, pagina=1, tamanho=100000, **filtros)
    linhas = [[b.rotulo, b.descricao, rotulo_curto(b.localizacao), ROTULOS_SITUACAO[b.situacao], b.conservacao, b.grupo.nome if b.grupo else "", b.valor_aquisicao,
               servico_bens.valor_efetivo(b), b.data_aquisicao, servico_bens.garantia_fim(b), ROTULOS_GARANTIA[servico_bens.situacao_garantia(b)]] for b in bens]
    colunas = [Coluna("Chapa", largura=16), Coluna("Descrição", largura=44), Coluna("Sala", largura=30), Coluna("Situação", largura=14), Coluna("Conservação", "0", 12),
               Coluna("Grupo", largura=24), Coluna("Aquisição", FORMATO_MOEDA, 14), Coluna("Valor atual", FORMATO_MOEDA, 14), Coluna("Data de aquisição", FORMATO_DATA, 14),
               Coluna("Fim da garantia", FORMATO_DATA, 14), Coluna("Garantia", largura=12)]
    return _saida(formato, "Bens do Patrimônio", "patrimonio-bens", colunas, linhas, autor, larguras_pdf=[1.1, 3, 2.4, 1.2, 0.9, 1.6, 1.2, 1.2, 1.2, 1.2, 1])


def exportar_fora_garantia(sessao: Session, formato: str, autor: Usuario) -> tuple[bytes, str, str]:
    dados = servico_paineis.painel(sessao, garantia="vencida")
    linhas = [[b["rotulo"], b["descricao"], b["sala"], b["fim_garantia"], b["dias"]] for b in dados["fora_garantia"]]
    colunas = [Coluna("Chapa", largura=16), Coluna("Descrição", largura=44), Coluna("Sala", largura=30), Coluna("Fim da garantia", FORMATO_DATA, 14), Coluna("Dias", "0", 8)]
    return _saida(formato, "Bens fora de garantia", "patrimonio-fora-garantia", colunas, linhas, autor, larguras_pdf=[1.2, 3.5, 2.6, 1.3, 0.8])


def exportar_painel(sessao: Session, formato: str, autor: Usuario, agrupar_por: str = "andar", **filtros) -> tuple[bytes, str, str]:
    dados = servico_paineis.painel(sessao, agrupar_por=agrupar_por, **filtros)
    linhas = [[g["rotulo"], g["quantidade"], g["valor"]] for g in dados["grupos"]]
    colunas = [Coluna(agrupar_por.capitalize(), largura=40), Coluna("Quantidade", "0", 12), Coluna("Valor atual", FORMATO_MOEDA, 16)]
    return _saida(formato, f"Patrimônio por {agrupar_por}", "patrimonio-painel", colunas, linhas, autor, larguras_pdf=[4, 1, 1.6])


def exportar_movimentacoes(sessao: Session, formato: str, autor: Usuario, **filtros) -> tuple[bytes, str, str]:
    movs = servico_movimentacoes.listar(sessao, **filtros)
    linhas = []
    for m in movs:
        origens = ", ".join(sorted({i.origem.codigo or i.origem.nome for i in m.itens}))
        linhas.append([_data(m.solicitada_em), ROTULOS_STATUS_MOV[m.status], origens, m.destino.codigo or m.destino.nome, len(m.itens), sum(1 for i in m.itens if i.recebido_em),
                       nome_do_autor(m.solicitante) if m.solicitante else "", m.motivo])
    colunas = [Coluna("Solicitada em", largura=17), Coluna("Status", largura=12), Coluna("Origem", largura=22), Coluna("Destino", largura=12), Coluna("Bens", "0", 8),
               Coluna("Recebidos", "0", 10), Coluna("Solicitante", largura=26), Coluna("Motivo", largura=44)]
    return _saida(formato, "Movimentações do Patrimônio", "patrimonio-movimentacoes", colunas, linhas, autor, larguras_pdf=[1.4, 1, 1.8, 1, 0.6, 0.8, 2, 3.5])
