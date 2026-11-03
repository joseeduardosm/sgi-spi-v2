# Criado por José Eduardo Santana Martins
# Este arquivo serve para subir a API do laboratório do manual dos Chamados (SQLite temporário), sem tocar no PostgreSQL de produção.
import os, sys
import bcrypt
from cryptography.fernet import Fernet
D = os.path.dirname(os.path.abspath(__file__))
os.environ["URL_BANCO_DADOS"] = f"sqlite:///{D}/lab.db"
os.environ["CHAVE_SECRETA_JWT"] = "chave-do-laboratorio-com-pelo-menos-32-caracteres"
os.environ["LOGIN_ADMIN"] = "root"
os.environ["HASH_SENHA_ADMIN"] = bcrypt.hashpw(b"senha-teste", bcrypt.gensalt(rounds=4)).decode()
os.environ["MINUTOS_EXPIRACAO_TOKEN"] = "600"
os.environ["CHAVE_CIFRA_LDAP"] = Fernet.generate_key().decode()
os.environ["INTERVALO_SINCRONIZACAO_LDAP_MINUTOS"] = "0"
os.environ["ANEXOS_DIRETORIO"] = f"{D}/anexos"
os.environ["NOTIFICACOES_DESPACHO"] = "desligado"
os.environ["URL_PUBLICA"] = "http://localhost:8302"
sys.path.insert(0, "/home/administrador/projeto/backend")
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
import app.models  # noqa
from app.core.banco import Base, motor
Base.metadata.create_all(motor)
import uvicorn
uvicorn.run("app.main:app", host="127.0.0.1", port=8301, log_level="warning")
