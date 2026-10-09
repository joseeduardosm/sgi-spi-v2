# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras do Protocolo: reserva de números, anexo, sigilo, faixas por exercício, painel e avisos.
"""Protocolo: numeração institucional por tipo de documento e exercício.

- **Quem reserva:** qualquer usuário com acesso ao recurso `protocolo` pega o **próximo número livre** da sequência (atômico: duas
  pessoas nunca recebem o mesmo). Só **CONTROLE_TOTAL** (e o SuperRoot) lança um número específico e **amplia a faixa** para trás e
  para frente.
- **Ciclo do número:** livre → reservado (finalidade) → utilizado (documento anexado). Uma reserva sem documento pode ser
  **liberada** (volta a livre) por quem reservou ou pela administração; a administração também pode **anular** um número (fora de
  uso para sempre). Toda mudança entra na **linha do tempo** do número, que sobrevive a liberações.
- **Sigilo:** o dono marca o documento como sigiloso: só ele e o SuperRoot veem o conteúdo do arquivo; os dados do número e a linha
  do tempo seguem visíveis para quem tem acesso ao Protocolo.
- **Avisos:** reserva sem documento há `PROTOCOLO_DIAS_AVISO` dias gera aviso (mensagem e e-mail) ao responsável; encerrado ao anexar,
  liberar ou anular.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import BinaryIO

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.core.banco import hoje_sao_paulo
from app.core.banco import agora_utc
from app.core.configuracao import obter_configuracao
from app.models.acl import NivelAcl
from app.models.contratos import Contrato
from app.models.protocolo import EventoProtocolo, NumeroProtocolo, SequenciaProtocolo, TipoProtocolo
from app.models.usuario import Usuario
from app.services import servico_acl, servico_anexos, servico_mensagens
from app.services.documentos.pdf import FUSO_SAO_PAULO, DocumentoPdf
from app.services.documentos.planilha import Aba, Coluna, gerar_planilha
from app.services.servico_auditoria import auditar

RECURSO = "protocolo"
MAXIMO_NUMEROS_POR_SEQUENCIA = 10000
ROTULOS_ESTADO = {"livre": "Livre", "reservado": "Reservado", "utilizado": "Utilizado", "anulado": "Anulado"}


class ErroProtocolo(Exception):
    """Regra do Protocolo violada (vira 400, ou o `status` indicado)."""

    def __init__(self, detalhe: str, status: int = 400, codigo: str = "invalido") -> None:
        super().__init__(detalhe)
        self.status, self.codigo = status, codigo


def _nome(usuario: Usuario | None) -> str:
    return (usuario.nome_completo or usuario.login) if usuario else "Sistema"


def _local(instante: datetime | None) -> str:
    """Data e hora em São Paulo (o SQLite devolve datas sem fuso: tratadas como UTC)."""
    if instante is None:
        return ""
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=UTC)
    return instante.astimezone(FUSO_SAO_PAULO).strftime("%d/%m/%Y %H:%M")


def formatar_numero(numero: int, exercicio: int) -> str:
    """"5" em 2026 → "005/2026"."""
    return f"{numero:03d}/{exercicio}"


def controle_total(sessao: Session, usuario: Usuario) -> bool:
    """SuperRoot ou CONTROLE_TOTAL no recurso `protocolo`."""
    return usuario.superusuario or servico_acl.resolver_acesso(sessao, usuario, RECURSO) == NivelAcl.CONTROLE_TOTAL


def pode_ver_documento(numero: NumeroProtocolo, usuario: Usuario) -> bool:
    """Documento sigiloso: só quem reservou o número e o SuperRoot veem o conteúdo."""
    return not numero.sigiloso or usuario.superusuario or numero.reservado_por_id == usuario.id


# --- Eventos ------------------------------------------------------------------------------------

def _evento(numero: NumeroProtocolo, tipo: str, autor: Usuario | None, texto: str = "", dados: dict | None = None, quando: datetime | None = None) -> None:
    numero.eventos.append(EventoProtocolo(tipo=tipo, autor_id=autor.id if autor else None, autor_nome=_nome(autor), texto=texto, dados=dados,
                                          ocorrido_em=quando or agora_utc()))


# --- Tipos --------------------------------------------------------------------------------------

def listar_tipos(sessao: Session) -> list[TipoProtocolo]:
    return list(sessao.scalars(select(TipoProtocolo).options(selectinload(TipoProtocolo.sequencias)).order_by(func.lower(TipoProtocolo.nome))))


def _tipo(sessao: Session, tipo_id: uuid.UUID) -> TipoProtocolo:
    tipo = sessao.get(TipoProtocolo, tipo_id)
    if tipo is None:
        raise ErroProtocolo("Tipo de documento não encontrado.", 404, "nao_encontrado")
    return tipo


def _validar_nome(sessao: Session, nome: str, ignorar: uuid.UUID | None = None) -> str:
    nome = (nome or "").strip()
    if not nome:
        raise ErroProtocolo("Informe o nome do documento.")
    if len(nome) > 200:
        raise ErroProtocolo("O nome deve ter até 200 caracteres.")
    outro = sessao.scalar(select(TipoProtocolo).where(TipoProtocolo.nome_chave == nome.lower()))
    if outro is not None and outro.id != ignorar:
        raise ErroProtocolo("Já existe um tipo de documento com esse nome.", 409, "conflito")
    return nome


def criar_tipo(sessao: Session, nome: str, autor: Usuario) -> TipoProtocolo:
    nome = _validar_nome(sessao, nome)
    tipo = TipoProtocolo(nome=nome, nome_chave=nome.lower())
    sessao.add(tipo)
    sessao.flush()
    auditar(sessao, autor.login, "protocolo.tipo.criar", nome, autor_id=autor.id, alvo_tipo="protocolo_tipo", alvo_id=tipo.id)
    sessao.commit()
    return tipo


def renomear_tipo(sessao: Session, tipo_id: uuid.UUID, nome: str, autor: Usuario) -> TipoProtocolo:
    tipo = _tipo(sessao, tipo_id)
    nome = _validar_nome(sessao, nome, ignorar=tipo.id)
    antes, tipo.nome, tipo.nome_chave = tipo.nome, nome, nome.lower()
    auditar(sessao, autor.login, "protocolo.tipo.alterar", nome, autor_id=autor.id, alvo_tipo="protocolo_tipo", alvo_id=tipo.id, dados={"de": antes, "para": nome})
    sessao.commit()
    return tipo


def excluir_tipo(sessao: Session, tipo_id: uuid.UUID, autor: Usuario) -> None:
    """Só tipos sem nenhum número reservado, utilizado ou anulado (e sem histórico)."""
    tipo = _tipo(sessao, tipo_id)
    usados = sessao.scalar(select(func.count(NumeroProtocolo.id)).join(SequenciaProtocolo).where(
        SequenciaProtocolo.tipo_id == tipo.id, (NumeroProtocolo.reservado_em.is_not(None)) | (NumeroProtocolo.anulado_em.is_not(None))))
    if usados:
        raise ErroProtocolo("Tipos com números reservados, utilizados ou anulados não podem ser excluídos.", 409, "conflito")
    auditar(sessao, autor.login, "protocolo.tipo.excluir", tipo.nome, autor_id=autor.id, alvo_tipo="protocolo_tipo", alvo_id=tipo.id)
    sessao.delete(tipo)
    sessao.commit()


# --- Sequências (faixas por exercício) ------------------------------------------------------------

def _sequencia(sessao: Session, sequencia_id: uuid.UUID) -> SequenciaProtocolo:
    sequencia = sessao.get(SequenciaProtocolo, sequencia_id)
    if sequencia is None:
        raise ErroProtocolo("Sequência não encontrada.", 404, "nao_encontrado")
    return sequencia


def _validar_faixa(inicio: int, fim: int) -> None:
    if inicio < 0 or fim < inicio:
        raise ErroProtocolo("Informe um intervalo válido.")
    if fim - inicio + 1 > MAXIMO_NUMEROS_POR_SEQUENCIA:
        raise ErroProtocolo(f"O intervalo pode conter no máximo {MAXIMO_NUMEROS_POR_SEQUENCIA:,} números.".replace(",", "."))


def criar_sequencia(sessao: Session, tipo_id: uuid.UUID, exercicio: int, inicio: int, fim: int, autor: Usuario) -> SequenciaProtocolo:
    tipo = _tipo(sessao, tipo_id)
    _validar_faixa(inicio, fim)
    if not 2000 <= exercicio <= 2200:
        raise ErroProtocolo("Exercício inválido.")
    if sessao.scalar(select(SequenciaProtocolo.id).where(SequenciaProtocolo.tipo_id == tipo.id, SequenciaProtocolo.exercicio == exercicio)):
        raise ErroProtocolo(f"{tipo.nome} já tem uma sequência para {exercicio}.", 409, "conflito")
    sequencia = SequenciaProtocolo(tipo_id=tipo.id, exercicio=exercicio, inicio=inicio, fim=fim)
    sequencia.numeros = [NumeroProtocolo(numero=n) for n in range(inicio, fim + 1)]
    sessao.add(sequencia)
    sessao.flush()
    auditar(sessao, autor.login, "protocolo.sequencia.criar", f"{tipo.nome} {exercicio}: {inicio} a {fim}", autor_id=autor.id,
            alvo_tipo="protocolo_sequencia", alvo_id=sequencia.id)
    sessao.commit()
    return sequencia


def alterar_faixa(sessao: Session, sequencia_id: uuid.UUID, inicio: int, fim: int, autor: Usuario) -> SequenciaProtocolo:
    """Amplia a faixa para trás (`inicio` menor) e para frente (`fim` maior), criando só os números novos.

    Também aceita encolher uma ponta, desde que os números removidos estejam livres e nunca tenham sido usados.
    """
    sequencia = _sequencia(sessao, sequencia_id)
    _validar_faixa(inicio, fim)
    existentes = {n.numero: n for n in sequencia.numeros}
    bloqueados = [n.numero for n in existentes.values() if (n.numero < inicio or n.numero > fim) and (n.reservado_em or n.anulado_em or n.eventos)]
    if bloqueados:
        raise ErroProtocolo("O novo intervalo não pode excluir números já reservados, utilizados ou anulados.", 409, "conflito")
    removidos = [n for n in existentes.values() if n.numero < inicio or n.numero > fim]
    for numero in removidos:
        sequencia.numeros.remove(numero)
    novos = [NumeroProtocolo(numero=n) for n in range(inicio, fim + 1) if n not in existentes]
    sequencia.numeros.extend(novos)
    antes = (sequencia.inicio, sequencia.fim)
    sequencia.inicio, sequencia.fim = inicio, fim
    sessao.flush()
    auditar(sessao, autor.login, "protocolo.sequencia.alterar", f"{sequencia.tipo.nome} {sequencia.exercicio}: {antes[0]}–{antes[1]} → {inicio}–{fim}",
            autor_id=autor.id, alvo_tipo="protocolo_sequencia", alvo_id=sequencia.id, dados={"criados": len(novos), "removidos": len(removidos)})
    sessao.commit()
    return sequencia


# --- Reserva ------------------------------------------------------------------------------------

def _numero(sessao: Session, numero_id: uuid.UUID) -> NumeroProtocolo:
    numero = sessao.scalar(select(NumeroProtocolo).where(NumeroProtocolo.id == numero_id).options(
        selectinload(NumeroProtocolo.sequencia).selectinload(SequenciaProtocolo.tipo), selectinload(NumeroProtocolo.anexo),
        selectinload(NumeroProtocolo.eventos)))
    if numero is None:
        raise ErroProtocolo("Número não encontrado.", 404, "nao_encontrado")
    return numero


def _validar_contrato(sessao: Session, usuario: Usuario, contrato_id: uuid.UUID | None) -> None:
    if contrato_id is None:
        return
    if sessao.get(Contrato, contrato_id) is None:
        raise ErroProtocolo("Contrato não encontrado.", 404, "nao_encontrado")
    if not usuario.superusuario and servico_acl.resolver_acesso(sessao, usuario, "contratos") is None:
        raise ErroProtocolo("Você não tem acesso ao Módulo de Contratos para vincular o documento.", 403, "acl_negado")


def _finalidade(texto: str) -> str:
    texto = (texto or "").strip()
    if not texto or len(texto) > 1000:
        raise ErroProtocolo("Informe a finalidade com até 1000 caracteres.")
    return texto


def _reservar(sessao: Session, candidato_id: uuid.UUID, finalidade: str, contrato_id: uuid.UUID | None, autor: Usuario) -> bool:
    """Reserva o número só se ainda estiver livre (UPDATE condicional): quem chegar depois recebe `False`."""
    agora = agora_utc()
    resultado = sessao.execute(update(NumeroProtocolo).where(
        NumeroProtocolo.id == candidato_id, NumeroProtocolo.reservado_em.is_(None), NumeroProtocolo.anulado_em.is_(None),
    ).values(finalidade=finalidade, reservado_por_id=autor.id, reservado_por_nome=_nome(autor), reservado_em=agora, contrato_id=contrato_id,
             atualizado_em=agora))
    return resultado.rowcount == 1


def proximo(sessao: Session, sequencia_id: uuid.UUID, finalidade: str, contrato_id: uuid.UUID | None, autor: Usuario) -> NumeroProtocolo:
    """Reserva o **menor número livre** da sequência. Concorrência: se outra pessoa pegar o mesmo candidato no meio, tenta o seguinte."""
    sequencia = _sequencia(sessao, sequencia_id)
    finalidade = _finalidade(finalidade)
    _validar_contrato(sessao, autor, contrato_id)
    for _ in range(8):
        candidato = sessao.scalar(select(NumeroProtocolo.id).where(
            NumeroProtocolo.sequencia_id == sequencia.id, NumeroProtocolo.reservado_em.is_(None), NumeroProtocolo.anulado_em.is_(None),
        ).order_by(NumeroProtocolo.numero).limit(1).with_for_update(skip_locked=True))
        if candidato is None:
            raise ErroProtocolo(f"A sequência de {sequencia.tipo.nome} em {sequencia.exercicio} não tem mais números livres. "
                                "Peça à administração para ampliar a faixa.", 409, "sequencia_esgotada")
        if _reservar(sessao, candidato, finalidade, contrato_id, autor):
            return _concluir_reserva(sessao, candidato, "reservou", autor, "Reservou o próximo número")
        sessao.rollback()
    raise ErroProtocolo("Não foi possível reservar agora. Tente de novo.", 409, "conflito")


def lancar(sessao: Session, numero_id: uuid.UUID, finalidade: str, contrato_id: uuid.UUID | None, autor: Usuario) -> NumeroProtocolo:
    """Reserva um número específico (só CONTROLE_TOTAL; a rota confere)."""
    numero = _numero(sessao, numero_id)
    if numero.anulado_em is not None:
        raise ErroProtocolo("Este número foi anulado e não pode ser reservado.", 409, "conflito")
    finalidade = _finalidade(finalidade)
    _validar_contrato(sessao, autor, contrato_id)
    sessao.expire(numero)
    if not _reservar(sessao, numero_id, finalidade, contrato_id, autor):
        sessao.rollback()
        raise ErroProtocolo("Este número já foi reservado por outro usuário.", 409, "conflito")
    return _concluir_reserva(sessao, numero_id, "lancou", autor, "Lançou o número escolhido")


def _concluir_reserva(sessao: Session, numero_id: uuid.UUID, tipo_evento: str, autor: Usuario, texto: str) -> NumeroProtocolo:
    sessao.flush()
    sessao.expire_all()
    numero = _numero(sessao, numero_id)
    rotulo = f"{numero.sequencia.tipo.nome} {formatar_numero(numero.numero, numero.sequencia.exercicio)}"
    _evento(numero, tipo_evento, autor, texto, {"finalidade": numero.finalidade})
    auditar(sessao, autor.login, "protocolo.reservar", rotulo, autor_id=autor.id, alvo_tipo="protocolo_numero", alvo_id=numero.id,
            dados={"finalidade": numero.finalidade})
    sessao.commit()
    return numero


def _dono_ou_admin(sessao: Session, numero: NumeroProtocolo, usuario: Usuario) -> bool:
    return numero.reservado_por_id == usuario.id or controle_total(sessao, usuario)


def liberar(sessao: Session, numero_id: uuid.UUID, motivo: str, autor: Usuario) -> NumeroProtocolo:
    """Desfaz uma reserva ainda sem documento: o número volta a livre (o histórico fica)."""
    numero = _numero(sessao, numero_id)
    if numero.estado != "reservado":
        raise ErroProtocolo("Só é possível liberar um número reservado e sem documento.", 409, "conflito")
    if not _dono_ou_admin(sessao, numero, autor):
        raise ErroProtocolo("Só quem reservou o número ou a administração do Protocolo pode liberá-lo.", 403, "sem_permissao")
    motivo = (motivo or "").strip()
    if not motivo:
        raise ErroProtocolo("Informe o motivo da liberação.")
    rotulo = f"{numero.sequencia.tipo.nome} {formatar_numero(numero.numero, numero.sequencia.exercicio)}"
    _evento(numero, "liberou", autor, motivo, {"reservado_por": numero.reservado_por_nome, "finalidade": numero.finalidade})
    numero.finalidade, numero.reservado_por_id, numero.reservado_por_nome, numero.reservado_em = "", None, "", None
    numero.contrato_id, numero.sigiloso = None, False
    servico_mensagens.encerrar(sessao, prefixo=f"protocolo:{numero.id}:")
    auditar(sessao, autor.login, "protocolo.liberar", rotulo, autor_id=autor.id, alvo_tipo="protocolo_numero", alvo_id=numero.id, dados={"motivo": motivo})
    sessao.commit()
    return numero


def anular(sessao: Session, numero_id: uuid.UUID, motivo: str, autor: Usuario) -> NumeroProtocolo:
    """Tira o número de uso para sempre (só CONTROLE_TOTAL; a rota confere). O documento anexado, se houver, continua guardado."""
    numero = _numero(sessao, numero_id)
    if numero.anulado_em is not None:
        raise ErroProtocolo("Este número já está anulado.", 409, "conflito")
    motivo = (motivo or "").strip()
    if not motivo:
        raise ErroProtocolo("Informe o motivo da anulação.")
    rotulo = f"{numero.sequencia.tipo.nome} {formatar_numero(numero.numero, numero.sequencia.exercicio)}"
    numero.anulado_em, numero.anulado_por_nome, numero.motivo_anulacao = agora_utc(), _nome(autor), motivo
    _evento(numero, "anulou", autor, motivo)
    servico_mensagens.encerrar(sessao, prefixo=f"protocolo:{numero.id}:")
    auditar(sessao, autor.login, "protocolo.anular", rotulo, autor_id=autor.id, alvo_tipo="protocolo_numero", alvo_id=numero.id, dados={"motivo": motivo})
    sessao.commit()
    return numero


def anexar(sessao: Session, numero_id: uuid.UUID, origem: BinaryIO, nome_arquivo: str, autor: Usuario, *, ignorar_dono: bool = False) -> NumeroProtocolo:
    """Anexa o documento ao número reservado: ele passa a utilizado. Só quem reservou ou a administração; um documento por número.

    `ignorar_dono=True` é para módulos que reservam o número por trás de um fluxo próprio (portarias dos contratos) e já conferiram a permissão."""
    numero = _numero(sessao, numero_id)
    if numero.anulado_em is not None:
        raise ErroProtocolo("Este número foi anulado.", 409, "conflito")
    if numero.reservado_em is None:
        raise ErroProtocolo("Reserve o número antes de anexar o documento.", 409, "conflito")
    if numero.anexo_id is not None:
        raise ErroProtocolo("Este número já possui documento anexado e não pode ser reutilizado.", 409, "conflito")
    if not ignorar_dono and not _dono_ou_admin(sessao, numero, autor):
        raise ErroProtocolo("Só quem reservou o número ou a administração do Protocolo pode anexar o documento.", 403, "sem_permissao")
    try:
        anexo = servico_anexos.guardar_arquivo(sessao, origem, nome_arquivo, "protocolo-documento", autor.id)
    except servico_anexos.ErroAnexo as erro:
        raise ErroProtocolo(str(erro)) from erro
    numero.anexo, numero.usado_em = anexo, agora_utc()
    _evento(numero, "anexou", autor, anexo.nome_original)
    servico_mensagens.encerrar(sessao, prefixo=f"protocolo:{numero.id}:")
    rotulo = f"{numero.sequencia.tipo.nome} {formatar_numero(numero.numero, numero.sequencia.exercicio)}"
    auditar(sessao, autor.login, "protocolo.anexar", rotulo, autor_id=autor.id, alvo_tipo="protocolo_numero", alvo_id=numero.id)
    sessao.commit()
    return numero


def definir_sigilo(sessao: Session, numero_id: uuid.UUID, sigiloso: bool, autor: Usuario) -> NumeroProtocolo:
    """Marca ou desmarca o sigilo do documento (quem reservou ou o SuperRoot)."""
    numero = _numero(sessao, numero_id)
    if numero.reservado_em is None:
        raise ErroProtocolo("Só um número reservado pode ser marcado como sigiloso.", 409, "conflito")
    if numero.reservado_por_id != autor.id and not autor.superusuario:
        raise ErroProtocolo("Só quem reservou o número ou o SuperRoot pode alterar o sigilo.", 403, "sem_permissao")
    if numero.sigiloso != sigiloso:
        numero.sigiloso = sigiloso
        _evento(numero, "sigilo", autor, "Documento marcado como sigiloso" if sigiloso else "Sigilo removido")
        auditar(sessao, autor.login, "protocolo.sigilo", f"{formatar_numero(numero.numero, numero.sequencia.exercicio)}: {'sim' if sigiloso else 'não'}",
                autor_id=autor.id, alvo_tipo="protocolo_numero", alvo_id=numero.id)
    sessao.commit()
    return numero


def vincular_contrato(sessao: Session, numero_id: uuid.UUID, contrato_id: uuid.UUID | None, autor: Usuario) -> NumeroProtocolo:
    """Vincula (ou desvincula) o número a um contrato. Quem reservou ou a administração."""
    numero = _numero(sessao, numero_id)
    if numero.reservado_em is None:
        raise ErroProtocolo("Só um número reservado pode ser vinculado a um contrato.", 409, "conflito")
    if not _dono_ou_admin(sessao, numero, autor):
        raise ErroProtocolo("Só quem reservou o número ou a administração do Protocolo pode vincular o contrato.", 403, "sem_permissao")
    _validar_contrato(sessao, autor, contrato_id)
    if numero.contrato_id != contrato_id:
        numero.contrato_id = contrato_id
        contrato = sessao.get(Contrato, contrato_id) if contrato_id else None
        _evento(numero, "vinculou", autor, f"Vinculado ao contrato {contrato.numero}" if contrato else "Vínculo com o contrato removido")
        auditar(sessao, autor.login, "protocolo.vincular", contrato.numero if contrato else "removido", autor_id=autor.id, alvo_tipo="protocolo_numero", alvo_id=numero.id)
    sessao.commit()
    return numero


def obter(sessao: Session, numero_id: uuid.UUID) -> NumeroProtocolo:
    return _numero(sessao, numero_id)


def numeros_do_contrato(sessao: Session, contrato_id: uuid.UUID) -> list[NumeroProtocolo]:
    return list(sessao.scalars(select(NumeroProtocolo).where(NumeroProtocolo.contrato_id == contrato_id).options(
        selectinload(NumeroProtocolo.sequencia).selectinload(SequenciaProtocolo.tipo), selectinload(NumeroProtocolo.anexo),
    ).order_by(NumeroProtocolo.reservado_em.desc())))


def numeros_da_sequencia(sessao: Session, sequencia_id: uuid.UUID) -> tuple[SequenciaProtocolo, list[NumeroProtocolo]]:
    sequencia = sessao.scalar(select(SequenciaProtocolo).where(SequenciaProtocolo.id == sequencia_id).options(selectinload(SequenciaProtocolo.tipo)))
    if sequencia is None:
        raise ErroProtocolo("Sequência não encontrada.", 404, "nao_encontrado")
    numeros = list(sessao.scalars(select(NumeroProtocolo).where(NumeroProtocolo.sequencia_id == sequencia.id).options(selectinload(NumeroProtocolo.anexo))
                                  .order_by(NumeroProtocolo.numero)))
    return sequencia, numeros


# --- Painel -------------------------------------------------------------------------------------

@dataclass
class PessoaContagem:
    usuario_id: int | None
    nome: str
    quantidade: int


def painel(sessao: Session, tipo_id: uuid.UUID, ano: int) -> dict:
    """Reservas e utilizações por mês, top 10 pessoas e reservados sem documento (do tipo, em todas as sequências)."""
    tipo = _tipo(sessao, tipo_id)
    if not 2000 <= ano <= 2200:
        raise ErroProtocolo("Exercício inválido.")
    linhas = list(sessao.scalars(select(NumeroProtocolo).join(SequenciaProtocolo).where(
        SequenciaProtocolo.tipo_id == tipo.id, NumeroProtocolo.reservado_em.is_not(None)).options(selectinload(NumeroProtocolo.sequencia))))

    def ano_de(valor: datetime | None) -> tuple[int, int] | None:
        return (valor.year, valor.month) if valor else None

    meses = [{"mes": m, "reservados": sum(1 for n in linhas if ano_de(n.reservado_em) == (ano, m) and n.anexo_id is None),
              "utilizados": sum(1 for n in linhas if ano_de(n.usado_em) == (ano, m))} for m in range(1, 13)]

    def ranking(filtro) -> list[PessoaContagem]:
        contagem: dict[tuple, int] = {}
        for n in linhas:
            if filtro(n):
                chave = (n.reservado_por_id, n.reservado_por_nome)
                contagem[chave] = contagem.get(chave, 0) + 1
        ordenado = sorted(contagem.items(), key=lambda item: (-item[1], item[0][1]))
        return [PessoaContagem(usuario_id=k[0], nome=k[1], quantidade=v) for k, v in ordenado[:10]]

    sem_documento = sorted((n for n in linhas if n.anexo_id is None and n.anulado_em is None), key=lambda n: n.reservado_em)
    return {
        "tipo": tipo, "ano": ano, "meses": meses,
        "mais_reservaram": ranking(lambda n: n.reservado_em.year == ano),
        "mais_utilizaram": ranking(lambda n: n.usado_em is not None and n.usado_em.year == ano),
        "sem_documento": sem_documento,
    }


# --- Exportação ---------------------------------------------------------------------------------

def exportar(sessao: Session, tipo_id: uuid.UUID | None, exercicio: int | None, formato: str, autor: Usuario) -> tuple[bytes, str, str]:
    """Controle de numeração em XLSX ou PDF (todas as sequências, ou só as filtradas)."""
    consulta = select(NumeroProtocolo).join(SequenciaProtocolo).join(TipoProtocolo).options(
        selectinload(NumeroProtocolo.sequencia).selectinload(SequenciaProtocolo.tipo), selectinload(NumeroProtocolo.anexo))
    descricao = []
    if tipo_id:
        consulta = consulta.where(SequenciaProtocolo.tipo_id == tipo_id)
        descricao.append(_tipo(sessao, tipo_id).nome)
    if exercicio:
        consulta = consulta.where(SequenciaProtocolo.exercicio == exercicio)
        descricao.append(str(exercicio))
    # Só números com movimento: a faixa inteira (centenas de livres) não interessa no controle
    consulta = consulta.where((NumeroProtocolo.reservado_em.is_not(None)) | (NumeroProtocolo.anulado_em.is_not(None)))
    numeros = list(sessao.scalars(consulta.order_by(func.lower(TipoProtocolo.nome), SequenciaProtocolo.exercicio, NumeroProtocolo.numero)))
    contratos = {c.id: c.numero for c in sessao.scalars(select(Contrato).where(Contrato.id.in_({n.contrato_id for n in numeros if n.contrato_id})))} if numeros else {}
    titulo = "Controle do Protocolo" + (f" — {' · '.join(descricao)}" if descricao else "")
    linhas = [[n.sequencia.tipo.nome, n.sequencia.exercicio, formatar_numero(n.numero, n.sequencia.exercicio), ROTULOS_ESTADO[n.estado], n.finalidade,
               n.reservado_por_nome, _local(n.reservado_em), _local(n.usado_em), contratos.get(n.contrato_id, ""), "Sim" if n.sigiloso else "",
               n.motivo_anulacao or ""] for n in numeros]
    sufixo = hoje_sao_paulo().strftime("%Y-%m-%d")
    if formato == "xlsx":
        colunas = [Coluna("Tipo", largura=18), Coluna("Exercício", "0", 10), Coluna("Número", largura=11), Coluna("Situação", largura=12), Coluna("Finalidade", largura=50),
                   Coluna("Responsável", largura=30), Coluna("Reservado em", largura=17), Coluna("Utilizado em", largura=17), Coluna("Contrato", largura=18),
                   Coluna("Sigiloso", largura=9), Coluna("Motivo da anulação", largura=30)]
        return gerar_planilha([Aba(nome="Protocolo", colunas=colunas, linhas=linhas, titulo=titulo)]), f"protocolo-{sufixo}.xlsx", \
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    documento = DocumentoPdf(titulo=titulo, subtitulo=f"{len(numeros)} número(s) com movimento", autor=_nome(autor))
    documento.secao("Números")
    documento.tabela(["Tipo", "Número", "Situação", "Finalidade", "Responsável", "Reservado em", "Utilizado em"],
                     [[l[0], l[2], l[3], l[4], l[5], l[6], l[7]] for l in linhas], larguras=[1.6, 1.1, 1.2, 4, 2.4, 1.6, 1.6])
    return documento.gerar(), f"protocolo-{sufixo}.pdf", "application/pdf"


# --- Avisos -------------------------------------------------------------------------------------

def lembrar_reservas(sessao: Session, dia: date | None = None) -> int:
    """Reservas sem documento há `protocolo_dias_aviso` dias (e de novo ao dobro): aviso com e-mail ao responsável.

    Idempotente pela chave `protocolo:{número}:{marco}`; encerrado ao anexar, liberar ou anular.
    """
    dias = obter_configuracao().protocolo_dias_aviso
    agora = agora_utc()
    avisados = 0
    for n in sessao.scalars(select(NumeroProtocolo).where(
        NumeroProtocolo.reservado_em.is_not(None), NumeroProtocolo.anexo_id.is_(None), NumeroProtocolo.anulado_em.is_(None),
        NumeroProtocolo.reservado_por_id.is_not(None)).options(selectinload(NumeroProtocolo.sequencia).selectinload(SequenciaProtocolo.tipo))):
        reservado = n.reservado_em if n.reservado_em.tzinfo else n.reservado_em.replace(tzinfo=agora.tzinfo)
        idade = (agora - reservado).days
        marco = 2 if idade >= 2 * dias else 1 if idade >= dias else 0
        if not marco:
            continue
        rotulo = f"{n.sequencia.tipo.nome} {formatar_numero(n.numero, n.sequencia.exercicio)}"
        if servico_mensagens.notificar(
            sessao, [n.reservado_por_id], f"Documento pendente no Protocolo: {rotulo}",
            f"Você reservou o número {rotulo} há {idade} dias ({n.finalidade[:120]}) e ainda não anexou o documento. "
            "Anexe o documento ou, se o número não for mais necessário, libere a reserva.",
            chave=f"protocolo:{n.id}:{marco}", categoria="pendencia", prioridade="alta", link="/protocolo", email=True,
        ):
            avisados += 1
    sessao.commit()
    return avisados
