# Marca o perfil de um usuário do laboratório como revisado (evita a tela "Atualize seu cadastro").
import sys
sys.path.insert(0, "/home/administrador/projeto/backend")
import lab_env  # noqa
from sqlalchemy import select
from app.core.banco import FabricaSessao
from app.models import Usuario
from app.core.banco import agora_utc
with FabricaSessao() as s:
    u = s.scalar(select(Usuario).where(Usuario.login == sys.argv[1])); u.perfil_revisado_em = agora_utc(); s.commit(); print("ok", u.login)
