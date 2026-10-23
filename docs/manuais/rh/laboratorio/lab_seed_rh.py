# Base fictícia do laboratório do RH (SQLite isolado): setores, pessoas, cargos e vagas, checklists, Protocolo e fichas. Nenhum dado é real.
import io, sys
sys.path.insert(0, "/home/administrador/projeto/backend")
import lab_env  # noqa
import lab_patches
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
import app.models  # noqa
from app.core.banco import Base, FabricaSessao, agora_utc, motor
from app.core.seguranca import gerar_hash_senha
from app.main import app
from app.models import Usuario
from app.services import servico_diretorio

lab_patches.aplicar()
PERFIL = {"email": "pessoa@exemplo.sp.gov.br", "ramal": "1234", "andar": "5", "predio": "A"}


def foto(cor, letra):
    imagem = Image.new("RGB", (240, 240), cor)
    ImageDraw.Draw(imagem).ellipse((70, 40, 170, 140), fill=(245, 245, 245))
    ImageDraw.Draw(imagem).ellipse((40, 150, 200, 300), fill=(245, 245, 245))
    saida = io.BytesIO(); imagem.save(saida, "PNG"); return saida.getvalue()


def usuario(login, nome, cargo, departamento, cor=None, **extra):
    with FabricaSessao() as s:
        u = Usuario(login=login, hash_senha=gerar_hash_senha("senha-lab-1"), superusuario=False, nome_completo=nome, cargo=cargo, departamento=departamento,
                    origem="local_ldap", **{**PERFIL, "email": f"{login}@exemplo.sp.gov.br", **extra})
        u.perfil_revisado_em = agora_utc()
        u.boas_vindas_em = agora_utc()  # quem já usa o sistema não vê as boas-vindas
        s.add(u); s.commit(); s.refresh(u)
        if cor:
            servico_diretorio.definir_foto(s, u, foto(cor, nome[0]), "upload", None); s.commit()
        return u.id


Base.metadata.create_all(motor)
with TestClient(app) as c:
    def h(login, senha="senha-lab-1"):
        r = c.post("/api/autenticacao/login", json={"login": login, "senha": senha}); assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['token_acesso']}"}

    def ok(r, esperado=(200, 201, 204)):
        assert r.status_code in esperado, (r.request.url, r.status_code, r.text[:300]); return r

    admin = h("root", "senha-teste")
    # Pessoas (fictícias). Quem tem foto aparece com ela no organograma.
    rita = usuario("rita", "Rita Moura Gestora de Pessoas", "FCESP 2.15 – Assessor Especial III", "Coordenadoria de Gestão de Pessoas", (178, 34, 46))
    sofia = usuario("sofia", "Sofia Andrade Subsecretária", "CCESP 1.17 – Subsecretário", "Subsecretaria de Gestão Corporativa", (46, 98, 150))
    diego = usuario("diego", "Diego Matos Diretor", "CCESP 1.15 – Diretor", "Diretoria de Gestão Administrativa", (60, 130, 90))
    lucas = usuario("lucas", "Lucas Prado Coordenador", "CCESP 1.13 – Coordenador", "Coordenadoria de Gestão de Pessoas", (150, 100, 40))
    bruna = usuario("bruna", "Bruna Teixeira Assessora", "CCESP 2.10 – Assessor II", "Coordenadoria de Gestão de Pessoas")
    marcos = usuario("marcos", "Marcos Vieira Assessor", "CCESP 2.11 – Assessor III", "Diretoria de Gestão Administrativa", (120, 70, 150))
    camila = usuario("camila", "Camila Duarte Assistente", "CCESP 2.07 – Assistente Técnico III", "Serviço de Apoio Administrativo")
    paulo = usuario("paulo", "Paulo Nunes Subsecretário de Parcerias", "CCESP 1.17 – Subsecretário", "Subsecretaria de Gestão de Parcerias", (40, 110, 120))
    pedro = usuario("pedro", "Pedro Lima Analista", "Analista de Projetos", "Subsecretaria de Gestão de Parcerias")
    helena = usuario("helena", "Helena Rocha Assessora", "Assessor Técnico - CCESP 2.09", "Diretoria de Gestão Administrativa")  # cargo em texto livre: aparece em "A reconciliar"
    # Setores
    def setor(nome, sigla, tipo, pai=None, lider=None):
        corpo = {"nome": nome, "sigla": sigla, "tipo_unidade": tipo, "setor_pai_id": pai, "lider_id": lider, "membros_ids": []}
        return ok(c.post("/api/setores", json=corpo, headers=admin)).json()["id"]
    spi = setor("Secretaria de Parcerias em Investimentos", "SPI", "secretaria")
    sgc = setor("Subsecretaria de Gestão Corporativa", "SGC", "subsecretaria", spi, sofia)
    dga = setor("Diretoria de Gestão Administrativa", "DGA", "diretoria", sgc, diego)
    cgp = setor("Coordenadoria de Gestão de Pessoas", "CGP", "coordenadoria", dga, lucas)
    saa = setor("Serviço de Apoio Administrativo", "SAA", "servico", dga)
    sgp = setor("Subsecretaria de Gestão de Parcerias", "SGP", "subsecretaria", spi, paulo)
    dep = setor("Diretoria de Estruturação de Parcerias", "DEP", "diretoria", sgp)
    # Acesso: Rita é o RH (controle total no recurso `rh`); o Protocolo opera por ela
    for nome, slug in (("RH", "rh"), ("Protocolo", "protocolo")):
        rr = c.post("/api/acl/recursos", json={"nome": nome, "slug": slug}, headers=admin)
        if rr.status_code == 201:
            ok(c.post("/api/acl/regras", json={"recurso_id": rr.json()["id"], "nivel": "CONTROLE_TOTAL" if slug == "rh" else "MODIFICACAO", "usuarios_ids": [rita], "setores_ids": []}, headers=admin))
    hr = h("rita")
    tipos = {t["codigo"]: t["id"] for t in c.get("/api/rh/tipos-cargo", headers=hr).json()}
    # Cargos (vagas) e ocupações
    def cargo(setor_id, tipo, grupo, nivel, nome, quantidade=1, ocupantes=()):
        vagas = ok(c.post("/api/rh/cargos", json={"setor_id": setor_id, "tipo_id": tipos[tipo], "grupo": grupo, "nivel": nivel, "denominacao": nome, "quantidade": quantidade}, headers=hr)).json()
        for vaga, pessoa in zip(vagas, ocupantes):
            ok(c.post(f"/api/rh/cargos/{vaga['id']}/ocupacao", json={"usuario_id": pessoa, "inicio": "2025-03-03", "ato": "Resolução SPI 08/2025"}, headers=hr))
        return vagas
    cargo(spi, "CCESP", 1, 18, "Secretário Executivo")
    cargo(sgc, "CCESP", 1, 17, "Subsecretário", 1, [sofia])
    cargo(sgc, "FCESP", 2, 16, "Assessor Especial IV", 2)  # duas vagas livres
    cargo(dga, "CCESP", 1, 15, "Diretor", 1, [diego])
    cargo(dga, "CCESP", 2, 11, "Assessor III", 1, [marcos])
    cargo(dga, "CCESP", 2, 7, "Assistente Técnico III", 1)  # vaga livre
    cargo(cgp, "CCESP", 1, 13, "Coordenador", 1, [lucas])
    cargo(cgp, "FCESP", 2, 15, "Assessor Especial III", 1, [rita])
    cargo(cgp, "CCESP", 2, 10, "Assessor II", 2, [bruna])  # uma livre
    cargo(saa, "CCESP", 2, 7, "Assistente Técnico III", 1, [camila])
    cargo(sgp, "CCESP", 1, 17, "Subsecretário", 1, [paulo])
    cargo(dep, "CCESP", 1, 15, "Diretor", 1)
    # Protocolo: tipo de Resolução com faixa no ano
    tipo = ok(c.post("/api/protocolo/tipos", json={"nome": "Resoluções SPI"}, headers=admin)).json()
    ok(c.post(f"/api/protocolo/tipos/{tipo['id']}/sequencias", json={"exercicio": agora_utc().year, "inicio": 1, "fim": 99}, headers=admin))
    # Checklists por classificação
    ok(c.post("/api/rh/checklists", json={"nome": "Documentos de direção e chefia (1.15 a 1.18)", "classificacoes": [{"grupo": 1, "nivel": n} for n in (15, 16, 17, 18)],
        "itens": [{"descricao": "Cópia do RG e do CPF", "obrigatorio": True}, {"descricao": "Comprovante de residência", "obrigatorio": True}, {"descricao": "Declaração de bens", "obrigatorio": True}, {"descricao": "Foto 3x4", "obrigatorio": False}]}, headers=hr))
    ok(c.post("/api/rh/checklists", json={"nome": "Documentos de assessoria (2.04 a 2.17)", "classificacoes": [{"grupo": 2, "nivel": n} for n in range(4, 18)],
        "itens": [{"descricao": "Cópia do RG e do CPF", "obrigatorio": True}, {"descricao": "Comprovante de residência", "obrigatorio": True}, {"descricao": "Certidão de antecedentes", "obrigatorio": True}, {"descricao": "Comprovante de escolaridade", "obrigatorio": False}]}, headers=hr))
    # Fichas: uma pronta (aguardando a conta, com a vaga FCESP 2.16 da SGC) e um rascunho
    vagas = c.get("/api/rh/cargos", params={"situacao": "vago"}, headers=hr).json()
    vaga_sgc = next(v for v in vagas if v["setor_nome"].startswith("Subsecretaria de Gestão Corporativa"))
    ficha = {"nome_completo": "Mariana Costa Ribeiro", "cpf": "529.982.247-25", "rg_numero": "12.345.678-9", "rg_orgao": "SSP", "rg_uf": "SP", "data_nascimento": "1991-04-12", "sexo": "Feminino",
             "estado_civil": "Casado(a)", "nacionalidade": "Brasileira", "naturalidade_cidade": "Campinas", "naturalidade_uf": "SP", "nome_mae": "Helena Costa Ribeiro",
             "email_pessoal": "mariana.ribeiro@exemplo.com", "celular": "(11) 99999-1234", "cep": "01310-100", "logradouro": "Avenida Paulista", "numero": "1000", "bairro": "Bela Vista", "cidade": "São Paulo", "uf": "SP",
             "vinculo_tipo": "Servidor efetivo cedido", "orgao_origem": "Prefeitura de Campinas", "cargo_origem": "Analista de Planejamento", "rs_pv": "123456-7", "inicio_previsto": "2026-11-03",
             "cargo_id": vaga_sgc["id"], "login_proposto": "mariana.ribeiro", "status": "aguardando_conta",
             "formacoes": [{"nivel": "Pós-graduação", "curso": "Gestão Pública", "instituicao": "Unicamp", "ano_conclusao": 2018}], "experiencias": [{"empresa": "Prefeitura de Campinas", "cargo": "Analista de Planejamento", "inicio": "2014-02-03", "descricao": "Planejamento e acompanhamento de projetos."}]}
    ok(c.post("/api/rh/pre-cadastros", json=ficha, headers=hr))
    ok(c.post("/api/rh/pre-cadastros", json={"nome_completo": "Rafael Almeida Santos", "cpf": "168.995.350-09", "status": "rascunho"}, headers=hr))
    # Boas-vindas do lab: o texto padrão dos modelos nasce na primeira consulta
    c.get("/api/rh/modelos", headers=hr)
print("seed ok")
