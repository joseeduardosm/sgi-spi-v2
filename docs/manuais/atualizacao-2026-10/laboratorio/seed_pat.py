import sys, uuid
sys.path.insert(0, "/home/administrador/projeto/backend")
import lab_env  # noqa
from decimal import Decimal
from fastapi.testclient import TestClient
import app.models  # noqa
from app.core.banco import FabricaSessao, agora_utc
from app.core.seguranca import gerar_hash_senha
from app.main import app
from app.models import Usuario
from app.models.patrimonio import GrupoMaterial, Localizacao
from app.models.setor import Setor
from sqlalchemy import select

def usuario(login, nome, cargo):
    with FabricaSessao() as s:
        u = s.scalar(select(Usuario).where(Usuario.login == login))
        if u is None:
            u = Usuario(login=login, hash_senha=gerar_hash_senha("senha-lab-1"), nome_completo=nome, cargo=cargo, email="pessoa@exemplo.sp.gov.br", ramal="1234", andar="5", predio="A", departamento="Patrimônio")
            u.perfil_revisado_em = agora_utc(); s.add(u); s.commit(); s.refresh(u)
        return u.id
fernanda, ricardo, tereza = usuario("fernanda", "Fernanda Lopes Patrimônio", "Analista de Patrimônio"), usuario("ricardo", "Ricardo Alves Chefe", "Chefe de Patrimônio"), usuario("tereza", "Tereza Gomes Apoio", "Assistente")
with FabricaSessao() as s:
    fin, dep = Setor(nome="Financeiro"), Setor(nome="Depósito inservível"); s.add_all([fin, dep]); s.flush()
    raiz = Localizacao(id=uuid.uuid4(), tipo="predio", nome="Prédio SPI"); andar = Localizacao(id=uuid.uuid4(), pai_id=raiz.id, tipo="andar", nome="5º andar", andar=5)
    lado = Localizacao(id=uuid.uuid4(), pai_id=andar.id, tipo="lado", nome="Lado A", andar=5, lado="A"); s.add_all([raiz, andar, lado]); s.flush()
    salas = {}
    for cod, st, resp in (("05A01", fin, ricardo), ("05A02", fin, ricardo), ("05A15", dep, ricardo)):
        sala = Localizacao(id=uuid.uuid4(), pai_id=lado.id, tipo="sala", nome=cod, codigo=cod, andar=5, lado="A", setor_id=st.id, responsavel_id=resp); s.add(sala); salas[cod] = str(sala.id)
    s.add(GrupoMaterial(id=uuid.uuid4(), codigo="MOB", nome="Mobiliário", vida_util_meses=120, residual_percentual=Decimal("10"), deprecia=True)); s.commit()
with TestClient(app) as c:
    def h(l, s="senha-lab-1"): return {"Authorization": "Bearer " + c.post("/api/autenticacao/login", json={"login": l, "senha": s}).json()["token_acesso"]}
    adm = h("root", "senha-teste")
    r = c.post("/api/acl/recursos", json={"nome": "Patrimônio", "slug": "patrimonio"}, headers=adm); rid = r.json()["id"]
    for nivel, ids in (("MODIFICACAO", [fernanda, tereza]), ("CONTROLE_TOTAL", [ricardo])):
        c.post("/api/acl/regras", json={"recurso_id": rid, "nivel": nivel, "usuarios_ids": ids, "setores_ids": []}, headers=adm)
    hf = h("fernanda")
    itens = [("PAT-0101", "Cadeira giratória preta", "05A01"), ("PAT-0102", "Cadeira giratória preta", "05A01"), ("PAT-0103", "Mesa de reunião 8 lugares", "05A01"),
             ("PAT-0201", "Monitor 24 polegadas", "05A02"), ("PAT-0202", "Nobreak 1200 VA", "05A02"), ("PAT-0203", "Armário de aço 2 portas", "05A02")]
    for chapa, desc, sala in itens:
        print(c.post("/api/patrimonio/bens", json={"chapa": chapa, "descricao": desc, "localizacao_id": salas[sala], "conservacao": 2}, headers=hf).status_code)
    lista = c.post("/api/patrimonio/classificacoes", json={"tipo": "inservivel"}, headers=hf).json()
    for chapa in ("PAT-0201", "PAT-0202", "PAT-0203"):
        print(c.post(f"/api/patrimonio/classificacoes/{lista['id']}/bens", json={"chapa": chapa}, headers=hf).status_code)
    print("lista", lista["id"], lista["numero"])
    open("lista.txt", "w").write(lista["id"])
