# Criado por José Eduardo Santana Martins
# Este arquivo serve para gerar o relatório memorial de uma tarefa (PDF ou XLSX) com todos os acontecimentos da linha do tempo.
"""Memorial da tarefa: dados da tarefa, dias em aberto e **todos** os acontecimentos, do mais antigo para o mais recente.

Entram comentários, mudanças de situação, prazos, atribuições, anexos, checklist, escalonamentos e atividades. Itens removidos da linha
do tempo (SuperRoot) aparecem identificados como removidos, sem o conteúdo. A permissão de ver a tarefa é conferida na rota.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import em_sao_paulo
from app.models.tarefas import EventoTarefa, Tarefa
from app.models.usuario import Usuario
from app.services.tarefas import servico_tarefas as servico

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ROTULOS_TIPO = {
    "criada": "Criação", "editada": "Edição", "status": "Mudança de situação", "entregue": "Entrega", "validada": "Validação", "devolvida": "Devolução",
    "reaberta": "Reabertura", "prazo": "Prazo", "transferida": "Transferência", "comentario": "Comentário", "participantes": "Participantes",
    "marcadores": "Marcadores", "checklist": "Checklist", "removido": "Remoção", "escalonada": "Escalonamento", "atividade": "Atividade", "contrato": "Contrato",
}


def _data(d: datetime | None) -> str:
    return em_sao_paulo(d).strftime("%d/%m/%Y %H:%M") if d else "—"


def _situacao(valor: str | None) -> str:
    return servico.ROTULOS_STATUS.get(valor or "", valor or "—")


def _detalhes(e: EventoTarefa) -> str:
    """Texto, situação de/para e anexos do acontecimento (itens removidos só mostram quem removeu e por quê)."""
    if e.removido_em is not None:
        return f"Removido por {e.removido_por_nome or '—'} em {_data(e.removido_em)}. Motivo: {e.motivo_remocao or '—'}"
    partes = [e.texto.strip()] if (e.texto or "").strip() else []
    dados = e.dados or {}
    if dados.get("de") in servico.ROTULOS_STATUS and dados.get("para") in servico.ROTULOS_STATUS:
        partes.append(f"Situação: {_situacao(dados['de'])} → {_situacao(dados['para'])}")
    if e.anexos:
        partes.append("Anexos: " + ", ".join(v.anexo.nome_original for v in e.anexos))
    return "\n".join(partes)


def acontecimentos(sessao: Session, t: Tarefa) -> list[list[str]]:
    """Linhas `[data e hora, tipo, quem, acontecimento, detalhes]` em ordem cronológica."""
    eventos = sessao.scalars(select(EventoTarefa).where(EventoTarefa.tarefa_id == t.id).order_by(EventoTarefa.criado_em, EventoTarefa.id))
    return [[_data(e.criado_em), ROTULOS_TIPO.get(e.tipo, e.tipo), e.autor_nome or "Sistema", e.titulo, _detalhes(e)] for e in eventos]


def resumo(sessao: Session, t: Tarefa, agora: datetime) -> list[tuple[str, str]]:
    """Dados da tarefa para o cabeçalho do memorial."""
    nomes = {u.id: (u.nome_completo or u.login) for u in sessao.scalars(select(Usuario).where(Usuario.id.in_(servico.envolvidos(t))))} if servico.envolvidos(t) else {}
    dias = servico.dias_em_aberto(t, agora)
    if dias is None:
        dias_texto = f"{servico.dias_ate_concluir(t)} dia(s) até a conclusão"
    else:
        dias_texto = f"{dias} dia(s) em aberto"
    return [
        ("Tarefa", f"#{t.numero} · {t.titulo}"), ("Equipe", t.equipe.nome if t.equipe else "Pessoal"), ("Situação", _situacao(t.status)),
        ("Prioridade", servico.ROTULOS_PRIORIDADE[t.prioridade]), ("Responsáveis", ", ".join(sorted(nomes.values())) or "—"),
        ("Marcadores", ", ".join(sorted(m.nome for m in t.marcadores)) or "—"), ("Criada em", _data(t.criado_em)), ("Prazo original", _data(t.prazo_original)),
        ("Prazo atual", _data(t.prazo)), ("Iniciada em", _data(t.iniciada_em)), ("Concluída em", _data(t.concluida_em)), ("Tempo", dias_texto),
        ("Checklist", f"{sum(1 for i in t.checklist if i.concluido_em)}/{len(t.checklist)}" if t.checklist else "—"),
    ]


def gerar(sessao: Session, autor: Usuario, t: Tarefa, formato: str, agora: datetime) -> tuple[bytes, str, str]:
    """Conteúdo, nome do arquivo e tipo do memorial."""
    linhas = acontecimentos(sessao, t)
    dados = resumo(sessao, t, agora)
    titulo = f"Memorial da tarefa #{t.numero}"
    nome = f"memorial-tarefa-{t.numero}"
    if formato == "xlsx":
        from app.services.documentos.planilha import Aba, Coluna, gerar_planilha

        conteudo = gerar_planilha([
            Aba("Resumo", [Coluna("Campo", largura=22), Coluna("Valor", largura=80)], [list(par) for par in dados], titulo=f"{titulo}: {t.titulo}"),
            Aba("Acontecimentos", [Coluna("Data e hora", largura=17), Coluna("Tipo", largura=20), Coluna("Quem", largura=28), Coluna("Acontecimento", largura=50),
                                   Coluna("Detalhes", largura=80)], linhas, titulo=f"{titulo}: {t.titulo}",
                 observacoes=[f"{len(linhas)} acontecimento(s), do mais antigo para o mais recente."]),
        ])
        return conteudo, f"{nome}.xlsx", XLSX
    from app.services.documentos.pdf import DocumentoPdf

    documento = DocumentoPdf("Memorial da tarefa", f"#{t.numero} · {t.titulo}", paisagem=True, autor=(autor.nome_completo or autor.login))
    documento.secao("Dados da tarefa").campos(dados, colunas=2)
    documento.secao(f"Acontecimentos ({len(linhas)})").tabela(
        ["Data e hora", "Tipo", "Quem", "Acontecimento", "Detalhes"], linhas, larguras=[1.3, 1.5, 1.8, 3.2, 4.2])
    return documento.gerar(), f"{nome}.pdf", "application/pdf"
