# Marca o perfil de uma conta como revisado (o que a pessoa faz em "Meu perfil" depois das boas-vindas), para o laboratório seguir para as outras telas.
import sys
sys.path.insert(0, "/home/administrador/projeto/backend")
import lab_env  # noqa
from sqlalchemy import select
from app.core.banco import FabricaSessao, agora_utc
from app.models.usuario import Usuario

with FabricaSessao() as s:
    u = s.scalar(select(Usuario).where(Usuario.login == sys.argv[1]))
    u.ramal, u.andar, u.predio = u.ramal or "1234", u.andar or "5", u.predio or "A"  # o que a pessoa preenche no perfil
    u.celular = u.celular or "(11) 99999-1234"
    u.perfil_revisado_em = agora_utc()
    s.commit(); print("perfil revisado:", u.login)
