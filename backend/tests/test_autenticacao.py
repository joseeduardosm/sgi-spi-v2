# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar login, sessão, perfil e a documentação OpenAPI.

from datetime import UTC, datetime, timedelta

import jwt

from app.core.configuracao import obter_configuracao


def test_login_valido(cliente):
    r = cliente.post("/api/autenticacao/login", json={"login": "root", "senha": "senha-teste"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["tipo_token"] == "bearer"
    assert corpo["expira_em_segundos"] == 3600
    assert corpo["usuario"]["login"] == "root"
    assert corpo["usuario"]["papeis"] == ["SuperRoot"]
    assert corpo["usuario"]["origem"] == "local"
    conteudo = jwt.decode(corpo["token_acesso"], options={"verify_signature": False})
    assert conteudo["sub"] == str(corpo["usuario"]["id"]) and conteudo["tipo"] == "acesso"


def test_login_senha_errada(cliente):
    r = cliente.post("/api/autenticacao/login", json={"login": "root", "senha": "errada"})
    assert r.status_code == 401
    assert r.json() == {"detalhe": "Usuário ou senha inválidos.", "codigo": "nao_autenticado"}


def test_login_usuario_inexistente(cliente):
    r = cliente.post("/api/autenticacao/login", json={"login": "fulano", "senha": "senha-teste"})
    assert r.status_code == 401


def test_login_campos_ausentes_em_portugues(cliente):
    r = cliente.post("/api/autenticacao/login", json={"login": "root"})
    assert r.status_code == 422
    corpo = r.json()
    assert corpo["codigo"] == "validacao"
    assert corpo["erros"] == [{"campo": "senha", "mensagem": "campo obrigatório"}]


def test_sessao_com_token(cliente, admin):
    r = cliente.get("/api/autenticacao/sessao", headers=admin)
    assert r.status_code == 200
    assert r.json()["login"] == "root"


def test_sessao_sem_token(cliente):
    r = cliente.get("/api/autenticacao/sessao")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"
    assert r.json()["codigo"] == "nao_autenticado"


def test_sessao_token_invalido(cliente):
    r = cliente.get("/api/autenticacao/sessao", headers={"Authorization": "Bearer abc.def.ghi"})
    assert r.status_code == 401
    assert r.json()["detalhe"] == "Token inválido."


def test_sessao_token_expirado(cliente):
    config = obter_configuracao()
    passado = datetime.now(UTC) - timedelta(hours=2)
    expirado = jwt.encode(
        {"sub": "1", "iat": passado, "exp": passado + timedelta(minutes=1), "tipo": "acesso"},
        config.chave_secreta_jwt.get_secret_value(),
        algorithm=config.algoritmo_jwt,
    )
    r = cliente.get("/api/autenticacao/sessao", headers={"Authorization": f"Bearer {expirado}"})
    assert r.status_code == 401
    assert r.json()["detalhe"] == "Sessão expirada."


def test_rota_inexistente_em_portugues(cliente):
    r = cliente.get("/api/nao-existe")
    assert r.status_code == 404 and r.json()["codigo"] == "nao_encontrado"


def test_saude(cliente):
    r = cliente.get("/api/saude")
    assert r.status_code == 200
    assert r.json()["situacao"] == "ok"


# Módulo de contratos (docs/endpoints/contratos-*.md)
CAMINHOS_CONTRATOS = {
    "/api/contratos/empresas",
    "/api/contratos/empresas/opcoes",
    "/api/contratos/empresas/{empresa_id}",
    "/api/contratos/empresas/{empresa_id}/prepostos",
    "/api/contratos/empresas/{empresa_id}/prepostos/{preposto_id}",
    "/api/contratos/modelos",
    "/api/contratos/migracao-sgi",
    "/api/contratos/modelos/{modelo_id}",
    "/api/contratos/relatorios/notas-empenho",
    "/api/contratos/relatorios/previsao-orcamentaria",
    "/api/contratos/painel",
    "/api/contratos",
    "/api/contratos/proximo-numero",
    "/api/contratos/opcoes-usuarios",
    "/api/contratos/{contrato_id}",
    "/api/contratos/{contrato_id}/historico",
    "/api/contratos/{contrato_id}/documentos",
    "/api/contratos/{contrato_id}/documentos/{codigo}",
    "/api/contratos/{contrato_id}/documentos/{codigo}/arquivo",
    "/api/contratos/{contrato_id}/previsao",
    "/api/contratos/{contrato_id}/previsao/{sequencia_vigencia}",
    "/api/contratos/{contrato_id}/previsao/{sequencia_vigencia}/xlsx",
    "/api/contratos/{contrato_id}/notas-empenho",
    "/api/contratos/{contrato_id}/notas-empenho/{nota_id}",
    "/api/contratos/{contrato_id}/checklists",
    "/api/contratos/{contrato_id}/checklists/{checklist_id}",
    "/api/contratos/{contrato_id}/checklists/{checklist_id}/duplicar",
    "/api/contratos/{contrato_id}/checklists/{checklist_id}/ativar",
    "/api/contratos/{contrato_id}/formularios",
    "/api/contratos/{contrato_id}/formularios/{formulario_id}",
    "/api/contratos/{contrato_id}/formularios/{formulario_id}/duplicar",
    "/api/contratos/{contrato_id}/formularios/{formulario_id}/ativar",
    "/api/contratos/{contrato_id}/execucao",
    "/api/contratos/{contrato_id}/execucao/gerar",
    "/api/contratos/{contrato_id}/competencias/identificador/{identificador}",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/arquivos/{anexo_id}",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/medicao",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/medicao/ciencia",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/medicao/concluir",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/avaliacao/inicial",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/avaliacao/gestor",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/avaliacao/assinaturas",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/avaliacao/ciencia",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/avaliacao/pdf",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/avaliacao/assinada",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/avaliacao/reconsideracao",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/nota-fiscal",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/cadin",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/checklist/concluir",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/checklist/{documento_id}",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/consolidado",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/ordem-bancaria",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/reabrir",
    "/api/contratos/{contrato_id}/prorrogacao",
    "/api/contratos/{contrato_id}/prorrogacao/ciencia",
    "/api/contratos/{contrato_id}/prorrogacao/parecer",
    "/api/contratos/{contrato_id}/prorrogacao/registrar",
    "/api/contratos/{contrato_id}/prorrogacoes",
    "/api/contratos/{contrato_id}/prorrogacoes/arquivos/{anexo_id}",
    "/api/contratos/{contrato_id}/prorrogacoes/{prorrogacao_id}",
    "/api/contratos/{contrato_id}/reajustes",
    "/api/contratos/{contrato_id}/reajustes/{reajuste_id}/evidencia",
    "/api/contratos/{contrato_id}/reajustes/{reajuste_id}/memoria",
    "/api/contratos/{contrato_id}/reajustes/{reajuste_id}/memoria/arquivos",
    "/api/contratos/{contrato_id}/reajustes/{reajuste_id}/concluir",
    "/api/contratos/{contrato_id}/reajustes/{reajuste_id}/cancelar",
    "/api/contratos/{contrato_id}/reajustes/{reajuste_id}/arquivos/{anexo_id}",
    "/api/contratos/{contrato_id}/alteracoes",
    "/api/contratos/{contrato_id}/alteracoes/{alteracao_id}/documentos/{tipo}",
    "/api/contratos/{contrato_id}/alteracoes/{alteracao_id}/quantitativos",
    "/api/contratos/{contrato_id}/alteracoes/{alteracao_id}/ciencia",
    "/api/contratos/{contrato_id}/alteracoes/{alteracao_id}/memoria",
    "/api/contratos/{contrato_id}/alteracoes/{alteracao_id}/consolidado",
    "/api/contratos/{contrato_id}/alteracoes/{alteracao_id}/concluir",
    "/api/contratos/{contrato_id}/alteracoes/{alteracao_id}/cancelar",
    "/api/contratos/{contrato_id}/alteracoes/{alteracao_id}/arquivos/{anexo_id}",
}


def test_openapi_documenta_endpoints(cliente):
    """Falha quando endpoints mudam: atualize docs/ e esta lista na mesma alteração."""
    especificacao = cliente.get("/api/openapi.json").json()
    assert set(especificacao["paths"]) == {
        "/api/saude",
        "/api/autenticacao/login",
        "/api/autenticacao/sessao",
        "/api/autenticacao/perfil",
        "/api/autenticacao/perfil/opcoes-gestor",
        "/api/usuarios",
        "/api/usuarios/opcoes",
        "/api/usuarios/{usuario_id}",
        "/api/setores",
        "/api/setores/{setor_id}",
        "/api/acl/meus-acessos",
        "/api/acl/efetivo/{usuario_id}",
        "/api/acl/recursos",
        "/api/acl/recursos/{recurso_id}",
        "/api/acl/regras",
        "/api/acl/regras/{regra_id}",
        "/api/ldap/diretorios",
        "/api/ldap/diretorios/testar",
        "/api/ldap/diretorios/{diretorio_id}",
        "/api/ldap/diretorios/{diretorio_id}/testar",
        "/api/ldap/diretorios/{diretorio_id}/sincronizar",
        "/api/ldap/diretorios/{diretorio_id}/diagnosticar",
        *CAMINHOS_CONTRATOS,
    }
    login = especificacao["paths"]["/api/autenticacao/login"]["post"]["responses"]
    assert "401" in login and "422" in login
    assert especificacao["paths"]["/api/autenticacao/sessao"]["get"]["security"] == [{"TokenBearer": []}]
    esquemas = especificacao["components"]["schemas"]
    assert "HTTPValidationError" not in esquemas and "RespostaErroValidacao" in esquemas
