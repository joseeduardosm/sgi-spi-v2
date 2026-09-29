# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras de preenchimento e revalidação do perfil institucional.
"""Regras do perfil institucional: preenchimento obrigatório e revalidação periódica.

Todo usuário comum precisa manter o perfil completo e confirmá-lo uma vez por mês civil (no primeiro
acesso de cada mês, horário de São Paulo). Campos alterados ficam pendentes de validação da CGP (Módulo
RH), mas o envio já libera o acesso: os valores pendentes contam como preenchidos. Enquanto
estiver pendente, o acesso fica restrito à tela do próprio perfil (a API responde 403
`revisao_perfil_obrigatoria` nas demais rotas).
"""

from datetime import UTC
from zoneinfo import ZoneInfo

from sqlalchemy.orm import object_session

from app.core.banco import agora_utc
from app.core.configuracao import obter_configuracao
from app.models.usuario import Usuario

# A revalidação vale até o fim do mês civil, no horário de São Paulo
FUSO = ZoneInfo("America/Sao_Paulo")

# Campos obrigatórios do perfil e seus rótulos (celular, nascimento e gestor são opcionais)
CAMPOS_OBRIGATORIOS: dict[str, str] = {
    "nome_completo": "nome completo",
    "email": "e-mail",
    "ramal": "ramal",
    "cargo": "cargo",
    "departamento": "departamento",
    "andar": "andar",
    "predio": "prédio",
}


def _valores_pendentes(usuario: Usuario) -> dict:
    """Valores propostos e ainda pendentes de validação da CGP (contam como preenchidos)."""
    sessao = object_session(usuario)
    if sessao is None or usuario.id is None:
        return {}
    from app.services.rh.servico_cadastro import valores_pendentes

    return valores_pendentes(sessao, usuario.id)


def campos_pendentes(usuario: Usuario) -> list[str]:
    """Nomes dos campos obrigatórios ainda vazios (ou só com espaços), considerando os valores pendentes."""
    vazios = [campo for campo in CAMPOS_OBRIGATORIOS if not (getattr(usuario, campo) or "").strip()]
    if not vazios:
        return []
    pendentes = _valores_pendentes(usuario)
    return [campo for campo in vazios if not str(pendentes.get(campo) or "").strip()]


def revisao_vencida(usuario: Usuario) -> bool:
    """Indica se o perfil ainda não foi confirmado no mês civil atual (horário de São Paulo)."""
    revisado_em = usuario.perfil_revisado_em
    if revisado_em is None:
        return True
    if revisado_em.tzinfo is None:  # SQLite devolve datas sem fuso
        revisado_em = revisado_em.replace(tzinfo=UTC)
    revisado, agora = revisado_em.astimezone(FUSO), agora_utc().astimezone(FUSO)
    return (revisado.year, revisado.month) < (agora.year, agora.month)


def dispensado(usuario: Usuario) -> bool:
    """Só a conta administrativa principal (login `LOGIN_ADMIN`, padrão "root") não atualiza o cadastro.

    Todos os demais, inclusive os SuperRoot, confirmam o perfil todo mês e informam o superior imediato.
    """
    return usuario.login.strip().lower() == obter_configuracao().login_admin.strip().lower()


def perfil_restrito(usuario: Usuario) -> bool:
    """Perfil incompleto ou confirmação do mês pendente: só pode atualizar o próprio perfil (exceto a conta root)."""
    return not dispensado(usuario) and (bool(campos_pendentes(usuario)) or revisao_vencida(usuario))
