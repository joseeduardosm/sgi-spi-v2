# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar o backup geral (banco + anexos): gerar, listar, baixar e importar, só pelo SuperRoot.
"""Backup geral. Os testes rodam em SQLite: as ferramentas do PostgreSQL (`pg_dump`/`pg_restore`), as migrações e o
reinício da API são trocados por versões que só registram o que foi pedido; a montagem do .zip, a conferência, o backup
automático antes de importar e a troca dos anexos são os de verdade."""

import io
import json
import zipfile

import pytest

from app.core.configuracao import obter_configuracao
from app.services import servico_backup
from tests.conftest import cabecalho, criar_usuario

URL = "/api/admin/backups"


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    config = obter_configuracao()
    anexos = tmp_path / "anexos"
    (anexos / "2026" / "10").mkdir(parents=True)
    (anexos / "2026" / "10" / "a.pdf").write_bytes(b"%PDF-original")
    monkeypatch.setattr(config, "anexos_diretorio", anexos)
    monkeypatch.setattr(config, "backups_diretorio", tmp_path / "backups")
    chamadas = {"restaurado": None, "migrou": False, "reiniciou": False}

    def restaurar(origem):
        chamadas["restaurado"] = origem.read_bytes()

    monkeypatch.setattr(servico_backup, "despejar_banco", lambda destino: destino.write_bytes(b"DUMP-ATUAL"))
    monkeypatch.setattr(servico_backup, "restaurar_banco", restaurar)
    monkeypatch.setattr(servico_backup, "migrar", lambda: chamadas.__setitem__("migrou", True))
    monkeypatch.setattr(servico_backup, "reiniciar_api", lambda: chamadas.__setitem__("reiniciou", True))
    monkeypatch.setattr(servico_backup, "em_segundo_plano", lambda funcao, *args: funcao(*args))
    monkeypatch.setattr(servico_backup, "_revisoes_conhecidas", lambda: {"abc123"})
    return anexos, chamadas


def _zip_de_outro_servidor(revisao="abc123", confere=True) -> bytes:
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w") as z:
        z.writestr("manifesto.json", json.dumps({"sistema": "SGI SPI" if confere else "Outro", "revisao_banco": revisao, "servidor": "prod"}))
        z.writestr("banco.dump", b"DUMP-DE-PRODUCAO")
        z.writestr("anexos/2025/01/b.pdf", b"%PDF-de-producao")
    return saida.getvalue()


def test_so_superroot(cliente, ambiente):
    criar_usuario("comum")
    h = cabecalho(cliente, "comum")
    assert cliente.get(URL, headers=h).status_code == 403
    assert cliente.post(URL, headers=h).status_code == 403


def test_gerar_listar_e_baixar(cliente, admin, ambiente):
    r = cliente.post(URL, headers=admin)
    assert r.status_code == 202, r.text
    painel = r.json()
    assert painel["andamento"]["situacao"] == "concluido" and len(painel["backups"]) == 1
    nome = painel["backups"][0]["nome"]
    arquivo = cliente.get(f"{URL}/arquivo/{nome}", headers=admin)
    assert arquivo.status_code == 200 and arquivo.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(arquivo.content)) as z:
        assert z.read("banco.dump") == b"DUMP-ATUAL" and z.read("anexos/2026/10/a.pdf") == b"%PDF-original"
        manifesto = json.loads(z.read("manifesto.json"))
    assert manifesto["sistema"] == "SGI SPI" and manifesto["anexos"] == 1
    # Nome fora da pasta não é servido
    assert cliente.get(f"{URL}/arquivo/..%2Fsegredo.zip", headers=admin).status_code == 404


def test_importar_substitui_e_guarda_o_estado_anterior(cliente, admin, ambiente):
    anexos, chamadas = ambiente
    envio = {"arquivo": ("backup.zip", _zip_de_outro_servidor(), "application/zip")}
    # Sem a confirmação digitada, nada acontece
    assert cliente.post(f"{URL}/importar", files=envio, data={"confirmacao": "sim"}, headers=admin).status_code == 400
    assert chamadas["restaurado"] is None

    r = cliente.post(f"{URL}/importar", files=envio, data={"confirmacao": "SUBSTITUIR"}, headers=admin)
    assert r.status_code == 202, r.text
    assert r.json()["servidor"] == "prod"
    # Banco restaurado, anexos trocados, migrações aplicadas e API reiniciada
    assert chamadas["restaurado"] == b"DUMP-DE-PRODUCAO" and chamadas["migrou"] and chamadas["reiniciou"]
    assert (anexos / "2025" / "01" / "b.pdf").read_bytes() == b"%PDF-de-producao" and not (anexos / "2026").exists()
    # O estado anterior ficou guardado num backup automático, com o anexo antigo
    painel = cliente.get(URL, headers=admin).json()
    assert painel["andamento"]["situacao"] == "reiniciando"
    anterior = next(b for b in painel["backups"] if b["antes_da_importacao"])
    with zipfile.ZipFile(obter_configuracao().backups_diretorio / anterior["nome"]) as z:
        assert z.read("anexos/2026/10/a.pdf") == b"%PDF-original"


def test_importar_recusa_arquivo_invalido_ou_de_versao_mais_nova(cliente, admin, ambiente):
    _, chamadas = ambiente
    for conteudo in (b"nao e zip", _zip_de_outro_servidor(confere=False), _zip_de_outro_servidor(revisao="versao-futura")):
        r = cliente.post(f"{URL}/importar", files={"arquivo": ("b.zip", conteudo, "application/zip")}, data={"confirmacao": "SUBSTITUIR"}, headers=admin)
        assert r.status_code == 400, r.text
    assert chamadas["restaurado"] is None


def test_link_temporario_baixa_sem_cabecalho_e_so_o_arquivo_dele(cliente, admin, ambiente):
    nome = cliente.post(URL, headers=admin).json()["backups"][0]["nome"]
    link = cliente.post(f"{URL}/arquivo/{nome}/link", headers=admin)
    assert link.status_code == 200, link.text
    url = link.json()["url"]
    # O navegador abre o link direto, sem o token de acesso
    r = cliente.get(url)
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip" and nome in r.headers["content-disposition"]
    chave = url.split("chave=")[1]
    # A chave não vale para outro arquivo, nem como token de acesso, nem adulterada
    assert cliente.get(f"{URL}/arquivo/outro.zip/baixar?chave={chave}").status_code == 404
    assert cliente.get(URL, headers={"Authorization": f"Bearer {chave}"}).status_code == 401
    assert cliente.get(f"{URL}/arquivo/{nome}/baixar?chave={chave}x").status_code == 404


def test_andamento_informa_etapa_e_percentual(cliente, admin, ambiente):
    andamento = cliente.post(URL, headers=admin).json()["andamento"]
    assert andamento["etapa"] == "finalizar" and andamento["percentual"] == 100
