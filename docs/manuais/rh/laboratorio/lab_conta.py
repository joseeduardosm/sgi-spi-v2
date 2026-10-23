# Simula a TI criando a conta no AD: a pessoa aparece na sincronização, a ficha se liga a ela e ela ganha senha local só para o laboratório entrar.
import sys
sys.path.insert(0, "/home/administrador/projeto/backend")
import lab_env  # noqa
import lab_patches
from app.core.banco import FabricaSessao
from app.core.seguranca import gerar_hash_senha
from app.models.diretorio_ldap import DiretorioLdap
from app.models.usuario import Usuario
from app.services import servico_ldap
from app.services.cliente_ldap import IdentidadeLdap
from sqlalchemy import select

lab_patches.aplicar()
login, nome = sys.argv[1], sys.argv[2]
with FabricaSessao() as s:
    d = s.scalar(select(DiretorioLdap)) or DiretorioLdap(nome="AD do laboratório", servidor="ad.exemplo", porta=389, usar_ssl=False, base_dn="DC=exemplo,DC=sp,DC=gov,DC=br", bind_dn="x", senha_bind_cifrada="x", ativo=True)
    s.add(d); s.commit()
    servico_ldap.aplicar_fotografia(s, d, [IdentidadeLdap(login=login, nome_completo=nome, email=f"{login}@exemplo.sp.gov.br", dn=f"CN={login}", id_externo=f"guid-{login}")])
    s.commit()
    u = s.scalar(select(Usuario).where(Usuario.login == login))
    u.hash_senha, u.origem = gerar_hash_senha("senha-lab-1"), "local_ldap"  # só no laboratório: para entrar sem AD
    s.commit(); print("conta criada:", u.login, "| ficha ligada, foto:", bool(u.foto_anexo_id))
