# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a gestão de usuários e setores pela ACL (ex.: CGP com CONTROLE_TOTAL) e seus limites.
"""Gestão de usuários e setores por CONTROLE_TOTAL na ACL, sem escalada de privilégio."""

from app.core.banco import FabricaSessao
from app.models.acl import RecursoAcl, RegraAcl
from app.models.setor import MembroSetor, Setor
from tests.conftest import cabecalho, criar_usuario

PERFIL = {"nome_completo": "Nova Pessoa", "email": "nova@sp.gov.br", "ramal": "1234", "cargo": "Analista", "departamento": "Diretoria A",
          "andar": "3", "predio": "Sede"}


def _cgp_com_controle_total() -> tuple[int, int]:
    """Setor CGP (com a Rita) e regras CONTROLE_TOTAL em `usuarios` e `setores`."""
    rita = criar_usuario("rita")
    with FabricaSessao() as sessao:
        cgp = Setor(nome="Coordenadoria de Gestão de Pessoas")
        sessao.add(cgp)
        sessao.flush()
        sessao.add(MembroSetor(setor_id=cgp.id, usuario_id=rita))
        for slug in ("usuarios", "setores"):
            recurso = RecursoAcl(nome=slug.title(), slug=slug)
            sessao.add(recurso)
            sessao.flush()
            regra = RegraAcl(recurso_id=recurso.id, nivel="CONTROLE_TOTAL")
            regra.setores.append(cgp)
            sessao.add(regra)
        sessao.commit()
        return rita, cgp.id


def test_sem_regras_ninguem_alem_do_superroot_grava(cliente, admin):
    """Recurso sem regras continua aberto para leitura, mas não libera gravação."""
    criar_usuario("comum")
    h = cabecalho(cliente, "comum")
    assert cliente.get("/api/usuarios", headers=h).status_code == 200
    r = cliente.post("/api/setores", json={"nome": "Setor X"}, headers=h)
    assert r.status_code == 403 and r.json()["codigo"] == "acl_negado"
    assert cliente.post("/api/setores", json={"nome": "Setor X"}, headers=admin).status_code == 201


def test_cgp_administra_usuarios_sem_escalar_privilegio(cliente, admin):
    _cgp_com_controle_total()
    criar_usuario("comum")
    chefe = criar_usuario("chefe", superusuario=True)
    h_cgp, h_comum = cabecalho(cliente, "rita"), cabecalho(cliente, "comum")
    # Lista positiva: quem não está na regra perde até a leitura
    assert cliente.get("/api/usuarios", headers=h_comum).status_code == 403
    assert cliente.get("/api/usuarios", headers=h_cgp).status_code == 200
    # Criar conta comum: pode; conceder SuperRoot: não
    conta = {"login": "nova.pessoa", "senha": "senha-forte-1", "ativo": True, "superusuario": False, "perfil": PERFIL}
    r = cliente.post("/api/usuarios", json=conta, headers=h_cgp)
    assert r.status_code == 201, r.text
    nova = r.json()["id"]
    r = cliente.post("/api/usuarios", json={**conta, "login": "outra", "superusuario": True}, headers=h_cgp)
    assert r.status_code == 403 and "papel de administrador" in r.json()["detalhe"]
    # Alterar perfil e situação de conta comum: pode; senha de outra pessoa ou papel SuperRoot: não
    alteracao = {"senha": None, "ativo": False, "superusuario": False, "perfil": PERFIL}
    assert cliente.put(f"/api/usuarios/{nova}", json=alteracao, headers=h_cgp).status_code == 200
    assert "senha local" in cliente.put(f"/api/usuarios/{nova}", json={**alteracao, "senha": "nova-senha-1"}, headers=h_cgp).json()["detalhe"]
    assert cliente.put(f"/api/usuarios/{nova}", json={**alteracao, "superusuario": True}, headers=h_cgp).status_code == 403
    # Contas SuperRoot: nem alterar nem excluir
    assert cliente.put(f"/api/usuarios/{chefe}", json={**alteracao, "superusuario": True}, headers=h_cgp).status_code == 403
    assert cliente.delete(f"/api/usuarios/{chefe}", headers=h_cgp).status_code == 403
    assert cliente.delete(f"/api/usuarios/{nova}", headers=h_cgp).status_code == 204
    # O SuperRoot continua podendo tudo
    assert cliente.put(f"/api/usuarios/{chefe}", json={**alteracao, "ativo": True, "superusuario": True, "senha": "outra-senha-1"},
                       headers=admin).status_code == 200


def test_cgp_administra_setores_menos_os_sistemicos(cliente, admin):
    rita, _ = _cgp_com_controle_total()
    h = cabecalho(cliente, "rita")
    r = cliente.post("/api/setores", json={"nome": "Diretoria Nova", "membros_ids": [rita]}, headers=h)
    assert r.status_code == 201, r.text
    setor = r.json()["id"]
    assert cliente.put(f"/api/setores/{setor}", json={"nome": "Diretoria Renomeada", "membros_ids": []}, headers=h).status_code == 200
    assert cliente.delete(f"/api/setores/{setor}", headers=h).status_code == 204
    # Grupos sistêmicos: só SuperRoot
    r = cliente.post("/api/setores", json={"nome": "Administradores", "sistemico": True}, headers=h)
    assert r.status_code == 403 and "sistêmicos" in r.json()["detalhe"]
    grupo = cliente.post("/api/setores", json={"nome": "Auditores", "sistemico": True}, headers=admin).json()["id"]
    assert cliente.put(f"/api/setores/{grupo}", json={"nome": "Auditores", "sistemico": False, "membros_ids": [rita]}, headers=h).status_code == 403
    assert cliente.delete(f"/api/setores/{grupo}", headers=h).status_code == 403
