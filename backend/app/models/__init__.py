# Importa todos os modelos para que Base.metadata os conheça (Alembic e testes).
from app.models.acl import NivelAcl, RecursoAcl, RegraAcl, acl_regras_setores, acl_regras_usuarios
from app.models.anexo import Anexo
from app.models.auditoria import RegistroAuditoria
from app.models.contratos import (
    Contrato,
    DesignacaoEquipe,
    DocumentoContrato,
    EmpresaContratada,
    ItemContrato,
    PrepostoEmpresa,
)
from app.models.diretorio_ldap import DiretorioLdap
from app.models.setor import MembroSetor, Setor
from app.models.usuario import OrigemUsuario, Papel, Usuario

__all__ = [
    "Anexo",
    "Contrato",
    "DesignacaoEquipe",
    "DocumentoContrato",
    "EmpresaContratada",
    "ItemContrato",
    "PrepostoEmpresa",
    "DiretorioLdap",
    "MembroSetor",
    "NivelAcl",
    "OrigemUsuario",
    "Papel",
    "RecursoAcl",
    "RegistroAuditoria",
    "RegraAcl",
    "Setor",
    "Usuario",
    "acl_regras_setores",
    "acl_regras_usuarios",
]
