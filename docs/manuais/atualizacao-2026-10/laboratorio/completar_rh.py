"""
===============================================================================
ARQUIVO: completar_rh.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Completar os dados funcionais (RS/PV e RG/CIN) de um usuário do laboratório,
informado na linha de comando.

RESUMO TÉCNICO:
Importa lab_env (que aponta o sistema para o SQLite do laboratório), busca o
Usuario pelo login (sys.argv[1]) e cria ou atualiza os DadosFuncionais com
valores fictícios, gravando com commit.

FINALIDADE DE NEGÓCIO:
A portaria de designação só segue quando o RH tem RS/PV e RG/CIN de cada
nomeado; este script simula o RH completando o cadastro para os prints do
manual da portaria.

CONTEXTO NO SISTEMA:
Ferramenta de documentação (laboratório). Usa app.models.Usuario e
app.models.rh.DadosFuncionais. Uso: python completar_rh.py <login>.

===============================================================================
"""

import sys
# A pasta backend/ entra no caminho de importação; lab_env precisa vir antes do app
# para as variáveis de ambiente do laboratório valerem.
sys.path.insert(0, "/home/administrador/projeto/backend")
import lab_env  # noqa
from sqlalchemy import select
from app.core.banco import FabricaSessao
from app.models import Usuario
from app.models.rh import DadosFuncionais
# Cria os dados funcionais se o usuário ainda não tiver e preenche valores fictícios.
with FabricaSessao() as s:
    u = s.scalar(select(Usuario).where(Usuario.login == sys.argv[1]))
    d = s.scalar(select(DadosFuncionais).where(DadosFuncionais.usuario_id == u.id)) or DadosFuncionais(usuario_id=u.id)
    d.rs_pv, d.rg_cin = "55123", "12.345.678-9"
    s.add(d); s.commit(); print("ok", u.login)
