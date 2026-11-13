# Criado por José Eduardo Santana Martins
# Este arquivo serve para a RDM (Requisição de Mudança) das tarefas: rascunho, envio com número do Protocolo, aprovação com PDF e e-mail, reprovação.
"""RDM digital das tarefas (decisões do usuário, 06/11/2026).

| Situação da tarefa | Ação | Quem | Efeito |
|---|---|---|---|
| Em andamento | salvar rascunho / **enviar** | responsáveis (e liderança) | Enviar reserva o número no Protocolo (tipo "RDM SGI", só na 1ª vez), RDM **pendente** e a tarefa vai a Em validação |
| Em validação, RDM pendente | **aprovar** | liderança | RDM **aprovada**; tarefa volta a Em andamento; PDF anexado à tarefa e ao Protocolo; e-mail "RDM Tarefa #N - aprovada" com o PDF |
| Em validação, RDM pendente | **reprovar** (motivo) | liderança | RDM **reprovada**, sem PDF; tarefa volta a Em andamento com o motivo |
| Em andamento, RDM reprovada | corrigir e reenviar | responsáveis | Mesmo número; volta a pendente |
| Tarefa concluída | — | — | RDM aprovada vira **concluída** |

Uma RDM por tarefa; só tarefa com equipe (é a liderança da equipe que decide). Com a RDM pendente, a validação da tarefa mostra só
aprovar/reprovar RDM (não "Validar"/"Devolver").
"""

import io
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc, hoje_sao_paulo
from app.models.protocolo import SequenciaProtocolo, TipoProtocolo
from app.models.tarefas import AnexoEventoTarefa, RdmTarefa, Tarefa
from app.models.usuario import Usuario
from app.schemas.tarefas_rdm import DOCUMENTOS_CONHECIMENTO, FormularioRdm, LinhaConhecimento, LinhaCronograma
from app.services import notificacoes, servico_anexos, servico_protocolo
from app.services.servico_auditoria import auditar
from app.services.tarefas import pdf_rdm
from app.services.tarefas import servico_tarefas as tarefas
from app.services.tarefas.servico_tarefas import ErroTarefa

NOME_TIPO = "RDM SGI"
CHAVE_TIPO = "rdm sgi"
# Faixa criada a cada ano; ampliada sozinha quando acaba
TAMANHO_FAIXA = 500


# ---------------------------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------------------------

def da_tarefa(sessao: Session, tarefa: Tarefa) -> RdmTarefa | None:
    return sessao.scalar(select(RdmTarefa).where(RdmTarefa.tarefa_id == tarefa.id))


def rotulo(rdm: RdmTarefa) -> str:
    return pdf_rdm.rotulo(rdm)


def formulario_inicial(tarefa: Tarefa, autor: Usuario) -> FormularioRdm:
    """Valores iniciais: título da tarefa, quem preenche, o setor dele, hoje, as três etapas do cronograma e os cinco documentos."""
    f = FormularioRdm(titulo=tarefa.titulo[:300])
    f.identificacao.solicitante = autor.nome_completo or autor.login
    f.identificacao.area = (autor.departamento or "").strip()
    f.identificacao.data_solicitacao = hoje_sao_paulo()
    f.cronograma = [LinhaCronograma(etapa=e) for e in ("HOMOLOGAÇÃO", "EXECUÇÃO", "VALIDAÇÃO")]
    f.conhecimento = [LinhaConhecimento(tipo_documento=d) for d in DOCUMENTOS_CONHECIMENTO]
    return f


def pode_editar(sessao: Session, usuario: Usuario, tarefa: Tarefa, rdm: RdmTarefa | None) -> bool:
    """Responsáveis e liderança, com a tarefa em andamento (e com equipe), RDM ainda não enviada ou reprovada."""
    if tarefa.equipe is None or tarefa.status != "em_andamento" or tarefa.controlada_externamente:
        return False
    if rdm is not None and rdm.situacao not in ("rascunho", "reprovada"):
        return False
    return usuario.id in tarefas.envolvidos(tarefa) or tarefas.eh_lider(sessao, usuario, tarefa)


def pode_decidir(sessao: Session, usuario: Usuario, tarefa: Tarefa, rdm: RdmTarefa | None) -> bool:
    return rdm is not None and rdm.situacao == "pendente" and tarefa.status == "em_validacao" and tarefas.eh_lider(sessao, usuario, tarefa)


def pendente(sessao: Session, tarefa: Tarefa) -> bool:
    """Tarefa em validação com RDM aguardando a liderança (a validação comum fica escondida)."""
    rdm = da_tarefa(sessao, tarefa)
    return rdm is not None and rdm.situacao == "pendente"


# ---------------------------------------------------------------------------------------------
# Rascunho e envio
# ---------------------------------------------------------------------------------------------

def _guardar(sessao: Session, tarefa: Tarefa, rdm: RdmTarefa | None, formulario: FormularioRdm) -> RdmTarefa:
    if rdm is None:
        rdm = RdmTarefa(tarefa_id=tarefa.id, situacao="rascunho")
        sessao.add(rdm)
    rdm.titulo = formulario.titulo.strip()[:300]
    rdm.dados = formulario.model_dump(mode="json")
    return rdm


def salvar(sessao: Session, autor: Usuario, tarefa: Tarefa, formulario: FormularioRdm) -> RdmTarefa:
    rdm = da_tarefa(sessao, tarefa)
    if not pode_editar(sessao, autor, tarefa, rdm):
        raise ErroTarefa("A RDM só pode ser preenchida pelos responsáveis com a tarefa em andamento (e enquanto não estiver aguardando aprovação).", 403, "sem_permissao")
    rdm = _guardar(sessao, tarefa, rdm, formulario)
    sessao.commit()
    return rdm


def faltas(formulario: FormularioRdm) -> list[str]:
    """Campos obrigatórios para enviar (o restante é opcional)."""
    f = formulario
    falta = []
    if not f.titulo.strip():
        falta.append("título (assunto)")
    if not f.identificacao.tipo:
        falta.append("tipo da mudança")
    if not f.objetivo.strip():
        falta.append("objetivo")
    if not f.justificativa.strip():
        falta.append("justificativa")
    if f.janela.inicio_data is None or f.janela.fim_data is None:
        falta.append("janela de implantação (data de início e de fim)")
    elif f.janela.fim_data < f.janela.inicio_data:
        falta.append("janela de implantação (o fim é antes do início)")
    if not any(a.atividade.strip() for a in f.plano_execucao):
        falta.append("ao menos uma atividade no plano de execução")
    if not any(a.atividade.strip() for a in f.rollback):
        falta.append("ao menos uma atividade no plano de remediação (rollback)")
    return falta


def _tipo_protocolo(sessao: Session, autor: Usuario) -> TipoProtocolo:
    """O tipo "RDM SGI" no Protocolo (criado no primeiro uso; numerado só pelo sistema)."""
    tipo = sessao.scalar(select(TipoProtocolo).where(TipoProtocolo.nome_chave == CHAVE_TIPO))
    if tipo is None:
        tipo = TipoProtocolo(nome=NOME_TIPO, nome_chave=CHAVE_TIPO)
        sessao.add(tipo)
        sessao.flush()
        auditar(sessao, autor.login, "protocolo.tipo.criar", NOME_TIPO, autor_id=autor.id, alvo_tipo="protocolo_tipo", alvo_id=tipo.id,
                dados={"origem": "tarefas.rdm"})
    return tipo


def _sequencia_do_ano(sessao: Session, autor: Usuario) -> SequenciaProtocolo:
    """A sequência do ano corrente (começa em 1); se a faixa acabou, amplia em mais `TAMANHO_FAIXA` números."""
    tipo = _tipo_protocolo(sessao, autor)
    exercicio = hoje_sao_paulo().year
    sequencia = sessao.scalar(select(SequenciaProtocolo).where(SequenciaProtocolo.tipo_id == tipo.id, SequenciaProtocolo.exercicio == exercicio))
    if sequencia is None:
        sequencia = servico_protocolo._nova_sequencia(sessao, tipo, exercicio, 1, TAMANHO_FAIXA, None, autor)
        sessao.flush()
    from app.models.protocolo import NumeroProtocolo

    livre = sessao.scalar(select(NumeroProtocolo.id).where(NumeroProtocolo.sequencia_id == sequencia.id, NumeroProtocolo.reservado_em.is_(None),
                                                           NumeroProtocolo.anulado_em.is_(None)).limit(1))
    if livre is None:
        servico_protocolo.alterar_faixa(sessao, sequencia.id, sequencia.inicio, sequencia.fim + TAMANHO_FAIXA, autor)
    return sequencia


def formatar(numero: int, exercicio: int) -> str:
    """"1" em 2026 → "00001/2026" (cinco dígitos, decisão do usuário)."""
    return f"{numero:05d}/{exercicio}"


def enviar(sessao: Session, autor: Usuario, tarefa: Tarefa, formulario: FormularioRdm) -> RdmTarefa:
    """Salva, confere os obrigatórios, numera (1ª vez) e leva a tarefa a Em validação, avisando a liderança."""
    rdm = da_tarefa(sessao, tarefa)
    if tarefa.equipe is None:
        raise ErroTarefa("A RDM é aprovada pela liderança da equipe: coloque a tarefa numa equipe antes.")
    if not pode_editar(sessao, autor, tarefa, rdm):
        raise ErroTarefa("Só os responsáveis enviam a RDM, com a tarefa em andamento.", 403, "sem_permissao")
    if "entregar" not in tarefas.acoes(sessao, autor, tarefa) and not tarefas.eh_lider(sessao, autor, tarefa):
        raise ErroTarefa("Você não pode entregar esta tarefa para validação.", 403, "sem_permissao")
    falta = faltas(formulario)
    if falta:
        raise ErroTarefa("Preencha antes de enviar: " + "; ".join(falta) + ".")
    reenvio = rdm is not None and rdm.situacao == "reprovada"
    rdm = _guardar(sessao, tarefa, rdm, formulario)
    sessao.flush()
    if rdm.numero_protocolo_id is None:
        # Número do Protocolo (o `proximo` grava e confirma a reserva)
        sequencia = _sequencia_do_ano(sessao, autor)
        numero = servico_protocolo.proximo(sessao, sequencia.id, f"RDM da tarefa #{tarefa.numero}: {rdm.titulo}"[:500], None, autor, fora_da_reserva=True)
        rdm = da_tarefa(sessao, tarefa)
        rdm.numero_protocolo_id, rdm.numero = numero.id, formatar(numero.numero, numero.sequencia.exercicio)
    rdm.situacao, rdm.enviada_em, rdm.enviada_por_id, rdm.enviada_por_nome = "pendente", agora_utc(), autor.id, tarefas._nome(autor)
    rdm.motivo_reprovacao = rdm.motivo_reprovacao if reenvio else ""
    auditar(sessao, autor.login, "tarefas.rdm.enviar", rotulo(rdm), autor_id=autor.id, alvo_tipo="tarefa_rdm", alvo_id=rdm.id, dados={"tarefa": tarefa.numero, "reenvio": reenvio})
    # Leva a tarefa a Em validação pelo pipeline normal (avisos de validação à liderança, estágio, histórico); o `mover` grava tudo
    tarefas.mover(sessao, autor, tarefa, "entregar", f"{rotulo(rdm)} enviada para aprovação" + (" (corrigida e reenviada)" if reenvio else "") + ".")
    return rdm


# ---------------------------------------------------------------------------------------------
# Decisão da liderança
# ---------------------------------------------------------------------------------------------

def _voltar_para_andamento(sessao: Session, autor: Usuario, tarefa: Tarefa, tipo_evento: str, titulo: str, texto: str):
    """Em validação → Em andamento sem passar pelo "Devolver" (outros avisos): tempo em andamento, estágio, marco e histórico."""
    agora = agora_utc()
    de = tarefa.status
    tarefa.em_andamento_desde = agora
    tarefa.concluida_em = None
    tarefa.status, tarefa.versao = "em_andamento", tarefa.versao + 1
    tarefa.estagio_id = tarefas.estagio_da_categoria(sessao, tarefa.equipe_id, "em_andamento")
    tarefas.reavaliar_marco(sessao, tarefa.marco_id)
    notificacoes.encerrar(sessao, prefixo=f"tarefa-validacao:{tarefa.id}:")
    notificacoes.encerrar(sessao, prefixo=f"tarefa-validacao-parada:{tarefa.id}:")
    evento = tarefas._evento(sessao, tarefa, tipo_evento, autor, titulo, texto, de=de, para="em_andamento")
    tarefas.registrar_nas_subtarefas(sessao, tarefa, autor, f"{tarefas.ROTULOS_STATUS[de]} → {tarefas.ROTULOS_STATUS['em_andamento']}", de=de, para="em_andamento")
    return evento


def _exigir_decisao(sessao: Session, autor: Usuario, tarefa: Tarefa) -> RdmTarefa:
    rdm = da_tarefa(sessao, tarefa)
    if rdm is None or rdm.situacao != "pendente" or tarefa.status != "em_validacao":
        raise ErroTarefa("Esta tarefa não tem RDM aguardando aprovação.", 409, "conflito")
    if not tarefas.eh_lider(sessao, autor, tarefa):
        raise ErroTarefa(f"Só a liderança da equipe ({tarefa.equipe.nome if tarefa.equipe else ''}) aprova ou reprova a RDM.", 403, "sem_permissao")
    return rdm


def _decidir(rdm: RdmTarefa, autor: Usuario) -> None:
    from app.services.rh.papeis import setor_do_usuario

    rdm.decidida_em, rdm.decidida_por_id, rdm.decidida_por_nome = agora_utc(), autor.id, tarefas._nome(autor)
    rdm.decidida_por_cargo = (autor.cargo or "").strip()[:150]
    setor = setor_do_usuario(autor)
    rdm.decidida_por_setor = "" if setor == "Sem setor" else setor[:150]


def destinatarios_email(sessao: Session, tarefa: Tarefa, aprovador: Usuario) -> list[str]:
    """Responsáveis, seguidores e quem aprovou (decisão do usuário), sem repetir e só com e-mail cadastrado."""
    ids = tarefas.envolvidos(tarefa) | tarefas.seguidores(sessao, tarefa) | {aprovador.id}
    emails = []
    for u in sessao.scalars(select(Usuario).where(Usuario.id.in_(ids), Usuario.ativo.is_(True))):
        email = (u.email or "").strip()
        if email and email.lower() not in {e.lower() for e in emails}:
            emails.append(email)
    return sorted(emails, key=str.lower)


def _enviar_email(sessao: Session, rdm: RdmTarefa, tarefa: Tarefa, aprovador: Usuario, pdf: bytes) -> str:
    """E-mail "RDM Tarefa #N - aprovada" com o PDF. Devolve o resultado (vai no histórico); falha de envio não desfaz a aprovação."""
    from app.services import servico_smtp
    from app.services.cliente_smtp import AnexoEmail, Mensagem

    para = destinatarios_email(sessao, tarefa, aprovador)
    if not para:
        return "sem destinatários com e-mail cadastrado"
    assunto = f"RDM Tarefa #{tarefa.numero} - aprovada"
    texto = (f"A {rotulo(rdm)} da tarefa #{tarefa.numero} ({tarefa.titulo}) foi aprovada por {rdm.decidida_por_nome}.\n\n"
             "O formulário da RDM preenchido segue em anexo (PDF) e também está anexado à tarefa no SGI SPI.")
    try:
        envio = servico_smtp.enviar_email(sessao, Mensagem(para=para, assunto=assunto, texto=texto, anexos=[AnexoEmail(nome=pdf_rdm.nome_arquivo(rdm), conteudo=pdf)]))
        return f"enviado para {len(para)} destinatário(s)" if envio.sucesso else f"falhou: {envio.mensagem}"
    except servico_smtp.SemServidorAtivo as erro:
        return f"não enviado: {erro}"


def aprovar(sessao: Session, autor: Usuario, tarefa: Tarefa) -> RdmTarefa:
    """Aprova: PDF (anexado à tarefa e ao número do Protocolo), e-mail com o PDF, tarefa de volta a Em andamento."""
    rdm = _exigir_decisao(sessao, autor, tarefa)
    _decidir(rdm, autor)
    rdm.situacao, rdm.motivo_reprovacao = "aprovada", ""
    pdf = pdf_rdm.gerar(rdm, tarefa)
    anexo = servico_anexos.guardar_pdf_gerado(sessao, pdf, pdf_rdm.nome_arquivo(rdm), "tarefa-rdm", autor.id)
    rdm.pdf_anexo_id = anexo.id
    resultado_email = _enviar_email(sessao, rdm, tarefa, autor, pdf)
    evento = _voltar_para_andamento(sessao, autor, tarefa, "status", f"{rotulo(rdm)} aprovada",
                                    f"RDM aprovada: a tarefa voltou para Em andamento para a execução da mudança. E-mail: {resultado_email}.")
    sessao.flush()
    sessao.add(AnexoEventoTarefa(evento_id=evento.id, anexo_id=anexo.id))
    tarefas._avisar(sessao, tarefas.envolvidos(tarefa), f"RDM aprovada: {tarefas._rotulo(tarefa)}",
                    f"{tarefas._nome(autor)} aprovou a {rotulo(rdm)}. A tarefa voltou para Em andamento; o PDF está anexado à tarefa.",
                    tarefa, f"tarefa-rdm-aprovada:{tarefa.id}:{tarefa.versao}", autor=autor, categoria="comunicado", evento="tarefas.entrega_validada")
    auditar(sessao, autor.login, "tarefas.rdm.aprovar", rotulo(rdm), autor_id=autor.id, alvo_tipo="tarefa_rdm", alvo_id=rdm.id,
            dados={"tarefa": tarefa.numero, "email": resultado_email})
    sessao.commit()
    # O PDF também vai para o número do Protocolo, que passa a "utilizado" (o `anexar` grava por conta própria)
    if rdm.numero_protocolo_id is not None:
        servico_protocolo.anexar(sessao, rdm.numero_protocolo_id, io.BytesIO(pdf), pdf_rdm.nome_arquivo(rdm), autor, ignorar_dono=True)
    return rdm


def reprovar(sessao: Session, autor: Usuario, tarefa: Tarefa, motivo: str) -> RdmTarefa:
    """Reprova com motivo: sem PDF; tarefa de volta a Em andamento; a RDM pode ser corrigida e reenviada com o mesmo número."""
    rdm = _exigir_decisao(sessao, autor, tarefa)
    motivo = (motivo or "").strip()
    if not motivo:
        raise ErroTarefa("Informe o motivo da reprovação.")
    _decidir(rdm, autor)
    rdm.situacao, rdm.motivo_reprovacao = "reprovada", motivo[:4000]
    _voltar_para_andamento(sessao, autor, tarefa, "devolvida", f"{rotulo(rdm)} reprovada", motivo)
    tarefas._avisar(sessao, tarefas.envolvidos(tarefa), f"RDM reprovada: {tarefas._rotulo(tarefa)}",
                    f"{tarefas._nome(autor)} reprovou a {rotulo(rdm)}.\n\nMotivo: {motivo}\n\nCorrija a RDM e envie de novo (o número continua o mesmo).",
                    tarefa, f"tarefa-rdm-reprovada:{tarefa.id}:{tarefa.versao}", autor=autor, categoria="pendencia", prioridade="alta", evento="tarefas.entrega_devolvida")
    auditar(sessao, autor.login, "tarefas.rdm.reprovar", rotulo(rdm), autor_id=autor.id, alvo_tipo="tarefa_rdm", alvo_id=rdm.id,
            dados={"tarefa": tarefa.numero, "motivo": motivo})
    sessao.commit()
    return rdm


def ao_mudar_status(sessao: Session, tarefa: Tarefa, para: str) -> None:
    """Chamado pelo pipeline: concluir a tarefa leva a RDM aprovada a concluída (verde); reabrir a devolve a aprovada. Sem commit."""
    rdm = da_tarefa(sessao, tarefa)
    if rdm is None:
        return
    if para == "concluida" and rdm.situacao == "aprovada":
        rdm.situacao = "concluida"
    elif para != "concluida" and rdm.situacao == "concluida":
        rdm.situacao = "aprovada"


# ---------------------------------------------------------------------------------------------
# Lista e selos
# ---------------------------------------------------------------------------------------------

def resumos(sessao: Session, ids_tarefas: list) -> dict:
    """{tarefa_id: (rótulo, situação)} das RDMs das tarefas (uma consulta, para o quadro)."""
    if not ids_tarefas:
        return {}
    return {r.tarefa_id: (rotulo(r), r.situacao) for r in sessao.scalars(select(RdmTarefa).where(RdmTarefa.tarefa_id.in_(ids_tarefas)))}


def listar(sessao: Session, usuario: Usuario, situacao: str | None = None) -> list[tuple[RdmTarefa, Tarefa]]:
    """RDMs já enviadas das tarefas que o usuário enxerga, da mais recente para a mais antiga."""
    consulta = select(RdmTarefa, Tarefa).join(Tarefa, Tarefa.id == RdmTarefa.tarefa_id).where(RdmTarefa.situacao != "rascunho")
    if situacao:
        consulta = consulta.where(RdmTarefa.situacao == situacao)
    itens = [(r, t) for r, t in sessao.execute(consulta.order_by(RdmTarefa.enviada_em.desc()))]
    return [(r, t) for r, t in itens if tarefas.pode_ver(sessao, usuario, t)]


def por_numero_protocolo(sessao: Session, ids_numeros: list) -> dict:
    """{numero_protocolo_id: (situação, número da tarefa)} para a grade do Protocolo."""
    if not ids_numeros:
        return {}
    linhas = sessao.execute(select(RdmTarefa.numero_protocolo_id, RdmTarefa.situacao, Tarefa.numero).join(Tarefa, Tarefa.id == RdmTarefa.tarefa_id)
                            .where(RdmTarefa.numero_protocolo_id.in_(ids_numeros)))
    return {n: (s, t) for n, s, t in linhas}
