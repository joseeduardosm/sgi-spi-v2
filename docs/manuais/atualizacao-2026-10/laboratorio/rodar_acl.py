import sys, os
sys.path.insert(0, ".")
from cap import *
import api
t = api.login("root", "senha-teste")
if not os.environ.get("SO_FOTOS"):
    def mk(nome, pai=None):
        r = api.chamar("POST", "/setores", t, {"nome": nome, "setor_pai_id": pai, "lider_id": None, "sistemico": False, "ativo": True, "membros_ids": []}); return r["id"]
    sg = mk("Subsecretaria de Gestão"); c = mk("Coordenadoria de Contratos", sg); mk("Núcleo de Fiscalização", c); mk("Coordenadoria de Patrimônio", sg)
    recs = {r["slug"]: r for r in api.chamar("GET", "/acl/recursos", t)}
    perfil = api.chamar("POST", "/acl/perfis", t, {"nome": "Administrador de Contratos", "descricao": "Conduz contratos e portarias de designação", "ativo": True})
    api.chamar("PUT", f"/acl/perfis/{perfil['id']}/modulos/{recs['contratos']['id']}", t, {"acoes": ["LEITURA", "MODIFICACAO", "CONTROLE_TOTAL"]})
with sync_playwright() as p:
    nav, ctx = abrir(p, 1366, 900); ctx.set_default_timeout(20000)
    pg = entrar(ctx, "root", "senha-teste")
    pg.goto(f"{BASE}/admin/acl"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
    pg.locator("text=Administrador de Contratos").first.click(); pg.wait_for_timeout(1200)
    foto(pg, "a01-perfil-modulos", [(pg.locator(".acl-perfil-menu"), 1, "dir"), (pg.locator(".acl-perfil-menu button", has_text="Usuários"), 2, "dir")],
         legendas=["Cada perfil tem, por módulo, ações independentes (caixas de marcação)", "Aba Usuários: pessoas, setores e grupos que recebem o perfil"])
    pg.locator(".acl-perfil-menu button", has_text="Usuários").click(); pg.wait_for_timeout(1500)
    pg.locator(".acl-arvore-setores label", has_text="Subsecretaria de Gestão").locator("input").check(); pg.wait_for_timeout(500)
    foto(pg, "a02-perfil-setores", [(pg.locator("#perfil-busca-setor"), 1, "cima"), (pg.locator(".acl-arvore-setores label", has_text="Subsecretaria de Gestão"), 2, "esq"),
         (pg.locator(".acl-arvore-setores label", has_text="Núcleo de Fiscalização"), 3, "esq"), (pg.get_by_role("button", name="Salvar usuários"), 4, "cima")], rolar="#perfil-busca-setor",
         legendas=["Pesquise setores e grupos sistêmicos", "Marcar o setor pai marca também todos os setores abaixo dele", "Cada setor abaixo ainda pode ser desmarcado, de forma independente", "Salvar: quem é membro dos setores marcados recebe o perfil"])
    nav.close()
print("acl ok")
