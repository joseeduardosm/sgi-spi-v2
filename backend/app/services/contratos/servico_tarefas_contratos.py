# Criado por José Eduardo Santana Martins
# Este arquivo serve para ligar as competências dos contratos ao Módulo Tarefas: cria as tarefas de cada etapa na virada e as mantém em dia.
"""Tarefas das competências de contratos (para medir o trabalho da execução mensal).

Na virada de cada competência (dia seguinte ao fim do período) nascem, na equipe **Contratos**, as tarefas de cada etapa (medição, avaliação,
nota fiscal, retenção, CADIN, checklist, consolidado, subir no SEI, despachar e juntar a OB). As tarefas de etapa são **controladas pelo módulo
Contratos**: elas andam sozinhas (a fazer → em andamento → concluída) conforme a etapa evolui, e o histórico de quem fez o quê fica na linha do tempo.
"Subir no SEI" e "Despachar" não existem no módulo Contratos: são tarefas manuais, movidas por quem as faz.

Tudo passa por um motor único e idempotente, `sincronizar_competencia`: ele compara o estado real da competência com as tarefas e corrige o que
diverge (cria o que falta, move o que mudou, volta o que foi reaberto). É chamado (1) depois de cada ação de escrita em `servico_competencias`,
(2) pela rotina diária das 07:00 e (3) por um SuperRoot (`POST /api/tarefas/contratos/sincronizar`, com modo de ensaio).

Prazos em **dias úteis** (fim de semana e feriados de `rh_feriados` não contam), às 18:00, contados de `n` = dia seguinte ao fim do período.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc, hoje_sao_paulo
from app.core.configuracao import obter_configuracao
from app.models.contratos.contrato import Contrato
from app.models.contratos.execucao import Competencia
from app.models.tarefas import EquipeTarefas, EstagioTarefa, EventoTarefa, MarcadorTarefa, MembroEquipeTarefas, Tarefa
from app.models.usuario import Usuario
from app.services import calendario_util
from app.services.tarefas import servico_estagios, servico_origem
from app.services.tarefas import servico_tarefas as servico

log = logging.getLogger("sgi_spi.tarefas_contratos")

ORIGEM = "contrato_competencia"
NOME_EQUIPE = "Contratos"
FUSO = ZoneInfo("America/Sao_Paulo")
HORA_PRAZO = time(18, 0)
# Nascimento das tarefas espelhadas depois do dia `n`: a hora em que a rotina diária as teria criado
HORA_NASCIMENTO = time(7, 0)
RODAPE = (
    "\n\n---\nTarefa criada pelo módulo Contratos somente para dimensionamento e monitoramento do trabalho. "
    "Por favor, trate esta tarefa no módulo Contratos"
)
# Cor (paleta de marcadores) de cada etapa
MARCADORES_ETAPA = {
    "Medição": 4, "Avaliação": 5, "Nota fiscal": 3, "Retenção": 1, "CADIN": 2, "Checklist": 10, "Consolidado": 7, "SEI": 8, "Despacho": 9, "Ordem bancária": 6,
}
PAPEIS_ORDEM = ("gestor", "gestor_suplente", "fiscal_administrativo", "fiscal_administrativo_suplente", "fiscal_tecnico", "fiscal_tecnico_suplente")


@dataclass
class Alvo:
    """Uma tarefa que deve existir para a competência, com o estado em que ela deve estar."""
    chave: str
    titulo: str
    etapa: str
    prazo: datetime
    controlada: bool = True
    responsaveis: str = "equipe"  # equipe | financeiro | sei
    inicio: datetime | None = None
    fim: datetime | None = None
    autor_fim: int | None = None
    autor_inicio: int | None = None
    # Etapa de uma rodada de nota fiscal já recusada: fecha com o motivo no histórico
    nota: str = ""
    recusa: int = 0
    detalhe: str = ""
    # O prazo acompanha o estado da competência (ex.: vencimento do pagamento) e é ajustado enquanto a tarefa está aberta
    prazo_dinamico: bool = False
    # Quando a tarefa nasce (padrão: a hora da rotina da virada); rodadas novas da nota fiscal nascem na hora da recusa
    nascimento: datetime | None = None


@dataclass
class Resultado:
    criadas: int = 0
    atualizadas: int = 0
    removidas: int = 0
    competencias: int = 0
    erros: list[str] = field(default_factory=list)
    novas: list[Tarefa] = field(default_factory=list)

    def somar(self, outro: "Resultado") -> None:
        self.criadas += outro.criadas
        self.atualizadas += outro.atualizadas
        self.removidas += outro.removidas
        self.competencias += outro.competencias
        self.erros += outro.erros
        self.novas += outro.novas


# ---------------------------------------------------------------------------------------------
# Datas
# ---------------------------------------------------------------------------------------------

# Dias úteis: a lógica é comum ao portal (`services/calendario_util.py`); os nomes ficam aqui porque o módulo e os testes os usam
_feriados = calendario_util.feriados_cadastrados
_util = calendario_util.eh_util
somar_uteis = calendario_util.somar_uteis


def _prazo(dia: date) -> datetime:
    return datetime.combine(dia, HORA_PRAZO, tzinfo=FUSO).astimezone(timezone.utc)


def _data_local(momento: datetime) -> date:
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(FUSO).date()


def _utc(momento: datetime | None) -> datetime | None:
    if momento is None:
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def virada(competencia: Competencia) -> date:
    """`n`: dia em que a competência é liberada (seguinte ao fim do período)."""
    return competencia.periodo_fim + timedelta(days=1)


# ---------------------------------------------------------------------------------------------
# Elegibilidade
# ---------------------------------------------------------------------------------------------

def elegivel(competencia: Competencia, hoje: date) -> bool:
    """Competência regular, liberada, de contrato sem "Liberar todas as competências" e dentro do corte de cobrança."""
    from app.services.contratos import servico_competencias as comp
    from app.services.contratos import servico_contratos as contratos

    contrato = competencia.contrato
    if contrato is None or contrato.liberar_todas_competencias or competencia.tipo != "regular":
        return False
    if hoje <= competencia.periodo_fim or comp.anterior_ao_corte(competencia):
        return False
    return contratos.situacao(contrato) != "suspenso"


# ---------------------------------------------------------------------------------------------
# Catálogo: que tarefas existem e em que estado devem estar
# ---------------------------------------------------------------------------------------------

def catalogo(competencia: Competencia, feriados: set[date]) -> list[Alvo]:
    """Tarefas da competência, com o estado real de cada uma (início e fim vindos da própria competência)."""
    from app.services.contratos import servico_competencias as comp

    c = competencia
    n = virada(c)
    alvos: list[Alvo] = []

    def util(dias: int) -> datetime:
        return _prazo(somar_uteis(n, dias, feriados))

    # Medição
    alvos.append(Alvo("medicao", "Medição", "Medição", util(2), inicio=_utc(c.medicao_iniciada_em), fim=_utc(c.medicao_concluida_em)))

    # Avaliação de qualidade (só com formulário): preencher e, depois, anexar a via assinada
    if comp.tem_avaliacao(c):
        a = c.avaliacao
        pdf_em = _utc(a.pdf_gerado_anexo.criado_em) if a is not None and a.pdf_gerado_anexo is not None else None
        preenchimento = _utc(a.avaliacao_inicial_em or a.avaliacao_gestor_em) if a is not None else None
        alvos.append(Alvo("avaliacao_preencher", "Avaliação de qualidade: preencher", "Avaliação", util(3), inicio=preenchimento, fim=pdf_em,
                          autor_inicio=a.avaliador_inicial_id if a is not None else None, autor_fim=a.gestor_id if a is not None else None))
        alvos.append(Alvo("avaliacao_assinada", "Avaliação de qualidade: anexar a via assinada", "Avaliação", util(4), inicio=pdf_em,
                          fim=_utc(a.concluida_em) if a is not None else None))

    # Nota fiscal e retenção, em rodadas: cada recusa do Financeiro fecha a rodada e abre outra
    recusas = sorted(c.recusas, key=lambda r: r.ordem)
    for i, r in enumerate(recusas, start=1):
        quando = _utc(r.recusada_em)
        motivo = f"Recusada pelo Financeiro (recusa nº {r.ordem}): {r.justificativa}"
        abertura = _utc(recusas[i - 2].recusada_em) if i > 1 else None
        alvos.append(Alvo(f"nf:{i}", _titulo_nf(i), "Nota fiscal", util(4) if i == 1 else _prazo(somar_uteis(_data_local(abertura), 2, feriados)),
                          inicio=quando, fim=quando, autor_fim=r.recusada_por_id, nota=motivo, recusa=r.ordem, nascimento=abertura))
        for k in range(1, max(1, len(r.notas)) + 1):
            rotulo = (r.notas[k - 1].get("rotulo") or r.notas[k - 1].get("numero") or "") if r.notas else ""
            prazo_ret = util(5) if i == 1 else _prazo(somar_uteis(_data_local(abertura), 3, feriados))
            alvos.append(Alvo(f"retencao:{i}:{k}", _titulo_retencao(i, rotulo), "Retenção", prazo_ret, responsaveis="financeiro", inicio=quando, fim=quando,
                              autor_fim=r.recusada_por_id, nota=motivo, recusa=r.ordem, nascimento=abertura))
    rodada = len(recusas) + 1
    nf_em = _utc(c.nf_concluida_em)
    ultima_recusa = _data_local(_utc(recusas[-1].recusada_em)) if recusas else None
    prazo_nf = util(4) if rodada == 1 else _prazo(somar_uteis(ultima_recusa, 2, feriados))
    abertura_atual = _utc(recusas[-1].recusada_em) if recusas else None
    detalhe_nf = ("Notas juntadas: " + ", ".join(x.rotulo for x in sorted(c.notas_fiscais, key=lambda x: x.ordem))) if c.notas_fiscais else ""
    alvos.append(Alvo(f"nf:{rodada}", _titulo_nf(rodada), "Nota fiscal", prazo_nf, inicio=nf_em, fim=nf_em, nascimento=abertura_atual, detalhe=detalhe_nf))
    notas = sorted(c.notas_fiscais, key=lambda x: x.ordem)
    base_retencao = somar_uteis(n, 5, feriados) if rodada == 1 else somar_uteis(ultima_recusa, 3, feriados)
    if nf_em is not None:
        base_retencao = max(base_retencao, somar_uteis(_data_local(nf_em), 1, feriados))
    for k in range(1, max(1, len(notas)) + 1):
        rotulo = notas[k - 1].rotulo if notas else ""
        alvos.append(Alvo(f"retencao:{rodada}:{k}", _titulo_retencao(rodada, rotulo), "Retenção", _prazo(base_retencao), responsaveis="financeiro",
                          inicio=nf_em, fim=_utc(c.retencao_concluida_em), autor_fim=c.retencao_por_id, prazo_dinamico=True,
                          nascimento=abertura_atual if (rodada > 1 or k > 1) else None, detalhe="Retenção de tributos conferida" if c.retencao_concluida_em else ""))

    # CADIN, checklist e consolidado
    consultas = sorted(c.consultas_cadin, key=lambda x: x.criado_em)
    alvos.append(Alvo("cadin", "Consulta ao CADIN", "CADIN", util(6), inicio=_utc(consultas[0].criado_em) if consultas else None,
                      fim=_utc(c.cadin_concluido_em), autor_inicio=consultas[0].criado_por_id if consultas else None,
                      autor_fim=consultas[-1].criado_por_id if consultas else None,
                      detalhe=f"{len(consultas)} consulta(s) ao CADIN; a última sem pendência" if c.cadin_concluido_em and consultas else ""))
    enviados = sorted((d for d in c.documentos if d.enviado_em is not None), key=lambda d: d.enviado_em)
    alvos.append(Alvo("checklist", "Checklist de documentos mensais", "Checklist", util(6), inicio=_utc(enviados[0].enviado_em) if enviados else None,
                      fim=_utc(c.checklist_concluido_em), autor_inicio=enviados[0].enviado_por_id if enviados else None,
                      autor_fim=enviados[-1].enviado_por_id if enviados else None,
                      detalhe=f"{len(enviados)} de {len(c.documentos)} documento(s) enviados" if c.checklist_concluido_em else ""))
    alvos.append(Alvo("consolidado", "Gerar o documento consolidado", "Consolidado", util(6), inicio=_utc(c.consolidado_em), fim=_utc(c.consolidado_em)))

    # Manuais: o módulo Contratos não as conhece
    alvos.append(Alvo("sei", "Subir no SEI", "SEI", util(7), controlada=False, responsaveis="sei"))
    alvos.append(Alvo("despachar", "Despachar", "Despacho", util(7), controlada=False, responsaveis="sei"))

    # Juntar a ordem bancária: vence no pagamento (data da NF + prazo do contrato); até a NF entrar, n + 30 dias
    from app.services.contratos.servico_competencias import vencimento_pagamento

    vencimento = vencimento_pagamento(c) or n + timedelta(days=30)
    ob_em = _utc(c.ob_enviada_em or c.concluida_em)
    alvos.append(Alvo("ob", "Juntar a ordem bancária (OB)", "Ordem bancária", _prazo(vencimento), inicio=ob_em, fim=ob_em, prazo_dinamico=True))
    return alvos


def _rotulo_contrato(contrato: Contrato) -> str:
    """"Apelido - número" (só o número quando o contrato não tem apelido)."""
    apelido = (contrato.apelido or "").strip()
    return f"{apelido} - {contrato.numero}" if apelido else contrato.numero


def _titulo_completo(alvo: Alvo, competencia: Competencia) -> str:
    return f"{alvo.titulo} — {_rotulo_contrato(competencia.contrato)} — {competencia.numero_competencia}"[:200]


def _titulo_antigo(alvo: Alvo, competencia: Competencia) -> str:
    """Título de antes do apelido (as tarefas manuais, como o SEI, não são recriadas: só trocam o título se ainda estiver assim)."""
    return f"{alvo.titulo} — {competencia.contrato.numero} — {competencia.numero_competencia}"[:200]


def _titulo_nf(rodada: int) -> str:
    return "Subir a nota fiscal" if rodada == 1 else f"Subir a nota fiscal ({rodada}ª rodada)"


def _titulo_retencao(rodada: int, rotulo: str) -> str:
    base = f"Retenção de tributos — {rotulo}" if rotulo else "Retenção de tributos"
    return base if rodada == 1 else f"{base} ({rodada}ª rodada)"


# ---------------------------------------------------------------------------------------------
# Equipe, marcadores e responsáveis
# ---------------------------------------------------------------------------------------------

def usuario_sistema(sessao: Session) -> Usuario | None:
    """Conta administrativa que "cria" as tarefas (as ações do dia a dia aparecem com o autor real)."""
    return sessao.scalar(select(Usuario).where(Usuario.login == obter_configuracao().login_admin))


def equipe_contratos(sessao: Session, dono: Usuario) -> EquipeTarefas:
    """Equipe "Contratos" (criada na primeira vez, com os estágios padrão). A liderança é configurada na tela da equipe."""
    equipe = sessao.scalar(select(EquipeTarefas).where(EquipeTarefas.nome == NOME_EQUIPE, EquipeTarefas.ativa.is_(True)))
    if equipe is None:
        equipe = EquipeTarefas(nome=NOME_EQUIPE, dono_id=dono.id)
        sessao.add(equipe)
        sessao.flush()
    if not sessao.scalar(select(EstagioTarefa.id).where(EstagioTarefa.equipe_id == equipe.id).limit(1)):
        for posicao, (nome, categoria, cor) in enumerate(servico_estagios.PADRAO):
            sessao.add(EstagioTarefa(equipe_id=equipe.id, nome=nome, categoria=categoria, posicao=posicao, cor_indice=cor))
        sessao.flush()
    return equipe


def sincronizar_membros(sessao: Session, equipe: EquipeTarefas, extras: list[int] | None = None) -> int:
    """Põe na equipe "Contratos" todo mundo da equipe vigente de qualquer contrato (e do Financeiro); só acrescenta, nunca tira. Devolve quantos entraram."""
    from app.services.contratos import servico_retencao
    from app.services.contratos.servico_contratos import designacoes_vigentes

    ids = set(extras or [])
    for contrato in sessao.scalars(select(Contrato)):
        ids.update(d.usuario_id for d in designacoes_vigentes(contrato))
    ids.update(u.id for u in servico_retencao.usuarios_financeiro(sessao))
    ids = set(_ativos(sessao, sorted(ids))) - servico.membros(equipe)
    for i in sorted(ids):
        equipe.membros.append(MembroEquipeTarefas(equipe_id=equipe.id, usuario_id=i))
    if ids:
        sessao.flush()
    return len(ids)


def _marcador(sessao: Session, equipe: EquipeTarefas, nome: str, cor: int) -> MarcadorTarefa:
    existente = sessao.scalar(select(MarcadorTarefa).where(MarcadorTarefa.equipe_id == equipe.id, MarcadorTarefa.nome == nome))
    if existente is not None:
        return existente
    from app.services.tarefas import paleta

    marcador = MarcadorTarefa(equipe_id=equipe.id, nome=nome, cor_indice=cor, cor=paleta.borda(cor))
    sessao.add(marcador)
    sessao.flush()
    return marcador


def _marcadores(sessao: Session, equipe: EquipeTarefas, contrato: Contrato, etapa: str) -> list[MarcadorTarefa]:
    cor_contrato = 1 + (sum(ord(ch) for ch in contrato.numero) % 11)
    return [_marcador(sessao, equipe, contrato.numero, cor_contrato), _marcador(sessao, equipe, etapa, MARCADORES_ETAPA.get(etapa, 0))]


def _ativos(sessao: Session, ids: list[int]) -> list[int]:
    ativos = set(sessao.scalars(select(Usuario.id).where(Usuario.id.in_(ids), Usuario.ativo.is_(True)))) if ids else set()
    resultado: list[int] = []
    for i in ids:
        if i in ativos and i not in resultado:
            resultado.append(i)
    return resultado


def responsaveis(sessao: Session, contrato: Contrato, tipo: str, dono: Usuario) -> list[int]:
    """Quem responde pela tarefa: a equipe vigente do contrato (gestor primeiro); Financeiro + gestor na retenção; gestor e fiscal administrativo no SEI."""
    from app.services.contratos import servico_retencao
    from app.services.contratos.servico_contratos import designacoes_vigentes

    vigentes = sorted(designacoes_vigentes(contrato), key=lambda d: PAPEIS_ORDEM.index(d.papel) if d.papel in PAPEIS_ORDEM else 99)
    gestores = [d.usuario_id for d in vigentes if d.papel == "gestor"] or [d.usuario_id for d in vigentes[:1]]
    if tipo == "financeiro":
        ids = gestores + [u.id for u in servico_retencao.usuarios_financeiro(sessao)]
    elif tipo == "sei":
        ids = gestores + [d.usuario_id for d in vigentes if d.papel == "fiscal_administrativo"]
    else:
        ids = [d.usuario_id for d in vigentes]
    return _ativos(sessao, ids) or [dono.id]


def _descricao(competencia: Competencia, alvo: Alvo) -> str:
    c, contrato = competencia, competencia.contrato
    empresa = contrato.empresa.razao_social if getattr(contrato, "empresa", None) is not None else ""
    linhas = [f"Contrato {contrato.numero}" + (f" — {empresa}" if empresa else ""),
              f"Competência {c.numero_competencia} (período de {c.periodo_inicio:%d/%m/%Y} a {c.periodo_fim:%d/%m/%Y})",
              f"Etapa: {alvo.etapa}", f"Prazo: {_data_local(alvo.prazo):%d/%m/%Y} (dias úteis contados de {virada(c):%d/%m/%Y})"]
    texto = "\n".join(linhas)
    if alvo.controlada:
        texto += f"{RODAPE} (/contratos/{contrato.id}/execucao/{c.identificador})."
    else:
        texto += "\n\nTarefa manual: o módulo Contratos não controla esta etapa. Mova-a aqui, quando fizer."
    return texto


# ---------------------------------------------------------------------------------------------
# Motor de sincronização
# ---------------------------------------------------------------------------------------------

def _autor(sessao: Session, atuante: Usuario | None, conhecido: int | None) -> Usuario | None:
    """Quem aparece como autor do evento: o usuário que acabou de agir ou, ao espelhar um estado antigo, quem a competência registra."""
    if atuante is not None:
        return atuante
    return sessao.get(Usuario, conhecido) if conhecido else None


def sincronizar_competencia(sessao: Session, competencia: Competencia, atuante: Usuario | None = None, hoje: date | None = None,
                            feriados: set[date] | None = None) -> Resultado:
    """Cria o que falta e leva cada tarefa da competência ao estado real. Sem `commit` (o chamador decide)."""
    resultado = Resultado()
    hoje = hoje or hoje_sao_paulo()
    if not elegivel(competencia, hoje):
        return resultado
    dono = usuario_sistema(sessao)
    if dono is None:
        return resultado
    resultado.competencias = 1
    feriados = feriados if feriados is not None else _feriados(sessao)
    equipe = equipe_contratos(sessao, dono)
    sincronizar_membros(sessao, equipe)
    contrato = competencia.contrato
    existentes = {t.origem_chave: t for t in sessao.scalars(select(Tarefa).where(Tarefa.origem_tipo == ORIGEM, Tarefa.origem_id == competencia.id))}
    agora = agora_utc()
    # Nascimento padrão: a hora em que a rotina da virada teria criado a tarefa (ou agora, se a virada é hoje e ainda não passou das 07:00)
    nascimento_padrao = min(datetime.combine(virada(competencia), HORA_NASCIMENTO, tzinfo=FUSO).astimezone(timezone.utc), agora)
    cache_responsaveis: dict[str, list[int]] = {}
    alvos = catalogo(competencia, feriados)
    chaves = {a.chave for a in alvos}
    for alvo in alvos:
        tarefa = existentes.get(alvo.chave)
        if alvo.responsaveis not in cache_responsaveis:
            cache_responsaveis[alvo.responsaveis] = responsaveis(sessao, contrato, alvo.responsaveis, dono)
        donos = cache_responsaveis[alvo.responsaveis]
        if tarefa is None:
            tarefa = servico_origem.criar_de_origem(
                sessao, dono, equipe, _titulo_completo(alvo, competencia), _descricao(competencia, alvo), alvo.prazo, donos,
                _marcadores(sessao, equipe, contrato, alvo.etapa), ORIGEM, competencia.id, alvo.chave, alvo.controlada, alvo.nascimento or nascimento_padrao,
                evento_titulo="Tarefa criada pelo módulo Contratos" if alvo.controlada else "Tarefa criada na virada da competência")
            existentes[alvo.chave] = tarefa
            resultado.criadas += 1
            resultado.novas.append(tarefa)
        if not alvo.controlada:
            if tarefa.titulo == _titulo_antigo(alvo, competencia):
                tarefa.titulo = _titulo_completo(alvo, competencia)
            continue
        mudou = _ajustar(sessao, tarefa, alvo, competencia, atuante)
        if mudou:
            resultado.atualizadas += 1
    # Tarefa de uma chave que não existe mais (ex.: notas removidas ao zerar): só some se ainda não foi trabalhada
    for chave, tarefa in existentes.items():
        if chave not in chaves and tarefa.controlada_externamente and tarefa.status == "a_fazer":
            sessao.delete(tarefa)
            resultado.removidas += 1
    sessao.flush()
    return resultado


def _ajustar(sessao: Session, tarefa: Tarefa, alvo: Alvo, competencia: Competencia, atuante: Usuario | None) -> bool:
    """Leva a tarefa controlada ao estado do alvo (título, prazo dinâmico e situação). Devolve se mudou algo."""
    mudou = False
    titulo = _titulo_completo(alvo, competencia)
    if tarefa.titulo != titulo:
        tarefa.titulo, mudou = titulo, True
    # Prazo que depende de dados da competência (ex.: vencimento do pagamento) acompanha esses dados, salvo se a liderança já o alterou à mão
    if alvo.prazo_dinamico and tarefa.status != "concluida" and servico._comparavel(tarefa.prazo) == servico._comparavel(tarefa.prazo_original):
        antes = tarefa.prazo
        servico_origem.alterar_prazo(sessao, tarefa, alvo.prazo, None, "Prazo recalculado com os dados mais recentes da competência.", redefinir_original=True)
        mudou = mudou or antes != tarefa.prazo
    desejado = "concluida" if alvo.fim is not None else "em_andamento" if alvo.inicio is not None else "a_fazer"
    if alvo.nota:
        mudou = _registrar_recusa(sessao, tarefa, alvo, _autor(sessao, atuante, alvo.autor_fim)) or mudou
    if tarefa.status == desejado:
        return mudou
    if desejado == "concluida":
        quem = _autor(sessao, atuante, alvo.autor_fim)
        if tarefa.status == "a_fazer":
            servico_origem.aplicar_status(sessao, tarefa, "em_andamento", _autor(sessao, atuante, alvo.autor_inicio or alvo.autor_fim),
                                          "Etapa iniciada no módulo Contratos", quando=alvo.inicio or alvo.fim)
        servico_origem.aplicar_status(sessao, tarefa, "concluida", quem, "Etapa fechada: nota recusada pelo Financeiro" if alvo.nota else "Etapa concluída no módulo Contratos",
                                      "" if alvo.nota else alvo.detalhe, quando=alvo.fim)
    elif desejado == "em_andamento":
        reaberta = tarefa.status == "concluida"
        servico_origem.aplicar_status(sessao, tarefa, "em_andamento", _autor(sessao, atuante, alvo.autor_inicio),
                                      "Etapa reaberta no módulo Contratos" if reaberta else "Etapa iniciada no módulo Contratos",
                                      quando=agora_utc() if reaberta else (alvo.inicio or agora_utc()))
    else:
        servico_origem.aplicar_status(sessao, tarefa, "a_fazer", atuante, "Etapa voltou a ficar pendente no módulo Contratos", quando=agora_utc())
    return True


def _registrar_recusa(sessao: Session, tarefa: Tarefa, alvo: Alvo, quem: Usuario | None) -> bool:
    """Grava uma vez, na tarefa da rodada recusada, o motivo da recusa do Financeiro (evento `contrato` com o número da recusa)."""
    ja = any(e.tipo == "contrato" and (e.dados or {}).get("recusa") == alvo.recusa
             for e in sessao.scalars(select(EventoTarefa).where(EventoTarefa.tarefa_id == tarefa.id, EventoTarefa.tipo == "contrato")))
    if ja:
        return False
    servico_origem.evento_de_origem(sessao, tarefa, quem, f"Nota fiscal recusada pelo Financeiro (recusa nº {alvo.recusa})", alvo.nota, quando=alvo.fim,
                                    etapa=alvo.etapa, acao="recusar", recusa=alvo.recusa)
    return True


def sincronizar_seguro(sessao: Session, competencia: Competencia, atuante: Usuario | None) -> None:
    """Chamada depois de uma ação em Contratos: nunca derruba a ação (falha vira log; a rotina diária repara)."""
    try:
        with sessao.begin_nested():
            sincronizar_competencia(sessao, competencia, atuante)
    except Exception:  # noqa: BLE001 - a integração é acessória: o fluxo de contratos segue mesmo se ela falhar
        log.exception("Falha ao sincronizar as tarefas da competência %s", getattr(competencia, "id", "?"))


# ---------------------------------------------------------------------------------------------
# Rotina diária (virada) e comando manual
# ---------------------------------------------------------------------------------------------

def _competencias_a_sincronizar(sessao: Session, hoje: date) -> list[Competencia]:
    """Competências regulares liberadas e dentro do corte: as abertas, e as concluídas que ainda não têm tarefas."""
    from app.services.contratos import servico_competencias as comp

    todas = sessao.scalars(
        select(Competencia).join(Contrato, Contrato.id == Competencia.contrato_id)
        .where(Competencia.tipo == "regular", Contrato.liberar_todas_competencias.is_(False), Competencia.periodo_fim >= comp.PENDENCIAS_A_PARTIR_DE,
               Competencia.periodo_fim < hoje).order_by(Competencia.periodo_fim, Competencia.id)
    )
    com_tarefas = set(sessao.scalars(select(Tarefa.origem_id).where(Tarefa.origem_tipo == ORIGEM).distinct()))
    return [c for c in todas if c.etapa_atual != "concluida" or c.id not in com_tarefas]


def sincronizar_todas(sessao: Session, hoje: date | None = None, ensaio: bool = False) -> Resultado:
    """Rotina da virada: sincroniza cada competência (um `commit` por competência; erro de uma não impede as outras).

    Com `ensaio=True` nada é gravado: o resultado mostra o que seria feito.  Não manda e-mail nem aviso de tarefa criada ou concluída: quem avisa é o módulo Contratos."""
    hoje = hoje or hoje_sao_paulo()
    total = Resultado()
    feriados = _feriados(sessao)
    for competencia in _competencias_a_sincronizar(sessao, hoje):
        rotulo = f"{competencia.contrato.numero} {competencia.numero_competencia}"
        try:
            parcial = sincronizar_competencia(sessao, competencia, None, hoje, feriados)
            if ensaio:
                sessao.rollback()
            else:
                sessao.commit()
            total.somar(parcial)
        except Exception as erro:  # noqa: BLE001 - uma competência com problema não pode parar as demais nem a rotina das 07:00
            sessao.rollback()
            log.exception("Falha ao sincronizar as tarefas de %s", rotulo)
            total.erros.append(f"{rotulo}: {erro}")
    return total
