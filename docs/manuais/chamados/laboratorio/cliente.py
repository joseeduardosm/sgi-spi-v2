# Criado por José Eduardo Santana Martins
# Este arquivo serve para chamar a API do laboratório do manual dos Chamados (e abrir sessão no banco dele).
import json, os, sys, urllib.request, uuid
D = os.path.dirname(os.path.abspath(__file__))
os.environ["URL_BANCO_DADOS"] = f"sqlite:///{D}/lab.db"
os.environ.setdefault("CHAVE_SECRETA_JWT", "chave-do-laboratorio-com-pelo-menos-32-caracteres")
sys.path.insert(0, "/home/administrador/projeto/backend")
import app.models  # noqa
from app.core.banco import FabricaSessao, agora_utc
from app.core.seguranca import gerar_hash_senha
from app.models.setor import MembroSetor, Setor
from app.models.usuario import Usuario

API = "http://127.0.0.1:8301/api"
def chamar(m, p, tok=None, corpo=None, multipart=None):
    cab = {"Authorization": f"Bearer {tok}"} if tok else {}
    if multipart is not None:
        fronteira = uuid.uuid4().hex
        dados = f'--{fronteira}\r\nContent-Disposition: form-data; name="dados"\r\n\r\n{json.dumps(multipart)}\r\n--{fronteira}--\r\n'.encode()
        cab["Content-Type"] = f"multipart/form-data; boundary={fronteira}"
    else:
        dados = json.dumps(corpo).encode() if corpo is not None else None
        cab["Content-Type"] = "application/json"
    r = urllib.request.Request(API + p, data=dados, method=m, headers=cab)
    try:
        with urllib.request.urlopen(r, timeout=60) as x: return json.loads(x.read() or b"{}")
    except urllib.error.HTTPError as e: raise SystemExit(f"{m} {p} {e.code} {e.read()[:400]}")
def login(l, s="senha-lab-1"): return chamar("POST", "/autenticacao/login", corpo={"login": l, "senha": s})["token_acesso"]

