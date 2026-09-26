# API do contratos-spi

## Finalidade

A API expõe as regras de negócio e os dados do contratos-spi para o frontend Angular e para futuros sistemas consumidores. Hoje ela oferece:
- autenticação local e corporativa (LDAP), com perfil institucional obrigatório;
- cadastro de usuários e setores;
- controle de acesso por recurso (ACL);
- administração de diretórios LDAP;
- verificação de disponibilidade.

- módulo de contratos: empresas contratadas, carteira, cadastro, documentos importantes, orçamento, execução mensal, prorrogação, reajuste, aditamento/supressão e painel.

## Arquitetura e funcionamento

```text
Navegador
   │
   ▼
 Nginx (porta pública)
   │
   ├── /            → frontend Angular (arquivos estáticos em frontend/dist/contratos-spi/browser)
   │
   └── /api/*       → FastAPI (uvicorn em 127.0.0.1:8000, serviço systemd contratos-spi-api)
                          │
                          ├── PostgreSQL (URL_BANCO_DADOS)
                          ├── Anexos PDF em disco (ANEXOS_DIRETORIO)
                          └── Active Directory (LDAP) do diretório ativo
```

- O frontend e a API são servidos pela **mesma origem**. O Angular chama caminhos relativos (`/api/...`), sem CORS.
- A API não mantém sessão no servidor. Cada requisição autenticada carrega um JWT no cabeçalho `Authorization`.
- Organização do backend (`backend/app/`):

| Pasta | Responsabilidade |
|---|---|
| `api/routes/` | Rotas HTTP, uma por recurso (`autenticacao.py`, `usuarios.py`, `setores.py`, `acl.py`, `ldap.py`, `smtp.py`, `saude.py`); o módulo de contratos fica em `api/routes/contratos/` |
| `api/dependencias.py` | Autenticação (`obter_usuario_autenticado`, `obter_usuario_atual`) e autorização (`exigir_papeis`, `exigir_acl`) |
| `api/respostas.py` | Respostas de erro padronizadas para as rotas e o OpenAPI |
| `core/` | Configuração (`configuracao.py`), banco (`banco.py`), senhas e JWT (`seguranca.py`), cifra de segredos (`criptografia.py`), formato de erros (`erros.py`) |
| `models/` | Modelos SQLAlchemy: `Usuario`, `DiretorioLdap`, `RegistroAuditoria`, `Anexo`, `Setor`, `MembroSetor`, `RecursoAcl`, `RegraAcl` |
| `schemas/` | Schemas Pydantic de entrada e saída (contrato da API) |
| `services/` | Regras de negócio (`servico_*.py`, `cliente_ldap.py`, `agendador_ldap.py`, `cliente_smtp.py`), anexos em disco (`servico_anexos.py`) e auditoria (`servico_auditoria.py`) |
| `services/contratos/` | Regras do módulo de contratos; `calculos.py` concentra datas de vigência, situação e valores (funções puras) |
| `services/documentos/` | Geração de PDF com a identidade do Governo de SP (`pdf.py`, ReportLab + pypdf) e de planilhas XLSX (`planilha.py`, openpyxl) |
| `recursos/` | Arquivos usados pelos documentos gerados (brasão) |
| `alembic/` (em `backend/`) | Migrações do banco. Toda alteração de modelo exige uma nova migração |

### Tabelas

| Tabela | Conteúdo |
|---|---|
| `usuarios` | Contas locais e corporativas, com o perfil institucional |
| `diretorios_ldap` | Configuração dos diretórios LDAP (senha de bind cifrada) |
| `servidores_smtp` | Configuração dos servidores SMTP de envio de e-mail (senha cifrada; um ativo) |
| `setores`, `membros_setor` | Setores e seus membros |
| `acl_recursos`, `acl_regras`, `acl_regras_usuarios`, `acl_regras_setores` | Controle de acesso |
| `auditoria` | Registro das operações. `alvo_tipo`/`alvo_id` identificam o registro alterado e `dados` (JSONB) guarda o conteúdo do ato; nas alterações, `{"campos": {"campo": {"de", "para"}}}` alimenta o histórico por campo |
| `contratos_empresas`, `contratos_empresas_prepostos` | Empresas contratadas e prepostos |
| `contratos`, `contratos_itens`, `contratos_equipe`, `contratos_documentos` | Contrato, itens financeiros, designações da equipe (com início e fim) e documentos importantes |
| `contratos_previsoes`, `contratos_previsoes_limites`, `contratos_previsoes_apontamentos` | Previsão por vigência: selo, limites sob demanda e apontamentos mensais |
| `contratos_notas_empenho`, `contratos_notas_empenho_movimentos` | Notas de Empenho e extrato (débitos das OBs) |
| `contratos_checklists`, `contratos_checklists_itens`, `contratos_formularios`, `contratos_modelos` | Versões de checklist e de formulário de avaliação; modelos globais |
| `contratos_competencias` e `contratos_competencias_*` (`itens`, `notas`, `ciencias`, `memorias`, `cadin`, `documentos`, `avaliacoes`) | Competências de execução e tudo o que cada etapa registra |
| `contratos_diario_ocorrencias`, `contratos_diario_glosas` | Diário de bordo: ocorrências (imutáveis, com o resultado do e-mail) e glosas por item |
| `contratos_prorrogacoes`, `contratos_prorrogacoes_processos`, `contratos_prorrogacoes_ciencias` | Termos aditivos de prorrogação e o rascunho com parecer e ciências |
| `contratos_reajustes`, `contratos_reajustes_itens`, `contratos_reajustes_memorias` | Reajustes e memórias versionadas |
| `contratos_alteracoes`, `contratos_alteracoes_itens`, `contratos_alteracoes_ciencias` | Aditamentos e supressões |
| `anexos` | Metadados dos PDFs enviados ou gerados (nome original, chave em disco, SHA-256, tamanho, categoria, autor e `contrato_id` quando pertence a um contrato — usado para descartar os arquivos ao excluir o contrato). O arquivo fica em `ANEXOS_DIRETORIO/AAAA/MM/<uuid>.pdf` |

## URL base

| Ambiente | URL base |
|---|---|
| Servidor (via Nginx) | `http://<servidor>/api` |
| Backend direto (diagnóstico no servidor) | `http://127.0.0.1:8000/api` |
| Angular em desenvolvimento (`ng serve`) | `/api` (redirecionado pelo `proxy.conf.json` para `127.0.0.1:8000`) |

No Angular, a URL base vem de `ambiente.urlApi` (`/api`).

## Convenções

- Formato JSON (`Content-Type: application/json`), codificação UTF-8.
- Rotas, parâmetros, campos e códigos de erro em **português**, em `snake_case` e sem acentos (ex.: `nome_completo`, `revisao_obrigatoria`).
- Datas: ISO 8601 em UTC (ex.: `2026-09-23T20:30:00Z`). Datas sem hora: `AAAA-MM-DD`.
- Listas paginadas: `pagina`, `tamanho_pagina` na requisição; `itens`, `total`, `pagina`, `tamanho_pagina` na resposta.
- Toda resposta traz o cabeçalho `X-Correlacao`: um código de 12 caracteres que identifica a requisição nos logs da API. As telas o exibem nos erros para que o usuário o informe ao suporte.
- Anexos: somente PDF (o conteúdo precisa começar com `%PDF-`), não vazio e com até `ANEXOS_TAMANHO_MAXIMO_MB` (padrão 25 MB). Envio em `multipart/form-data` no campo `arquivo`. Exceção: o **XML da nota fiscal** (campos `xml`/`xml_adicional` da etapa de NF), validado pela leitura do próprio XML (até 5 MB, sem `DOCTYPE`).

## Autenticação e autorização

Resumo: obtenha o token em `POST /api/autenticacao/login` e envie-o em todas as chamadas protegidas:

```http
Authorization: Bearer <token_acesso>
```

A autorização combina três verificações, nesta ordem:
1. **perfil institucional em dia** (usuários comuns);
2. **papel** `SuperRoot` (administração);
3. **ACL** por recurso (módulos).

Detalhes em [autenticacao.md](autenticacao.md).

## Endpoints disponíveis

| Método | Caminho | Autorização | Descrição | Documentação |
|---|---|---|---|---|
| `GET` | `/api/saude` | Pública | Verifica se a API está no ar | [sistema.md](endpoints/sistema.md) |
| `POST` | `/api/autenticacao/login` | Pública | Autentica e emite o JWT | [autenticacao.md](endpoints/autenticacao.md#post-apiautenticacaologin) |
| `GET` | `/api/autenticacao/sessao` | Bearer (1) | Usuário autenticado | [autenticacao.md](endpoints/autenticacao.md#get-apiautenticacaosessao) |
| `GET` | `/api/autenticacao/perfil` | Bearer (1) | Meu perfil institucional | [autenticacao.md](endpoints/autenticacao.md#get-apiautenticacaoperfil) |
| `PUT` | `/api/autenticacao/perfil` | Bearer (1) | Atualiza e revalida meu perfil | [autenticacao.md](endpoints/autenticacao.md#put-apiautenticacaoperfil) |
| `GET` | `/api/autenticacao/perfil/opcoes-departamento` | Bearer (1) | Setores para o combobox Departamento | [autenticacao.md](endpoints/autenticacao.md#get-apiautenticacaoperfilopcoes-departamento) |
| `GET` | `/api/autenticacao/perfil/opcoes-gestor` | Bearer (1) | Opções de gestor imediato | [autenticacao.md](endpoints/autenticacao.md#get-apiautenticacaoperfilopcoes-gestor) |
| `GET` | `/api/usuarios` | ACL `usuarios` ≥ LEITURA | Lista usuários | [usuarios.md](endpoints/usuarios.md#get-apiusuarios) |
| `GET` | `/api/usuarios/opcoes` | ACL `usuarios` ≥ LEITURA | Opções para seletores | [usuarios.md](endpoints/usuarios.md#get-apiusuariosopcoes) |
| `GET` | `/api/usuarios/{usuario_id}` | ACL `usuarios` ≥ LEITURA | Consulta usuário | [usuarios.md](endpoints/usuarios.md#get-apiusuariosusuario_id) |
| `POST` | `/api/usuarios` | SuperRoot | Cria conta local | [usuarios.md](endpoints/usuarios.md#post-apiusuarios) |
| `PUT` | `/api/usuarios/{usuario_id}` | SuperRoot | Altera usuário | [usuarios.md](endpoints/usuarios.md#put-apiusuariosusuario_id) |
| `DELETE` | `/api/usuarios/{usuario_id}` | SuperRoot | Exclui usuário | [usuarios.md](endpoints/usuarios.md#delete-apiusuariosusuario_id) |
| `GET` | `/api/setores` | ACL `setores` ≥ LEITURA | Lista setores | [setores.md](endpoints/setores.md#get-apisetores) |
| `GET` | `/api/setores/{setor_id}` | ACL `setores` ≥ LEITURA | Consulta setor com membros | [setores.md](endpoints/setores.md#get-apisetoressetor_id) |
| `POST` | `/api/setores` | SuperRoot | Cria setor | [setores.md](endpoints/setores.md#post-apisetores) |
| `PUT` | `/api/setores/{setor_id}` | SuperRoot | Altera setor | [setores.md](endpoints/setores.md#put-apisetoressetor_id) |
| `DELETE` | `/api/setores/{setor_id}` | SuperRoot | Exclui setor | [setores.md](endpoints/setores.md#delete-apisetoressetor_id) |
| `GET` | `/api/acl/meus-acessos` | Bearer | Meus acessos efetivos | [acl.md](endpoints/acl.md#get-apiaclmeus-acessos) |
| `GET` | `/api/acl/efetivo/{usuario_id}` | SuperRoot | Acesso efetivo de um usuário | [acl.md](endpoints/acl.md#get-apiaclefetivousuario_id) |
| `GET` `POST` | `/api/acl/recursos` | SuperRoot | Lista / cadastra recursos | [acl.md](endpoints/acl.md#recursos) |
| `PUT` `DELETE` | `/api/acl/recursos/{recurso_id}` | SuperRoot | Altera / exclui recurso | [acl.md](endpoints/acl.md#recursos) |
| `GET` `POST` | `/api/acl/regras` | SuperRoot | Lista / cria regras | [acl.md](endpoints/acl.md#regras) |
| `PUT` `DELETE` | `/api/acl/regras/{regra_id}` | SuperRoot | Altera / exclui regra | [acl.md](endpoints/acl.md#regras) |
| `GET` `POST` | `/api/ldap/diretorios` | SuperRoot | Lista / cadastra diretórios | [ldap.md](endpoints/ldap.md) |
| `POST` | `/api/ldap/diretorios/testar` | SuperRoot | Testa configuração sem salvar | [ldap.md](endpoints/ldap.md#post-apildapdiretoriostestar) |
| `GET` `PUT` `DELETE` | `/api/ldap/diretorios/{diretorio_id}` | SuperRoot | Consulta / altera / exclui diretório | [ldap.md](endpoints/ldap.md) |
| `POST` | `/api/ldap/diretorios/{diretorio_id}/testar` | SuperRoot | Testa conectividade e registra o resultado | [ldap.md](endpoints/ldap.md#post-apildapdiretoriosdiretorio_idtestar) |
| `POST` | `/api/ldap/diretorios/{diretorio_id}/sincronizar` | SuperRoot | Sincroniza usuários | [ldap.md](endpoints/ldap.md#post-apildapdiretoriosdiretorio_idsincronizar) |
| `GET` | `/api/ldap/diretorios/{diretorio_id}/diagnosticar` | SuperRoot | Diagnostica um login | [ldap.md](endpoints/ldap.md#get-apildapdiretoriosdiretorio_iddiagnosticarloginlogin) |
| `GET` `POST` | `/api/smtp/servidores` | SuperRoot | Lista / cadastra servidores SMTP | [smtp.md](endpoints/smtp.md) |
| `POST` | `/api/smtp/servidores/testar` | SuperRoot | Testa configuração sem salvar | [smtp.md](endpoints/smtp.md#endpoints) |
| `GET` `PUT` `DELETE` | `/api/smtp/servidores/{servidor_id}` | SuperRoot | Consulta / altera / exclui servidor | [smtp.md](endpoints/smtp.md#endpoints) |
| `POST` | `/api/smtp/servidores/{servidor_id}/testar` | SuperRoot | Testa conexão e autenticação e registra o resultado | [smtp.md](endpoints/smtp.md#endpoints) |
| `POST` | `/api/smtp/servidores/{servidor_id}/enviar-teste` | SuperRoot | Envia e-mail de teste | [smtp.md](endpoints/smtp.md#endpoints) |

| `GET` `POST` | `/api/contratos/empresas` | ACL `contratos` ≥ LEITURA / ≥ MODIFICACAO | Lista / cadastra empresas | [contratos-empresas.md](endpoints/contratos-empresas.md) |
| `GET` | `/api/contratos/empresas/opcoes` | ACL `contratos` ≥ LEITURA | Empresas para o cadastro de contrato | [contratos-empresas.md](endpoints/contratos-empresas.md#get-apicontratosempresasopcoes) |
| `GET` `PUT` `DELETE` | `/api/contratos/empresas/{empresa_id}` | LEITURA / MODIFICACAO / CONTROLE_TOTAL | Consulta / altera / exclui empresa | [contratos-empresas.md](endpoints/contratos-empresas.md) |
| `POST` | `/api/contratos/empresas/{empresa_id}/prepostos` | ACL `contratos` ≥ MODIFICACAO | Cadastra preposto | [contratos-empresas.md](endpoints/contratos-empresas.md) |
| `PUT` `DELETE` | `/api/contratos/empresas/{empresa_id}/prepostos/{preposto_id}` | ACL `contratos` ≥ MODIFICACAO | Altera / exclui preposto | [contratos-empresas.md](endpoints/contratos-empresas.md) |
| `GET` `POST` | `/api/contratos` | ACL `contratos` ≥ LEITURA / ≥ MODIFICACAO | Carteira / cadastra contrato | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `GET` | `/api/contratos/proximo-numero` | ACL `contratos` ≥ LEITURA | Próximo número do ano | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `GET` | `/api/contratos/opcoes-usuarios` | ACL `contratos` ≥ MODIFICACAO | Usuários para a equipe | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `GET` `PUT` `DELETE` | `/api/contratos/{contrato_id}` | LEITURA / pode editar (2) / CONTROLE_TOTAL | Detalhe / altera / exclui contrato | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `GET` | `/api/contratos/{contrato_id}/historico` | ACL `contratos` ≥ LEITURA | Histórico por campo | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `GET` | `/api/contratos/{contrato_id}/documentos` | ACL `contratos` ≥ LEITURA | Documentos importantes | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `POST` | `/api/contratos/{contrato_id}/documentos/{codigo}` | Pode editar (2) | Anexa documento importante | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `GET` | `/api/contratos/{contrato_id}/documentos/{codigo}/arquivo` | ACL `contratos` ≥ LEITURA | Baixa documento importante | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `GET` | `/api/contratos/painel` | ACL `contratos` ≥ LEITURA | Painel: pendências, alertas, execução orçamentária | [contratos-painel.md](endpoints/contratos-painel.md) |
| `GET` | `/api/contratos/relatorios/notas-empenho` | SuperRoot | Relatório Executivo de NEs (XLSX/PDF) | [contratos-painel.md](endpoints/contratos-painel.md) |
| `GET` | `/api/contratos/relatorios/previsao-orcamentaria` | SuperRoot | Previsão consolidada com cenários | [contratos-painel.md](endpoints/contratos-painel.md) |
| `GET` `POST` `PUT` `DELETE` | `/api/contratos/modelos[/{modelo_id}]` | LEITURA / SuperRoot | Modelos globais de checklist e formulário | [contratos-painel.md](endpoints/contratos-painel.md) |
| `GET` `POST` | `/api/contratos/{contrato_id}/diario` | LEITURA / edição do contrato | Diário de bordo: lista / registra ocorrência (e-mail à equipe e ao preposto) | [contratos-diario.md](endpoints/contratos-diario.md) |
| `POST` | `/api/contratos/{contrato_id}/diario/{ocorrencia_id}/reenviar` | Edição do contrato | Reenvia o e-mail da ocorrência | [contratos-diario.md](endpoints/contratos-diario.md) |
| `GET` | `/api/contratos/{contrato_id}/diario/pdf` | LEITURA | Diário de bordo em PDF | [contratos-diario.md](endpoints/contratos-diario.md) |
| `POST` | `/api/contratos/{contrato_id}/competencias/{competencia_id}/reenviar-email-medicao` | Edição do contrato | Reenvia o e-mail da medição concluída | [contratos-execucao.md](endpoints/contratos-execucao.md) |
| `PUT` | `/api/contratos/{contrato_id}/competencias/{competencia_id}/retencao` | Financeiro, equipe ou SuperRoot | Retenção de tributos (conferência da NF lida do XML) | [contratos-execucao.md](endpoints/contratos-execucao.md) |
| `POST` | `/api/contratos/{contrato_id}/competencias/{competencia_id}/reenviar-email-nf` | Edição do contrato | Reenvia o e-mail da NF ao Financeiro | [contratos-execucao.md](endpoints/contratos-execucao.md) |
| `POST` | `/api/contratos/{contrato_id}/competencias/{competencia_id}/reenviar-email-retencao` | Financeiro, equipe ou SuperRoot | Reenvia o e-mail da retenção à equipe | [contratos-execucao.md](endpoints/contratos-execucao.md) |
| `GET` `POST` | `/api/contratos/migracao-sgi` | SuperRoot | Importação dos contratos do SGI SPI (estado / iniciar) | [contratos-migracao-sgi.md](endpoints/contratos-migracao-sgi.md) |
| `GET` `PUT` | `/api/contratos/{contrato_id}/previsao[/{sequencia_vigencia}]` | LEITURA / pode editar (2) | Previsão orçamentária | [contratos-orcamento.md](endpoints/contratos-orcamento.md) |
| `GET` | `/api/contratos/{contrato_id}/previsao/{sequencia_vigencia}/xlsx` | ACL `contratos` ≥ LEITURA | Exporta a previsão | [contratos-orcamento.md](endpoints/contratos-orcamento.md) |
| `GET` `POST` `PUT` `DELETE` | `/api/contratos/{contrato_id}/notas-empenho[/{nota_id}]` | LEITURA / pode editar (2) | Notas de Empenho | [contratos-orcamento.md](endpoints/contratos-orcamento.md) |
| vários | `/api/contratos/{contrato_id}/checklists/*`, `/formularios/*` | LEITURA / pode editar (2) | Versões de checklist e de formulário | [contratos-execucao.md](endpoints/contratos-execucao.md) |
| vários | `/api/contratos/{contrato_id}/execucao*`, `/competencias/*` | LEITURA / pode editar (2) / SuperRoot (reabrir) | Competências e etapas 1 a 7 | [contratos-execucao.md](endpoints/contratos-execucao.md) |
| vários | `/api/contratos/{contrato_id}/prorrogacao*`, `/prorrogacoes/*` | LEITURA / pode editar (2) | Prorrogação | [contratos-alteracoes.md](endpoints/contratos-alteracoes.md#prorrogação) |
| vários | `/api/contratos/{contrato_id}/reajustes/*` | LEITURA / pode editar (2) | Reajuste | [contratos-alteracoes.md](endpoints/contratos-alteracoes.md#reajuste) |
| vários | `/api/contratos/{contrato_id}/alteracoes/*` | LEITURA / pode editar (2) | Aditamento e supressão | [contratos-alteracoes.md](endpoints/contratos-alteracoes.md#aditamento--supressão) |
(1) Funciona mesmo com o perfil institucional pendente. Todos os demais endpoints autenticados exigem perfil em dia, exceto para o SuperRoot.

(2) **Pode editar** o contrato: ACL `contratos` ≥ MODIFICACAO **e** ser SuperRoot, criador do contrato ou integrante vigente da equipe (gestor, fiscais e suplentes). Sem vínculo: `403 acesso_negado`.

## Códigos HTTP e tratamento de erros

Todas as respostas de erro têm o mesmo formato:

```json
{ "detalhe": "Mensagem legível em português.", "codigo": "codigo_do_erro" }
```

| HTTP | `codigo` | Quando ocorre | Campos extras |
|---|---|---|---|
| `400` | `invalido` | Regra de negócio violada | — |
| `401` | `nao_autenticado` | Credenciais inválidas; token ausente, inválido ou expirado. Inclui o cabeçalho `WWW-Authenticate: Bearer` | — |
| `403` | `revisao_perfil_obrigatoria` | Perfil institucional incompleto ou com revalidação vencida | `campos_pendentes` |
| `403` | `acl_negado` | Nível de ACL insuficiente no recurso | `recurso`, `nivel_exigido`, `nivel_efetivo` |
| `403` | `acesso_negado` | Operação exige o papel SuperRoot | — |
| `404` | `nao_encontrado` | Registro ou rota inexistente | — |
| `409` | `conflito` | Registro duplicado (login, nome de setor, nome/slug de recurso) | — |
| `422` | `validacao` | Corpo ou parâmetros fora do schema | `erros` |
| `500` | `erro_interno` | Falha inesperada na API. O `detalhe` não expõe dados internos e informa o código para o suporte | `correlacao` |
| `503` | `servico_indisponivel` | Serviço externo indisponível (ex.: diretório LDAP na sincronização) | — |
| `502`/`504` | — | API fora do ar ou sem resposta (retornado pelo Nginx, em HTML) | — |

Os sucessos usam `200 OK`, `201 Created` (criação, com o registro no corpo) e `204 No Content` (exclusão).

### Erro de validação (422)

```json
{
  "detalhe": "Dados inválidos. senha: deve ter ao menos 8 caractere(s).",
  "codigo": "validacao",
  "erros": [{ "campo": "senha", "mensagem": "deve ter ao menos 8 caractere(s)" }]
}
```

`campo` usa ponto para campos aninhados (ex.: `perfil.email`).

### ACL insuficiente (403)

```json
{
  "detalhe": "Você não possui o nível de acesso necessário para este recurso. Esta operação exige LEITURA em 'usuarios'; seu acesso efetivo é nenhum.",
  "codigo": "acl_negado",
  "recurso": "usuarios",
  "nivel_exigido": "LEITURA",
  "nivel_efetivo": null
}
```

### Erro inesperado (500)

```json
{
  "detalhe": "Ocorreu um erro inesperado. Informe ao suporte o código 3f9a1c2b7d4e.",
  "codigo": "erro_interno",
  "correlacao": "3f9a1c2b7d4e"
}
```

O mesmo código aparece no cabeçalho `X-Correlacao` e na linha do log `contratos_spi.erros` com o rastreamento completo.

### Tratamento no Angular

- `401` em chamada autenticada: o `interceptadorAutenticacao` encerra a sessão e redireciona para `/login?sessao=expirada`.
- `403` com `revisao_perfil_obrigatoria`: o interceptador atualiza a sessão e leva à página `/perfil`.
- As telas exibem o `detalhe` recebido. Em `0` (sem conexão) ou `5xx`: "Serviço indisponível. Tente novamente em instantes."
