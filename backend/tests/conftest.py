import os
import tempfile
import uuid

import bcrypt
import pytest
from cryptography.fernet import Fernet

# Configuração isolada: os testes não dependem do backend/.env real nem do PostgreSQL.
_diretorio_temporario = tempfile.mkdtemp(prefix="contratos-spi-testes-")
os.environ["URL_BANCO_DADOS"] = f"sqlite:///{_diretorio_temporario}/teste.db"
os.environ["CHAVE_SECRETA_JWT"] = "chave-de-teste-com-pelo-menos-32-caracteres"
os.environ["LOGIN_ADMIN"] = "root"
os.environ["HASH_SENHA_ADMIN"] = bcrypt.hashpw(b"senha-teste", bcrypt.gensalt(rounds=4)).decode()
os.environ["MINUTOS_EXPIRACAO_TOKEN"] = "60"
os.environ["CHAVE_CIFRA_LDAP"] = Fernet.generate_key().decode()
os.environ["INTERVALO_SINCRONIZACAO_LDAP_MINUTOS"] = "0"
os.environ["ANEXOS_DIRETORIO"] = f"{_diretorio_temporario}/anexos"

from fastapi.testclient import TestClient  # noqa: E402
from ldap3 import MOCK_SYNC, NONE, Connection, Server  # noqa: E402
from ldap3.core.exceptions import LDAPSocketOpenError  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.banco import Base, FabricaSessao, agora_utc, motor  # noqa: E402
from app.core.seguranca import gerar_hash_senha  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Usuario  # noqa: E402
from app.services import cliente_ldap  # noqa: E402

BASE_DN = "dc=spi,dc=local"
DN_CONTA_TECNICA = "cn=svc,ou=servicos,dc=spi,dc=local"
SENHA_CONTA_TECNICA = "svc-senha"

PERFIL_COMPLETO = {
    "nome_completo": "Pessoa Teste",
    "email": "pessoa@spi.local",
    "ramal": "1234",
    "cargo": "Analista",
    "departamento": "Contratos",
    "andar": "5",
    "predio": "Sede",
}


class AdSimulado:
    """Active Directory simulado (ldap3 MOCK_SYNC). servidor='fora-do-ar' simula servidor indisponível."""

    def __init__(self) -> None:
        self.servidor = Server("ad-simulado", get_info=NONE)
        self._conexao = Connection(self.servidor, client_strategy=MOCK_SYNC)
        self._conexao.strategy.add_entry(BASE_DN, {"objectClass": ["top", "domain"], "dc": "spi"})
        self._conexao.strategy.add_entry(
            DN_CONTA_TECNICA, {"objectClass": ["top", "person"], "userPassword": SENHA_CONTA_TECNICA, "cn": "svc"}
        )

    def adicionar_usuario(
        self, login: str, senha: str, nome: str, email: str = "", desativado: bool = False, guid: uuid.UUID | None = None
    ) -> uuid.UUID:
        guid = guid or uuid.uuid4()
        self._conexao.strategy.add_entry(
            f"cn={nome},ou=pessoas,{BASE_DN}",
            {
                "objectClass": ["top", "person", "user"],
                "objectCategory": "person",
                "sAMAccountName": login,
                "userPrincipalName": f"{login}@spi.local",
                "displayName": nome,
                "mail": email,
                "userAccountControl": "514" if desativado else "512",
                "objectGUID": guid.bytes_le,
                "userPassword": senha,
            },
        )
        return guid

    def remover_usuario(self, nome: str) -> None:
        self._conexao.strategy.remove_entry(f"cn={nome},ou=pessoas,{BASE_DN}")

    def fabrica(self, parametros, usuario, senha):
        if parametros.servidor == "fora-do-ar":
            raise LDAPSocketOpenError("servidor fora do ar")
        return Connection(self.servidor, user=usuario, password=senha, client_strategy=MOCK_SYNC, raise_exceptions=False)


@pytest.fixture(autouse=True)
def _banco():
    # Recria o banco a cada teste; a verificação de chaves estrangeiras fica desligada só durante a remoção
    with motor.connect() as conexao:
        conexao.exec_driver_sql("PRAGMA foreign_keys=OFF")
        Base.metadata.drop_all(conexao)
        conexao.exec_driver_sql("PRAGMA foreign_keys=ON")
        conexao.commit()
    Base.metadata.create_all(motor)
    yield


@pytest.fixture
def ad(monkeypatch) -> AdSimulado:
    simulado = AdSimulado()
    monkeypatch.setattr(cliente_ldap, "fabrica_conexao", simulado.fabrica)
    return simulado


@pytest.fixture
def cliente() -> TestClient:
    with TestClient(app) as c:  # executa o ciclo de vida (cria a conta root)
        yield c


def entrar(cliente: TestClient, login: str, senha: str) -> str:
    r = cliente.post("/api/autenticacao/login", json={"login": login, "senha": senha})
    assert r.status_code == 200, r.text
    return r.json()["token_acesso"]


def cabecalho(cliente: TestClient, login: str, senha: str = "senha-local-1") -> dict[str, str]:
    return {"Authorization": f"Bearer {entrar(cliente, login, senha)}"}


@pytest.fixture
def token(cliente: TestClient) -> str:
    return entrar(cliente, "root", "senha-teste")


@pytest.fixture
def admin(token: str) -> dict[str, str]:
    """Cabeçalho de autorização do root (SuperRoot)."""
    return {"Authorization": f"Bearer {token}"}


def dados_diretorio(**alteracoes) -> dict:
    dados = {
        "nome": "AD01",
        "servidor": "ad-simulado",
        "porta": 389,
        "usar_ssl": False,
        "base_dn": BASE_DN,
        "bind_dn": DN_CONTA_TECNICA,
        "senha_bind": SENHA_CONTA_TECNICA,
        "ativo": True,
    }
    dados.update(alteracoes)
    return dados


def criar_usuario(login: str, senha: str = "senha-local-1", superusuario: bool = False, completo: bool = True, **perfil) -> int:
    """Cria usuário local direto no banco. `completo` preenche e revalida o perfil."""
    campos = {**(PERFIL_COMPLETO if completo else {}), **perfil}
    with FabricaSessao() as sessao:
        usuario = Usuario(login=login, hash_senha=gerar_hash_senha(senha), superusuario=superusuario, **campos)
        if completo:
            usuario.perfil_revisado_em = agora_utc()
        sessao.add(usuario)
        sessao.commit()
        return usuario.id
