import sys, runpy
sys.path.insert(0, "/home/administrador/projeto/backend")
import lab_env  # noqa
from datetime import date
import bcrypt
from fastapi.testclient import TestClient
import app.models  # noqa
from app.core.banco import Base, FabricaSessao, agora_utc, motor
from app.core.seguranca import gerar_hash_senha
from app.main import app
from app.models import Usuario
from app.models.rh import DadosFuncionais
from tests.apoio_contratos import criar_empresa, dados_contrato, item, PDF, restringir_contratos

HOJE = date(2026, 3, 15)
import app.services.contratos.servico_contratos as sc, app.services.contratos.servico_competencias as scomp
sc.hoje = lambda: HOJE; scomp.hoje = lambda: HOJE

PERFIL = {"email": "pessoa@exemplo.sp.gov.br", "ramal": "1234", "andar": "5", "predio": "A", "departamento": "Contratos"}
def usuario(login, nome, cargo="Analista", completo=True, **extra):
    with FabricaSessao() as s:
        u = Usuario(login=login, hash_senha=gerar_hash_senha("senha-lab-1"), superusuario=False, nome_completo=nome, cargo=cargo, **{**PERFIL, **extra})
        u.perfil_revisado_em = agora_utc()
        s.add(u); s.commit(); s.refresh(u); i = u.id
        if completo:
            s.add(DadosFuncionais(usuario_id=i, rs_pv=f"{i}0123", rg_cin=f"1{i}.222.333-4")); s.commit()
        return i

Base.metadata.create_all(motor)
with TestClient(app) as c:
    def h(login, senha="senha-lab-1"):
        r = c.post("/api/autenticacao/login", json={"login": login, "senha": senha}); assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['token_acesso']}"}
    admin = h("root", "senha-teste")
    marina = usuario("marina", "Marina Souza Gestora", "Gestora de Contratos")
    carlos = usuario("carlos", "Carlos Lima Fiscal", "Fiscal de Contratos")
    paulo = usuario("paulo", "Paulo Andrade Novo", "Analista Técnico")
    ana = usuario("ana", "Ana Ribeiro Suplente", "Analista Administrativa", completo=False)   # com dados do RH pendentes
    roberto = usuario("roberto", "Roberto Campos Autoridade", "Subsecretário de Gestão")
    protoc = usuario("protocolo", "Patrícia Protocolo", "Agente do Protocolo")
    restringir_contratos(c, admin, {marina: "MODIFICACAO", carlos: "MODIFICACAO", paulo: "MODIFICACAO", ana: "MODIFICACAO", roberto: "LEITURA"})
    # Protocolo
    rp = c.post("/api/acl/recursos", json={"nome": "Protocolo", "slug": "protocolo"}, headers=admin)
    if rp.status_code == 201:
        c.post("/api/acl/regras", json={"recurso_id": rp.json()["id"], "nivel": "CONTROLE_TOTAL", "usuarios_ids": [protoc], "setores_ids": []}, headers=admin)
    tipo = c.post("/api/protocolo/tipos", json={"nome": "Portaria SPI SSGC"}, headers=admin).json()
    c.post(f"/api/protocolo/tipos/{tipo['id']}/sequencias", json={"exercicio": 2026, "inicio": 1, "fim": 99}, headers=admin)
    # máscaras de portaria
    MASC = ('<p style="text-align: center"><strong>Portaria SPI SSGC nº #numeroportaria, de #anoportaria</strong></p>'
            '<p>Designa os responsáveis pela gestão e fiscalização do Contrato #numerodocontrato, firmado com #contratada, CNPJ #cnpjcontratada, cujo objeto é #objetodocontrato (processo SEI #nroprocessosei).</p>'
            '<p>I – #nomegestor – RS #rsgestor – Gestor;</p><p>II – #nomefiscaltecnico – RS #rsfiscaltecnico – Fiscal técnico;</p><p>III – #nomegestorsuplente – RS #rsgestorsuplente – Gestor suplente.</p>')
    ASS = '<p style="text-align: center">#nomeautoridade</p>'
    c.post("/api/contratos/modelos", json={"tipo": "portaria", "nome": "Portaria sem anterior", "variante": "sem_anterior", "html": MASC + ASS}, headers=admin)
    c.post("/api/contratos/modelos", json={"tipo": "portaria", "nome": "Portaria com anterior", "variante": "com_anterior", "html": MASC + ASS + '<p>Fica revogada a Portaria #nomedocumento nº #numeroportariaanterior, de #diaportariaanterior de #mesportariaanterior de #anoportariaanterior.</p>'}, headers=admin)
    c.post("/api/portarias/autoridades", json={"sigla": "SPI SSGC", "usuario_id": roberto, "ativa": True}, headers=admin)
    # contrato de exemplo
    emp = c.post("/api/contratos/empresas", json={"cnpj": "11222333000181", "razao_social": "Exemplo Serviços Prediais Ltda", "nome_fantasia": "Exemplo Serviços", "endereco": "Av. Exemplo, 100"}, headers=admin).json()
    corpo = dados_contrato(emp["id"], numero="900/2026", apelido="EXEMPLO – Limpeza e manutenção predial", objeto="Prestação de serviços de limpeza e manutenção predial", equipe={"gestor": marina, "fiscal_tecnico": carlos})
    r = c.post("/api/contratos", json=corpo, headers=admin); assert r.status_code == 201, r.text
    contrato = r.json()
    print("contrato", contrato["id"])
    open("ids.txt", "w").write(f"{contrato['id']}\n")
    # execução até a OB (competência 01/2026) para o item "Pagamentos"
    g = h("marina"); u = lambda p="": f"/api/contratos/{contrato['id']}{p}"
    from tests.test_contratos_execucao import _preparar_execucao
    from tests.apoio_contratos import juntar_nf, conferir_retencao
    _preparar_execucao(c, contrato, g)
    c.post(u("/execucao/gerar"), headers=g)
    notas = {n["numero"]: n["id"] for n in c.get(u("/notas-empenho"), headers=g).json()}
    ordem = [notas["2026NE00001"], notas["2026NE00002"]]
    comp = c.get(u("/competencias/identificador/2026-01"), headers=g).json(); base = u(f"/competencias/{comp['id']}")
    c.put(f"{base}/medicao", json={"itens": [{"id": i["id"], "quantidade_medida": i["quantidade_prevista"]} for i in comp["itens"]], "notas_empenho_ids": ordem}, headers=g)
    c.post(f"{base}/medicao/ciencia", headers=g)
    print(c.post(f"{base}/medicao/concluir", json={"notas_empenho_ids": ordem}, headers=g).status_code)
    print(juntar_nf(c, base, g, "2105.00", "123").status_code)
    d = conferir_retencao(c, base, g, {"ir": "31.58"}).json()
    for doc in d["documentos"]: c.post(f"{base}/checklist/{doc['id']}", files={"arquivo": ("d.pdf", PDF)}, headers=g)
    print(c.post(f"{base}/cadin", data={"possui_pendencia": "false"}, files={"certidao": ("c.pdf", PDF)}, headers=g).status_code)
    print(c.post(f"{base}/consolidado", headers=g).status_code)
    print(c.post(f"{base}/ordem-bancaria", files={"arquivo": ("ob.pdf", PDF)}, headers=g).status_code)
    # diário com ocorrências e anexo
    import json
    for dt, tx, anx in (("2026-02-10", "Posto de limpeza descoberto das 8h às 12h.", True), ("2026-02-10", "Material de limpeza entregue com atraso.", False), ("2026-02-18", "Vazamento no banheiro do 3º andar corrigido pela contratada.", False)):
        corpo_o = {"data_ocorrencia": dt, "descricao": tx, "possui_glosa": False, "glosas": [], "enviar_email": False}
        files = [("arquivos", ("foto-posto.pdf", PDF, "application/pdf"))] if anx else []
        print(c.post(u("/diario"), data={"dados": json.dumps(corpo_o)}, files=files, headers=g).status_code)
print("seed ok")
