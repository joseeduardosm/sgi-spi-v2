# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar login, sessão, perfil e a documentação OpenAPI.
"""Testes de login, sessão (token JWT) e da documentação OpenAPI da API."""

from datetime import UTC, datetime, timedelta

import jwt

from app.core.banco import FabricaSessao
from app.core.configuracao import obter_configuracao
from app.models import Usuario
from tests.conftest import criar_usuario


def test_login_valido(cliente):
    """Login correto devolve o token e os dados do usuário; o token traz o id no campo `sub`."""
    r = cliente.post("/api/autenticacao/login", json={"login": "root", "senha": "senha-teste"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["tipo_token"] == "bearer"
    assert corpo["expira_em_segundos"] == 3600
    assert corpo["usuario"]["login"] == "root"
    assert corpo["usuario"]["papeis"] == ["SuperRoot"]
    assert corpo["usuario"]["origem"] == "local"
    # Lê o conteúdo do token sem conferir a assinatura (só para inspecionar)
    conteudo = jwt.decode(corpo["token_acesso"], options={"verify_signature": False})
    assert conteudo["sub"] == str(corpo["usuario"]["id"]) and conteudo["tipo"] == "acesso"


def test_login_senha_errada(cliente):
    """Senha errada responde 401 com a mensagem padrão."""
    r = cliente.post("/api/autenticacao/login", json={"login": "root", "senha": "errada"})
    assert r.status_code == 401
    assert r.json() == {"detalhe": "Usuário ou senha inválidos.", "codigo": "nao_autenticado"}


def test_login_usuario_inexistente(cliente):
    """Login inexistente também responde 401 (sem revelar que o usuário não existe)."""
    r = cliente.post("/api/autenticacao/login", json={"login": "fulano", "senha": "senha-teste"})
    assert r.status_code == 401


def test_login_campos_ausentes_em_portugues(cliente):
    """Campo faltando responde 422 com a mensagem em português."""
    r = cliente.post("/api/autenticacao/login", json={"login": "root"})
    assert r.status_code == 422
    corpo = r.json()
    assert corpo["codigo"] == "validacao"
    assert corpo["erros"] == [{"campo": "senha", "mensagem": "campo obrigatório"}]


def test_sessao_com_token(cliente, admin):
    """Token válido dá acesso à sessão."""
    r = cliente.get("/api/autenticacao/sessao", headers=admin)
    assert r.status_code == 200
    assert r.json()["login"] == "root"


def test_sessao_sem_token(cliente):
    """Sem token: 401 com o cabeçalho `WWW-Authenticate: Bearer`."""
    r = cliente.get("/api/autenticacao/sessao")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"
    assert r.json()["codigo"] == "nao_autenticado"


def test_sessao_token_invalido(cliente):
    """Token mal formado: 401 "Token inválido."."""
    r = cliente.get("/api/autenticacao/sessao", headers={"Authorization": "Bearer abc.def.ghi"})
    assert r.status_code == 401
    assert r.json()["detalhe"] == "Token inválido."


def test_sessao_token_expirado(cliente):
    """Token vencido: 401 "Sessão expirada."."""
    # Gera um token que expirou há quase 2 horas, com a mesma chave da API
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
    """Rota inexistente responde 404 no formato padrão da API."""
    r = cliente.get("/api/nao-existe")
    assert r.status_code == 404 and r.json()["codigo"] == "nao_encontrado"


def test_saude(cliente):
    """A rota de saúde responde "ok"."""
    r = cliente.get("/api/saude")
    assert r.status_code == 200
    assert r.json()["situacao"] == "ok"


# Caminhos do módulo de contratos que devem aparecer na OpenAPI (documentados em docs/endpoints/contratos-*.md).
# Ao criar, alterar ou remover uma rota, atualize esta lista e a documentação na mesma alteração.
CAMINHOS_CONTRATOS = {
    "/api/contratos/empresas",
    "/api/contratos/empresas/opcoes",
    "/api/contratos/empresas/{empresa_id}",
    "/api/contratos/empresas/{empresa_id}/prepostos",
    "/api/contratos/empresas/{empresa_id}/prepostos/{preposto_id}",
    "/api/contratos/modelos",
    "/api/contratos/migracao-sgi",
    "/api/contratos/migracao-sgi/rascunho",
    "/api/contratos/importacao-xlsx",
    "/api/contratos/importacao-xlsx/previa",
    "/api/contratos/importacao-xlsx/modelo",
    "/api/contratos/{contrato_id}/{recurso}/importacao-xlsx/modelo",
    "/api/contratos/{contrato_id}/{recurso}/importacao-xlsx/previa",
    "/api/contratos/{contrato_id}/checklists/importacao-xlsx",
    "/api/contratos/{contrato_id}/formularios/importacao-xlsx",
    "/api/contratos/modelos/importacao-xlsx/{tipo}/modelo",
    "/api/contratos/modelos/importacao-xlsx/{tipo}/previa",
    "/api/contratos/modelos/importacao-xlsx/{tipo}",
    "/api/contratos/{contrato_id}/exportacao-xlsx",
    "/api/contratos/{contrato_id}/checklists/{checklist_id}/xlsx",
    "/api/contratos/{contrato_id}/formularios/{formulario_id}/xlsx",
    "/api/contratos/{contrato_id}/diario",
    "/api/contratos/{contrato_id}/diario/pdf",
    "/api/contratos/{contrato_id}/diario/{ocorrencia_id}/reenviar",
    "/api/contratos/{contrato_id}/diario/{ocorrencia_id}/anexos/{anexo_id}",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/reenviar-email-medicao",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/reenviar-email-avaliacao",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/reenviar-email-nf",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/retencao",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/retencao/recusar",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/recusas/{recusa_id}/reenviar-email",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/reenviar-email-retencao",
    "/api/contratos/modelos/{modelo_id}",
    "/api/contratos/relatorios/notas-empenho",
    "/api/contratos/relatorios/previsao-orcamentaria",
    "/api/contratos/painel",
    "/api/contratos/painel/vigencias",
    "/api/contratos/calendario",
    "/api/sla/politicas",
    "/api/contratos/verificar-documento",
    "/api/contratos",
    "/api/contratos/proximo-numero",
    "/api/contratos/opcoes-usuarios",
    "/api/contratos/{contrato_id}",
    "/api/contratos/{contrato_id}/itens/pdf",
    "/api/contratos/{contrato_id}/historico",
    "/api/contratos/{contrato_id}/vizinhos",
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
    "/api/contratos/{contrato_id}/checklists/{checklist_id}/itens/{item_id}/pedir-envio",
    "/api/contratos/{contrato_id}/formularios",
    "/api/contratos/{contrato_id}/formularios/{formulario_id}",
    "/api/contratos/{contrato_id}/formularios/{formulario_id}/duplicar",
    "/api/contratos/{contrato_id}/formularios/{formulario_id}/ativar",
    "/api/contratos/{contrato_id}/execucao",
    "/api/contratos/{contrato_id}/execucao/gerar",
    "/api/contratos/{contrato_id}/competencias/identificador/{identificador}",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/arquivos/{anexo_id}",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/adicional",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/medicao",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/medicao/ciencia",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/medicao/concluir",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/avaliacao/inicial",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/avaliacao/gestor",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/avaliacao/ciencia",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/avaliacao/pdf",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/avaliacao/assinada",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/avaliacao/reconsideracao",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/nota-fiscal",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/cadin",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/checklist/concluir",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/checklist/reaproveitar-todos",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/checklist/{documento_id}/reaproveitar",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/checklist/{documento_id}",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/consolidado",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/ordem-bancaria",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/zerar",
    "/api/contratos/{contrato_id}/competencias/{competencia_id}/reabrir",
    "/api/contratos/{contrato_id}/prorrogacao",
    "/api/contratos/{contrato_id}/prorrogacao/ciencia",
    "/api/contratos/{contrato_id}/portarias",
    "/api/contratos/{contrato_id}/portarias/{portaria_id}/reenviar",
    "/api/contratos/{contrato_id}/portarias/{portaria_id}/aceite",
    "/api/contratos/{contrato_id}/portarias/{portaria_id}/devolucao",
    "/api/contratos/{contrato_id}/portarias/{portaria_id}/cancelamento",
    "/api/contratos/{contrato_id}/portarias/{portaria_id}/minuta",
    "/api/contratos/{contrato_id}/portarias/{portaria_id}/publicacao",
    "/api/portarias/autoridades",
    "/api/tarefas/{numero}/memorial",
    "/api/contratos/modelos/portaria/placeholders",
    "/api/portarias/autoridades/{autoridade_id}",
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
    "/api/contratos/{contrato_id}/itens/correcoes",
    "/api/contratos/{contrato_id}/itens/correcoes/previa",
    "/api/contratos/{contrato_id}/itens/correcoes/{correcao_id}/confirmar",
    "/api/contratos/{contrato_id}/itens/correcoes/{correcao_id}/recusar",
    "/api/contratos/{contrato_id}/itens/correcoes/{correcao_id}/cancelar",
    "/api/contratos/{contrato_id}/itens/historico",
    "/api/contratos/{contrato_id}/prepostos",
    "/api/contratos/{contrato_id}/financeiro",
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


def test_openapi_documenta_endpoints(cliente, admin):
    """Falha quando endpoints mudam: atualize docs/ e esta lista na mesma alteração."""
    # A lista de caminhos precisa bater exatamente com a especificação gerada (a especificação exige login e a ACL `documentacao-api`)
    especificacao = cliente.get("/api/openapi.json", headers=admin).json()
    assert set(especificacao["paths"]) == {
        "/api/saude",
        "/api/reserva-espacos/contexto",
        "/api/reserva-espacos/agenda",
        "/api/reserva-espacos/disponibilidade",
        "/api/reserva-espacos/minhas",
        "/api/reserva-espacos/reservas",
        "/api/reserva-espacos/exportar",
        "/api/reserva-espacos/fila",
        "/api/reserva-espacos/reservas/{reserva_id}",
        "/api/reserva-espacos/reservas/predefinida",
        "/api/reserva-espacos/reservas/{reserva_id}/analise",
        "/api/reserva-espacos/reservas/{reserva_id}/cancelamento",
        "/api/reserva-espacos/usuarios",
        "/api/reserva-espacos/espacos",
        "/api/reserva-espacos/espacos/{espaco_id}",
        "/api/reserva-espacos/painel",
        "/api/reserva-espacos/configuracao",
        "/api/painel-executivo/acesso",
        "/api/painel-executivo/contratos",
        "/api/painel-executivo/rh",
        "/api/painel-executivo/tarefas",
        "/api/painel-executivo/{slide}/pdf",
        "/api/diretorio/ramais",
        "/api/diretorio/filtros",
        "/api/diretorio/ramais/{contato_id}",
        "/api/diretorio/ramais/{contato_id}/vcard",
        "/api/diretorio/ramais/{contato_id}/qrcode",
        "/api/diretorio/favoritos/{contato_id}",
        "/api/diretorio/aniversariantes",
        "/api/diretorio/aniversariantes/{aniversariante_id}/parabens",
        "/api/diretorio/preferencias",
        "/api/diretorio/foto",
        "/api/diretorio/fotos/{contato_id}",
        "/api/autenticacao/login",
        "/api/autenticacao/sessao",
        "/api/autenticacao/perfil",
        "/api/autenticacao/tema",
        "/api/busca",
        "/api/atalhos",
        "/api/manuais",
        "/api/manuais/busca",
        "/api/manuais/imagem",
        "/api/manuais/livros/{livro_id}",
        "/api/manuais/paginas/{pagina_id}",
        "/api/integracao-bookstack",
        "/api/integracao-bookstack/testar",
        "/api/atalhos/gestao",
        "/api/atalhos/categorias",
        "/api/atalhos/categorias/{categoria_id}",
        "/api/atalhos/itens",
        "/api/atalhos/itens/{atalho_id}",
        "/api/chamados",
        "/api/chamados/solicitante",
        "/api/integracao-glpi",
        "/api/integracao-glpi/testar",
        "/api/favoritos",
        "/api/autenticacao/perfil/opcoes-gestor",
        "/api/autenticacao/perfil/opcoes-departamento",
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
        "/api/smtp/servidores",
        "/api/rh/afastamentos",
        "/api/rh/afastamentos/aprovacoes",
        "/api/rh/afastamentos/meus",
        "/api/rh/afastamentos/painel",
        "/api/rh/afastamentos/painel/exportar",
        "/api/rh/afastamentos/{afastamento_id}",
        "/api/rh/afastamentos/{afastamento_id}/aprovar",
        "/api/rh/afastamentos/{afastamento_id}/ciencia",
        "/api/rh/afastamentos/{afastamento_id}/cancelar",
        "/api/rh/afastamentos/{afastamento_id}/recusar",
        "/api/rh/cadastro/alteracoes/{alteracao_id}/recusar",
        "/api/rh/cadastro/alteracoes/{alteracao_id}/validar",
        "/api/rh/cadastro/pendencias",
        "/api/rh/cadastro/usuarios/{usuario_id}",
        "/api/rh/cadastro/usuarios/{usuario_id}/funcionais",
        "/api/rh/papeis",
        "/api/rh/parametros",
        "/api/rh/cadastro/usuarios/{usuario_id}/periodo-vigente",
        "/api/rh/feriados",
        "/api/tarefas",
        "/api/tarefas/equipes",
        "/api/tarefas/equipes/{equipe_id}",
        "/api/tarefas/atividades",
        "/api/tarefas/atividades/{atividade_id}",
        "/api/tarefas/atividades/{atividade_id}/concluir",
        "/api/tarefas/equipes/{equipe_id}/desempenho",
        "/api/tarefas/pessoas/{usuario_id}/desempenho",
        "/api/tarefas/contratos/sincronizar",
        "/api/tarefas/equipes/{equipe_id}/marcos",
        "/api/tarefas/equipes/{equipe_id}/status",
        "/api/tarefas/marcos/{marco_id}",
        "/api/tarefas/marcos/{marco_id}/atingir",
        "/api/tarefas/marcos/{marco_id}/reabrir",
        "/api/tarefas/equipes/{equipe_id}/estagios",
        "/api/tarefas/equipes/{equipe_id}/marcadores",
        "/api/tarefas/equipes/{equipe_id}/marcadores/{marcador_id}",
        "/api/tarefas/recorrencias/previa",
        "/api/tarefas/recorrencias",
        "/api/tarefas/recorrencias/{recorrencia_id}",
        "/api/tarefas/recorrencias/{recorrencia_id}/pausar",
        "/api/tarefas/recorrencias/{recorrencia_id}/retomar",
        "/api/tarefas/marcadores/{marcador_id}",
        "/api/tarefas/ordem",
        "/api/tarefas/pessoas",
        "/api/tarefas/pessoas/{usuario_id}/agenda",
        "/api/tarefas/relatorio",
        "/api/noticias",
        "/api/noticias/categorias",
        "/api/noticias/categorias/{categoria_id}",
        "/api/noticias/opcoes-setores",
        "/api/noticias/opcoes-usuarios",
        "/api/noticias/papel",
        "/api/noticias/publicas",
        "/api/noticias/publicas/{slug}",
        "/api/noticias/publicas/{slug}/arquivos/{anexo_id}",
        "/api/noticias/{noticia_id}",
        "/api/noticias/{noticia_id}/anexos",
        "/api/noticias/{noticia_id}/anexos/{anexo_id}",
        "/api/noticias/{noticia_id}/aprovar",
        "/api/noticias/{noticia_id}/arquivar",
        "/api/noticias/{noticia_id}/arquivos/{anexo_id}",
        "/api/noticias/{noticia_id}/capa",
        "/api/noticias/{noticia_id}/ciencias",
        "/api/noticias/{noticia_id}/desarquivar",
        "/api/noticias/{noticia_id}/devolver",
        "/api/noticias/{noticia_id}/enviar-revisao",
        "/api/noticias/{noticia_id}/revisoes",
        "/api/melhorias/acesso",
        "/api/melhorias/sugestoes",
        "/api/melhorias/sugestoes/exportar",
        "/api/melhorias/sugestoes/relatorio",
        "/api/melhorias/sugestoes/{numero}",
        "/api/melhorias/sugestoes/{numero}/prints/{anexo_id}",
        "/api/melhorias/sugestoes/{numero}/tarefa",
        "/api/melhorias/minhas",
        "/api/melhorias/minhas/{numero}",
        "/api/portal",
        "/api/portal/atalhos",
        "/api/portal/atalhos/ordem",
        "/api/portal/atalhos/{atalho_id}",
        "/api/portal/atalhos/{atalho_id}/imagem",
        "/api/portal/configuracao",
        "/api/tarefas/com-anexos",
        "/api/tarefas/{numero}",
        "/api/tarefas/{numero}/anexos/{anexo_id}",
        "/api/tarefas/{numero}/checklist",
        "/api/tarefas/{numero}/comentarios",
        "/api/tarefas/{numero}/eventos/{evento_id}/remover",
        "/api/tarefas/{numero}/linha-do-tempo",
        "/api/tarefas/{numero}/mover",
        "/api/tarefas/{numero}/subtarefas",
        "/api/tarefas/{numero}/dependencias",
        "/api/tarefas/{numero}/estagio",
        "/api/tarefas/{numero}/atividades",
        "/api/tarefas/{numero}/seguir",
        "/api/tarefas/{numero}/marco",
        "/api/tarefas/{numero}/prazo",
        "/api/tarefas/{numero}/transferir",
        "/api/rh/afastamentos/lancamento",
        "/api/rh/relatorios/saldos",
        "/api/rh/cadastro/alteracoes/validar-lote",
        "/api/rh/cadastro/funcionais/importacao",
        "/api/rh/cadastro/funcionais/importacao/modelo",
        "/api/rh/cadastro/funcionais/importacao/previa",
        "/api/rh/feriados/{feriado_id}",
        "/api/rh/folha-ponto",
        "/api/rh/folha-ponto/competencias",
        "/api/mensagens",
        "/api/mensagens/resumo",
        "/api/mensagens/lote",
        "/api/mensagens/previa",
        "/api/assinatura-email/dados",
        "/api/assinatura-email/previa",
        "/api/assinatura-email/png",
        "/api/assinatura-email/html",
        "/api/protocolo/contratos/{contrato_id}",
        "/api/protocolo/exportar",
        "/api/protocolo/numeros/{numero_id}",
        "/api/protocolo/numeros/{numero_id}/anexo",
        "/api/protocolo/numeros/{numero_id}/anular",
        "/api/protocolo/numeros/{numero_id}/contrato",
        "/api/protocolo/numeros/{numero_id}/liberar",
        "/api/protocolo/numeros/{numero_id}/reservar",
        "/api/protocolo/numeros/{numero_id}/sigilo",
        "/api/protocolo/painel",
        "/api/protocolo/sequencias/{sequencia_id}/faixa",
        "/api/protocolo/sequencias/{sequencia_id}/numeros",
        "/api/protocolo/sequencias/{sequencia_id}/proximo",
        "/api/protocolo/tipos",
        "/api/protocolo/tipos/{tipo_id}",
        "/api/protocolo/tipos/{tipo_id}/sequencias",
        "/api/contratacoes/documentos",
        "/api/contratacoes/documentos/{documento_id}",
        "/api/contratacoes/documentos/{documento_id}/conferencia",
        "/api/contratacoes/documentos/{documento_id}/contrato",
        "/api/contratacoes/documentos/{documento_id}/duplicar",
        "/api/contratacoes/documentos/{documento_id}/exportar/pdf",
        "/api/contratacoes/documentos/{documento_id}/exportar/word",
        "/api/contratacoes/documentos/{documento_id}/historico/{historico_id}/restaurar",
        "/api/contratacoes/documentos/{documento_id}/itens",
        "/api/contratacoes/documentos/{documento_id}/itens/{item_id}",
        "/api/contratacoes/documentos/{documento_id}/itens/{item_id}/duplicar",
        "/api/contratacoes/documentos/{documento_id}/itens/{item_id}/historico",
        "/api/contratacoes/documentos/{documento_id}/itens/{item_id}/limpar-filhos",
        "/api/contratacoes/documentos/{documento_id}/itens/{item_id}/linhas-tr",
        "/api/contratacoes/documentos/{documento_id}/itens/{item_id}/mover",
        "/api/contratacoes/documentos/{documento_id}/itens/{item_id}/revisoes",
        "/api/contratacoes/documentos/{documento_id}/itens/{item_id}/revisoes/{revisao_id}/aplicar",
        "/api/contratacoes/documentos/{documento_id}/itens/{item_id}/revisoes/{revisao_id}/resolver",
        "/api/contratacoes/documentos/{documento_id}/linhas-tr/{linha_id}",
        "/api/contratacoes/documentos/{documento_id}/lote",
        "/api/contratacoes/documentos/{documento_id}/lote/previa",
        "/api/contratacoes/documentos/{documento_id}/membros/{usuario_id}",
        "/api/contratacoes/documentos/{documento_id}/secoes",
        "/api/contratacoes/documentos/{documento_id}/secoes/{secao_id}",
        "/api/contratacoes/documentos/{documento_id}/secoes/{secao_id}/ordem",
        "/api/contratacoes/documentos/{documento_id}/situacao",
        "/api/contratacoes/documentos/{documento_id}/versoes",
        "/api/contratacoes/documentos/{documento_id}/versoes/{numero}",
        "/api/contratacoes/documentos/{documento_id}/versoes/{numero}/alteracoes",
        "/api/contratacoes/documentos/{documento_id}/versoes/{numero}/restaurar",
        "/api/contratacoes/importar-word",
        "/api/contratacoes/opcoes-usuarios",
        "/api/contratacoes/painel",
        "/api/contratacoes/por-contrato/{contrato_id}",
        "/api/mensageria/changelog/rascunho",
        "/api/mensageria/changelog/previa",
        "/api/mensageria/changelog/envios",
        "/api/mensagens/destinatarios",
        "/api/mensagens/enviadas",
        "/api/mensagens/enviadas/{mensagem_id}",
        "/api/mensagens/enviadas/{mensagem_id}/lembrar",
        "/api/mensagens/{entrega_id}",
        "/api/mensagens/{entrega_id}/ciencia",
        "/api/smtp/servidores/testar",
        "/api/smtp/servidores/{servidor_id}",
        "/api/smtp/servidores/{servidor_id}/testar",
        "/api/smtp/servidores/{servidor_id}/enviar-teste",
        *CAMINHOS_CONTRATOS,
    }
    # Confere também respostas documentadas, segurança e o nome do schema de validação
    login = especificacao["paths"]["/api/autenticacao/login"]["post"]["responses"]
    assert "401" in login and "422" in login
    assert especificacao["paths"]["/api/autenticacao/sessao"]["get"]["security"] == [{"TokenBearer": []}]
    esquemas = especificacao["components"]["schemas"]
    assert "HTTPValidationError" not in esquemas and "RespostaErroValidacao" in esquemas


# --- Renovação deslizante do token ---------------------------------------------------------------

def _token(cliente, id_usuario: int, restam_minutos: float, inicio_horas_atras: float = 0.1, **extras) -> str:
    """Token de acesso do usuário com `restam_minutos` de validade (a sessão começou `inicio_horas_atras` horas atrás)."""
    config = obter_configuracao()
    agora = datetime.now(UTC)
    corpo = {"sub": str(id_usuario), "iat": agora - timedelta(hours=inicio_horas_atras), "ini": int((agora - timedelta(hours=inicio_horas_atras)).timestamp()),
             "exp": agora + timedelta(minutes=restam_minutos), "tipo": "acesso", **extras}
    return jwt.encode(corpo, config.chave_secreta_jwt.get_secret_value(), algorithm=config.algoritmo_jwt)


def _sessao(cliente, token: str):
    return cliente.get("/api/autenticacao/sessao", headers={"Authorization": f"Bearer {token}"})


def test_token_com_bastante_validade_nao_e_renovado(cliente, admin):
    uid = cliente.get("/api/autenticacao/sessao", headers=admin).json()["id"]
    r = _sessao(cliente, _token(cliente, uid, restam_minutos=50))
    assert r.status_code == 200 and "x-token-renovado" not in r.headers


def test_token_perto_de_vencer_e_renovado_e_o_novo_funciona(cliente, admin):
    uid = cliente.get("/api/autenticacao/sessao", headers=admin).json()["id"]
    r = _sessao(cliente, _token(cliente, uid, restam_minutos=10, login="root"))
    assert r.status_code == 200
    novo, expira_em = r.headers["x-token-renovado"], r.headers["x-token-expira-em"]
    # A validade recomeça (60 min), o início da sessão e as demais declarações se mantêm
    conteudo = jwt.decode(novo, obter_configuracao().chave_secreta_jwt.get_secret_value(), algorithms=["HS256"])
    assert conteudo["sub"] == str(uid) and conteudo["login"] == "root" and conteudo["tipo"] == "acesso"
    assert 55 * 60 < conteudo["exp"] - datetime.now(UTC).timestamp() <= 60 * 60 and expira_em.startswith(str(datetime.now(UTC).year))
    assert conteudo["ini"] < conteudo["iat"]
    assert _sessao(cliente, novo).status_code == 200


def test_sessao_maxima_para_a_renovacao(cliente, admin, monkeypatch):
    monkeypatch.setenv("HORAS_SESSAO_MAXIMA", "12")
    obter_configuracao.cache_clear()
    try:
        uid = cliente.get("/api/autenticacao/sessao", headers=admin).json()["id"]
        # Sessão de 13 horas: não renova mais (o token ainda vale até vencer); sessão de 2 horas renova
        assert "x-token-renovado" not in _sessao(cliente, _token(cliente, uid, restam_minutos=10, inicio_horas_atras=13)).headers
        assert "x-token-renovado" in _sessao(cliente, _token(cliente, uid, restam_minutos=10, inicio_horas_atras=2)).headers
    finally:
        monkeypatch.undo()
        obter_configuracao.cache_clear()


def test_token_antigo_sem_inicio_continua_valendo_e_renova(cliente, admin):
    uid = cliente.get("/api/autenticacao/sessao", headers=admin).json()["id"]
    agora = datetime.now(UTC)
    config = obter_configuracao()
    antigo = jwt.encode({"sub": str(uid), "iat": agora - timedelta(minutes=50), "exp": agora + timedelta(minutes=10), "tipo": "acesso"},
                        config.chave_secreta_jwt.get_secret_value(), algorithm=config.algoritmo_jwt)
    assert "x-token-renovado" in _sessao(cliente, antigo).headers


def test_usuario_desativado_perde_o_acesso_mesmo_com_token_renovavel(cliente, admin):
    uid = criar_usuario("saiu")
    token = _token(cliente, uid, restam_minutos=10)
    assert _sessao(cliente, token).status_code == 200
    with FabricaSessao() as sessao:
        sessao.get(Usuario, uid).ativo = False
        sessao.commit()
    r = _sessao(cliente, token)
    assert r.status_code == 401 and "x-token-renovado" not in r.headers


def test_token_expirado_nao_e_renovado(cliente, admin):
    uid = cliente.get("/api/autenticacao/sessao", headers=admin).json()["id"]
    r = _sessao(cliente, _token(cliente, uid, restam_minutos=-1))
    assert r.status_code == 401 and "x-token-renovado" not in r.headers


def test_tema_da_interface_e_salvo_no_perfil(cliente, admin):
    """O tema escolhido é gravado na conta e volta na sessão; valor desconhecido é recusado."""
    assert cliente.get("/api/autenticacao/sessao", headers=admin).json()["tema"] == "auto"
    r = cliente.put("/api/autenticacao/tema", json={"tema": "escuro"}, headers=admin)
    assert r.status_code == 200 and r.json()["tema"] == "escuro"
    assert cliente.get("/api/autenticacao/sessao", headers=admin).json()["tema"] == "escuro"
    assert cliente.put("/api/autenticacao/tema", json={"tema": "roxo"}, headers=admin).status_code == 422
    assert cliente.put("/api/autenticacao/tema", json={"tema": "claro"}).status_code == 401


def test_documentacao_da_api_exige_login_e_acl(cliente, admin):
    """O OpenAPI só sai com token e permissão; as páginas Swagger/ReDoc são só a casca HTML (sem dados)."""
    from tests.conftest import cabecalho, criar_usuario

    assert cliente.get("/api/openapi.json").status_code == 401
    # As páginas abrem sem token, mas não trazem nenhuma especificação embutida
    for pagina in ("/api/documentacao", "/api/redoc"):
        resposta = cliente.get(pagina)
        assert resposta.status_code == 200 and "text/html" in resposta.headers["content-type"]
        assert '"paths"' not in resposta.text
    # Recurso fechado (como na migração): só o usuário com regra enxerga
    liberado = criar_usuario("doc_liberado")
    criar_usuario("doc_negado")
    recurso = cliente.post("/api/acl/recursos", json={"nome": "Documentação da API", "slug": "documentacao-api"}, headers=admin).json()
    regra = cliente.post("/api/acl/regras", json={"recurso_id": recurso["id"], "nivel": "LEITURA", "usuarios_ids": [liberado], "setores_ids": []}, headers=admin)
    assert regra.status_code == 201, regra.text
    assert cliente.get("/api/openapi.json", headers=cabecalho(cliente, "doc_negado")).status_code == 403
    assert cliente.get("/api/openapi.json", headers=cabecalho(cliente, "doc_liberado")).status_code == 200
