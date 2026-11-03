# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a migração do GLPI pelo botão: configuração, execução (novidades e refazer), andamento e desativação.
"""Migração do GLPI pelo botão. O banco do GLPI é trocado pelo dump de exemplo do teste do importador (mesmas tabelas e formato)."""

from sqlalchemy import func, select

from app.core.banco import FabricaSessao
from app.models.chamados import AcompanhamentoChamado, Chamado, ValidacaoChamado
from app.services.chamados import importacao_glpi, migracao_glpi
from tests.test_chamados import BASE, _preparar
from tests.test_chamados_importacao_glpi import DUMP

MIGRACAO = f"{BASE}/parametros/migracao-glpi"


class _ThreadNaHora:
    """Roda o alvo na hora (no teste, a migração não fica em segundo plano)."""
    def __init__(self, target, args=(), daemon=None):
        self.alvo, self.args = target, args

    def start(self):
        self.alvo(*self.args)


class _ConexaoFalsa:
    def close(self):
        pass


def _ambiente(cliente, admin, monkeypatch, tmp_path):
    c = _preparar(cliente, admin)
    caminho = tmp_path / "glpi.sql"
    caminho.write_text(DUMP, encoding="utf-8")
    fonte = {"dados": importacao_glpi.ler_dump(caminho)}
    monkeypatch.setattr(migracao_glpi, "_pasta", lambda: tmp_path)  # o andamento não vai para a pasta de verdade
    monkeypatch.setattr(migracao_glpi.threading, "Thread", _ThreadNaHora)
    monkeypatch.setattr(migracao_glpi, "_conectar", lambda sessao: _ConexaoFalsa())
    monkeypatch.setattr(migracao_glpi, "ler_banco", lambda conexao, avisar=None: fonte["dados"])
    return c, fonte


def test_migracao_pelo_botao_novidades_refazer_e_desativar(cliente, admin, monkeypatch, tmp_path):
    c, fonte = _ambiente(cliente, admin, monkeypatch, tmp_path)
    inicial = cliente.get(MIGRACAO, headers=admin).json()
    assert inicial["ativa"] and not inicial["senha_cadastrada"] and inicial["ultima_sincronizacao"] is None
    assert cliente.get(MIGRACAO, headers=c["cab"]["tecnico"]).status_code == 403
    # Sem setor padrão: recusa antes de começar
    assert cliente.post(f"{MIGRACAO}/executar", json={"modo": "novidades"}, headers=admin).json()["codigo"] == "sem_configuracao"
    assert inicial["so_abertos"]  # padrão: só os não solucionados
    # Este teste traz o histórico também (os resolvidos), para cobrir a atualização; o "só abertos" tem teste próprio
    r = cliente.put(MIGRACAO, json={"host": "10.23.1.242", "usuario": "sgi_leitura", "senha": "segredo", "setor_padrao_id": c["ids"]["setor_ti"],
                                    "so_abertos": False}, headers=admin)
    assert r.status_code == 200 and r.json()["senha_cadastrada"] and "senha" not in r.json() and not r.json()["so_abertos"]

    # Aprovação cujo aprovador não tem par no SGI: não pode quebrar a migração (fica com o setor responsável)
    for v in fonte["dados"]["glpi_ticketvalidations"]:
        v["users_id_validate"] = v["items_id_target"] = 999
        v["itemtype_target"] = "User"

    # Primeira vez: tudo
    r = cliente.post(f"{MIGRACAO}/executar", json={"modo": "novidades"}, headers=admin)
    assert r.status_code == 202, r.text
    andamento = cliente.get(MIGRACAO, headers=admin).json()["andamento"]
    assert andamento["situacao"] == "concluido" and andamento["percentual"] == 100 and andamento["resumo"]["novos"] == 3
    with FabricaSessao() as sessao:
        assert sessao.scalar(select(func.count()).select_from(Chamado).where(Chamado.origem_glpi_id.is_not(None))) == 3
        validacao = sessao.scalar(select(ValidacaoChamado))
        assert validacao.alvo_setor_id == c["ids"]["setor_ti"] and validacao.alvo_usuario_id is None and "sem par no SGI" in validacao.pedido
        id_acompanhamento = sessao.scalar(select(AcompanhamentoChamado.id).where(AcompanhamentoChamado.origem_glpi_id == 41))

    # O aberto no GLPI (1501) entra como chamado normal: aparece na fila de quem atende; o resolvido (1500) é histórico somente leitura
    with FabricaSessao() as sessao:
        assert not sessao.scalar(select(Chamado.importado).where(Chamado.numero == 1501))
        assert sessao.scalar(select(Chamado.importado).where(Chamado.numero == 1500))
    assert 1501 in [x["numero"] for x in cliente.get(BASE, params={"filtro": "abertos"}, headers=admin).json()["itens"]]

    # De novo, sem mudança no GLPI: nada regravado
    cliente.post(f"{MIGRACAO}/executar", json={"modo": "novidades"}, headers=admin)
    resumo = cliente.get(MIGRACAO, headers=admin).json()["andamento"]["resumo"]
    assert (resumo["novos"], resumo["atualizados"], resumo["sem_mudanca"]) == (0, 0, 3)

    # Mudou no GLPI: só esse é regravado, e o acompanhamento mantém o id (os anexos continuam apontando para ele)
    ticket = next(t for t in fonte["dados"]["glpi_tickets"] if t["id"] == 1500)
    ticket["name"], ticket["date_mod"] = "Impressora trocada", "2099-01-01 10:00:00"
    cliente.post(f"{MIGRACAO}/executar", json={"modo": "novidades"}, headers=admin)
    resumo = cliente.get(MIGRACAO, headers=admin).json()["andamento"]["resumo"]
    assert (resumo["novos"], resumo["atualizados"]) == (0, 1)
    with FabricaSessao() as sessao:
        assert sessao.scalar(select(Chamado.titulo).where(Chamado.numero == 1500)) == "Impressora trocada"
        assert sessao.scalar(select(AcompanhamentoChamado.id).where(AcompanhamentoChamado.origem_glpi_id == 41)) == id_acompanhamento
        assert sessao.scalar(select(func.count()).select_from(AcompanhamentoChamado).where(AcompanhamentoChamado.origem_glpi_id == 41)) == 1

    # Trabalhado no SGI (assumido): mesmo mudando no GLPI, a migração não sobrescreve mais
    versao = cliente.get(f"{BASE}/1501", headers=admin).json()["versao"]
    assert cliente.post(f"{BASE}/1501/assumir", json={"versao": versao}, headers=admin).status_code == 200
    aberto = next(t for t in fonte["dados"]["glpi_tickets"] if t["id"] == 1501)
    aberto["name"], aberto["date_mod"] = "Mudou no GLPI depois", "2099-01-02 10:00:00"
    cliente.post(f"{MIGRACAO}/executar", json={"modo": "novidades"}, headers=admin)
    assert cliente.get(MIGRACAO, headers=admin).json()["andamento"]["resumo"]["trabalhados_sgi"] == 1
    with FabricaSessao() as sessao:
        assert sessao.scalar(select(Chamado.titulo).where(Chamado.numero == 1501)) != "Mudou no GLPI depois"

    # Refazer do zero: apaga TODOS os chamados (inclusive os abertos no SGI) e traz o GLPI de novo
    from tests.test_chamados import _abrir
    proprio = _abrir(cliente, c["cab"]["solicitante"], c["ids"]["categoria"], titulo="Aberto no SGI").json()["numero"]
    cliente.post(f"{MIGRACAO}/executar", json={"modo": "refazer"}, headers=admin)
    resumo = cliente.get(MIGRACAO, headers=admin).json()["andamento"]["resumo"]
    assert resumo["novos"] == 3
    with FabricaSessao() as sessao:
        assert sessao.scalar(select(func.count()).select_from(Chamado)) == 3
        assert sessao.scalar(select(Chamado).where(Chamado.numero == proprio, Chamado.importado.is_(False))) is None

    # Desativada: nem testa nem executa
    cliente.put(MIGRACAO, json={"ativa": False, "host": "10.23.1.242", "usuario": "sgi_leitura", "setor_padrao_id": c["ids"]["setor_ti"]}, headers=admin)
    assert cliente.post(f"{MIGRACAO}/executar", json={"modo": "novidades"}, headers=admin).json()["codigo"] == "desativada"
    assert cliente.post(f"{MIGRACAO}/testar", headers=admin).json()["codigo"] == "desativada"
    assert cliente.get(MIGRACAO, headers=admin).json()["senha_cadastrada"]  # a senha continua cadastrada


def test_erro_na_migracao_nao_grava_nada(cliente, admin, monkeypatch, tmp_path):
    c, _ = _ambiente(cliente, admin, monkeypatch, tmp_path)
    cliente.put(MIGRACAO, json={"host": "h", "usuario": "u", "senha": "s", "setor_padrao_id": c["ids"]["setor_ti"]}, headers=admin)

    def quebra(conexao, avisar=None):
        raise RuntimeError("conexão caiu no meio")

    monkeypatch.setattr(migracao_glpi, "ler_banco", quebra)
    cliente.post(f"{MIGRACAO}/executar", json={"modo": "novidades"}, headers=admin)
    andamento = cliente.get(MIGRACAO, headers=admin).json()["andamento"]
    assert andamento["situacao"] == "erro" and "nada foi gravado" in andamento["mensagem"]
    with FabricaSessao() as sessao:
        assert sessao.scalar(select(func.count()).select_from(Chamado)) == 0


def test_so_os_nao_solucionados(cliente, admin, monkeypatch, tmp_path):
    """Padrão: só o aberto (1501) vem; o resolvido (1500) e o excluído (1502) ficam no GLPI. O que já veio e foi resolvido lá é atualizado aqui."""
    c, fonte = _ambiente(cliente, admin, monkeypatch, tmp_path)
    cliente.put(MIGRACAO, json={"host": "h", "usuario": "u", "senha": "s", "setor_padrao_id": c["ids"]["setor_ti"]}, headers=admin)
    cliente.post(f"{MIGRACAO}/executar", json={"modo": "refazer"}, headers=admin)
    resumo = cliente.get(MIGRACAO, headers=admin).json()["andamento"]["resumo"]
    assert (resumo["novos"], resumo["resolvidos_nao_migrados"]) == (1, 2)
    with FabricaSessao() as sessao:
        assert list(sessao.scalars(select(Chamado.numero))) == [1501]
    # Resolveram no GLPI depois: o chamado (ninguém mexeu no SGI) fica resolvido aqui também, como histórico
    aberto = next(t for t in fonte["dados"]["glpi_tickets"] if t["id"] == 1501)
    aberto["status"], aberto["date_mod"], aberto["solvedate"] = 5, "2099-01-03 10:00:00", "2099-01-03 10:00:00"
    cliente.post(f"{MIGRACAO}/executar", json={"modo": "novidades"}, headers=admin)
    with FabricaSessao() as sessao:
        ch = sessao.scalar(select(Chamado).where(Chamado.numero == 1501))
        assert ch.status_base == "solucionado" and ch.importado

