# Criado por José Eduardo Santana Martins
# Este arquivo serve para gerar os avisos automáticos dos contratos na caixa de mensagens.
"""Avisos automáticos do módulo de contratos (caixa de mensagens).

Cada função é chamada no ponto do fluxo em que o evento acontece, antes do commit da operação: o aviso é
gravado na mesma transação. As chaves impedem avisos repetidos; os de pendência são encerrados quando a
ação é feita (sem exigir ciência). Os e-mails automáticos já existentes (diário, medição, NF, retenção)
continuam como estão; a caixa é um canal a mais.

Chaves:
- `diario:{ocorrencia}`, `medicao:{competencia}:{AAAAMMDDHHMMSS}`: informativos à equipe;
- `retencao:{competencia}`: pendência do Financeiro, encerrada ao salvar a retenção;
- `finais:{competencia}`: pendência da equipe (CADIN e checklist), encerrada ao gerar o consolidado;
- `prorrogacao:{id}`, `reajuste:{id}`, `alteracao:{id}`: informativos à equipe;
- `atraso:{competencia}` e `vencimento:{contrato}:{AAAAMMDD}:{marco}`: gerados pelos lembretes diários
  (`app.tarefas.mensageria`), encerrados ao concluir a medição e ao registrar a prorrogação.
"""

from sqlalchemy.orm import Session

from app.core.banco import agora_utc
from app.models.contratos import Competencia, Contrato
from app.models.usuario import Usuario
from app.services import servico_mensagens


def ids_da_equipe(contrato: Contrato) -> list[int]:
    """Usuários da equipe vigente do contrato."""
    from app.services.contratos.servico_contratos import designacoes_vigentes

    return [d.usuario_id for d in designacoes_vigentes(contrato)]


def _identificacao(contrato: Contrato) -> str:
    return f"Contrato {contrato.numero}" + (f" – {contrato.apelido}" if contrato.apelido else "")


def _rota_competencia(contrato: Contrato, competencia: Competencia, etapa: str | None = None) -> str:
    return f"/contratos/{contrato.id}/execucao/{competencia.identificador}" + (f"?etapa={etapa}" if etapa else "")


def avisar_equipe(sessao: Session, contrato: Contrato, assunto: str, corpo: str, *, chave: str, link: str,
                  categoria: str = "comunicado", prioridade: str = "normal", autor: Usuario | None = None) -> None:
    """Aviso à equipe vigente (menos o autor da ação)."""
    servico_mensagens.notificar(sessao, ids_da_equipe(contrato), assunto, corpo, chave=chave, categoria=categoria, prioridade=prioridade,
                                link=link, contrato_id=contrato.id, autor=autor)


def ocorrencia_registrada(sessao: Session, contrato: Contrato, ocorrencia, autor: Usuario) -> None:
    glosa = " (com glosa)" if ocorrencia.possui_glosa else ""
    avisar_equipe(
        sessao, contrato, f"{_identificacao(contrato)}: nova ocorrência no diário de bordo{glosa}",
        f"{ocorrencia.registrada_por_nome} registrou uma ocorrência em {ocorrencia.data_ocorrencia:%d/%m/%Y}{glosa}:\n\n{ocorrencia.descricao}",
        chave=f"diario:{ocorrencia.id}", link=f"/contratos/{contrato.id}?aba=diario",
        prioridade="alta" if ocorrencia.possui_glosa else "normal", autor=autor,
    )


def medicao_concluida(sessao: Session, contrato: Contrato, competencia: Competencia, autor: Usuario) -> None:
    """Informativo à equipe; encerra o aviso de medição atrasada, se houver."""
    servico_mensagens.encerrar(sessao, chave=f"atraso:{competencia.id}")
    avisar_equipe(
        sessao, contrato, f"{_identificacao(contrato)}: medição de {competencia.numero_competencia} concluída",
        f"{autor.nome_completo or autor.login} concluiu a medição da competência {competencia.numero_competencia}. "
        "A próxima etapa já está liberada.",
        chave=f"medicao:{competencia.id}:{agora_utc():%Y%m%d%H%M%S}", link=_rota_competencia(contrato, competencia), autor=autor,
    )


def nota_fiscal_juntada(sessao: Session, contrato: Contrato, competencia: Competencia, autor: Usuario) -> None:
    """Pendência do Financeiro: conferir a retenção de tributos (encerrada em `retencao_conferida`); encerra a pendência da recusa, se houver."""
    from app.services.contratos.servico_retencao import usuarios_financeiro

    for recusa in competencia.recusas:
        servico_mensagens.encerrar(sessao, chave=f"recusa-nf:{competencia.id}:{recusa.ordem}")

    servico_mensagens.notificar(
        sessao, [u.id for u in usuarios_financeiro(sessao)],
        f"{_identificacao(contrato)}: conferir retenção de tributos ({competencia.numero_competencia})",
        f"A nota fiscal da competência {competencia.numero_competencia} foi juntada por {autor.nome_completo or autor.login}. "
        "Confira a tributação e as retenções na etapa \"Retenção de tributos\".",
        chave=f"retencao:{competencia.id}", categoria="pendencia", prioridade="alta",
        link=_rota_competencia(contrato, competencia, "retencao"), contrato_id=contrato.id, autor=autor,
    )


def nota_recusada(sessao: Session, contrato: Contrato, competencia: Competencia, recusa, autor: Usuario) -> None:
    """Encerra a pendência do Financeiro e avisa a equipe (pendência) de que a nota foi recusada e outra deve ser juntada."""
    servico_mensagens.encerrar(sessao, chave=f"retencao:{competencia.id}")
    avisar_equipe(
        sessao, contrato, f"{_identificacao(contrato)}: nota fiscal recusada ({competencia.numero_competencia})",
        f"{recusa.recusada_por_nome} recusou a nota fiscal da competência {competencia.numero_competencia} (recusa nº {recusa.ordem}). "
        f"Justificativa: {recusa.justificativa}\n\nJunte outra nota fiscal na etapa \"Nota fiscal\".",
        chave=f"recusa-nf:{competencia.id}:{recusa.ordem}", link=_rota_competencia(contrato, competencia, "nota_fiscal"), categoria="pendencia",
        prioridade="alta", autor=autor,
    )


def retencao_conferida(sessao: Session, contrato: Contrato, competencia: Competencia, autor: Usuario) -> None:
    """Encerra a pendência do Financeiro e avisa a equipe do que falta (encerrado ao gerar o consolidado)."""
    servico_mensagens.encerrar(sessao, chave=f"retencao:{competencia.id}")
    from app.services.contratos.servico_competencias import etapas_abertas

    faltam = [e for e in etapas_abertas(competencia) if e in ("cadin", "checklist")]
    texto_faltam = " e ".join({"cadin": "CADIN", "checklist": "checklist"}[e] for e in faltam)
    avisar_equipe(
        sessao, contrato, f"{_identificacao(contrato)}: retenção conferida ({competencia.numero_competencia})",
        f"{autor.nome_completo or autor.login} conferiu a retenção de tributos da competência {competencia.numero_competencia}."
        + (f" Falta concluir: {texto_faltam}; depois, gere o documento consolidado." if faltam else " Já é possível gerar o documento consolidado."),
        chave=f"finais:{competencia.id}", link=_rota_competencia(contrato, competencia), categoria="pendencia", autor=autor,
    )


def consolidado_gerado(sessao: Session, competencia: Competencia) -> None:
    servico_mensagens.encerrar(sessao, chave=f"finais:{competencia.id}")


def alteracao_concluida(sessao: Session, contrato: Contrato, tipo: str, registro_id, descricao: str, autor: Usuario) -> None:
    """Prorrogação, reajuste ou aditamento/supressão concluídos: informativo à equipe.

    A prorrogação encerra os avisos de vencimento da vigência anterior.
    """
    if tipo == "prorrogacao":
        servico_mensagens.encerrar(sessao, prefixo=f"vencimento:{contrato.id}:")
    avisar_equipe(
        sessao, contrato, f"{_identificacao(contrato)}: {descricao}",
        f"{autor.nome_completo or autor.login} concluiu: {descricao}.", chave=f"{tipo}:{registro_id}",
        link=f"/contratos/{contrato.id}", autor=autor,
    )
