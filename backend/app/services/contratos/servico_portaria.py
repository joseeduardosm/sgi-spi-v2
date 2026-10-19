# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras da portaria de designação dos contratos: nomeações, ciência, autoridade, aceite e publicação.
"""Portaria de designação de gestão e fiscalização do contrato (único caminho para mudar a equipe, além do SuperRoot).

Ciclo:
1. **Nomeações** (1 a 6 funções, gestor obrigatório; quem cria é a equipe do contrato ou quem tem controle total em Contratos). Cada nomeado precisa ter
   RS/PV, RG/CIN e cargo preenchidos (o RH atualiza); enquanto faltar, a nomeação fica com o marcador de pendência e o RH é avisado.
2. **Ciência**: com os dados completos, cada nomeado vê um modal e confirma que está ciente.
3. **Autoridade**: com todos cientes, escolhe-se a autoridade competente. Só aqui o texto é gerado (HTML da máscara, para copiar) e o número é
   **reservado** no Protocolo ("Portaria SPI SSGC"), ainda pendente.
4. **Aceite** da autoridade (que pode **devolver**, liberando o número). Ao aceitar sai o **PDF de evidência** (ciências e aceite) para o SEI.
5. **Publicação**: quando o Protocolo anexa o PDF do D.O.E. ao número reservado, a portaria vira publicada, a nova equipe passa a valer (as funções que
   a portaria não cita ficam sem designado, pois ela revoga a anterior) e o documento entra em "Documentos Importantes" (tipo 16).
**Cancelar** libera o número reservado. Há uma portaria em andamento por contrato.

O Art. 5º cita a portaria anterior do contrato (as publicadas pelo sistema ou, na falta, um número de "Portaria" do Protocolo já vinculado ao contrato);
sem anterior, revoga genericamente. O RS vem do RH (restrito à CGP) e nunca é exposto.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.banco import agora_utc, hoje_sao_paulo
from app.models.contratos import PAPEIS_EQUIPE, Contrato, DesignacaoEquipe, DocumentoContrato
from app.models.contratos.execucao import ModeloGlobal
from app.models.contratos.portaria import AutoridadePortaria, NomeacaoPortaria, PortariaContrato
from app.models.protocolo import NumeroProtocolo, SequenciaProtocolo, TipoProtocolo
from app.models.rh import DadosFuncionais
from app.models.usuario import Usuario
from app.services import servico_anexos, notificacoes, servico_protocolo
from app.services.contratos import portaria_documento, portaria_mascara, setor_equipes
from app.services.contratos.erros import ErroRegraContrato, RegistroNaoEncontrado, SemPermissaoContrato
from app.schemas.contratos.portaria import (LeituraAutoridade, LeituraCienciaPendente, LeituraNomeacao, LeituraPortaria, NomeacaoEntrada, PainelPortarias)
from app.services.contratos.servico_contratos import (aplicar_equipe_por_ids, designacoes_vigentes, eh_administrador, integra_equipe, obter_contrato)
from app.services.documentos.pdf import FUSO_SAO_PAULO
from app.services.servico_auditoria import auditar

CODIGO_DOCUMENTO = 16
NOME_TIPO_PROTOCOLO = "portaria spi ssgc"
ANTES_DA_AUTORIDADE = ("nomeacao", "aguardando_ciencia", "aguardando_autoridade")
EM_ANDAMENTO = (*ANTES_DA_AUTORIDADE, "aguardando_aceite", "aceita")
ROTULOS_STATUS = {
    "nomeacao": "Nomeações: dados do RH pendentes", "aguardando_ciencia": "Aguardando ciência dos nomeados", "aguardando_autoridade": "Aguardando a escolha da autoridade",
    "aguardando_aceite": "Aguardando aceite da autoridade", "aceita": "Aceita: aguardando a publicação no D.O.E.", "publicada": "Publicada", "cancelada": "Cancelada",
}
MAXIMO_NOMEACOES = 6


def _nome(usuario: Usuario) -> str:
    return usuario.nome_completo or usuario.login


def _local(instante: datetime) -> datetime:
    return (instante if instante.tzinfo else instante.replace(tzinfo=UTC)).astimezone(FUSO_SAO_PAULO)


def _cnpj(valor: str) -> str:
    d = "".join(c for c in valor or "" if c.isdigit())
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else valor or ""


# --- Autoridades --------------------------------------------------------------------------------

def pode_gerir_autoridades(sessao: Session, usuario: Usuario) -> bool:
    """SuperRoot, controle total em Contratos, ou gestor/gestor suplente vigente de algum contrato."""
    if eh_administrador(sessao, usuario):
        return True
    agora = agora_utc()
    return sessao.scalar(select(func.count(DesignacaoEquipe.id)).where(
        DesignacaoEquipe.usuario_id == usuario.id, DesignacaoEquipe.papel.in_(("gestor", "gestor_suplente")),
        (DesignacaoEquipe.valido_ate.is_(None)) | (DesignacaoEquipe.valido_ate > agora))) > 0


def exigir_gestao_autoridades(sessao: Session, usuario: Usuario) -> None:
    if not pode_gerir_autoridades(sessao, usuario):
        raise SemPermissaoContrato("Somente o SuperRoot, quem tem controle total em Contratos ou o gestor (ou suplente) de um contrato cadastra as autoridades.")


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
    """A autoridade é um usuário do sistema (que dá o aceite); nome, cargo e setor em branco vêm do cadastro dele."""
    usuario = sessao.get(Usuario, dados.usuario_id)
    if usuario is None:
        raise ErroRegraContrato("Escolha o usuário que é a autoridade signatária.")
    padroes = {"nome": usuario.nome_completo or usuario.login, "cargo": usuario.cargo or "", "setor": usuario.departamento or ""}
    campos = {"sigla": (dados.sigla or "").strip()}
    for campo, padrao in padroes.items():
        campos[campo] = (getattr(dados, campo) or "").strip() or padrao.strip()
    rotulos = {"sigla": "a sigla (ex.: SPI SSGC)", "nome": "o nome", "cargo": "o cargo", "setor": "o setor"}
    faltam = [rotulos[c] for c, v in campos.items() if not v]
    if faltam:
        raise ErroRegraContrato("Informe " + ", ".join(faltam) + " da autoridade.")
    return {**campos, "usuario_id": usuario.id, "ativa": dados.ativa}


def buscar_usuarios(sessao: Session, busca: str, limite: int = 20) -> list[Usuario]:
    """Usuários ativos para escolher a autoridade (por nome ou login)."""
    consulta = select(Usuario).where(Usuario.ativo.is_(True)).order_by(func.lower(Usuario.nome_completo)).limit(limite)
    termo = (busca or "").strip().lower()
    if termo:
        consulta = consulta.where(func.lower(Usuario.nome_completo).like(f"%{termo}%") | func.lower(Usuario.login).like(f"%{termo}%"))
    return list(sessao.scalars(consulta))


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

def dados_pendentes(sessao: Session, usuario_id: int | None) -> list[str]:
    """O que falta no cadastro para o usuário ser nomeado: RS/PV e RG/CIN (dados do RH) e cargo (perfil)."""
    usuario = sessao.get(Usuario, usuario_id) if usuario_id else None
    if usuario is None:
        return ["usuário"]
    funcionais = sessao.scalar(select(DadosFuncionais).where(DadosFuncionais.usuario_id == usuario.id))
    faltam = []
    if not (funcionais and (funcionais.rs_pv or "").strip()):
        faltam.append("RS/PV")
    if not (funcionais and (funcionais.rg_cin or "").strip()):
        faltam.append("RG/CIN")
    if not (usuario.cargo or "").strip():
        faltam.append("cargo")
    return faltam


def _equipe(sessao: Session, portaria: PortariaContrato) -> list[dict]:
    """Nomeações da portaria na ordem dos papéis, com o RS lido do RH."""
    por_papel = {n.papel: n for n in portaria.nomeacoes}
    pessoas = [por_papel[p] for p in PAPEIS_EQUIPE if p in por_papel]
    rs = {r.usuario_id: (r.rs_pv or "").strip() for r in sessao.scalars(select(DadosFuncionais).where(DadosFuncionais.usuario_id.in_([n.usuario_id for n in pessoas])))}
    return [{"papel": n.papel, "usuario_id": n.usuario_id, "nome": n.nome_usuario, "rs": rs.get(n.usuario_id, "")} for n in pessoas]


def _anterior(sessao: Session, contrato: Contrato, excluir_id: uuid.UUID | None, excluir_numero_id: uuid.UUID | None) -> dict | None:
    """Portaria anterior do contrato para o Art. 5º (None → revogação genérica)."""
    consulta = select(PortariaContrato).where(PortariaContrato.contrato_id == contrato.id, PortariaContrato.status == "publicada")
    if excluir_id:
        consulta = consulta.where(PortariaContrato.id != excluir_id)
    anterior = sessao.scalars(consulta.order_by(PortariaContrato.publicada_em.desc())).first()
    if anterior is not None:
        quando = _local(anterior.publicada_em or anterior.aceita_em)
        return {"portaria_id": str(anterior.id), "sigla": anterior.sigla, "numero": anterior.numero,
                "dia": quando.day, "mes": quando.month, "ano": quando.year}
    # Sem portaria do sistema: um número de "Portaria" do Protocolo já vinculado ao contrato (cadastrado antes desta funcionalidade)
    ja_usados = select(PortariaContrato.numero_protocolo_id).where(PortariaContrato.numero_protocolo_id.is_not(None))
    numero = sessao.scalars(
        select(NumeroProtocolo).join(SequenciaProtocolo).join(TipoProtocolo).where(
            NumeroProtocolo.contrato_id == contrato.id, NumeroProtocolo.anulado_em.is_(None), NumeroProtocolo.reservado_em.is_not(None),
            TipoProtocolo.nome_chave.like("portaria%"), NumeroProtocolo.id.not_in(ja_usados), NumeroProtocolo.id != excluir_numero_id,
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


def montar_dados(sessao: Session, portaria: PortariaContrato, contrato: Contrato, autoridade: AutoridadePortaria, numero: int, exercicio: int,
                 excluir_numero_id: uuid.UUID | None = None) -> dict:
    """Retrato usado no texto da portaria (gerado na escolha da autoridade e atualizado no aceite), com o HTML da máscara já preenchido."""
    equipe = _equipe(sessao, portaria)
    if not any(p["papel"] == "gestor" for p in equipe):
        raise ErroRegraContrato("A portaria precisa nomear o gestor.")
    anterior = _anterior(sessao, contrato, portaria.id, excluir_numero_id)
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


# --- Consulta e permissões ----------------------------------------------------------------------

def _portaria(sessao: Session, contrato_id: uuid.UUID, portaria_id: uuid.UUID) -> PortariaContrato:
    portaria = sessao.get(PortariaContrato, portaria_id)
    if portaria is None or portaria.contrato_id != contrato_id:
        raise RegistroNaoEncontrado("Portaria")
    return portaria


def listar(sessao: Session, contrato_id: uuid.UUID) -> list[PortariaContrato]:
    obter_contrato(sessao, contrato_id)
    return list(sessao.scalars(select(PortariaContrato).where(PortariaContrato.contrato_id == contrato_id).order_by(PortariaContrato.solicitada_em.desc())))


def pode_criar_portaria(sessao: Session, contrato: Contrato, usuario: Usuario) -> bool:
    """Quem cria e conduz a portaria: integrante vigente da equipe do contrato, ou quem tem controle total em Contratos (perfil "Administrador de Contratos") e o SuperRoot."""
    return eh_administrador(sessao, usuario) or integra_equipe(contrato, usuario)


def exigir_criacao(sessao: Session, contrato: Contrato, usuario: Usuario) -> None:
    if not pode_criar_portaria(sessao, contrato, usuario):
        raise SemPermissaoContrato("Somente a equipe do contrato ou quem tem controle total em Contratos (Administrador de Contratos) cria e conduz a portaria de designação.")


def pode_decidir(sessao: Session, portaria: PortariaContrato, usuario: Usuario) -> bool:
    """Aceita ou devolve: o usuário vinculado à autoridade signatária (ou o SuperRoot)."""
    autoridade = sessao.get(AutoridadePortaria, portaria.autoridade_id) if portaria.autoridade_id else None
    return usuario.superusuario or (autoridade is not None and autoridade.usuario_id == usuario.id)


def _sequencia_do_ano(sessao: Session) -> SequenciaProtocolo:
    exercicio = hoje_sao_paulo().year
    sequencia = sessao.scalar(select(SequenciaProtocolo).join(TipoProtocolo).where(TipoProtocolo.nome_chave == NOME_TIPO_PROTOCOLO, SequenciaProtocolo.exercicio == exercicio))
    if sequencia is None:
        raise ErroRegraContrato(f"O Protocolo não tem a faixa de numeração de \"Portaria SPI SSGC\" para {exercicio}: peça à administração do Protocolo para cadastrá-la.")
    return sequencia


def _rotulo(portaria: PortariaContrato) -> str:
    if portaria.numero is None:
        return "Portaria de designação (em elaboração)"
    return f"Portaria {portaria.sigla} nº {portaria.numero:03d}/{portaria.exercicio}"


def _identificacao(contrato: Contrato) -> str:
    return f"{contrato.numero} – {contrato.apelido}" if contrato.apelido else contrato.numero


def _avisar(sessao: Session, portaria: PortariaContrato, destinatarios: list[int | None], assunto: str, corpo: str, autor: Usuario | None, categoria: str = "comunicado",
            evento: str = "contratos.portaria", chave: str | None = None, link: str | None = None, forcar_email: bool = False) -> None:
    notificacoes.notificar(sessao, [d for d in destinatarios if d], assunto, corpo, chave=chave or f"portaria:{portaria.id}:{portaria.status}:{agora_utc().timestamp()}",
                           categoria=categoria, link=link or f"/contratos/{portaria.contrato_id}?aba=equipe", contrato_id=portaria.contrato_id, autor=autor, evento=evento, forcar_email=forcar_email)


# --- Nomeações, dados do RH e ciência -----------------------------------------------------------

def _validar_nomeacoes(sessao: Session, entradas: list[NomeacaoEntrada]) -> list[tuple[str, Usuario]]:
    if not 1 <= len(entradas) <= MAXIMO_NOMEACOES:
        raise ErroRegraContrato(f"A portaria nomeia de 1 a {MAXIMO_NOMEACOES} funções.")
    papeis = [e.papel for e in entradas]
    if len(set(papeis)) != len(papeis):
        raise ErroRegraContrato("Cada função só pode aparecer uma vez na portaria.")
    if "gestor" not in papeis:
        raise ErroRegraContrato("O gestor é obrigatório na portaria.")
    saida = []
    for entrada in entradas:
        if entrada.papel not in PAPEIS_EQUIPE:
            raise ErroRegraContrato(f"Função inválida: {entrada.papel}.")
        usuario = sessao.get(Usuario, entrada.usuario_id)
        if usuario is None or not usuario.ativo:
            raise ErroRegraContrato("Um dos usuários indicados não existe ou está inativo.")
        saida.append((entrada.papel, usuario))
    return saida


def _sincronizar_nomeacoes(portaria: PortariaContrato, escolhidos: list[tuple[str, Usuario]]) -> None:
    """Grava as nomeações. Quem continua na mesma função mantém a ciência; trocar o nomeado de uma função (a linha é reaproveitada, pois
    há uma só por função) ou incluir função nova zera a ciência."""
    atuais = {n.papel: n for n in portaria.nomeacoes}
    papeis_novos = {p for p, _ in escolhidos}
    for papel, n in atuais.items():
        if papel not in papeis_novos:
            portaria.nomeacoes.remove(n)
    for ordem, (papel, usuario) in enumerate(escolhidos):
        existente = atuais.get(papel)
        if existente is None:
            portaria.nomeacoes.append(NomeacaoPortaria(papel=papel, ordem=ordem, usuario_id=usuario.id, nome_usuario=_nome(usuario)))
            continue
        existente.ordem = ordem
        if existente.usuario_id != usuario.id:
            existente.usuario_id, existente.nome_usuario, existente.ciente_em = usuario.id, _nome(usuario), None


def _avancar(sessao: Session, portaria: PortariaContrato, autor: Usuario | None = None) -> bool:
    """Recalcula a etapa de uma portaria ainda sem autoridade (dados do RH → ciência → escolha da autoridade) e avisa quem precisa agir.

    Devolve True se a situação mudou. É chamada ao nomear, ao dar ciência, ao abrir a aba e quando o RH atualiza um cadastro."""
    if portaria.status not in ANTES_DA_AUTORIDADE:
        return False
    contrato = obter_contrato(sessao, portaria.contrato_id)
    identificacao = _identificacao(contrato)
    pendentes = {n.id: dados_pendentes(sessao, n.usuario_id) for n in portaria.nomeacoes}
    antes = portaria.status
    if any(pendentes.values()):
        portaria.status = "nomeacao"
        # Avisa o RH (CGP) de cada pendência; a chave inclui o que falta, então só repete se o problema mudar
        from app.services.rh import papeis as papeis_rh
        cgp = [u.id for u in papeis_rh.usuarios_cgp(sessao)]
        for n in portaria.nomeacoes:
            if pendentes[n.id]:
                _avisar(sessao, portaria, cgp, f"RH: atualizar dados de {n.nome_usuario} para nomeação",
                        f"RH precisa atualizar os dados de {n.nome_usuario} ({', '.join(pendentes[n.id])}) para que ele seja nomeado como "
                        f"{portaria_documento.ROTULOS_PAPEL[n.papel]} no contrato {identificacao}.", autor, "pendencia", "contratos.portaria_dados_rh",
                        chave=f"portaria-rh:{portaria.id}:{n.usuario_id}:{','.join(pendentes[n.id])}")
    elif any(n.ciente_em is None for n in portaria.nomeacoes):
        portaria.status = "aguardando_ciencia"
        for n in portaria.nomeacoes:
            if n.ciente_em is None:
                _avisar(sessao, portaria, [n.usuario_id], f"Você foi indicado como {portaria_documento.ROTULOS_PAPEL[n.papel]} — contrato {identificacao}",
                        f"{portaria.solicitada_por_nome} indicou você como {portaria_documento.ROTULOS_PAPEL[n.papel]} do contrato {identificacao}. "
                        "Abra este aviso (ou entre no sistema) e confirme que está ciente: a notificação fica no sino até a sua ciência.", None, "pendencia", "contratos.portaria_nomeacao", chave=f"portaria-nomeacao:{n.id}",
                        link=f"/contratos/{portaria.contrato_id}?aba=equipe&ciencia={portaria.id}", forcar_email=True)
    else:
        portaria.status = "aguardando_autoridade"
        _avisar(sessao, portaria, [portaria.solicitada_por_id], f"Portaria pronta para a autoridade — contrato {identificacao}",
                "Todos os nomeados deram ciência. Escolha a autoridade competente na aba Equipe do contrato.", autor, "pendencia",
                chave=f"portaria-cientes:{portaria.id}")
    return portaria.status != antes


def reavaliar_usuario(sessao: Session, usuario_id: int) -> None:
    """Chamada quando o RH (ou o perfil) atualiza o cadastro de alguém: avança as portarias em que ele está nomeado (sem commit)."""
    ids = sessao.scalars(select(NomeacaoPortaria.portaria_id).where(NomeacaoPortaria.usuario_id == usuario_id)).all()
    for portaria in sessao.scalars(select(PortariaContrato).where(PortariaContrato.id.in_(ids), PortariaContrato.status.in_(ANTES_DA_AUTORIDADE))):
        _avancar(sessao, portaria)


def criar(sessao: Session, contrato_id: uuid.UUID, entradas: list[NomeacaoEntrada], autor: Usuario) -> PortariaContrato:
    """Abre a portaria com as nomeações (a equipe nova inteira: o que a portaria não cita deixa de ser designado quando ela for publicada)."""
    contrato = obter_contrato(sessao, contrato_id)
    exigir_criacao(sessao, contrato, autor)
    if sessao.scalar(select(func.count(PortariaContrato.id)).where(PortariaContrato.contrato_id == contrato.id, PortariaContrato.status.in_(EM_ANDAMENTO))):
        raise ErroRegraContrato("Este contrato já tem uma portaria em andamento: conclua ou cancele-a antes de criar outra.", conflito=True)
    escolhidos = _validar_nomeacoes(sessao, entradas)
    portaria = PortariaContrato(contrato_id=contrato.id, status="nomeacao", solicitada_por_id=autor.id, solicitada_por_nome=_nome(autor), dados={})
    sessao.add(portaria)
    _sincronizar_nomeacoes(portaria, escolhidos)
    sessao.flush()
    _avancar(sessao, portaria, autor)
    auditar(sessao, autor.login, "portaria.criar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"portaria_id": str(portaria.id), "nomeacoes": [{"papel": p, "usuario": u.login} for p, u in escolhidos]})
    sessao.commit()
    return portaria


def definir_nomeacoes(sessao: Session, contrato_id: uuid.UUID, portaria_id: uuid.UUID, entradas: list[NomeacaoEntrada], autor: Usuario) -> PortariaContrato:
    """Troca as nomeações enquanto a portaria ainda não tem autoridade (quem mudou perde a ciência)."""
    portaria = _portaria(sessao, contrato_id, portaria_id)
    exigir_criacao(sessao, obter_contrato(sessao, contrato_id), autor)
    if portaria.status not in ANTES_DA_AUTORIDADE:
        raise ErroRegraContrato("As nomeações só mudam antes de escolher a autoridade; devolva ou cancele a portaria.", conflito=True)
    _sincronizar_nomeacoes(portaria, _validar_nomeacoes(sessao, entradas))
    sessao.flush()
    sessao.refresh(portaria)
    _avancar(sessao, portaria, autor)
    auditar(sessao, autor.login, "portaria.nomeacoes", _rotulo(portaria), autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato_id, dados={"portaria_id": str(portaria.id)})
    sessao.commit()
    return portaria


def ciencias_pendentes(sessao: Session, usuario: Usuario) -> list[LeituraCienciaPendente]:
    """Nomeações do usuário aguardando a ciência dele (alimenta o modal que abre ao entrar no sistema)."""
    linhas = sessao.execute(
        select(NomeacaoPortaria, PortariaContrato, Contrato).join(PortariaContrato, NomeacaoPortaria.portaria_id == PortariaContrato.id)
        .join(Contrato, PortariaContrato.contrato_id == Contrato.id)
        .where(NomeacaoPortaria.usuario_id == usuario.id, NomeacaoPortaria.ciente_em.is_(None), PortariaContrato.status == "aguardando_ciencia")
        .order_by(PortariaContrato.solicitada_em)
    ).all()
    return [LeituraCienciaPendente(portaria_id=p.id, contrato_id=c.id, contrato=_identificacao(c), papel=n.papel, papel_rotulo=portaria_documento.ROTULOS_PAPEL[n.papel],
                                   nomeado_por=p.solicitada_por_nome) for n, p, c in linhas]


def registrar_ciencia(sessao: Session, portaria_id: uuid.UUID, autor: Usuario) -> None:
    """O nomeado confirma que está ciente (todas as funções dele na portaria). Com todos cientes, a portaria segue para a autoridade."""
    portaria = sessao.get(PortariaContrato, portaria_id)
    if portaria is None:
        raise RegistroNaoEncontrado("Portaria")
    minhas = [n for n in portaria.nomeacoes if n.usuario_id == autor.id]
    if not minhas:
        raise SemPermissaoContrato("Você não foi nomeado nesta portaria.")
    if portaria.status != "aguardando_ciencia":
        raise ErroRegraContrato("Esta portaria não está aguardando ciência.", conflito=True)
    agora = agora_utc()
    for n in minhas:
        n.ciente_em = n.ciente_em or agora
        notificacoes.encerrar(sessao, prefixo=f"portaria-nomeacao:{n.id}")
    auditar(sessao, autor.login, "portaria.ciencia", _rotulo(portaria), autor_id=autor.id, alvo_tipo="contrato", alvo_id=portaria.contrato_id,
            dados={"portaria_id": str(portaria.id), "funcoes": [n.papel for n in minhas]})
    sessao.flush()
    _avancar(sessao, portaria, autor)
    sessao.commit()


# --- Autoridade, aceite e cancelamento ----------------------------------------------------------

def escolher_autoridade(sessao: Session, contrato_id: uuid.UUID, portaria_id: uuid.UUID, autoridade_id: uuid.UUID, autor: Usuario) -> PortariaContrato:
    """Com todos cientes: escolhe a autoridade, gera o texto e reserva o número no Protocolo (pendente até o D.O.E.)."""
    portaria = _portaria(sessao, contrato_id, portaria_id)
    contrato = obter_contrato(sessao, contrato_id)
    exigir_criacao(sessao, contrato, autor)
    if portaria.status != "aguardando_autoridade":
        raise ErroRegraContrato("A autoridade só é escolhida depois que todos os nomeados derem ciência.", conflito=True)
    autoridade = _autoridade(sessao, autoridade_id)
    if not autoridade.ativa:
        raise ErroRegraContrato("Esta autoridade está desativada.")
    sequencia = _sequencia_do_ano(sessao)
    teste = montar_dados(sessao, portaria, contrato, autoridade, 0, sequencia.exercicio)  # valida máscara e equipe antes de gastar um número
    faltas = pendencias(teste)
    if faltas:
        raise ErroRegraContrato("Não é possível gerar a portaria: falta " + "; ".join(faltas) + ".")
    try:
        numero = servico_protocolo.proximo(sessao, sequencia.id, f"Portaria de designação de gestão e fiscalização do Contrato {contrato.numero}", contrato.id, autor,
                                           fora_da_reserva=True)
    except servico_protocolo.ErroProtocolo as erro:
        raise ErroRegraContrato(str(erro), conflito=erro.status == 409) from erro
    portaria.autoridade_id, portaria.sigla, portaria.numero, portaria.exercicio, portaria.numero_protocolo_id = autoridade.id, autoridade.sigla, numero.numero, sequencia.exercicio, numero.id
    portaria.dados = montar_dados(sessao, portaria, contrato, autoridade, numero.numero, sequencia.exercicio, excluir_numero_id=numero.id)
    anterior = portaria.dados["anterior"]
    portaria.portaria_anterior_id = uuid.UUID(anterior["portaria_id"]) if anterior and anterior["portaria_id"] else None
    portaria.status, portaria.motivo = "aguardando_aceite", ""
    auditar(sessao, autor.login, "portaria.autoridade", _rotulo(portaria), autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id, dados={"portaria_id": str(portaria.id)})
    _avisar(sessao, portaria, [autoridade.usuario_id], f"Portaria aguardando seu aceite — contrato {_identificacao(contrato)}",
            f"{_nome(autor)} elaborou a {_rotulo(portaria)}. Abra a aba Equipe do contrato para aceitar ou devolver.", autor, "pendencia")
    sessao.commit()
    return portaria


def aceitar(sessao: Session, contrato_id: uuid.UUID, portaria_id: uuid.UUID, autor: Usuario) -> PortariaContrato:
    """Aceite da autoridade signatária: atualiza o texto, gera o PDF de evidência (ciências e aceite) e espera a publicação no D.O.E."""
    portaria = _portaria(sessao, contrato_id, portaria_id)
    if not pode_decidir(sessao, portaria, autor):
        raise SemPermissaoContrato("Somente a autoridade signatária da portaria (ou o SuperRoot) pode aceitá-la.")
    if portaria.status != "aguardando_aceite":
        raise ErroRegraContrato("Esta portaria não está aguardando aceite.", conflito=True)
    contrato = obter_contrato(sessao, contrato_id)
    autoridade = _autoridade(sessao, portaria.autoridade_id)
    portaria.dados = montar_dados(sessao, portaria, contrato, autoridade, portaria.numero, portaria.exercicio, excluir_numero_id=portaria.numero_protocolo_id)
    faltas = pendencias(portaria.dados)
    if faltas:
        raise ErroRegraContrato("Não é possível aceitar: falta " + "; ".join(faltas) + ".")
    portaria.aceita_por_nome, portaria.aceita_em = _nome(autor), agora_utc()
    evidencia = portaria_documento.gerar_evidencia(
        portaria.dados, f"Contrato {_identificacao(contrato)}",
        [{"papel": n.papel, "nome": n.nome_usuario, "ciente_em": n.ciente_em} for n in portaria.nomeacoes],
        {"nome": _nome(autor), "cargo": autoridade.cargo, "aceita_em": portaria.aceita_em}, portaria.solicitada_por_nome, _nome(autor))
    portaria.evidencia = servico_anexos.guardar_pdf_gerado(sessao, evidencia, f"evidencia-portaria-{portaria.numero:03d}-{portaria.exercicio}.pdf", "contrato-portaria-evidencia",
                                                          autor.id, contrato_id=contrato.id)
    portaria.status = "aceita"
    notificacoes.encerrar(sessao, prefixo=f"portaria:{portaria.id}:")
    auditar(sessao, autor.login, "portaria.aceitar", _rotulo(portaria), autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato_id, dados={"portaria_id": str(portaria.id)})
    _avisar(sessao, portaria, [portaria.solicitada_por_id], f"Portaria aceita — {_rotulo(portaria)}",
            "A autoridade aceitou a portaria. Baixe o PDF de evidência e junte ao SEI para a publicação no D.O.E.; a nova equipe vale quando o Protocolo anexar o PDF publicado.", autor)
    sessao.commit()
    return portaria


def devolver(sessao: Session, contrato_id: uuid.UUID, portaria_id: uuid.UUID, motivo: str, autor: Usuario) -> PortariaContrato:
    """A autoridade devolve: o número volta ao Protocolo e quem criou ajusta as nomeações ou escolhe outra autoridade."""
    portaria = _portaria(sessao, contrato_id, portaria_id)
    if not pode_decidir(sessao, portaria, autor):
        raise SemPermissaoContrato("Somente a autoridade signatária da portaria (ou o SuperRoot) pode devolvê-la.")
    if portaria.status != "aguardando_aceite":
        raise ErroRegraContrato("Esta portaria não está aguardando aceite.", conflito=True)
    motivo = (motivo or "").strip()
    if not motivo:
        raise ErroRegraContrato("Informe o motivo da devolução.")
    _liberar_numero(sessao, portaria, f"Portaria devolvida: {motivo}", autor)
    _limpar_reserva(portaria)
    portaria.status, portaria.motivo = "aguardando_autoridade", motivo
    notificacoes.encerrar(sessao, prefixo=f"portaria:{portaria.id}:")
    auditar(sessao, autor.login, "portaria.devolver", _rotulo(portaria), autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato_id, dados={"motivo": motivo})
    sessao.flush()
    _avancar(sessao, portaria, autor)
    _avisar(sessao, portaria, [portaria.solicitada_por_id], "Portaria devolvida pela autoridade", f"Motivo: {motivo}", autor)
    sessao.commit()
    return portaria


def _liberar_numero(sessao: Session, portaria: PortariaContrato, motivo: str, autor: Usuario) -> None:
    """Devolve ao Protocolo o número reservado (a portaria cancelada mantém os dados no histórico)."""
    if portaria.numero_protocolo_id:
        try:
            servico_protocolo.liberar(sessao, portaria.numero_protocolo_id, motivo, autor, ignorar_dono=True)
        except servico_protocolo.ErroProtocolo as erro:
            raise ErroRegraContrato(str(erro)) from erro


def _limpar_reserva(portaria: PortariaContrato) -> None:
    """Depois da devolução: some o que dependia do número (texto, número, autoridade e evidência); as nomeações e ciências ficam."""
    portaria.numero_protocolo_id = portaria.numero = portaria.exercicio = portaria.autoridade_id = portaria.evidencia_anexo_id = None
    portaria.sigla, portaria.dados = "", {}
    portaria.aceita_em = portaria.aceita_por_nome = None


def cancelar(sessao: Session, contrato_id: uuid.UUID, portaria_id: uuid.UUID, motivo: str, autor: Usuario) -> PortariaContrato:
    """Cancela a portaria e libera o número no Protocolo (para quem reservou ou a administração do Protocolo)."""
    portaria = _portaria(sessao, contrato_id, portaria_id)
    exigir_criacao(sessao, obter_contrato(sessao, contrato_id), autor)
    if portaria.status not in EM_ANDAMENTO:
        raise ErroRegraContrato("Só portarias em andamento podem ser canceladas.", conflito=True)
    motivo = (motivo or "").strip()
    if not motivo:
        raise ErroRegraContrato("Informe o motivo do cancelamento.")
    rotulo = _rotulo(portaria)
    _liberar_numero(sessao, portaria, f"Portaria cancelada: {motivo}", autor)
    portaria.status, portaria.motivo = "cancelada", motivo
    notificacoes.encerrar(sessao, prefixo=f"portaria:{portaria.id}:")
    for n in portaria.nomeacoes:
        notificacoes.encerrar(sessao, prefixo=f"portaria-nomeacao:{n.id}")
    auditar(sessao, autor.login, "portaria.cancelar", rotulo, autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato_id, dados={"motivo": motivo})
    sessao.commit()
    return portaria


def evidencia(sessao: Session, contrato_id: uuid.UUID, portaria_id: uuid.UUID):
    """Anexo do PDF de evidência (depois do aceite)."""
    portaria = _portaria(sessao, contrato_id, portaria_id)
    if portaria.evidencia is None:
        raise ErroRegraContrato("O PDF de evidência é gerado quando a autoridade aceita a portaria.")
    return portaria.evidencia


# --- Publicação (pelo Protocolo) ----------------------------------------------------------------

def portaria_do_numero(sessao: Session, numero_id: uuid.UUID) -> PortariaContrato | None:
    """Portaria em andamento que reservou este número do Protocolo."""
    return sessao.scalar(select(PortariaContrato).where(PortariaContrato.numero_protocolo_id == numero_id, PortariaContrato.status.in_(EM_ANDAMENTO)))


def validar_anexo_no_numero(sessao: Session, numero_id: uuid.UUID, nome_arquivo: str) -> None:
    """O Protocolo só anexa ao número de uma portaria depois do aceite da autoridade, e o documento é o PDF do D.O.E."""
    portaria = portaria_do_numero(sessao, numero_id)
    if portaria is None:
        return
    if portaria.status != "aceita":
        raise ErroRegraContrato("Este número é de uma portaria de designação que ainda não foi aceita pela autoridade: aguarde o aceite para anexar o D.O.E.", conflito=True)
    if not (nome_arquivo or "").lower().endswith(".pdf"):
        raise ErroRegraContrato("Anexe o PDF do Diário Oficial (D.O.E.) que comprova a publicação da portaria.")


def publicar_pelo_protocolo(sessao: Session, numero: NumeroProtocolo, autor: Usuario) -> PortariaContrato | None:
    """Chamada depois que o Protocolo anexou o PDF ao número (sem commit): publica a portaria, aplica a equipe e guarda em Documentos Importantes."""
    portaria = portaria_do_numero(sessao, numero.id)
    if portaria is None or portaria.status != "aceita" or numero.anexo is None:
        return None
    contrato = obter_contrato(sessao, portaria.contrato_id)
    conteudo = servico_anexos.caminho(numero.anexo).read_bytes()
    anexo = servico_anexos.guardar_pdf_gerado(sessao, conteudo, numero.anexo.nome_original or "portaria.pdf", "contrato-documento", autor.id, contrato_id=contrato.id)
    agora = agora_utc()
    # A portaria revoga a anterior: a equipe passa a ser exatamente a nomeada (funções não citadas ficam sem designado)
    nomeados = {n.papel: n.usuario_id for n in portaria.nomeacoes}
    mudancas = aplicar_equipe_por_ids(sessao, contrato, {papel: nomeados.get(papel) for papel in PAPEIS_EQUIPE}, agora)
    contrato.versao += 1
    sessao.flush()
    setor_equipes.sincronizar(sessao)
    titulo = f"Portaria {portaria.sigla} nº {portaria.numero:03d}/{portaria.exercicio}"
    documento = next((d for d in contrato.documentos if d.codigo_tipo == CODIGO_DOCUMENTO), None)
    if documento is None:
        documento = DocumentoContrato(codigo_tipo=CODIGO_DOCUMENTO, titulo=titulo)
        contrato.documentos.append(documento)
    elif documento.anexo:
        servico_anexos.descartar(documento.anexo)
    documento.titulo = titulo
    documento.anexo, documento.enviado_em, documento.enviado_por_id = anexo, agora, autor.id
    portaria.status, portaria.publicada_em = "publicada", agora
    auditar(sessao, autor.login, "portaria.publicar", titulo, autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
            dados={"portaria_id": str(portaria.id), "sha256": anexo.sha256})
    if mudancas:
        auditar(sessao, autor.login, "contrato.equipe.alterar", f"Contrato {contrato.numero}", autor_id=autor.id, alvo_tipo="contrato", alvo_id=contrato.id,
                dados={"campos": mudancas, "portaria": titulo})
    identificacao = _identificacao(contrato)
    for n in portaria.nomeacoes:
        _avisar(sessao, portaria, [n.usuario_id], f"{titulo}: você integra a equipe do contrato {identificacao}",
                f"A {titulo} foi publicada. A partir de agora você é {portaria_documento.ROTULOS_PAPEL[n.papel]} do contrato {identificacao}.", None, "atribuicao",
                "contratos.equipe_incluido", chave=f"portaria-publicada:{portaria.id}:{n.id}")
    _avisar(sessao, portaria, [portaria.solicitada_por_id], f"Portaria publicada — {titulo}", "O Protocolo anexou o D.O.E.: a nova equipe já está valendo no contrato.", None)
    return portaria


# --- Painel -------------------------------------------------------------------------------------

def _rotulo_anterior(dados: dict) -> str | None:
    anterior = dados.get("anterior")
    if not anterior:
        return None
    return f"Portaria {anterior['sigla']} nº {anterior['numero']:03d}, de {anterior['dia']} de {portaria_documento.MESES[anterior['mes'] - 1]} de {anterior['ano']}".replace("  ", " ")


def _leitura(sessao: Session, portaria: PortariaContrato, usuario: Usuario, pode_criar: bool) -> LeituraPortaria:
    autoridade = sessao.get(AutoridadePortaria, portaria.autoridade_id) if portaria.autoridade_id else None
    dados = portaria.dados or {}
    em_aberto = portaria.status in EM_ANDAMENTO
    com_texto = portaria.status in ("aguardando_aceite", "aceita", "publicada") and "texto_html" in dados
    numero_txt = f"{portaria.numero:03d}/{portaria.exercicio}" if portaria.numero is not None else None
    aviso = None
    if portaria.status in ("aguardando_aceite", "aceita") and numero_txt:
        aviso = (f"A portaria {numero_txt} foi reservada. Os novos usuários ganharão acesso ao contrato neste sistema quando o Protocolo subir o PDF do D.O.E. "
                 "no módulo do Protocolo, comprovando a sua publicação.")
    return LeituraPortaria(
        id=portaria.id, titulo=portaria_documento.titulo(dados) if portaria.numero is not None and dados else "Portaria de designação (em elaboração)", sigla=portaria.sigla,
        numero=portaria.numero, exercicio=portaria.exercicio, status=portaria.status, status_rotulo=ROTULOS_STATUS[portaria.status], motivo=portaria.motivo,
        autoridade_nome=autoridade.nome if autoridade else (dados.get("autoridade") or {}).get("nome", ""), solicitada_por_nome=portaria.solicitada_por_nome,
        solicitada_em=portaria.solicitada_em, aceita_por_nome=portaria.aceita_por_nome, aceita_em=portaria.aceita_em, publicada_em=portaria.publicada_em,
        numero_protocolo_id=portaria.numero_protocolo_id, anterior=_rotulo_anterior(dados),
        nomeacoes=[LeituraNomeacao(papel=n.papel, papel_rotulo=portaria_documento.ROTULOS_PAPEL[n.papel], usuario_id=n.usuario_id, nome=n.nome_usuario,
                                   dados_pendentes=dados_pendentes(sessao, n.usuario_id) if portaria.status in ANTES_DA_AUTORIDADE else [], ciente_em=n.ciente_em)
                   for n in portaria.nomeacoes],
        texto_html=dados.get("texto_html") if com_texto else None,
        pendencias=pendencias(dados) if portaria.status == "aguardando_aceite" else [],
        aviso_reserva=aviso, tem_evidencia=portaria.evidencia_anexo_id is not None,
        pode_decidir=portaria.status == "aguardando_aceite" and pode_decidir(sessao, portaria, usuario),
        pode_alterar=pode_criar and em_aberto,
    )


def painel(sessao: Session, contrato_id: uuid.UUID, usuario: Usuario) -> PainelPortarias:
    """Histórico de portarias do contrato, autoridades ativas e o que o usuário pode fazer (avança a etapa das portarias sem autoridade)."""
    contrato = obter_contrato(sessao, contrato_id)
    pode_criar = pode_criar_portaria(sessao, contrato, usuario)
    portarias = listar(sessao, contrato_id)
    if any(_avancar(sessao, p) for p in portarias):
        sessao.commit()
    nomes = {u.id: _nome(u) for u in sessao.scalars(select(Usuario).where(Usuario.id.in_([a.usuario_id for a in listar_autoridades(sessao) if a.usuario_id])))}
    vigentes = {d.papel: d.usuario_id for d in designacoes_vigentes(contrato)}
    return PainelPortarias(
        portarias=[_leitura(sessao, p, usuario, pode_criar) for p in portarias],
        autoridades=[leitura_autoridade(a, nomes) for a in listar_autoridades(sessao, somente_ativas=True)],
        em_andamento=any(p.status in EM_ANDAMENTO for p in portarias), pode_criar=pode_criar,
        equipe_vigente=[NomeacaoEntrada(papel=papel, usuario_id=vigentes[papel]) for papel in PAPEIS_EQUIPE if papel in vigentes],
    )


def leitura_autoridade(autoridade: AutoridadePortaria, nomes: dict[int, str]) -> LeituraAutoridade:
    return LeituraAutoridade(id=autoridade.id, sigla=autoridade.sigla, nome=autoridade.nome, cargo=autoridade.cargo, setor=autoridade.setor,
                             usuario_id=autoridade.usuario_id, ativa=autoridade.ativa, usuario_nome=nomes.get(autoridade.usuario_id))


def autoridades_com_nomes(sessao: Session) -> list[LeituraAutoridade]:
    autoridades = listar_autoridades(sessao)
    nomes = {u.id: _nome(u) for u in sessao.scalars(select(Usuario).where(Usuario.id.in_([a.usuario_id for a in autoridades if a.usuario_id])))}
    return [leitura_autoridade(a, nomes) for a in autoridades]
