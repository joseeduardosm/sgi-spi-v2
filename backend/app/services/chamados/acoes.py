# Criado por José Eduardo Santana Martins
# Este arquivo serve para as ações do atendimento do marco 2: pendência, "Não resolveu", alterações, em cópia, tarefas, aprovações e local.
"""Ações do atendimento dos Chamados (marco 2).

- **Pendente** pausa o prazo de solução (o tempo útil parado empurra o prazo); retomar, ou a resposta do solicitante, volta ao atendimento.
- **"Não resolveu"**: o solicitante (ou alguém do setor solicitante) reabre o mesmo chamado em até N dias úteis depois da solução
  (parâmetro `dias_reabrir`, padrão 5), dizendo o porquê. O prazo de solução recomeça da reabertura.
- **Alterar** (quem atende): responsável, setor responsável, categoria (reaplica setor, SLAs e prioridade da categoria nova) e prioridade
  (com motivo). Trava otimista pela `versao`.
- **Em cópia**: pessoas ou setores que veem o chamado e recebem os avisos.
- **Tarefas** da equipe e **aprovação** pedida a uma pessoa ou a um setor (enquanto houver aprovação aguardando, o chamado fica "Em aprovação").
- **Local**: a sala do Patrimônio sugerida para o solicitante e a busca de salas.
"""

import uuid
from datetime import datetime
from html import escape

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.banco import agora_utc
from app.models.chamados import (
    PRIORIDADES, STATUS_EM_APROVACAO, STATUS_EM_ATENDIMENTO, STATUS_NOVO, STATUS_PENDENTE, STATUS_SOLUCIONADO, AcompanhamentoChamado, AtorChamado,
    CategoriaChamados, Chamado, TarefaChamado, ValidacaoChamado,
)
from app.models.patrimonio import Bem, Localizacao
from app.models.setor import MembroSetor, Setor
from app.models.usuario import Usuario
from app.services.chamados import acesso, motor_sla, parametros
from app.services.chamados.acesso import Papeis
from app.services.chamados.servico import (
    ErroChamado, _avisar, _exigir_aberto, _nome, _prazo, catalogo, membros_ativos, obter, retomar_relogio,
)
from app.services.patrimonio import servico_localizacoes
from app.services.servico_auditoria import auditar


def _registrar(chamado: Chamado, autor: Usuario, texto: str) -> None:
    """Registro automático na linha do tempo."""
    chamado.acompanhamentos.append(AcompanhamentoChamado(autor_id=autor.id, texto=texto, automatico=True, criado_em=agora_utc()))


def _exigir_atendente(sessao: Session, usuario: Usuario, p: Papeis, numero: int, mensagem: str) -> Chamado:
    chamado, a = obter(sessao, usuario, p, numero)
    if not acesso.atende(a, p, chamado):
        raise ErroChamado(mensagem, 403, "acesso_negado")
    return chamado


def _conferir_versao(chamado: Chamado, versao: int | None) -> None:
    if versao is not None and versao != chamado.versao:
        raise ErroChamado("Este chamado foi alterado por outra pessoa. Recarregue para ver como está.", 409, "chamado_alterado")


# ---------------------------------------------------------------------------------------------
# Pendência
# ---------------------------------------------------------------------------------------------

def pendente(sessao: Session, usuario: Usuario, p: Papeis, numero: int, motivo: str) -> Chamado:
    """Põe o chamado em pendente: o prazo de solução para de contar até retomar (ou até o solicitante responder)."""
    chamado = _exigir_atendente(sessao, usuario, p, numero, "Só quem atende o chamado põe em pendente.")
    _exigir_aberto(chamado)
    if chamado.status_base == STATUS_PENDENTE:
        return chamado
    chamado.status_base = STATUS_PENDENTE
    chamado.espera_desde = agora_utc()
    chamado.versao += 1
    texto = f"{_nome(usuario)} pôs o chamado em pendente" + (f": {motivo.strip()}" if motivo.strip() else ".")
    _registrar(chamado, usuario, texto)
    if chamado.solicitante_id:
        _avisar(sessao, [chamado.solicitante_id], f"Seu chamado #{chamado.numero} aguarda você", texto, chamado,
                f"pendente:{chamado.versao}", "chamados.acompanhamento", usuario)
    return chamado


def retomar(sessao: Session, usuario: Usuario, p: Papeis, numero: int) -> Chamado:
    chamado = _exigir_atendente(sessao, usuario, p, numero, "Só quem atende o chamado retoma o atendimento.")
    _exigir_aberto(chamado)
    if chamado.status_base != STATUS_PENDENTE:
        return chamado
    retomar_relogio(sessao, chamado, agora_utc())
    chamado.versao += 1
    _registrar(chamado, usuario, f"{_nome(usuario)} retomou o atendimento.")
    return chamado


# ---------------------------------------------------------------------------------------------
# "Não resolveu"
# ---------------------------------------------------------------------------------------------

def nao_resolveu(sessao: Session, usuario: Usuario, p: Papeis, numero: int, motivo: str) -> Chamado:
    """O solicitante reabre o chamado resolvido, dentro do prazo, dizendo o porquê."""
    chamado, a = obter(sessao, usuario, p, numero)
    do_solicitante = usuario.id == chamado.solicitante_id or (chamado.setor_solicitante_id is not None and chamado.setor_solicitante_id in a.setores_membro)
    if not do_solicitante:
        raise ErroChamado("Só quem pediu (ou alguém do setor solicitante) diz que não resolveu.", 403, "acesso_negado")
    if chamado.importado or chamado.status_base != STATUS_SOLUCIONADO:
        raise ErroChamado("Só um chamado resolvido pode ser reaberto.", 409, "chamado_aberto")
    agora = agora_utc()
    limite = _utc(chamado.reabrir_ate)
    if limite is None or agora > limite:
        raise ErroChamado("O prazo para dizer que não resolveu já passou. Abra um chamado novo e escolha este como relacionado.", 409, "prazo_reabertura")
    motivo = motivo.strip()
    if len(motivo) < 5:
        raise ErroChamado("Conte o que continua sem resolver.")
    for solucao in chamado.solucoes:
        solucao.status = "substituida"
    chamado.status_base = STATUS_EM_ATENDIMENTO if chamado.responsavel_id else STATUS_NOVO
    chamado.solucionado_em = None
    chamado.reabrir_ate = None
    chamado.reaberturas += 1
    chamado.ttr_estourado_em = None
    # O prazo de solução recomeça da reabertura (o tempo já gasto não volta)
    feriados = parametros.feriados_do_sla(sessao)
    _, chamado.prazo_ttr = _prazo(sessao, chamado.sla_ttr_id, agora, feriados)
    chamado.versao += 1
    chamado.acompanhamentos.append(AcompanhamentoChamado(autor_id=usuario.id, texto=f"<p><strong>Não resolveu:</strong> {_escapar(motivo)}</p>", criado_em=agora))
    auditar(sessao, usuario.login, "chamados.reabrir", f"#{chamado.numero}", motivo[:300], autor_id=usuario.id, alvo_tipo="chamado", alvo_id=chamado.id)
    ids = [chamado.responsavel_id] if chamado.responsavel_id else membros_ativos(sessao, chamado.setor_id)
    _avisar(sessao, ids, f"Chamado #{chamado.numero} reaberto: não resolveu", f"{_nome(usuario)}: {motivo[:300]}", chamado,
            f"reaberto:{chamado.reaberturas}", "chamados.reaberto", usuario, forcar_email=not chamado.responsavel_id, prioridade="alta")
    return chamado


def _escapar(texto: str) -> str:
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------------------------
# Alterar (responsável, setor, categoria, prioridade)
# ---------------------------------------------------------------------------------------------

def alterar(sessao: Session, usuario: Usuario, p: Papeis, numero: int, versao: int, *, campos: dict) -> Chamado:
    """Aplica só os campos enviados. Trocar a categoria reaplica setor, SLAs e prioridade dela (o que vier junto prevalece)."""
    chamado = _exigir_atendente(sessao, usuario, p, numero, "Só quem atende o chamado altera os dados dele.")
    _exigir_aberto(chamado)
    _conferir_versao(chamado, versao)
    mudancas: list[str] = []
    novo_setor_id: int | None = None

    if "categoria_id" in campos and campos["categoria_id"] != chamado.categoria_id:
        categoria = sessao.get(CategoriaChamados, campos["categoria_id"])
        if categoria is None or categoria not in catalogo(sessao, p):
            raise ErroChamado("Escolha uma categoria disponível.", 400, "categoria_invalida")
        efetiva = parametros.efetiva(categoria)
        antiga = chamado.categoria.caminho
        chamado.categoria_id, chamado.categoria = categoria.id, categoria
        feriados = parametros.feriados_do_sla(sessao)
        chamado.sla_tto_id, chamado.prazo_tto = _prazo(sessao, efetiva.sla_tto_id, chamado.aberto_em, feriados)
        chamado.sla_ttr_id, chamado.prazo_ttr = _prazo(sessao, efetiva.sla_ttr_id, chamado.aberto_em, feriados)
        # O tempo que já ficou pendente continua descontado do prazo novo
        if chamado.prazo_ttr is not None and chamado.espera_minutos_uteis:
            faixas = parametros.faixas_do_expediente(chamado_sla(sessao, chamado.sla_ttr_id).expediente)
            chamado.prazo_ttr = motor_sla.somar_minutos_uteis(chamado.prazo_ttr, chamado.espera_minutos_uteis, faixas, feriados)
        if chamado.prioridade_origem == "categoria":
            chamado.prioridade = efetiva.prioridade_padrao
        mudancas.append(f"categoria: {antiga} → {categoria.caminho}")
        # Ainda sem classificação ITIL: o novo assunto traz a dele (a que o técnico já escolheu não muda)
        if chamado.categoria_itil_id is None:
            chamado.categoria_itil_id = efetiva.categoria_itil_id
        if efetiva.setor_id != chamado.setor_id and "setor_id" not in campos:
            novo_setor_id = efetiva.setor_id

    if "setor_id" in campos and campos["setor_id"] != chamado.setor_id:
        novo_setor_id = campos["setor_id"]
    if novo_setor_id is not None:
        setor = sessao.get(Setor, novo_setor_id)
        if setor is None or not setor.ativo:
            raise ErroChamado("Escolha um setor ativo.", 400, "setor_invalido")
        mudancas.append(f"setor responsável: {chamado.setor_nome} → {setor.nome}")
        chamado.setor_id, chamado.setor_nome = setor.id, setor.nome
        # Quem atendia era do setor antigo: o chamado volta a esperar alguém do setor novo (a menos que o responsável venha junto)
        if "responsavel_id" not in campos and chamado.responsavel_id is not None and not _membro(sessao, chamado.responsavel_id, setor.id):
            chamado.responsavel_id = None
            if chamado.status_base == STATUS_EM_ATENDIMENTO:
                chamado.status_base = STATUS_NOVO

    if "responsavel_id" in campos and campos["responsavel_id"] != chamado.responsavel_id:
        novo = campos["responsavel_id"]
        if novo is not None:
            pessoa = sessao.get(Usuario, novo)
            if pessoa is None or not pessoa.ativo or not _membro(sessao, novo, chamado.setor_id):
                raise ErroChamado("O responsável precisa ser alguém ativo do setor responsável.", 400, "responsavel_invalido")
            mudancas.append(f"responsável: {_nome(pessoa)}")
            chamado.tomado_em = chamado.tomado_em or agora_utc()
            if chamado.status_base == STATUS_NOVO:
                chamado.status_base = STATUS_EM_ATENDIMENTO
        else:
            mudancas.append("responsável removido")
            if chamado.status_base == STATUS_EM_ATENDIMENTO:
                chamado.status_base = STATUS_NOVO
        chamado.responsavel_id = novo

    if "substatus_id" in campos and campos["substatus_id"] != chamado.substatus_id:
        from app.models.chamados import SubstatusChamados

        novo = campos["substatus_id"]
        if novo is not None:
            sub = sessao.get(SubstatusChamados, novo)
            if sub is None or not sub.ativo or sub.status_base != chamado.status_base:
                raise ErroChamado("Escolha um sub-status do status atual.", 400, "substatus_invalido")
            mudancas.append(f"sub-status: {sub.nome}")
        else:
            mudancas.append("sub-status removido")
        chamado.substatus_id = novo

    if "prioridade" in campos and campos["prioridade"] != chamado.prioridade:
        if campos["prioridade"] not in PRIORIDADES:
            raise ErroChamado("Prioridade inválida.")
        motivo = (campos.get("motivo_prioridade") or "").strip()
        if len(motivo) < 5:
            raise ErroChamado("Diga por que a prioridade mudou.", 400, "motivo_obrigatorio")
        mudancas.append(f"prioridade: {chamado.prioridade} → {campos['prioridade']} ({motivo})")
        chamado.prioridade, chamado.prioridade_origem = campos["prioridade"], "responsavel"

    if not mudancas:
        return chamado
    chamado.versao += 1
    _registrar(chamado, usuario, f"{_nome(usuario)} alterou " + "; ".join(mudancas) + ".")
    auditar(sessao, usuario.login, "chamados.alterar", f"#{chamado.numero}", "; ".join(mudancas)[:500], autor_id=usuario.id, alvo_tipo="chamado", alvo_id=chamado.id)
    if novo_setor_id is not None:
        _avisar(sessao, membros_ativos(sessao, chamado.setor_id), f"Chamado #{chamado.numero} passou para {chamado.setor_nome}",
                f"{_nome(usuario)} encaminhou o chamado \"{chamado.titulo}\" para o seu setor.", chamado, f"setor:{chamado.setor_id}:{chamado.versao}",
                "chamados.novo", usuario, forcar_email=True)
    if "responsavel_id" in campos and chamado.responsavel_id and chamado.responsavel_id != usuario.id:
        _avisar(sessao, [chamado.responsavel_id], f"Chamado #{chamado.numero} atribuído a você", f"{_nome(usuario)} pôs você como responsável.", chamado,
                f"responsavel:{chamado.responsavel_id}:{chamado.versao}", "chamados.novo", usuario, forcar_email=True)
    return chamado


def classificar(sessao: Session, usuario: Usuario, p: Papeis, numero: int, versao: int, categoria_itil_id: uuid.UUID | None) -> Chamado:
    """Categoria ITIL do chamado (ou `None` = pendente). Só quem atende; vale também depois de resolvido (classificar ao fechar é comum).
    Vai para a linha do tempo como nota **privada** (o solicitante não vê a classificação)."""
    from app.models.chamados import CategoriaItilChamados

    chamado = _exigir_atendente(sessao, usuario, p, numero, "Só quem atende o chamado classifica a categoria ITIL.")
    _conferir_versao(chamado, versao)
    if categoria_itil_id == chamado.categoria_itil_id:
        return chamado
    if categoria_itil_id is not None:
        itil = sessao.get(CategoriaItilChamados, categoria_itil_id)
        if itil is None or not itil.ativa:
            raise ErroChamado("Escolha uma categoria ITIL ativa.", 400, "categoria_invalida")
        texto = f"{_nome(usuario)} classificou como {itil.caminho} (categoria ITIL)."
    else:
        texto = f"{_nome(usuario)} deixou a categoria ITIL pendente."
    chamado.categoria_itil_id = categoria_itil_id
    chamado.versao += 1
    chamado.acompanhamentos.append(AcompanhamentoChamado(autor_id=usuario.id, texto=f"<p>{escape(texto)}</p>", privado=True, automatico=True))
    auditar(sessao, usuario.login, "chamados.categoria_itil", f"#{chamado.numero}", texto[:500], autor_id=usuario.id, alvo_tipo="chamado", alvo_id=chamado.id)
    sessao.flush()
    return chamado


def chamado_sla(sessao: Session, sla_id):
    from app.models.chamados import SlaChamados

    return sessao.get(SlaChamados, sla_id)


def _membro(sessao: Session, usuario_id: int, setor_id: int) -> bool:
    return sessao.get(MembroSetor, {"setor_id": setor_id, "usuario_id": usuario_id}) is not None


def responsaveis_possiveis(sessao: Session, usuario: Usuario, p: Papeis, numero: int) -> list[Usuario]:
    """Membros ativos do setor responsável (para o seletor de responsável)."""
    chamado = _exigir_atendente(sessao, usuario, p, numero, "Só quem atende vê a equipe do setor.")
    return list(sessao.scalars(
        select(Usuario).join(MembroSetor, MembroSetor.usuario_id == Usuario.id)
        .where(MembroSetor.setor_id == chamado.setor_id, Usuario.ativo.is_(True)).order_by(Usuario.nome_completo)
    ))


# ---------------------------------------------------------------------------------------------
# Em cópia
# ---------------------------------------------------------------------------------------------

def incluir_em_copia(sessao: Session, usuario: Usuario, p: Papeis, numero: int, usuario_id: int | None, setor_id: int | None) -> Chamado:
    """Quem atende inclui pessoas ou setores; o solicitante também pode incluir (ex.: o chefe dele)."""
    chamado, a = obter(sessao, usuario, p, numero)
    if not (acesso.atende(a, p, chamado) or usuario.id == chamado.solicitante_id):
        raise ErroChamado("Só quem atende ou quem pediu inclui pessoas em cópia.", 403, "acesso_negado")
    _exigir_aberto(chamado)
    if (usuario_id is None) == (setor_id is None):
        raise ErroChamado("Escolha uma pessoa ou um setor.")
    if usuario_id is not None:
        pessoa = sessao.get(Usuario, usuario_id)
        if pessoa is None or not pessoa.ativo:
            raise ErroChamado("Pessoa não encontrada.", 404, "nao_encontrado")
        if any(x.usuario_id == usuario_id for x in chamado.atores):
            return chamado
        nome = _nome(pessoa)
    else:
        setor = sessao.get(Setor, setor_id)
        if setor is None or not setor.ativo:
            raise ErroChamado("Setor não encontrado.", 404, "nao_encontrado")
        if any(x.setor_id == setor_id for x in chamado.atores):
            return chamado
        nome = setor.nome
    chamado.atores.append(AtorChamado(usuario_id=usuario_id, setor_id=setor_id))
    chamado.versao += 1
    _registrar(chamado, usuario, f"{_nome(usuario)} pôs {nome} em cópia.")
    sessao.flush()
    ids = [usuario_id] if usuario_id else membros_ativos(sessao, setor_id)
    _avisar(sessao, ids, f"Você está em cópia no chamado #{chamado.numero}", f"{_nome(usuario)} incluiu você no chamado \"{chamado.titulo}\".",
            chamado, f"copia:{usuario_id or 's' + str(setor_id)}", "chamados.acompanhamento", usuario)
    return chamado


def remover_em_copia(sessao: Session, usuario: Usuario, p: Papeis, numero: int, ator_id: uuid.UUID) -> Chamado:
    chamado, a = obter(sessao, usuario, p, numero)
    ator = next((x for x in chamado.atores if x.id == ator_id), None)
    if ator is None:
        raise ErroChamado("Não está em cópia.", 404, "nao_encontrado")
    if not (acesso.atende(a, p, chamado) or usuario.id in (chamado.solicitante_id, ator.usuario_id)):
        raise ErroChamado("Só quem atende, quem pediu ou a própria pessoa tira alguém da cópia.", 403, "acesso_negado")
    chamado.atores.remove(ator)
    chamado.versao += 1
    _registrar(chamado, usuario, f"{_nome(usuario)} tirou uma pessoa ou setor da cópia.")
    return chamado


# ---------------------------------------------------------------------------------------------
# Tarefas
# ---------------------------------------------------------------------------------------------

def criar_tarefa(sessao: Session, usuario: Usuario, p: Papeis, numero: int, texto: str, responsavel_id: int | None, privada: bool) -> TarefaChamado:
    chamado = _exigir_atendente(sessao, usuario, p, numero, "Só quem atende cria tarefas.")
    _exigir_aberto(chamado)
    texto = " ".join(texto.split())
    if not 3 <= len(texto) <= 500:
        raise ErroChamado("A tarefa precisa ter de 3 a 500 caracteres.")
    if responsavel_id is not None:
        pessoa = sessao.get(Usuario, responsavel_id)
        if pessoa is None or not pessoa.ativo:
            raise ErroChamado("Responsável não encontrado.", 404, "nao_encontrado")
    tarefa = TarefaChamado(autor_id=usuario.id, responsavel_id=responsavel_id, texto=texto, privada=privada)
    chamado.tarefas.append(tarefa)
    if chamado.tomado_em is None:
        chamado.tomado_em = agora_utc()
    chamado.versao += 1
    sessao.flush()
    if responsavel_id and responsavel_id != usuario.id:
        _avisar(sessao, [responsavel_id], f"Tarefa para você no chamado #{chamado.numero}", texto, chamado, f"tarefa:{tarefa.id}", "chamados.novo", usuario)
    return tarefa


def marcar_tarefa(sessao: Session, usuario: Usuario, p: Papeis, numero: int, tarefa_id: uuid.UUID, feita: bool) -> TarefaChamado:
    chamado = _exigir_atendente(sessao, usuario, p, numero, "Só quem atende mexe nas tarefas.")
    tarefa = next((t for t in chamado.tarefas if t.id == tarefa_id), None)
    if tarefa is None:
        raise ErroChamado("Tarefa não encontrada.", 404, "nao_encontrado")
    tarefa.estado = "feita" if feita else "a_fazer"
    tarefa.feita_em = agora_utc() if feita else None
    return tarefa


# ---------------------------------------------------------------------------------------------
# Aprovação
# ---------------------------------------------------------------------------------------------

def pedir_aprovacao(sessao: Session, usuario: Usuario, p: Papeis, numero: int, alvo_usuario_id: int | None, alvo_setor_id: int | None,
                    pedido: str) -> ValidacaoChamado:
    chamado = _exigir_atendente(sessao, usuario, p, numero, "Só quem atende pede aprovação.")
    _exigir_aberto(chamado)
    if (alvo_usuario_id is None) == (alvo_setor_id is None):
        raise ErroChamado("Escolha quem aprova: uma pessoa ou um setor.")
    if alvo_usuario_id is not None:
        pessoa = sessao.get(Usuario, alvo_usuario_id)
        if pessoa is None or not pessoa.ativo:
            raise ErroChamado("Aprovador não encontrado.", 404, "nao_encontrado")
        destinatarios, nome = [alvo_usuario_id], _nome(pessoa)
    else:
        setor = sessao.get(Setor, alvo_setor_id)
        if setor is None or not setor.ativo:
            raise ErroChamado("Setor aprovador não encontrado.", 404, "nao_encontrado")
        destinatarios, nome = membros_ativos(sessao, alvo_setor_id), setor.nome
    validacao = ValidacaoChamado(solicitante_id=usuario.id, alvo_usuario_id=alvo_usuario_id, alvo_setor_id=alvo_setor_id, pedido=pedido.strip()[:2000])
    chamado.validacoes.append(validacao)
    if chamado.status_base == STATUS_PENDENTE:
        retomar_relogio(sessao, chamado, agora_utc())
    chamado.status_base = STATUS_EM_APROVACAO
    chamado.versao += 1
    _registrar(chamado, usuario, f"{_nome(usuario)} pediu aprovação a {nome}.")
    sessao.flush()
    _avisar(sessao, destinatarios, f"Aprovação pedida no chamado #{chamado.numero}", f"{_nome(usuario)} pede sua aprovação: {pedido.strip()[:300]}",
            chamado, f"validacao:{validacao.id}", "chamados.validacao_pedida", usuario, forcar_email=True, prioridade="alta")
    return validacao


def _pode_responder(sessao: Session, usuario: Usuario, v: ValidacaoChamado) -> bool:
    if v.alvo_usuario_id is not None:
        return v.alvo_usuario_id == usuario.id
    return _membro(sessao, usuario.id, v.alvo_setor_id) if v.alvo_setor_id else False


def minhas_aprovacoes(sessao: Session, usuario: Usuario) -> list[ValidacaoChamado]:
    """Aprovações aguardando a pessoa ou um setor dela."""
    setores = acesso.setores_do_usuario(sessao, usuario)
    return list(sessao.scalars(
        select(ValidacaoChamado).join(Chamado).where(
            ValidacaoChamado.status == "aguardando", Chamado.excluido_em.is_(None),
            or_(ValidacaoChamado.alvo_usuario_id == usuario.id, ValidacaoChamado.alvo_setor_id.in_(setores or {-1})),
        ).options(selectinload(ValidacaoChamado.chamado)).order_by(ValidacaoChamado.criado_em)
    ))


def responder_aprovacao(sessao: Session, usuario: Usuario, validacao_id: uuid.UUID, aprovar: bool, resposta: str) -> ValidacaoChamado:
    v = sessao.get(ValidacaoChamado, validacao_id)
    if v is None or not _pode_responder(sessao, usuario, v):
        raise ErroChamado("Aprovação não encontrada.", 404, "nao_encontrado")
    if v.status != "aguardando":
        raise ErroChamado("Esta aprovação já foi respondida.", 409, "ja_respondida")
    if not aprovar and len(resposta.strip()) < 5:
        raise ErroChamado("Diga por que não aprova.", 400, "motivo_obrigatorio")
    chamado = v.chamado
    agora = agora_utc()
    v.status, v.resposta, v.respondida_por_id, v.respondida_em = ("aprovada" if aprovar else "recusada"), resposta.strip()[:2000], usuario.id, agora
    # Sem outra aprovação aguardando, o chamado volta ao atendimento
    if chamado.status_base == STATUS_EM_APROVACAO and not any(x.status == "aguardando" for x in chamado.validacoes if x is not v):
        chamado.status_base = STATUS_EM_ATENDIMENTO if chamado.responsavel_id else STATUS_NOVO
    chamado.versao += 1
    texto = f"{_nome(usuario)} {'aprovou' if aprovar else 'não aprovou'}" + (f": {resposta.strip()}" if resposta.strip() else ".")
    _registrar(chamado, usuario, texto)
    auditar(sessao, usuario.login, "chamados.aprovacao", f"#{chamado.numero}", texto[:300], autor_id=usuario.id, alvo_tipo="chamado", alvo_id=chamado.id)
    ids = [x for x in (v.solicitante_id, chamado.responsavel_id) if x]
    _avisar(sessao, ids, f"Chamado #{chamado.numero}: {'aprovado' if aprovar else 'não aprovado'}", texto, chamado, f"validacao:{v.id}:resposta",
            "chamados.acompanhamento", usuario)
    return v


# ---------------------------------------------------------------------------------------------
# Local (Patrimônio) e chamados relacionáveis
# ---------------------------------------------------------------------------------------------

def local_sugerido(sessao: Session, usuario: Usuario) -> Localizacao | None:
    """Sala do solicitante pelo Patrimônio: a sala de que ele é responsável; senão, a sala com mais bens sob a responsabilidade dele;
    senão, a única sala do setor dele. Ninguém é obrigado a usar: o solicitante troca na tela."""
    salas_ativas = (Localizacao.tipo == "sala", Localizacao.ativo.is_(True))
    sala = sessao.scalar(select(Localizacao).where(Localizacao.responsavel_id == usuario.id, *salas_ativas).limit(1))
    if sala is not None and not servico_localizacoes.eh_sem_local(sala):
        return sala
    mais_bens = sessao.execute(
        select(Bem.localizacao_id, func.count()).where(Bem.responsavel_id == usuario.id).group_by(Bem.localizacao_id).order_by(func.count().desc()).limit(1)
    ).first()
    if mais_bens:
        sala = sessao.get(Localizacao, mais_bens[0])
        if sala is not None and sala.ativo and sala.tipo == "sala" and not servico_localizacoes.eh_sem_local(sala):
            return sala
    setores = acesso.setores_do_usuario(sessao, usuario)
    if setores:
        do_setor = list(sessao.scalars(select(Localizacao).where(Localizacao.setor_id.in_(setores), *salas_ativas).limit(2)))
        if len(do_setor) == 1:
            return do_setor[0]
    return None


def buscar_locais(sessao: Session, busca: str, limite: int = 20) -> list[Localizacao]:
    """Salas ativas do Patrimônio cujo código, nome ou setor contém o texto."""
    termo = f"%{busca.strip()}%"
    consulta = select(Localizacao).outerjoin(Setor, Setor.id == Localizacao.setor_id).where(Localizacao.tipo == "sala", Localizacao.ativo.is_(True))
    if busca.strip():
        consulta = consulta.where(or_(Localizacao.codigo.ilike(termo), Localizacao.nome.ilike(termo), Setor.nome.ilike(termo)))
    return [s for s in sessao.scalars(consulta.order_by(Localizacao.andar, Localizacao.codigo).limit(limite)) if not servico_localizacoes.eh_sem_local(s)]


def relacionaveis(sessao: Session, usuario: Usuario, limite: int = 50) -> list[Chamado]:
    """Os chamados do próprio solicitante, do mais recente para o mais antigo (só os dele: decisão do usuário)."""
    return list(sessao.scalars(
        select(Chamado).where(Chamado.solicitante_id == usuario.id, Chamado.excluido_em.is_(None)).order_by(Chamado.aberto_em.desc()).limit(limite)
    ))


def dado_pessoal(sessao: Session, usuario: Usuario, p: Papeis, numero: int, campo_id: uuid.UUID) -> str:
    """Valor completo de um campo marcado como dado pessoal, só para quem atende. Cada consulta fica na auditoria (LGPD)."""
    chamado = _exigir_atendente(sessao, usuario, p, numero, "Só quem atende o chamado vê o dado pessoal completo.")
    valor = next((v for v in chamado.valores if v.campo_id == campo_id), None)
    if valor is None:
        raise ErroChamado("Campo não encontrado.", 404, "nao_encontrado")
    auditar(sessao, usuario.login, "chamados.dado_pessoal", f"#{chamado.numero}", f"campo {valor.campo.rotulo}", autor_id=usuario.id,
            alvo_tipo="chamado", alvo_id=chamado.id)
    return valor.valor


def _utc(instante: datetime | None) -> datetime | None:
    """Data com fuso (o SQLite devolve sem fuso; tudo no banco é UTC)."""
    from datetime import UTC

    return None if instante is None else instante if instante.tzinfo else instante.replace(tzinfo=UTC)
