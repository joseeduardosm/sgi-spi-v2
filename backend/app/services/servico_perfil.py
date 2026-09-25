# Criado por José Eduardo Santana Martins
# Este arquivo serve para aplicar as regras de preenchimento e revalidação do perfil institucional.
"""Regras do perfil institucional: preenchimento obrigatório e revalidação periódica.

Todo usuário comum precisa manter o perfil completo e confirmá-lo a cada 30 dias. Enquanto
estiver pendente, o acesso fica restrito à tela do próprio perfil (a API responde 403
`revisao_perfil_obrigatoria` nas demais rotas).
"""

from datetime import UTC, timedelta

from app.core.banco import agora_utc
from app.models.usuario import Usuario

# Prazo máximo entre duas revalidações do perfil
INTERVALO_REVISAO = timedelta(days=30)

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


def campos_pendentes(usuario: Usuario) -> list[str]:
    """Nomes dos campos obrigatórios ainda vazios (ou só com espaços)."""
    return [campo for campo in CAMPOS_OBRIGATORIOS if not (getattr(usuario, campo) or "").strip()]


def revisao_vencida(usuario: Usuario) -> bool:
    """Indica se a última revalidação tem mais de 30 dias ou nunca aconteceu."""
    revisado_em = usuario.perfil_revisado_em
    if revisado_em is None:
        return True
    if revisado_em.tzinfo is None:  # SQLite devolve datas sem fuso
        revisado_em = revisado_em.replace(tzinfo=UTC)
    return revisado_em < agora_utc() - INTERVALO_REVISAO


def perfil_restrito(usuario: Usuario) -> bool:
    """Usuário comum com perfil incompleto ou revalidação vencida só pode atualizar o próprio perfil."""
    return not usuario.superusuario and (bool(campos_pendentes(usuario)) or revisao_vencida(usuario))
