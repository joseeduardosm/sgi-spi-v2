import sys
sys.path.insert(0, "/home/administrador/projeto/backend")
import lab_env  # noqa
from sqlalchemy import select
from app.core.banco import FabricaSessao
from app.models import Usuario
from app.models.rh import DadosFuncionais
with FabricaSessao() as s:
    u = s.scalar(select(Usuario).where(Usuario.login == sys.argv[1]))
    d = s.scalar(select(DadosFuncionais).where(DadosFuncionais.usuario_id == u.id)) or DadosFuncionais(usuario_id=u.id)
    d.rs_pv, d.rg_cin = "55123", "12.345.678-9"
    s.add(d); s.commit(); print("ok", u.login)
