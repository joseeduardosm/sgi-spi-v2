# Criado por José Eduardo Santana Martins
# Este arquivo serve para gerar o relatório de tarefas (XLSX ou PDF) de um escopo: minhas, equipe ou pessoa.
"""Relatório de tarefas em XLSX (abas Tarefas e Por pessoa) ou PDF (resumo, pessoas e lista).

Entram as tarefas do escopo que estiveram ativas no período: criadas até o fim dele e ainda abertas ou concluídas a partir
do início. Filtros opcionais por marcador. As permissões do escopo são conferidas antes, na rota.
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.banco import em_sao_paulo
from app.models.tarefas import Tarefa
from app.models.usuario import Usuario
from app.services.tarefas import servico_tarefas as servico

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FUSO = ZoneInfo("America/Sao_Paulo")


def _local(d: datetime | None) -> datetime | None:
    return servico._comparavel(d).astimezone(FUSO).replace(tzinfo=None) if d else None


def _nome(sessao: Session, usuario_id: int | None) -> str:
    u = sessao.get(Usuario, usuario_id) if usuario_id else None
    return (u.nome_completo or u.login) if u else "—"


def no_periodo(tarefas: list[Tarefa], de: date | None, ate: date | None) -> list[Tarefa]:
    """Tarefas ativas no período (sem datas: todas)."""
    inicio = datetime.combine(de, time.min, FUSO) if de else None
    fim = datetime.combine(ate, time.max, FUSO) if ate else None
    resultado = []
    for t in tarefas:
        if fim and servico._comparavel(t.criado_em) > fim:
            continue
        if inicio and t.status == "concluida" and t.concluida_em and servico._comparavel(t.concluida_em) < inicio:
            continue
        resultado.append(t)
    return sorted(resultado, key=lambda t: t.numero)


def por_pessoa(sessao: Session, tarefas: list[Tarefa], agora: datetime) -> list[list]:
    """Uma linha por envolvido: a fazer, em andamento, em validação, concluídas, atrasadas e carga."""
    contagem: dict[int, dict] = {}
    for t in tarefas:
        for i in servico.envolvidos(t):
            c = contagem.setdefault(i, {"a_fazer": 0, "em_andamento": 0, "em_validacao": 0, "concluida": 0, "atrasadas": 0, "carga": 0.0})
            c[t.status] += 1
            if t.status in servico.OPERACIONAIS and servico._comparavel(t.prazo) < agora:
                c["atrasadas"] += 1
            c["carga"] += servico.carga(t, agora)
    linhas = [[_nome(sessao, i), c["a_fazer"], c["em_andamento"], c["em_validacao"], c["concluida"], c["atrasadas"], round(c["carga"], 1),
               servico.faixa(c["carga"])] for i, c in contagem.items()]
    return sorted(linhas, key=lambda l: (-l[6], l[0].lower()))


def gerar(sessao: Session, autor: Usuario, titulo_escopo: str, tarefas: list[Tarefa], prorrogacoes: dict, formato: str, de: date | None,
          ate: date | None, agora: datetime) -> tuple[bytes, str, str]:
    """Conteúdo, nome do arquivo e tipo. `prorrogacoes`: mudanças de prazo por id de tarefa."""
    tarefas = no_periodo(tarefas, de, ate)
    periodo = f"{de.strftime('%d/%m/%Y') if de else 'início'} a {ate.strftime('%d/%m/%Y') if ate else 'hoje'}"
    titulo = f"{titulo_escopo}: {periodo}"
    sufixo = agora.astimezone(FUSO).strftime("%Y-%m-%d")
    linhas = []
    for t in tarefas:
        atrasada = t.status in servico.OPERACIONAIS and servico._comparavel(t.prazo) < agora
        linhas.append([
            t.numero, t.titulo, t.equipe.nome if t.equipe else "Pessoal", _nome(sessao, t.responsavel_id),
            ", ".join(sorted(_nome(sessao, p.usuario_id) for p in t.responsaveis if p.usuario_id != t.responsavel_id)) or "—",
            servico.ROTULOS_PRIORIDADE[t.prioridade], servico.ROTULOS_STATUS[t.status] + (" (atrasada)" if atrasada else ""),
            _local(t.criado_em), _local(t.prazo_original), _local(t.prazo), prorrogacoes.get(t.id, 0), _local(t.concluida_em),
            ", ".join(sorted(m.nome for m in t.marcadores)) or "—",
            f"{sum(1 for i in t.checklist if i.concluido_em)}/{len(t.checklist)}" if t.checklist else "—",
            _rotulo_sla(sessao, t),
        ])
    pessoas = por_pessoa(sessao, tarefas, agora)
    if formato == "xlsx":
        from app.services.documentos.planilha import Aba, Coluna, gerar_planilha

        data = "dd/mm/yyyy hh:mm"
        colunas = [Coluna("Nº", "0", 7), Coluna("Tarefa", largura=48), Coluna("Equipe", largura=24), Coluna("Responsável", largura=28),
                   Coluna("Demais responsáveis", largura=34), Coluna("Prioridade", largura=11), Coluna("Situação", largura=22), Coluna("Criada", data, 16),
                   Coluna("Prazo original", data, 16), Coluna("Prazo", data, 16), Coluna("Prorrogações", "0", 12), Coluna("Concluída", data, 16),
                   Coluna("Marcadores", largura=26), Coluna("Checklist", largura=10), Coluna("SLA (resolução)", largura=22)]
        colunas_pessoas = [Coluna("Pessoa", largura=34), Coluna("A fazer", "0", 9), Coluna("Em andamento", "0", 13), Coluna("Em validação", "0", 13),
                           Coluna("Concluídas", "0", 11), Coluna("Atrasadas", "0", 10), Coluna("Carga (pts)", "0.0", 11), Coluna("Faixa", largura=20)]
        conteudo = gerar_planilha([
            Aba("Tarefas", colunas, linhas, titulo=titulo, observacoes=[
                "Tarefas ativas no período: criadas até o fim dele e ainda abertas ou concluídas a partir do início."]),
            Aba("Por pessoa", colunas_pessoas, pessoas, titulo=titulo, observacoes=[
                "Cada tarefa conta para cada um dos seus responsáveis. A carga só considera tarefas a fazer e em andamento."]),
        ])
        return conteudo, f"tarefas-{sufixo}.xlsx", XLSX
    from app.services.documentos.pdf import DocumentoPdf

    ind = servico.indicadores(tarefas, agora)
    documento = DocumentoPdf("Relatório de tarefas", titulo, paisagem=True, autor=(autor.nome_completo or autor.login))
    documento.secao("Resumo").campos([
        ("Tarefas no período", str(len(tarefas))), ("Em aberto", str(ind["operacionais"])), ("Atrasadas", str(ind["atrasadas"])),
        ("Em validação", str(ind["em_validacao"])), ("Concluídas", str(ind["concluidas"])), ("Carga total", f"{ind['carga']:.1f} pts"),
    ], colunas=3)
    if pessoas:
        documento.secao("Por pessoa").tabela(
            ["Pessoa", "A fazer", "Em andamento", "Em validação", "Concluídas", "Atrasadas", "Carga", "Faixa"],
            [[l[0], l[1], l[2], l[3], l[4], l[5], f"{l[6]:.1f}", l[7]] for l in pessoas],
            larguras=[3.2, 0.8, 1.1, 1.1, 1, 0.9, 0.8, 1.6], alinhar_direita=[1, 2, 3, 4, 5, 6],
        )
    documento.secao(f"Tarefas ({len(linhas)})").tabela(
        ["Nº", "Tarefa", "Equipe", "Responsável", "Prioridade", "Situação", "Prazo", "Prorr.", "Concluída"],
        [[str(l[0]), l[1], l[2], l[3], l[5], l[6], _texto_local(l[9]), str(l[10]), _texto_local(l[11])] for l in linhas],
        larguras=[0.5, 3.6, 1.6, 1.8, 0.9, 1.5, 1.2, 0.6, 1.2], alinhar_direita=[0, 7],
    )
    return documento.gerar(), f"tarefas-{sufixo}.pdf", "application/pdf"


ROTULOS_SLA = {"no_prazo": "No prazo", "em_risco": "Em risco", "estourado": "Estourado", "cumprido": "Cumprido", "cumprido_fora": "Cumprido fora do prazo"}


def _rotulo_sla(sessao: Session, t: Tarefa) -> str:
    """Situação do SLA de resolução (traço nas tarefas controladas por outro módulo, que não têm SLA)."""
    from app.services.sla import servico_sla

    item = servico_sla.da_tarefa(sessao, t)
    return ROTULOS_SLA[item.situacao_resolucao] if item else "—"


def _texto_local(d: datetime | None) -> str:
    return em_sao_paulo(d).strftime("%d/%m/%Y %H:%M") if d else "—"
