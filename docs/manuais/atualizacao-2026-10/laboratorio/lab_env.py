# Ambiente isolado (SQLite + anexos num diretório temporário) para gerar os prints dos manuais; nunca toca no PostgreSQL de produção.
import os, bcrypt
from cryptography.fernet import Fernet
D = os.path.dirname(os.path.abspath(__file__))
os.environ["URL_BANCO_DADOS"] = f"sqlite:///{D}/lab.db"
os.environ["CHAVE_SECRETA_JWT"] = "chave-do-laboratorio-com-pelo-menos-32-caracteres"
os.environ["LOGIN_ADMIN"] = "root"
os.environ["HASH_SENHA_ADMIN"] = bcrypt.hashpw(b"senha-teste", bcrypt.gensalt(rounds=4)).decode()
os.environ["MINUTOS_EXPIRACAO_TOKEN"] = "600"
os.environ["CHAVE_CIFRA_LDAP"] = Fernet.generate_key().decode() if not os.path.exists(f"{D}/.cifra") else open(f"{D}/.cifra").read()
if not os.path.exists(f"{D}/.cifra"): open(f"{D}/.cifra", "w").write(os.environ["CHAVE_CIFRA_LDAP"])
os.environ["INTERVALO_SINCRONIZACAO_LDAP_MINUTOS"] = "0"
os.environ["ANEXOS_DIRETORIO"] = f"{D}/anexos"
os.environ["NOTIFICACOES_DESPACHO"] = "desligado"
os.environ["URL_PUBLICA"] = "http://localhost:8200"

# SQLite devolve datas sem fuso; o PostgreSQL de produção devolve com fuso. Para o laboratório se comportar como produção, marca como UTC.
from datetime import timezone as _tz
import sqlalchemy.dialects.sqlite.base as _b
_orig = _b.DATETIME.result_processor
def _rp(self, dialect, coltype):
    f = _orig(self, dialect, coltype)
    def conv(v):
        d = f(v) if f else v
        return d.replace(tzinfo=_tz.utc) if d is not None and getattr(d, "tzinfo", 1) is None else d
    return conv
_b.DATETIME.result_processor = _rp
