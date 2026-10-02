# Criado por José Eduardo Santana Martins
# Este arquivo serve para gerar o relatório de saldos de férias e licença-prêmio de todos os servidores (CGP).
"""Relatório de saldos (CGP), em XLSX ou PDF: uma linha por servidor ativo.

Serve para conferir a carga inicial dos dados funcionais e acompanhar quem tem saldo a vencer:
servidor, setor, autorizador, período aquisitivo vigente (creditados, agendados, disponíveis, fim, data-limite para
pedir) e licença-prêmio do ano (saldo, usado, disponível). Quem ainda não tem o início do período aquisitivo aparece
com "não informado", para a CGP completar. A conta root (sem vínculo funcional) fica de fora.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.configuracao import obter_configuracao
from app.models.usuario import Usuario
from app.services.rh import servico_periodos
from app.services.rh.papeis import dados_funcionais, exigir_cgp, setor_do_usuario
from app.services.rh.servico_afastamentos import saldos

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TITULOS = ["Servidor", "Login", "Setor", "Autorizador", "Exercício (período de gozo)", "Creditados", "Agendados", "Disponíveis",
           "Expira em", "Pedir até", "LP (ano)", "LP saldo", "LP usado", "LP disponível"]


def _data(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


def _nome(u: Usuario | None) -> str:
    return (u.nome_completo or u.login) if u else "—"


def linhas(sessao: Session, referencia: date) -> list[list]:
    """Uma linha por servidor ativo (em ordem de nome)."""
    login_admin = obter_configuracao().login_admin.strip().lower()
    usuarios = [u for u in sessao.scalars(select(Usuario).where(Usuario.ativo.is_(True))) if u.login.strip().lower() != login_admin]
    resultado = []
    for u in sorted(usuarios, key=lambda x: _nome(x).lower()):
        dados = dados_funcionais(sessao, u.id)
        autorizador = sessao.get(Usuario, dados.autorizador_id) if dados and dados.autorizador_id else None
        periodo = servico_periodos.vigente(sessao, u.id, referencia)
        if periodo is not None:
            s = servico_periodos.situacao(sessao, periodo, referencia)
            ferias = [f"{servico_periodos.exercicio_do_periodo(periodo.inicio, periodo.fim)} · {_data(periodo.inicio)} a {_data(periodo.fim)}", periodo.dias_creditados, s.usado, s.disponivel,
                      _data(periodo.fim), _data(s.data_limite_pedido)]
        else:
            ferias = ["não informado", None, None, None, "—", "—"]
        ano = dados.exercicio if dados and dados.exercicio else referencia.year
        lp = saldos(sessao, u.id, ano)["licenca_premio"]
        resultado.append([_nome(u), u.login, setor_do_usuario(u), _nome(autorizador) if autorizador else "—", *ferias,
                          ano, lp.saldo, lp.usado, lp.disponivel])
    sessao.commit()
    return resultado


def gerar(sessao: Session, autor: Usuario, formato: str, referencia: date) -> tuple[bytes, str, str]:
    exigir_cgp(sessao, autor)
    dados = linhas(sessao, referencia)
    titulo = f"Saldos de férias e licença-prêmio em {_data(referencia)}"
    sufixo = referencia.strftime("%Y-%m-%d")
    if formato == "xlsx":
        from app.services.documentos.planilha import Aba, Coluna, gerar_planilha

        colunas = [Coluna("Servidor", largura=34), Coluna("Login", largura=18), Coluna("Setor", largura=40), Coluna("Autorizador", largura=30),
                   Coluna("Exercício (período de gozo)", largura=34), Coluna("Creditados", "0", 11), Coluna("Agendados", "0", 11),
                   Coluna("Disponíveis", "0", 11), Coluna("Expira em", largura=12), Coluna("Pedir até", largura=12),
                   Coluna("LP (ano)", "0", 9), Coluna("LP saldo", "0", 9), Coluna("LP usado", "0", 9), Coluna("LP disponível", "0", 12)]
        conteudo = gerar_planilha([Aba("Saldos", colunas, dados, titulo=titulo, observacoes=[
            "Exercício \"não informado\": a CGP ainda não preencheu o início do período aquisitivo nos dados funcionais.",
            "Agendados: férias pendentes, aprovadas e gozadas que começam no período. \"Pedir até\": última data para pedir todo o saldo.",
        ])])
        return conteudo, f"saldos-ferias-lp-{sufixo}.xlsx", XLSX
    from app.services.documentos.pdf import DocumentoPdf

    def numero(v) -> str:
        return "—" if v is None else str(v)

    documento = DocumentoPdf("Saldos de férias e licença-prêmio", titulo, paisagem=True, autor=_nome(autor))
    documento.secao(f"Servidores ({len(dados)})").tabela(
        ["Servidor", "Setor", "Exercício (período)", "Cred.", "Agend.", "Disp.", "Pedir até", "LP disp."],
        [[l[0], l[2], l[4], numero(l[5]), numero(l[6]), numero(l[7]), l[9], numero(l[13])] for l in dados],
        larguras=[3.2, 3.6, 2.2, 0.7, 0.7, 0.7, 1.1, 0.8], alinhar_direita=[3, 4, 5, 7],
    )
    return documento.gerar(), f"saldos-ferias-lp-{sufixo}.pdf", "application/pdf"
