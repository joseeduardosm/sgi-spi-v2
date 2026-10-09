# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras da portaria de designação dos contratos: solicitação, aceite, exportação e publicação.
"""Portaria de designação de gestão e fiscalização do contrato.

Ciclo: **solicitar** (reserva o número no Protocolo, tipo "Portaria", e congela o texto) → **aguardando aceite** da autoridade signatária
(que pode **devolver**; o solicitante ajusta e **reenvia**) → **aceita** → **publicada** (o PDF publicado volta ao sistema: fica anexado
ao número do Protocolo e em "Documentos Importantes" do contrato, tipo 16). Antes da publicação, Word e PDF saem com a marca d'água
"MINUTA". **Cancelar** libera o número reservado. Há uma portaria em andamento por contrato.

O Art. 5º cita a portaria anterior do contrato (as aceitas/publicadas pelo sistema ou, na falta, um número de "Portaria" do Protocolo já
vinculado ao contrato); sem anterior, revoga genericamente. O RS vem do RH (restrito à CGP) e nunca é exposto: sem ele, não há aceite.
"""

import uuid
from datetime import UTC, datetime
from io import BytesIO
from typing import BinaryIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc, hoje_sao_paulo
from app.models.contratos import PAPEIS_EQUIPE, Contrato, DocumentoContrato
from app.models.contratos.execucao import ModeloGlobal
from app.models.contratos.portaria import AutoridadePortaria, PortariaContrato
from app.models.protocolo import NumeroProtocolo, SequenciaProtocolo, TipoProtocolo
from app.models.rh import DadosFuncionais
from app.models.usuario import Usuario
from app.services import servico_anexos, servico_mensagens, servico_protocolo
from app.services.contratos import portaria_documento, portaria_mascara
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado, SemPermissaoContrato
from app.schemas.contratos.portaria import LeituraAutoridade, LeituraPessoaPortaria, LeituraPortaria, PainelPortarias
from app.services.contratos.servico_contratos import designacoes_vigentes, exigir_edicao, obter_contrato, pode_editar
from app.services.documentos.pdf import FUSO_SAO_PAULO
from app.services.servico_auditoria import auditar

CODIGO_DOCUMENTO = 16
NOME_TIPO_PROTOCOLO = "portaria"
EM_ANDAMENTO = ("aguardando_aceite", "devolvida", "aceita")
ROTULOS_STATUS = {"aguardando_aceite": "Aguardando aceite", "devolvida": "Devolvida", "aceita": "Aceita", "publicada": "Publicada", "cancelada": "Cancelada"}


def _nome(usuario: Usuario) -> str:
    return usuario.nome_completo or usuario.login


def _local(instante: datetime) -> datetime:
    return (instante if instante.tzinfo else instante.replace(tzinfo=UTC)).astimezone(FUSO_SAO_PAULO)


def _cnpj(valor: str) -> str:
    d = "".join(c for c in valor or "" if c.isdigit())
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else valor or ""


# --- Autoridades --------------------------------------------------------------------------------

def listar_autoridades(sessao: Session, somente_ativas: bool = False) -> list[AutoridadePortaria]:
    consulta = select(AutoridadePortaria).order_by(func.lower(AutoridadePortaria.sigla), func.lower(AutoridadePortaria.nome))
    if somente_ativas:
        consulta = consulta.where(AutoridadePortaria.ativa.is_(True))
    return list(sessao.scalars(consulta))


def _autoridade(sessao: Session, autoridade_id: uuid.UUID) -> AutoridadePortaria:
    autoridade = sessao.get(AutoridadePortaria, autoridade_id)
    if autoridade is None:
        raise RegistroNaoEncontrado("Autoridade")
    return autoridade


def _validar_autoridade(sessao: Session, dados) -> dict:
    campos = {c: (getattr(dados, c) or "").strip() for c in ("sigla", "nome", "cargo", "setor")}
    if not all(campos.values()):
        raise ErroRegraContrato("Informe sigla, nome, cargo e setor da autoridade.")
    if dados.usuario_id is not None and sessao.get(Usuario, dados.usuario_id) is None:
        raise ErroRegraContrato("O usuário que dará o aceite não foi encontrado.")
    return {**campos, "usuario_id": dados.usuario_id, "ativa": dados.ativa}


def criar_autoridade(sessao: Session, dados, autor: Usuario) -> AutoridadePortaria:
    autoridade = AutoridadePortaria(**_validar_autoridade(sessao, dados))
    sessao.add(autoridade)
    sessao.flush()
    auditar(sessao, autor.login, "portaria.autoridade.criar", autoridade.nome, autor_id=autor.id, alvo_tipo="portaria_autoridade", alvo_id=autoridade.id)
    sessao.commit()
    return autoridade


def alterar_autoridade(sessao: Session, autoridade_id: uuid.UUID, dados, autor: Usuario) -> AutoridadePortaria:
    autoridade = _autoridade(sessao, autoridade_id)
    for campo, valor in _validar_autoridade(sessao, dados).items():
        setattr(autoridade, campo, valor)
    auditar(sessao, autor.login, "portaria.autoridade.alterar", autoridade.nome, autor_id=autor.id, alvo_tipo="portaria_autoridade", alvo_id=autoridade.id)
    sessao.commit()
    return autoridade


def excluir_autoridade(sessao: Session, autoridade_id: uuid.UUID, autor: Usuario) -> None:
    """Só autoridades sem portaria; as demais são apenas desativadas."""
    autoridade = _autoridade(sessao, autoridade_id)
    if sessao.scalar(select(func.count(PortariaContrato.id)).where(PortariaContrato.autoridade_id == autoridade.id)):
        raise ErroRegraContrato("Esta autoridade já assinou portarias: desative-a em vez de excluir.", conflito=True)
    auditar(sessao, autor.login, "portaria.autoridade.excluir", autoridade.nome, autor_id=autor.id, alvo_tipo="portaria_autoridade", alvo_id=autoridade.id)
    sessao.delete(autoridade)
    sessao.commit()


# --- Dados do texto -----------------------------------------------------------------------------

def _equipe(sessao: Session, contrato: Contrato) -> list[dict]:
    """Equipe vigente na ordem dos papéis (papel sem designado é omitido), com o RS lido do RH."""
    vigentes = {d.papel: d for d in designacoes_vigentes(contrato)}
    pessoas = [vigentes[p] for p in PAPEIS_EQUIPE if p in vigentes]
    rs = {r.usuario_id: (r.rs_pv or "").strip() for r in sessao.scalars(select(DadosFuncionais).where(DadosFuncionais.usuario_id.in_([d.usuario_id for d in pessoas])))}
    return [{"papel": d.papel, "usuario_id": d.usuario_id, "nome": d.nome_usuario, "rs": rs.get(d.usuario_id, "")} for d in pessoas]


def _anterior(sessao: Session, contrato: Contrato, excluir_id: uuid.UUID | None, excluir_numero_id: uuid.UUID | None) -> dict | None:
    """Portaria anterior do contrato para o Art. 5º (None → revogação genérica)."""
    consulta = select(PortariaContrato).where(PortariaContrato.contrato_id == contrato.id, PortariaContrato.status.in_(("aceita", "publicada")))
    if excluir_id:
        consulta = consulta.where(PortariaContrato.id != excluir_id)
    anterior = sessao.scalars(consulta.order_by(PortariaContrato.aceita_em.desc())).first()
    if anterior is not None:
        quando = _local(anterior.aceita_em)
        return {"portaria_id": str(anterior.id), "sigla": anterior.sigla, "numero": anterior.numero,
                "dia": quando.day, "mes": quando.month, "ano": quando.year}
    # Sem portaria do sistema: um número de "Portaria" do Protocolo já vinculado ao contrato (cadastrado antes desta funcionalidade)
    ja_usados = select(PortariaContrato.numero_protocolo_id).where(PortariaContrato.numero_protocolo_id.is_not(None))
    numero = sessao.scalars(
        select(NumeroProtocolo).join(SequenciaProtocolo).join(TipoProtocolo).where(
            NumeroProtocolo.contrato_id == contrato.id, NumeroProtocolo.anulado_em.is_(None), NumeroProtocolo.reservado_em.is_not(None),
            TipoProtocolo.nome_chave == NOME_TIPO_PROTOCOLO, NumeroProtocolo.id.not_in(ja_usados), NumeroProtocolo.id != excluir_numero_id,
        ).order_by(NumeroProtocolo.reservado_em.desc())
    ).first()
    if numero is None:
        return None
    quando = _local(numero.reservado_em)
    return {"portaria_id": None, "sigla": "", "numero": numero.numero, "dia": quando.day, "mes": quando.month, "ano": quando.year}


def _mascara(sessao: Session, variante: str) -> str:
    """HTML da máscara ativa da variante (cadastrada em Contratos → Modelos)."""
    for modelo in sessao.scalars(select(ModeloGlobal).where(ModeloGlobal.tipo == "portaria", ModeloGlobal.ativo.is_(True))):
        if modelo.conteudo.get("variante") == variante:
            return modelo.conteudo["html"]
    rotulo = "com portaria anterior" if variante == "com_anterior" else "sem portaria anterior"
    raise ErroRegraContrato(f"Não há máscara de portaria ativa ({rotulo}). Peça a quem administra Contratos para cadastrá-la em Contratos → Modelos.")


def _valores(dados: dict) -> dict[str, str]:
    """Valor de cada placeholder da máscara."""
    por_papel = {p["papel"]: p for p in dados["equipe"]}
    fiscal = por_papel.get("fiscal_tecnico") or por_papel.get("fiscal_administrativo") or {}
    valores = {
        "numeroportaria": f"{dados['numero']:03d}", "anoportaria": str(dados["exercicio"]), "numerodocontrato": dados["contrato_numero"],
        "contratada": dados["empresa"], "cnpjcontratada": dados["cnpj"], "objetodocontrato": (dados["objeto"] or "").strip().rstrip("."),
        "nroprocessosei": dados["processo_sei"], "nomeautoridade": dados["autoridade"]["nome"],
        "nomefiscal": fiscal.get("nome", ""), "rsfiscal": fiscal.get("rs", ""),
    }
    for chave, papel in (("gestor", "gestor"), ("gestorsuplente", "gestor_suplente"), ("fiscaladministrativo", "fiscal_administrativo"),
                         ("fiscaladministrativosuplente", "fiscal_administrativo_suplente"), ("fiscaltecnico", "fiscal_tecnico"),
                         ("fiscaltecnicosuplente", "fiscal_tecnico_suplente")):
        valores[f"nome{chave}"], valores[f"rs{chave}"] = por_papel.get(papel, {}).get("nome", ""), por_papel.get(papel, {}).get("rs", "")
    anterior = dados.get("anterior")
    if anterior:
        valores |= {"nomedocumento": anterior["sigla"], "numeroportariaanterior": f"{anterior['numero']:03d}", "diaportariaanterior": str(anterior["dia"]),
                    "mesportariaanterior": portaria_documento.MESES[anterior["mes"] - 1], "anoportariaanterior": str(anterior["ano"])}
    return valores


def montar_dados(sessao: Session, contrato: Contrato, autoridade: AutoridadePortaria, numero: int, exercicio: int, excluir_id: uuid.UUID | None = None,
                 excluir_numero_id: uuid.UUID | None = None) -> dict:
    """Retrato usado no texto da portaria (congelado na solicitação e atualizado no reenvio e no aceite), com o HTML da máscara já preenchido."""
    equipe = _equipe(sessao, contrato)
    if not any(p["papel"] == "gestor" for p in equipe):
        raise ErroRegraContrato("Designe o gestor na aba Equipe do contrato antes de solicitar a portaria.")
    anterior = _anterior(sessao, contrato, excluir_id, excluir_numero_id)
    if anterior:
        anterior["sigla"] = autoridade.sigla
    mascara = _mascara(sessao, "com_anterior" if anterior else "sem_anterior")
    dados = {
        "sigla": autoridade.sigla, "numero": numero, "exercicio": exercicio,
        "autoridade": {"nome": autoridade.nome, "cargo": autoridade.cargo, "setor": autoridade.setor},
        "contrato_numero": contrato.numero, "empresa": contrato.empresa.razao_social, "cnpj": _cnpj(contrato.empresa.cnpj),
        "processo_sei": contrato.sei_gestao_numero or "", "objeto": contrato.objeto or "", "equipe": equipe, "anterior": anterior,
        "placeholders": sorted(portaria_mascara.usados(mascara)),
    }
    dados["texto_html"] = portaria_mascara.preencher(mascara, _valores(dados))
    return dados


def pendencias(dados: dict) -> list[str]:
    """O que impede o aceite: RS ausente de quem aparece na máscara, processo SEI ou objeto em branco."""
    usados = set(dados.get("placeholders") or [])
    faltas = []
    for p in dados["equipe"]:
        chaves = {f"rs{p['papel'].replace('_', '')}"}
        if p["papel"] in ("fiscal_tecnico", "fiscal_administrativo"):
            chaves.add("rsfiscal")
        if not p["rs"] and chaves & usados:
            faltas.append(f"RS de {p['nome']} (peça à CGP)")
    if not dados["processo_sei"] and "nroprocessosei" in usados:
        faltas.append("Número do processo SEI de gestão no contrato")
    if not dados["objeto"].strip():
        faltas.append("Objeto do contrato")
    return faltas


# --- Consulta -----------------------------------------------------------------------------------

def _portaria(sessao: Session, contrato_id: uuid.UUID, portaria_id: uuid.UUID) -> PortariaContrato:
    portaria = sessao.get(PortariaContrato, portaria_id)
    if portaria is None or portaria.contrato_id != contrato_id:
        raise RegistroNaoEncontrado("Portaria")
    return portaria


def listar(sessao: Session, contrato_id: uuid.UUID) -> list[PortariaContrato]:
    obter_contrato(sessao, contrato_id)
    return list(sessao.scalars(select(PortariaContrato).where(PortariaContrato.contrato_id == contrato_id).order_by(PortariaContrato.solicitada_em.desc())))


def pode_decidir(sessao: Session, portaria: PortariaContrato, usuario: Usuario) -> bool:
    """Aceita ou devolve: o usuário vinculado à autoridade signatária (ou o SuperRoot)."""
    autoridade = sessao.get(AutoridadePortaria, portaria.autoridade_id) if portaria.autoridade_id else None
    return usuario.superusuario or (autoridade is not None and autoridade.usuario_id == usuario.id)


# --- Fluxo --------------------------------------------------------------------------------------

def _sequencia_do_ano(sessao: Session) -> SequenciaProtocolo:
    exercicio = hoje_sao_paulo().year
    sequencia = sessao.scalar(select(SequenciaProtocolo).join(TipoProtocolo).where(TipoProtocolo.nome_chave == NOME_TIPO_PROTOCOLO, SequenciaProtocolo.exercicio == exercicio))
    if sequencia is None:
        raise ErroRegraContrato(f"O Protocolo não tem a faixa de numeração de Portaria para {exercicio}: peça à administração do Protocolo para cadastrá-la.")
    return sequencia


def _avisar(sessao: Session, portaria: PortariaContrato, destinatarios: list[int | None], assunto: str, corpo: str, autor: Usuario, categoria: str = "comunicado") -> None:
    servico_mensagens.notificar(sessao, [d for d in destinatarios if d], assunto, corpo, chave=f"portaria:{portaria.id}:{portaria.status}:{agora_utc().timestamp()}",
                                categoria=categoria, link=f"/contratos/{portaria.contrato_id}?aba=portaria", contrato_id=portaria.contrato_id, autor=autor)


def _rotulo(portaria: PortariaContrato) -> str:
    return f"Portaria {portaria.sigla} nº {portaria.numero:03d}/{portaria.exercicio}"


def solicitar(sessao: Session, contrato_id: uuid.UUID, autoridade_id: uuid.UUID, autor: Usuario) -> PortariaContrato:
    """Reserva o número no Protocolo, congela o texto e envia para o aceite da autoridade."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    autoridade = _autoridade(sessao, autoridade_id)
    if not autoridade.ativa:
        raise ErroRegraContrato("Esta autoridade está desativada.")
    if sessao.scalar(select(func.count(PortariaContrato.id)).where(PortariaContrato.contrato_id == contrato.id, PortariaContrato.status.in_(EM_ANDAMENTO))):
        raise ErroRegraContrato("Este contrato já tem uma portaria em andamento: conclua ou cancele-a antes de solicitar outra.", conflito=True)
    sequencia = _sequencia_do_ano(sessao)
    montar_dados(sessao, contrato, autoridade, 0, sequencia.exercicio)  # valida a equipe antes de gastar um número
    try:
        numero = servico_protocolo.proximo(sessao, sequencia.id, f"Portaria de designação de gestão e fiscalização do Contrato {contrato.numero}", contrato.id, autor)
    except servico_protocolo.ErroProtocolo as erro:
        raise ErroRegraContrato(str(erro), conflito=erro.status == 409) from erro
    portaria = PortariaContrato(
        contrato_id=contrato.id, autoridade_id=autoridade.id, numero_protocolo_id=numero.id, sigla=autoridade.sigla, numero=numero.numero,
        exercicio=sequencia.exercicio, status="aguardando_aceite", solicitada_por_id=autor.id, solicitada_por_nome=_nome(autor),
        dados=montar_dados(sessao, contrato, autoridade, numero.numero, sequencia.exercicio, excluir_numero_id=numero.id),
    )
    portaria.portaria_anterior_id = (uuid.UUID(portaria.dados["anterior"]["portaria_id"]) if portaria.dados["anterior"] and portaria.dados["anterior"]["portaria_id"] else None)
    sessao.add(portaria)
    sessao.flush()
    auditar(sessao, autor.login, "portaria.solicitar", _rotulo(portaria), autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id, dados={"portaria_id": str(portaria.id)})
    _avisar(sessao, portaria, [autoridade.usuario_id], f"Portaria aguardando seu aceite — Contrato {contrato.numero}",
            f"{_nome(autor)} solicitou a {_rotulo(portaria)}. Abra a aba Portarias do contrato para aceitar ou devolver.", autor, "pendencia")
    sessao.commit()
    return portaria


def _atualizar(sessao: Session, portaria: PortariaContrato) -> None:
    contrato = obter_contrato(sessao, portaria.contrato_id)
    autoridade = _autoridade(sessao, portaria.autoridade_id) if portaria.autoridade_id else None
    if autoridade is None:
        raise ErroRegraContrato("A autoridade desta portaria foi excluída.")
    portaria.dados = montar_dados(sessao, contrato, autoridade, portaria.numero, portaria.exercicio, excluir_id=portaria.id,
                                  excluir_numero_id=portaria.numero_protocolo_id)


def reenviar(sessao: Session, contrato_id: uuid.UUID, portaria_id: uuid.UUID, autor: Usuario) -> PortariaContrato:
    """Depois de devolvida (ou para atualizar equipe e dados), refaz o texto e volta para o aceite."""
    portaria = _portaria(sessao, contrato_id, portaria_id)
    exigir_edicao(sessao, obter_contrato(sessao, contrato_id), autor)
    if portaria.status not in ("devolvida", "aguardando_aceite"):
        raise ErroRegraContrato("Só portarias aguardando aceite ou devolvidas podem ser reenviadas.", conflito=True)
    _atualizar(sessao, portaria)
    portaria.status, portaria.motivo = "aguardando_aceite", ""
    auditar(sessao, autor.login, "portaria.reenviar", _rotulo(portaria), autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato_id, dados={"portaria_id": str(portaria.id)})
    autoridade = sessao.get(AutoridadePortaria, portaria.autoridade_id)
    _avisar(sessao, portaria, [autoridade.usuario_id if autoridade else None], f"Portaria aguardando seu aceite — {_rotulo(portaria)}",
            f"{_nome(autor)} reenviou a {_rotulo(portaria)} para o seu aceite.", autor, "pendencia")
    sessao.commit()
    return portaria


def aceitar(sessao: Session, contrato_id: uuid.UUID, portaria_id: uuid.UUID, autor: Usuario) -> PortariaContrato:
    """Aceite da autoridade signatária. Atualiza o texto com a equipe e o RS atuais; sem RS, o aceite é bloqueado."""
    portaria = _portaria(sessao, contrato_id, portaria_id)
    if not pode_decidir(sessao, portaria, autor):
        raise SemPermissaoContrato("Somente a autoridade signatária da portaria (ou o SuperRoot) pode aceitá-la.")
    if portaria.status != "aguardando_aceite":
        raise ErroRegraContrato("Esta portaria não está aguardando aceite.", conflito=True)
    _atualizar(sessao, portaria)
    faltas = pendencias(portaria.dados)
    if faltas:
        raise ErroRegraContrato("Não é possível aceitar: falta " + "; ".join(faltas) + ".")
    portaria.status, portaria.aceita_por_nome, portaria.aceita_em = "aceita", _nome(autor), agora_utc()
    servico_mensagens.encerrar(sessao, prefixo=f"portaria:{portaria.id}:")
    auditar(sessao, autor.login, "portaria.aceitar", _rotulo(portaria), autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato_id, dados={"portaria_id": str(portaria.id)})
    _avisar(sessao, portaria, [portaria.solicitada_por_id], f"Portaria aceita — {_rotulo(portaria)}",
            "A autoridade aceitou a portaria. Exporte a minuta, publique no SEI e no DOE e anexe o PDF publicado na aba Portarias.", autor)
    sessao.commit()
    return portaria


def devolver(sessao: Session, contrato_id: uuid.UUID, portaria_id: uuid.UUID, motivo: str, autor: Usuario) -> PortariaContrato:
    portaria = _portaria(sessao, contrato_id, portaria_id)
    if not pode_decidir(sessao, portaria, autor):
        raise SemPermissaoContrato("Somente a autoridade signatária da portaria (ou o SuperRoot) pode devolvê-la.")
    if portaria.status != "aguardando_aceite":
        raise ErroRegraContrato("Esta portaria não está aguardando aceite.", conflito=True)
    motivo = (motivo or "").strip()
    if not motivo:
        raise ErroRegraContrato("Informe o motivo da devolução.")
    portaria.status, portaria.motivo = "devolvida", motivo
    servico_mensagens.encerrar(sessao, prefixo=f"portaria:{portaria.id}:")
    auditar(sessao, autor.login, "portaria.devolver", _rotulo(portaria), autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato_id, dados={"motivo": motivo})
    _avisar(sessao, portaria, [portaria.solicitada_por_id], f"Portaria devolvida — {_rotulo(portaria)}", f"Motivo: {motivo}", autor)
    sessao.commit()
    return portaria


def cancelar(sessao: Session, contrato_id: uuid.UUID, portaria_id: uuid.UUID, motivo: str, autor: Usuario) -> PortariaContrato:
    """Cancela a portaria e libera o número no Protocolo (para quem reservou ou a administração do Protocolo)."""
    portaria = _portaria(sessao, contrato_id, portaria_id)
    exigir_edicao(sessao, obter_contrato(sessao, contrato_id), autor)
    if portaria.status not in EM_ANDAMENTO:
        raise ErroRegraContrato("Só portarias em andamento podem ser canceladas.", conflito=True)
    motivo = (motivo or "").strip()
    if not motivo:
        raise ErroRegraContrato("Informe o motivo do cancelamento.")
    if portaria.numero_protocolo_id:
        try:
            servico_protocolo.liberar(sessao, portaria.numero_protocolo_id, f"Portaria cancelada: {motivo}", autor)
        except servico_protocolo.ErroProtocolo as erro:
            raise ErroRegraContrato(str(erro)) from erro
    portaria.status, portaria.motivo = "cancelada", motivo
    servico_mensagens.encerrar(sessao, prefixo=f"portaria:{portaria.id}:")
    auditar(sessao, autor.login, "portaria.cancelar", _rotulo(portaria), autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato_id, dados={"motivo": motivo})
    sessao.commit()
    return portaria


def publicar(sessao: Session, contrato_id: uuid.UUID, portaria_id: uuid.UUID, arquivo: BinaryIO, nome_arquivo: str, autor: Usuario) -> PortariaContrato:
    """Recebe o PDF publicado: anexa ao número do Protocolo e a "Documentos Importantes" do contrato (tipo 16)."""
    portaria = _portaria(sessao, contrato_id, portaria_id)
    contrato = obter_contrato(sessao, contrato_id)
    exigir_edicao(sessao, contrato, autor)
    if portaria.status != "aceita":
        raise ErroRegraContrato("Só portarias aceitas podem receber o PDF publicado.", conflito=True)
    conteudo = arquivo.read()
    try:
        if portaria.numero_protocolo_id:
            servico_protocolo.anexar(sessao, portaria.numero_protocolo_id, BytesIO(conteudo), nome_arquivo, autor, ignorar_dono=True)
        anexo = servico_anexos.guardar_pdf_gerado(sessao, conteudo, nome_arquivo or "portaria.pdf", "contrato-documento", autor.id, contrato_id=contrato.id)
    except servico_protocolo.ErroProtocolo as erro:
        raise ErroRegraContrato(str(erro)) from erro
    documento = next((d for d in contrato.documentos if d.codigo_tipo == CODIGO_DOCUMENTO), None)
    if documento is None:
        documento = DocumentoContrato(codigo_tipo=CODIGO_DOCUMENTO, titulo=f"Portaria {portaria.sigla} nº {portaria.numero:03d}/{portaria.exercicio}")
        contrato.documentos.append(documento)
    elif documento.anexo:
        servico_anexos.descartar(documento.anexo)
    documento.titulo = f"Portaria {portaria.sigla} nº {portaria.numero:03d}/{portaria.exercicio}"
    documento.anexo, documento.enviado_em, documento.enviado_por_id = anexo, agora_utc(), autor.id
    portaria.status, portaria.publicada_em = "publicada", agora_utc()
    auditar(sessao, autor.login, "portaria.publicar", _rotulo(portaria), autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato_id,
            dados={"portaria_id": str(portaria.id), "arquivo": nome_arquivo, "sha256": anexo.sha256})
    sessao.commit()
    return portaria


def exportar(sessao: Session, contrato_id: uuid.UUID, portaria_id: uuid.UUID, formato: str) -> tuple[bytes, str, str]:
    """(conteúdo, nome do arquivo, tipo de conteúdo) da minuta com marca d'água, a partir do texto congelado."""
    portaria = _portaria(sessao, contrato_id, portaria_id)
    if portaria.status == "cancelada":
        raise ErroRegraContrato("Portarias canceladas não são exportadas.")
    contrato = obter_contrato(sessao, contrato_id)
    base = f"MINUTA_PORTARIA_{portaria.numero:03d}_{portaria.exercicio}_SPI_{contrato.numero_arquivo}"
    if formato == "docx":
        return portaria_documento.gerar_word(portaria.dados), f"{base}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return portaria_documento.gerar_pdf(portaria.dados), f"{base}.pdf", "application/pdf"


# --- Painel -------------------------------------------------------------------------------------

def _rotulo_anterior(dados: dict) -> str | None:
    anterior = dados.get("anterior")
    if not anterior:
        return None
    return f"Portaria {anterior['sigla']} nº {anterior['numero']:03d}, de {anterior['dia']} de {portaria_documento.MESES[anterior['mes'] - 1]} de {anterior['ano']}".replace("  ", " ")


def _leitura(sessao: Session, portaria: PortariaContrato, usuario: Usuario, pode_alterar: bool) -> LeituraPortaria:
    autoridade = sessao.get(AutoridadePortaria, portaria.autoridade_id) if portaria.autoridade_id else None
    dados = portaria.dados
    em_aberto = portaria.status in EM_ANDAMENTO
    return LeituraPortaria(
        id=portaria.id, titulo=portaria_documento.titulo(dados), sigla=portaria.sigla, numero=portaria.numero, exercicio=portaria.exercicio,
        status=portaria.status, status_rotulo=ROTULOS_STATUS[portaria.status], motivo=portaria.motivo,
        autoridade_nome=autoridade.nome if autoridade else dados["autoridade"]["nome"], solicitada_por_nome=portaria.solicitada_por_nome,
        solicitada_em=portaria.solicitada_em, aceita_por_nome=portaria.aceita_por_nome, aceita_em=portaria.aceita_em, publicada_em=portaria.publicada_em,
        numero_protocolo_id=portaria.numero_protocolo_id, anterior=_rotulo_anterior(dados),
        equipe=[LeituraPessoaPortaria(papel=p["papel"], papel_rotulo=portaria_documento.ROTULOS_PAPEL[p["papel"]], nome=p["nome"], rs_informado=bool(p["rs"]))
                for p in dados["equipe"]],
        pendencias=pendencias(dados) if portaria.status in ("aguardando_aceite", "devolvida") else [],
        pode_decidir=portaria.status == "aguardando_aceite" and pode_decidir(sessao, portaria, usuario),
        pode_alterar=pode_alterar and em_aberto,
    )


def painel(sessao: Session, contrato_id: uuid.UUID, usuario: Usuario) -> PainelPortarias:
    """Histórico de portarias do contrato, autoridades ativas e o que o usuário pode fazer."""
    contrato = obter_contrato(sessao, contrato_id)
    pode_alterar = pode_editar(sessao, contrato, usuario)
    portarias = listar(sessao, contrato_id)
    nomes = {u.id: _nome(u) for u in sessao.scalars(select(Usuario).where(Usuario.id.in_([a.usuario_id for a in listar_autoridades(sessao) if a.usuario_id])))}
    return PainelPortarias(
        portarias=[_leitura(sessao, p, usuario, pode_alterar) for p in portarias],
        autoridades=[leitura_autoridade(a, nomes) for a in listar_autoridades(sessao, somente_ativas=True)],
        em_andamento=any(p.status in EM_ANDAMENTO for p in portarias),
    )


def leitura_autoridade(autoridade: AutoridadePortaria, nomes: dict[int, str]) -> LeituraAutoridade:
    return LeituraAutoridade(id=autoridade.id, sigla=autoridade.sigla, nome=autoridade.nome, cargo=autoridade.cargo, setor=autoridade.setor,
                             usuario_id=autoridade.usuario_id, ativa=autoridade.ativa, usuario_nome=nomes.get(autoridade.usuario_id))


def autoridades_com_nomes(sessao: Session) -> list[LeituraAutoridade]:
    autoridades = listar_autoridades(sessao)
    nomes = {u.id: _nome(u) for u in sessao.scalars(select(Usuario).where(Usuario.id.in_([a.usuario_id for a in autoridades if a.usuario_id])))}
    return [leitura_autoridade(a, nomes) for a in autoridades]
