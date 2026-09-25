# Criado por José Eduardo Santana Martins
# Este arquivo serve para importar todos os modelos para que o banco e o Alembic os conheçam.
"""Pacote dos modelos (tabelas) do banco, escritos com SQLAlchemy 2.

Cada classe aqui representa uma tabela. Importar todas neste arquivo garante que
`Base.metadata` conheça o banco inteiro: o Alembic compara esse retrato com o banco real para
gerar as migrações, e os testes o usam para criar as tabelas no SQLite.
"""
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

# Nomes exportados por `from app.models import *`
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
