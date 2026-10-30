# Prepara o laboratório dos manuais de Contratos (depois de atualizacao-2026-10/laboratorio/reset.sh): usuário do DOF e ACL do Financeiro.
import sys; sys.path.insert(0, "/home/administrador/projeto/docs/manuais/atualizacao-2026-10/laboratorio")
from api import chamar, login
import sqlite3, os
tok = login("root", "senha-teste")
# Usuário do DOF criado como conta local pelo SuperRoot (perfil completo, para não cair na tela de revisão)
r = chamar("POST", "/usuarios", tok, {"login": "dof", "senha": "senha-lab-1", "perfil": {"nome_completo": "Diego Orçamento (DOF)", "email": "dof@exemplo.sp.gov.br", "ramal": "2200", "cargo": "Analista do Financeiro",
          "departamento": "Diretoria de Orçamento e Finanças", "andar": "3", "predio": "A", "celular": "11 98888-0000"}})
dof = r["id"]
rec = chamar("POST", "/acl/recursos", tok, {"nome": "Financeiro", "slug": "financeiro"})
chamar("POST", "/acl/regras", tok, {"recurso_id": rec["id"], "nivel": "MODIFICACAO", "usuarios_ids": [dof], "setores_ids": []})
contratos = next(r for r in chamar("GET", "/acl/recursos", tok) if r["slug"] == "contratos")
chamar("POST", "/acl/regras", tok, {"recurso_id": contratos["id"], "nivel": "LEITURA", "usuarios_ids": [dof], "setores_ids": []})
print("DOF pronto:", dof)
