# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a importação dos dados do SGI SPI.
"""Importação do SGI: rascunho de um contrato (conta root) e a importação completa (SuperRoot, senhas conferidas antes, uma execução por vez)."""

import json
import os

import pytest
from sqlalchemy import func, select

from app.core.banco import FabricaSessao
from app.models.contratos import Contrato, EmpresaContratada
from app.services.contratos import servico_migracao_sgi as servico
from tests.conftest import cabecalho, criar_usuario

# Endereço da rota e senhas fictícias usadas nos testes
URL = "/api/contratos/migracao-sgi"
SENHAS = {"senha_origem": "S3nh@-Orig-7f2", "senha_destino": "S3nh@-Dest-9k1"}


@pytest.fixture(autouse=True)
def _isolar(monkeypatch, tmp_path):
    """Isola cada teste: pasta de estado temporária e `subprocess.Popen` falso (nenhum processo real roda).

    Devolve a lista de processos "iniciados", para os testes conferirem comando e ambiente.
    """
    monkeypatch.setattr(servico, "_diretorio", lambda: tmp_path)
    iniciados = []

    class ProcessoFalso:
        """Substituto do Popen: só anota o comando e o ambiente recebidos."""
        pid = os.getpid()  # processo vivo: o estado continua "executando"

        def __init__(self, comando, **opcoes):
            iniciados.append((comando, opcoes["env"]))

    monkeypatch.setattr(servico.subprocess, "Popen", ProcessoFalso)
    return iniciados


def test_somente_superroot(cliente, admin):
    """Usuário comum recebe 403; o SuperRoot vê o estado inicial "ociosa"."""
    criar_usuario("comum")
    comum = cabecalho(cliente, "comum")
    assert cliente.get(URL, headers=comum).status_code == 403
    assert cliente.post(URL, json=SENHAS, headers=comum).status_code == 403
    estado = cliente.get(URL, headers=admin).json()
    assert estado["situacao"] == "ociosa" and estado["origem"].endswith("10.23.1.220")


def test_senha_incorreta_nao_inicia(cliente, admin, monkeypatch, _isolar):
    """Senha recusada responde 400 e nenhum processo é iniciado."""
    def recusar(*_):
        raise servico.ErroMigracao("Senha incorreta para administrador@10.23.1.220 (origem).", "senha_invalida")

    monkeypatch.setattr(servico, "validar_senhas", recusar)
    r = cliente.post(URL, json=SENHAS, headers=admin)
    assert r.status_code == 400 and r.json()["codigo"] == "senha_invalida"
    assert not _isolar and cliente.get(URL, headers=admin).json()["situacao"] == "ociosa"


def test_inicia_em_segundo_plano_e_bloqueia_outra(cliente, admin, monkeypatch, _isolar):
    """Com senhas válidas, inicia (202), passa a senha só pelo ambiente e recusa uma segunda execução (409)."""
    monkeypatch.setattr(servico, "validar_senhas", lambda *_: None)
    r = cliente.post(URL, json=SENHAS, headers=admin)
    assert r.status_code == 202 and r.json()["situacao"] == "executando"
    comando, ambiente = _isolar[0]
    assert comando[-2:] == ["1", "root"] and ambiente["SGI_SENHA"] == "S3nh@-Orig-7f2"
    # A senha não fica no estado nem no registro
    gravado = servico._arquivo_estado().read_text() + servico._arquivo_log().read_text()
    assert "S3nh@" not in gravado
    r = cliente.post(URL, json=SENHAS, headers=admin)
    assert r.status_code == 409 and r.json()["codigo"] == "conflito"


def test_execucao_interrompida_vira_erro(cliente, admin):
    """Estado "executando" com processo morto é mostrado como erro de interrupção."""
    servico._gravar_estado(situacao="executando", etapa="extraindo", pid=999999999)
    estado = cliente.get(URL, headers=admin).json()
    assert estado["situacao"] == "erro" and "interrompida" in estado["mensagem"]


# --- Rascunho de um contrato (botão "Importar do SGI" da conta root) ----------------------------

class _CanalFalso:
    def __init__(self, status: int = 0):
        self.status = status

    def shutdown_write(self):
        pass

    def recv_exit_status(self):
        return self.status


class _Fluxo:
    def __init__(self, texto: str = "", status: int = 0):
        self.texto, self.channel = texto, _CanalFalso(status)

    def write(self, _):
        pass

    def read(self):
        return self.texto.encode()


class _SgiFalso:
    """Responde à consulta do contrato (psql) e à leitura dos usuários (python3) como o SGI."""

    def __init__(self, contrato: dict | None):
        self.contrato, self.comandos = contrato, []

    def exec_command(self, comando, timeout=None):
        self.comandos.append(comando)
        if comando.startswith("sudo"):
            saida = "" if self.contrato is None else json.dumps(self.contrato, indent=1)  # json_agg quebra linhas
            return _Fluxo(), _Fluxo(saida), _Fluxo()
        return _Fluxo(), _Fluxo(json.dumps({"7": {"login": "Ana.Gestora", "externo": "", "nome": "Ana Gestora"},
                                             "8": {"login": "sem.conta", "externo": "", "nome": "Sem Conta"}})), _Fluxo()

    def close(self):
        pass


def _contrato_sgi() -> dict:
    return {
        "contrato": {"Sequence": 10, "Year": 2024, "Nickname": "Suporte", "Object": "Outsourcing de TIC", "StartDate": "2024-08-05",
                     "InitialTermMonths": 12, "MaximumTermMonths": 60, "ExecutionPeriodicity": "Monthly", "AdjustmentMonth": 1,
                     "ManagementSeiNumber": "021.1/2024", "ManagementSeiUrl": "https://sei.sp.gov.br/g", "ExecutionSeiNumber": "021.2/2024",
                     "ExecutionSeiUrl": "https://sei.sp.gov.br/e"},
        "empresa": {"Cnpj": "62.577.929/0001-35", "CorporateName": "PRODESP", "TradeName": "Prodesp", "Address": "Taboão da Serra"},
        "prepostos": [{"Cpf": "123.456.789-09", "Name": "Pedro Preposto", "Phone": "", "Email": "pedro@prodesp.sp.gov.br", "JobTitle": ""}],
        "itens": [{"Description": "Administrador de rede", "Type": "Continuous", "CalculatesProRata": True, "ClassCode": "1", "ExpenseNatureCode": "2",
                   "SiafisicoCode": "3", "CatmatCatserCode": "4", "MonthlyQuantity": 336.0, "TotalQuantity": 4032.0, "UnitPrice": 171.22}],
        "equipe": [{"UserId": 7, "Role": "Manager", "UserDisplayName": "Ana Gestora"}, {"UserId": 8, "Role": "TechnicalInspector", "UserDisplayName": "Sem Conta"}],
        "prorrogacoes": 1, "competencias": 3, "notas_empenho": 0,
    }


def test_rascunho_so_para_a_conta_root_e_nada_e_gravado(cliente, admin, monkeypatch):
    url = f"{URL}/rascunho"
    ana = criar_usuario("ana.gestora", nome_completo="Ana Gestora")
    criar_usuario("outro.super", superusuario=True)
    sgi = _SgiFalso(_contrato_sgi())
    monkeypatch.setattr(servico, "_conectar", lambda *_: sgi)
    corpo = {"numero": "10/2024", "senha_origem": "S3nh@"}
    # SuperRoot que não é a conta root: 403
    assert cliente.post(url, json=corpo, headers=cabecalho(cliente, "outro.super")).status_code == 403
    assert cliente.post(url, json={**corpo, "numero": "abc"}, headers=admin).status_code == 422

    r = cliente.post(url, json=corpo, headers=admin)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["numero"] == "010/2024" and d["periodicidade_meses"] == 1 and d["data_inicio"] == "2024-08-05"
    assert d["empresa"]["id"] is None and d["empresa"]["cnpj"] == "62577929000135" and d["prepostos"][0]["cpf"] == "12345678909"
    assert d["equipe"] == [{"papel": "gestor", "usuario_id": ana, "login": "ana.gestora", "nome": "Ana Gestora"}]
    assert d["itens"][0]["quantidade_mensal"] == "336" and d["itens"][0]["valor_unitario"] == "171.22"
    avisos = " ".join(d["avisos"])
    assert "Sem Conta" in avisos and "prorrogação" in avisos and "3 competência" in avisos and "não está cadastrada" in avisos
    # Nada gravado aqui (a consulta no SGI roda numa transação `read only`)
    assert "read only" in servico.CONSULTA_RASCUNHO
    with FabricaSessao() as s:
        assert s.scalar(select(func.count()).select_from(Contrato)) == 0 and s.scalar(select(func.count()).select_from(EmpresaContratada)) == 0

    # Contrato inexistente no SGI → 404
    monkeypatch.setattr(servico, "_conectar", lambda *_: _SgiFalso(None))
    assert cliente.post(url, json=corpo, headers=admin).status_code == 404
