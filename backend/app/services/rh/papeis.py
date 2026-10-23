# Criado por José Eduardo Santana Martins
# Este arquivo serve para identificar os papéis do Módulo RH (CGP, autorizador e substituto) e o setor de cada usuário.
"""Papéis do Módulo RH.

- **RH** (a antiga "CGP"): quem a **ACL do recurso `rh`** contempla (CONTROLE_TOTAL = é o RH; MODIFICACAO = gere setores e cargos), por regra direta, por
  setor ou por perfil: **parametrizável** em Controle de acesso, não embutido no código. SuperRoot sempre. Enquanto o recurso `rh` não tiver regras nem perfis
  (instalação nova ou ainda não migrada), vale o setor configurado em `setor_cgp` (membros, filhos e quem o tem como Departamento), só para o sistema nunca ficar sem RH.
- **Autorizador** de um usuário: `DadosFuncionais.autorizador_id`, definido pela CGP.
- **Substituto**: definido pela CGP nos dados do autorizador; aprova enquanto o autorizador estiver afastado
  (afastamento aprovado ou gozado cobrindo hoje). Sem substituto, só a CGP aprova.
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.configuracao import obter_configuracao
from app.models.acl import NivelAcl
from app.models.rh import Afastamento, DadosFuncionais
from app.models.setor import MembroSetor, Setor
from app.models.usuario import Usuario
from app.services import servico_acl


class SemPermissaoRh(Exception):
    """Ação do RH não permitida para o usuário (vira 403)."""


def setor_com_descendentes(sessao: Session, raiz_ids: list[int]) -> list[Setor]:
    """Os setores informados e todos os seus descendentes."""
    todos = list(sessao.scalars(select(Setor)))
    resultado = [s for s in todos if s.id in raiz_ids]
    fila = list(raiz_ids)
    while fila:
        pai = fila.pop()
        for filho in (s for s in todos if s.setor_pai_id == pai):
            resultado.append(filho)
            fila.append(filho.id)
    return resultado


def setores_cgp(sessao: Session) -> list[Setor]:
    nome = obter_configuracao().setor_cgp.strip().lower()
    raizes = [s.id for s in sessao.scalars(select(Setor)) if s.nome.strip().lower() == nome]
    return setor_com_descendentes(sessao, raizes)


def setores_reserva_protocolo(sessao: Session) -> list[Setor]:
    """Setor da Coordenadoria de Gestão e Infraestrutura (CGI) e seus descendentes; vazio se o setor não existir."""
    from app.models.rh import ParametrosRh

    parametros = sessao.get(ParametrosRh, 1)
    if parametros is not None and parametros.setor_reserva_protocolo_id is not None:
        return setor_com_descendentes(sessao, [parametros.setor_reserva_protocolo_id])
    nome = obter_configuracao().setor_reserva_protocolo.strip().lower()
    raizes = [s.id for s in sessao.scalars(select(Setor)) if s.nome.strip().lower() == nome]
    return setor_com_descendentes(sessao, raizes)


def setores_apoio_administrativo(sessao: Session) -> list[Setor]:
    """Setor do Serviço de Apoio Administrativo (SAA) e seus descendentes; vazio se o setor não existir."""
    from app.models.rh import ParametrosRh

    parametros = sessao.get(ParametrosRh, 1)
    if parametros is not None and parametros.setor_apoio_administrativo_id is not None:
        return setor_com_descendentes(sessao, [parametros.setor_apoio_administrativo_id])
    nome = obter_configuracao().setor_apoio_administrativo.strip().lower()
    raizes = [s.id for s in sessao.scalars(select(Setor)) if s.nome.strip().lower() == nome]
    return setor_com_descendentes(sessao, raizes)


def usuarios_dos_setores(sessao: Session, setores: list[Setor]) -> list[Usuario]:
    """Usuários ativos que são membros dos setores ou têm um deles como Departamento."""
    if not setores:
        return []
    ids = [s.id for s in setores]
    nomes = [s.nome.strip().lower() for s in setores]
    membros = select(MembroSetor.usuario_id).where(MembroSetor.setor_id.in_(ids))
    return list(sessao.scalars(
        select(Usuario).where(Usuario.ativo.is_(True), Usuario.id.in_(membros) | func.lower(func.trim(Usuario.departamento)).in_(nomes))
    ))


SLUG_RH = "rh"


def rh_configurado(sessao: Session) -> bool:
    """O recurso `rh` já tem regras ou perfis (a ACL define quem é o RH)?"""
    return servico_acl.possui_regras(sessao, SLUG_RH)


def usuarios_cgp(sessao: Session) -> list[Usuario]:
    """Usuários ativos que são o RH (CONTROLE_TOTAL em `rh`; sem ACL configurada, o setor `setor_cgp`). Não inclui SuperRoot que não esteja contemplado."""
    if not rh_configurado(sessao):
        return usuarios_dos_setores(sessao, setores_cgp(sessao))
    ids = servico_acl.usuarios_com_nivel(sessao, SLUG_RH, NivelAcl.CONTROLE_TOTAL)
    return list(sessao.scalars(select(Usuario).where(Usuario.id.in_(ids), Usuario.ativo.is_(True)))) if ids else []


def tem_nivel_rh(sessao: Session, usuario: Usuario, nivel: str = NivelAcl.CONTROLE_TOTAL) -> bool:
    """O usuário tem pelo menos `nivel` no RH? SuperRoot sempre; com a ACL configurada vale ela; antes disso, o setor `setor_cgp` tem todos os poderes."""
    if usuario.superusuario:
        return True
    if rh_configurado(sessao):
        return servico_acl.pode_porta(sessao, usuario, SLUG_RH, nivel)
    return any(u.id == usuario.id for u in usuarios_dos_setores(sessao, setores_cgp(sessao)))


def eh_cgp(sessao: Session, usuario: Usuario) -> bool:
    """É o RH (CONTROLE_TOTAL em `rh`)."""
    return tem_nivel_rh(sessao, usuario, NivelAcl.CONTROLE_TOTAL)


def eh_da_reserva_protocolo(sessao: Session, usuario: Usuario) -> bool:
    """Usuário alocado na Coordenadoria de Gestão e Infraestrutura (membro do setor ou com o setor como Departamento). O SuperRoot não entra por aqui."""
    return any(u.id == usuario.id for u in usuarios_dos_setores(sessao, setores_reserva_protocolo(sessao)))


def eh_apoio_administrativo(sessao: Session, usuario: Usuario) -> bool:
    """Usuário alocado no Serviço de Apoio Administrativo (membro do setor ou com o setor como Departamento). O SuperRoot não entra por aqui."""
    return any(u.id == usuario.id for u in usuarios_dos_setores(sessao, setores_apoio_administrativo(sessao)))


def exigir_cgp(sessao: Session, usuario: Usuario) -> None:
    if not eh_cgp(sessao, usuario):
        raise SemPermissaoRh("Somente o RH (acesso de Controle total no módulo RH) pode fazer esta operação.")


def exigir_nivel_rh(sessao: Session, usuario: Usuario, nivel: str = NivelAcl.MODIFICACAO) -> None:
    """Exige pelo menos `nivel` no RH (gerir setores e cargos = MODIFICACAO)."""
    if not tem_nivel_rh(sessao, usuario, nivel):
        raise SemPermissaoRh("Esta operação exige acesso ao módulo RH (Controle de acesso > RH).")


def dados_funcionais(sessao: Session, usuario_id: int) -> DadosFuncionais | None:
    return sessao.get(DadosFuncionais, usuario_id)


def afastado_em(sessao: Session, usuario_id: int, dia: date) -> bool:
    """Tem afastamento aprovado (ou já gozado) cobrindo o dia."""
    return sessao.scalar(select(Afastamento.id).where(
        Afastamento.usuario_id == usuario_id, Afastamento.status.in_(("aprovado", "gozado")),
        Afastamento.inicio <= dia, Afastamento.fim >= dia,
    ).limit(1)) is not None


def aprovadores_de(sessao: Session, usuario_id: int, dia: date) -> list[int]:
    """Quem aprova os afastamentos do usuário hoje: o autorizador ou, se ele estiver afastado, o substituto."""
    dados = dados_funcionais(sessao, usuario_id)
    if dados is None or dados.autorizador_id is None:
        return []
    if not afastado_em(sessao, dados.autorizador_id, dia):
        return [dados.autorizador_id]
    do_autorizador = dados_funcionais(sessao, dados.autorizador_id)
    return [do_autorizador.substituto_id] if do_autorizador and do_autorizador.substituto_id else []


def autorizados_por(sessao: Session, aprovador_id: int, dia: date) -> list[int]:
    """Usuários cujos afastamentos o aprovador decide hoje (como autorizador ou como substituto)."""
    ids = list(sessao.scalars(select(DadosFuncionais.usuario_id).where(DadosFuncionais.autorizador_id == aprovador_id)))
    if not afastado_em(sessao, aprovador_id, dia):
        resultado = set(ids)
    else:
        resultado = set()
    # Autorizadores de quem ele é substituto e que estão afastados hoje
    titulares = sessao.scalars(select(DadosFuncionais.usuario_id).where(DadosFuncionais.substituto_id == aprovador_id))
    for titular in titulares:
        if afastado_em(sessao, titular, dia):
            resultado |= set(sessao.scalars(select(DadosFuncionais.usuario_id).where(DadosFuncionais.autorizador_id == titular)))
    resultado.discard(aprovador_id)
    return sorted(resultado)


def eh_autorizador(sessao: Session, usuario: Usuario) -> bool:
    """Autoriza alguém (ou é substituto de algum autorizador)."""
    return sessao.scalar(select(DadosFuncionais.usuario_id).where(
        (DadosFuncionais.autorizador_id == usuario.id) | (DadosFuncionais.substituto_id == usuario.id)
    ).limit(1)) is not None


def setor_do_usuario(usuario: Usuario) -> str:
    """Setor exibido no painel: o Departamento em vigor."""
    return (usuario.departamento or "").strip() or "Sem setor"
