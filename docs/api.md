# API do sgi-spi

## Finalidade

A API expõe as regras de negócio e os dados do sgi-spi para o frontend Angular e para futuros sistemas consumidores. Hoje ela oferece:
- autenticação local e corporativa (LDAP), com perfil institucional obrigatório;
- cadastro de usuários e setores;
- controle de acesso por recurso (ACL);
- administração de diretórios LDAP;
- verificação de disponibilidade.

- módulo de contratos: empresas contratadas, carteira, cadastro, documentos importantes, orçamento, execução mensal, prorrogação, reajuste, aditamento/supressão, painel e importação de contrato por planilha XLSX.

## Arquitetura e funcionamento

```text
Navegador
   │
   ▼
 Nginx (porta pública)
   │
   ├── /            → frontend Angular (arquivos estáticos em frontend/dist/sgi-spi/browser)
   │
   └── /api/*       → FastAPI (uvicorn em 127.0.0.1:8000, serviço systemd sgi-spi-api)
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
| `api/routes/` | Rotas HTTP, uma por recurso (`autenticacao.py`, `usuarios.py`, `setores.py`, `acl.py`, `ldap.py`, `smtp.py`, `notificacoes.py`, `notificacoes_changelog.py`, `rh.py`, `saude.py`); o módulo de contratos fica em `api/routes/contratos/` |
| `api/dependencias.py` | Autenticação (`obter_usuario_autenticado`, `obter_usuario_atual`) e autorização (`exigir_papeis`, `exigir_acl`) |
| `api/respostas.py` | Respostas de erro padronizadas para as rotas e o OpenAPI |
| `core/` | Configuração (`configuracao.py`), banco (`banco.py`), senhas e JWT (`seguranca.py`), cifra de segredos (`criptografia.py`), formato de erros (`erros.py`) |
| `models/` | Modelos SQLAlchemy: `Usuario`, `DiretorioLdap`, `RegistroAuditoria`, `Anexo`, `Setor`, `MembroSetor`, `RecursoAcl`, `RegraAcl` |
| `schemas/` | Schemas Pydantic de entrada e saída (contrato da API) |
| `services/` | Regras de negócio (`servico_*.py`, `cliente_ldap.py`, `agendador_ldap.py`, `cliente_smtp.py`), anexos em disco (`servico_anexos.py`) e auditoria (`servico_auditoria.py`) |
| `services/contratos/` | Regras do módulo de contratos; `calculos.py` concentra datas de vigência, situação e valores (funções puras) |
| `services/documentos/` | Geração de PDF com a identidade do Governo de SP (`pdf.py`, ReportLab + pypdf) e de planilhas XLSX (`planilha.py`, openpyxl) |
| `recursos/` | Arquivos usados pelos documentos gerados (brasão) e o modelo da planilha de importação de contrato |
| `alembic/` (em `backend/`) | Migrações do banco. Toda alteração de modelo exige uma nova migração |

### Tabelas

| Tabela | Conteúdo |
|---|---|
| `usuarios` | Contas locais e corporativas, com o perfil institucional |
| `diretorios_ldap` | Configuração dos diretórios LDAP (senha de bind cifrada) |
| `servidores_smtp` | Configuração dos servidores SMTP de envio de e-mail (senha cifrada; um ativo) |
| `rh_alteracoes_cadastrais`, `rh_dados_funcionais` | Módulo RH: alterações de cadastro pendentes de validação da CGP (histórico) e dados funcionais (autorizador, substituto, início do período aquisitivo, saldo de LP, jornada, horários, RG/CIN e RS/PV) |
| `rh_periodos_aquisitivos` | Módulo RH: períodos aquisitivos de férias (12 meses), dias creditados, ajuste da CGP e expiração |
| `rh_feriados` | Módulo RH: feriados e pontos facultativos (um por data), usados no calendário, no painel, na regra de início e na folha de ponto |
| `rh_admissoes`, `rh_admissao_documentos`, `rh_checklists`, `rh_checklist_itens`, `rh_checklist_tipos`, `rh_modelos` | Módulo RH: trilha de admissão, checklists de documentos por tipo de cargo e modelos editáveis (resolução, e-mail, termo de posse, boas-vindas) |
| `rh_pre_cadastros`, `rh_ficha_formacoes`, `rh_ficha_experiencias` | Módulo RH: ficha de pré-cadastro (dados pessoais, login proposto, vínculo com a conta), formações e experiências |
| `rh_pre_cadastros`, `rh_ficha_formacoes`, `rh_ficha_experiencias` | Módulo RH: ficha de pré-cadastro (dados pessoais, login proposto, vínculo com a conta), formações e experiências |
| `rh_tipos_cargo`, `rh_cargos`, `rh_ocupacoes`, `rh_historico` | Módulo RH: cargos como vagas por setor, ocupações (histórico) e livro-razão do histórico funcional |
| `rh_afastamentos`, `rh_afastamentos_eventos`, `rh_parametros` | Módulo RH: férias e licença-prêmio, histórico de status e regras de agendamento |
| `notificacoes`, `notificacoes_entregas` | Notificações: mensagens (avulsas e automáticas, com o `evento` do catálogo) e a entrega a cada destinatário (lida, ciência, encerrada, canais e resultado do e-mail e do navegador) |
| `notificacoes_preferencias`, `notificacoes_config_usuario`, `notificacoes_inscricoes_navegador`, `notificacoes_silenciados`, `notificacoes_obrigatorias` | Preferências de notificação: canais ligados por evento, frequência do e-mail e não perturbe, navegadores inscritos (Web Push), contratos e tarefas silenciados e eventos obrigatórios por setor ou usuário |
| `noticias`, `noticias_revisoes`, `noticias_anexos`, `noticias_categorias`, `portal_atalhos`, `portal_configuracao` | Módulo Notícias: notícias com fluxo de aprovação, histórico, anexos, categorias, atalhos e parâmetros do slider do portal |
| `sla_politicas` | Política de SLA de prazos (dias úteis de resposta e de resolução por módulo e prioridade) |
| `tarefas`, `tarefas_equipes` (+ `_membros`, `_lideres`), `tarefas_participantes`, `tarefas_eventos` (+ `_anexos`), `tarefas_marcadores` (+ `_vinculos`), `tarefas_checklist` | Módulo Tarefas: tarefas com pipeline de validação, equipes, envolvidos, linha do tempo, marcadores e checklist |
| `melhorias_sugestoes`, `melhorias_anexos`, `melhorias_eventos` | Módulo Melhorias: sugestões dos usuários (com a tela de origem), prints anexados e histórico da triagem |
| `usuarios_preferencias_colunas` | Colunas que cada usuário escolheu mostrar nas listagens, por tela (lista ordenada de ids) |
| `diretorio_favoritos`, `diretorio_parabens`, `diretorio_curtidas` | Módulo Diretório: contatos favoritos por usuário, mural de parabéns e curtidas nos cartões (foto e opt-out de aniversário ficam em colunas de `usuarios`) |
| `notificacoes_envios_changelog` | Notificações: e-mails de changelog enviados pela conta root (texto, destino, até que data do CHANGELOG e resultado) |
| `setores`, `membros_setor` | Setores e seus membros |
| `acl_recursos`, `acl_regras`, `acl_regras_usuarios`, `acl_regras_setores`, `acl_perfis`, `acl_perfis_direitos`, `usuarios_perfis` | Controle de acesso (regras e perfis) |
| `auditoria` | Registro das operações. `alvo_tipo`/`alvo_id` identificam o registro alterado e `dados` (JSONB) guarda o conteúdo do ato; nas alterações, `{"campos": {"campo": {"de", "para"}}}` alimenta o histórico por campo |
| `contratos_empresas`, `contratos_empresas_prepostos` | Empresas contratadas e prepostos |
| `contratos`, `contratos_itens`, `contratos_equipe`, `contratos_documentos` | Contrato, itens financeiros, designações da equipe (com início e fim) e documentos importantes |
| `contratos_previsoes`, `contratos_previsoes_limites`, `contratos_previsoes_apontamentos` | Previsão por vigência: selo, limites sob demanda e apontamentos mensais |
| `contratos_notas_empenho`, `contratos_notas_empenho_movimentos` | Notas de Empenho e extrato (débitos das OBs) |
| `contratos_checklists`, `contratos_checklists_itens`, `contratos_formularios`, `contratos_modelos` | Versões de checklist e de formulário de avaliação; modelos globais |
| `contratos_competencias` e `contratos_competencias_*` (`itens`, `notas`, `ciencias`, `memorias`, `cadin`, `documentos`, `avaliacoes`) | Competências de execução e tudo o que cada etapa registra |
| `contratos_diario_ocorrencias`, `contratos_diario_glosas`, `contratos_diario_anexos`, `contratos_diario_itens_avaliacao` | Diário de bordo: ocorrências (imutáveis, com o resultado do e-mail), glosas por item, anexos (até 5) e itens da avaliação impactados |
| `contratos_prorrogacoes`, `contratos_prorrogacoes_processos`, `contratos_prorrogacoes_ciencias` | Termos aditivos de prorrogação e o rascunho com parecer, ciências e os dados digitados das minutas (`dados_minuta`) e o checklist do Parecer Referencial (`enquadramento`) |
| `contratos_vigencias_retroativas` | Vigências anteriores ao início do contrato, cadastradas com o termo |
| `contratos_reajustes`, `contratos_reajustes_itens`, `contratos_reajustes_memorias` | Reajustes (inclusive retroativos, coluna `retroativo`) e memórias versionadas |
| `contratos_abatimentos_reajuste` | Crédito de desconto de reajuste retroativo abatido no valor autorizado das competências (`competencia_id` nulo = pendente) |
| `contratos_alteracoes`, `contratos_alteracoes_itens`, `contratos_alteracoes_ciencias` | Aditamentos e supressões |
| `portarias_autoridades`, `contratos_portarias`, `contratos_portarias_nomeacoes` | Autoridades signatárias, portarias de designação (texto congelado, número do Protocolo, aceite e publicação) e as nomeações com a ciência de cada nomeado |
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
| `GET` `POST` | `/api/chamados[/solicitante]` | ACL `abrir-chamado` (aberta a todos) | Dados do cadastro que vão no chamado; abre o chamado no GLPI; meus chamados | [chamados.md](endpoints/chamados.md) |
| `GET` `PUT` `POST` | `/api/integracao-glpi[/testar]` | SuperRoot | Configuração da integração com o GLPI (tokens cifrados) e teste de conexão | [chamados.md](endpoints/chamados.md#getput-apiintegracao-glpi-e-post-apiintegracao-glpitestar-superroot) |
| `GET` | `/api/busca` | Bearer (1), com ACL por módulo | Busca global em contratos, contratações, tarefas, pessoas e setores | [navegacao.md](endpoints/navegacao.md#get-apibusca) |
| `GET` `PUT` | `/api/favoritos` | Bearer (1) | Favoritos do menu (telas fixadas pelo usuário) | [navegacao.md](endpoints/navegacao.md#get-apifavoritos) |
| `GET` `PUT` `DELETE` | `/api/preferencias/colunas/{tela}` | Bearer (1) | Colunas que o usuário escolheu mostrar em cada listagem (por usuário e tela, na ordem) | [navegacao.md](endpoints/navegacao.md#get-apipreferenciascolunastela) |
| `GET` | `/api/openapi.json` | Bearer + ACL `documentacao-api` ≥ LEITURA | Especificação OpenAPI da API (não aparece nela mesma) | [documentacao-api.md](endpoints/documentacao-api.md) |
| `GET` | `/api/documentacao`, `/api/redoc` | Páginas HTML sem dados; carregam o OpenAPI com o token da sessão do SGI | Swagger UI e ReDoc | [documentacao-api.md](endpoints/documentacao-api.md) |
| `GET` | `/api/manuais[/…]` | Bearer; ACL `manuais` ≥ LEITURA (sem regras: todos) | Manuais do BookStack lidos pelo portal: estantes, livros, páginas, busca e imagens | [manuais.md](endpoints/manuais.md) |
| `GET` `PUT` `POST` | `/api/integracao-bookstack[/testar]` | SuperRoot | Configuração da integração com o BookStack (token cifrado) e teste de conexão | [manuais.md](endpoints/manuais.md#getput-apiintegracao-bookstack-e-post-apiintegracao-bookstacktestar-superroot) |
| `GET` `POST` `PUT` `DELETE` | `/api/atalhos[/…]` | Bearer (leitura); ACL `atalhos` ≥ MODIFICACAO (gestão) | Atalhos fixos por categoria (CRUD); o menu lateral passou a ser configurado em `/api/menu` | [atalhos.md](endpoints/atalhos.md) |
| `GET` `PUT` `POST` | `/api/integracao-sigeo[/testar|/conferir]` | SuperRoot | Integração com o SIGEO: credencial cifrada, teste e conferência diária das OBs pagas (conclui a etapa da OB) | [integracao-sigeo.md](endpoints/integracao-sigeo.md) |
| `GET` `POST` | `/api/admin/backups[/arquivo/{nome}|/importar]` | SuperRoot | Backup geral: gerar e baixar um .zip com o banco inteiro e os anexos, e importar um (substitui tudo, guardando antes o estado atual) | [backup-geral.md](endpoints/backup-geral.md) |
| `GET` `PUT` `DELETE` | `/api/menu` | Bearer (leitura); ACL `atalhos` ≥ MODIFICACAO (gravar e restaurar) | Menu lateral configurável: ordem, grupos, nomes, links e itens ocultos | [menu.md](endpoints/menu.md) |
| `GET` | `/api/contratos/{contrato_id}/vizinhos` | LEITURA | Contrato anterior e próximo na lista (carteira) | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `PUT` | `/api/autenticacao/tema` | Bearer (1) | Salva meu tema da interface (claro, escuro ou automático) | [autenticacao.md](endpoints/autenticacao.md#put-apiautenticacaotema) |
| `POST` | `/api/autenticacao/perfil-ativo` | Bearer | Troca o perfil de acesso ativo (token novo) | [autenticacao.md](endpoints/autenticacao.md#post-apiautenticacaoperfil-ativo) |
| `POST` | `/api/autenticacao/personificar` | SuperRoot | Navega como outro usuário (token novo) | [autenticacao.md](endpoints/autenticacao.md#personificação-de-usuário) |
| `POST` | `/api/autenticacao/personificar/parar` | Bearer | Encerra a personificação | [autenticacao.md](endpoints/autenticacao.md#personificação-de-usuário) |
| `GET` | `/api/autenticacao/perfil` | Bearer (1) | Meu perfil institucional | [autenticacao.md](endpoints/autenticacao.md#get-apiautenticacaoperfil) |
| `PUT` | `/api/autenticacao/perfil` | Bearer (1) | Atualiza e revalida meu perfil | [autenticacao.md](endpoints/autenticacao.md#put-apiautenticacaoperfil) |
| `GET` | `/api/autenticacao/perfil/opcoes-departamento` | Bearer (1) | Setores para o combobox Departamento | [autenticacao.md](endpoints/autenticacao.md#get-apiautenticacaoperfilopcoes-departamento) |
| `GET` | `/api/autenticacao/perfil/opcoes-gestor` | Bearer (1) | Opções de gestor imediato | [autenticacao.md](endpoints/autenticacao.md#get-apiautenticacaoperfilopcoes-gestor) |
| `GET` | `/api/usuarios` | ACL `usuarios` ≥ LEITURA | Lista usuários | [usuarios.md](endpoints/usuarios.md#get-apiusuarios) |
| `GET` | `/api/usuarios/opcoes` | ACL `usuarios` ≥ LEITURA | Opções para seletores | [usuarios.md](endpoints/usuarios.md#get-apiusuariosopcoes) |
| `GET` | `/api/usuarios/{usuario_id}` | ACL `usuarios` ≥ LEITURA | Consulta usuário | [usuarios.md](endpoints/usuarios.md#get-apiusuariosusuario_id) |
| `POST` | `/api/usuarios` | SuperRoot ou ACL `usuarios` = CONTROLE_TOTAL | Cria conta local | [usuarios.md](endpoints/usuarios.md#post-apiusuarios) |
| `PUT` | `/api/usuarios/{usuario_id}` | SuperRoot ou ACL `usuarios` = CONTROLE_TOTAL | Altera usuário | [usuarios.md](endpoints/usuarios.md#put-apiusuariosusuario_id) |
| `DELETE` | `/api/usuarios/{usuario_id}` | SuperRoot ou ACL `usuarios` = CONTROLE_TOTAL | Exclui usuário | [usuarios.md](endpoints/usuarios.md#delete-apiusuariosusuario_id) |
| `GET` | `/api/setores` | ACL `setores` ≥ LEITURA ou qualquer nível em `rh` | Lista setores | [setores.md](endpoints/setores.md#get-apisetores) |
| `GET` | `/api/setores/{setor_id}` | ACL `setores` ≥ LEITURA | Consulta setor com membros | [setores.md](endpoints/setores.md#get-apisetoressetor_id) |
| `POST` | `/api/setores` | SuperRoot ou ACL `rh` ≥ MODIFICACAO | Cria setor | [setores.md](endpoints/setores.md#post-apisetores) |
| `PUT` | `/api/setores/{setor_id}` | SuperRoot ou ACL `rh` ≥ MODIFICACAO | Altera setor | [setores.md](endpoints/setores.md#put-apisetoressetor_id) |
| `DELETE` | `/api/setores/{setor_id}` | SuperRoot ou ACL `rh` ≥ MODIFICACAO | Exclui setor | [setores.md](endpoints/setores.md#delete-apisetoressetor_id) |
| `GET` | `/api/acl/meus-acessos` | Bearer | Meus acessos efetivos | [acl.md](endpoints/acl.md#get-apiaclmeus-acessos) |
| `GET` | `/api/acl/efetivo/{usuario_id}` | SuperRoot | Acesso efetivo de um usuário | [acl.md](endpoints/acl.md#get-apiaclefetivousuario_id) |
| `GET` `POST` | `/api/acl/recursos` | SuperRoot | Lista / cadastra recursos | [acl.md](endpoints/acl.md#recursos) |
| `PUT` `DELETE` | `/api/acl/recursos/{recurso_id}` | SuperRoot | Altera / exclui recurso | [acl.md](endpoints/acl.md#recursos) |
| `GET` `POST` | `/api/acl/regras` | SuperRoot | Lista / cria regras | [acl.md](endpoints/acl.md#regras) |
| `PUT` `DELETE` | `/api/acl/regras/{regra_id}` | SuperRoot | Altera / exclui regra | [acl.md](endpoints/acl.md#regras) |
| `GET` `POST` | `/api/acl/perfis` | SuperRoot | Lista / cadastra perfis de acesso | [acl.md](endpoints/acl.md#perfis-de-acesso) |
| `GET` `PUT` `DELETE` | `/api/acl/perfis/{perfil_id}` | SuperRoot | Detalha / altera / exclui perfil | [acl.md](endpoints/acl.md#perfis-de-acesso) |
| `PUT` `DELETE` | `/api/acl/perfis/{perfil_id}/modulos/{recurso_id}` | SuperRoot | Adiciona/edita (ações independentes) ou remove um módulo do perfil | [acl.md](endpoints/acl.md#perfis-de-acesso) |
| `PUT` | `/api/acl/perfis/{perfil_id}/usuarios` | SuperRoot | Substitui os usuários do perfil | [acl.md](endpoints/acl.md#perfis-de-acesso) |
| `PUT` | `/api/acl/perfis/{perfil_id}/setores` | SuperRoot | Substitui os setores/grupos que recebem o perfil | [acl.md](endpoints/acl.md#perfis-de-acesso) |
| `GET` `PUT` | `/api/acl/usuarios/{usuario_id}/perfis` | SuperRoot | Perfis de um usuário e o padrão | [acl.md](endpoints/acl.md#perfis-de-acesso) |
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
| `GET` | `/api/rh/papeis` | Autenticado | Papéis no RH (CGP, autorizador) | [rh-cadastro.md](endpoints/rh-cadastro.md) |
| `GET` `POST` `PUT` | `/api/rh/cadastro/…` | CGP | Pendências, cadastro, validar/recusar alteração, dados funcionais, ajuste do período aquisitivo vigente | [rh-cadastro.md](endpoints/rh-cadastro.md) |
| `GET` `POST` `PUT` | `/api/rh/afastamentos[/…]` | Autenticado (por papel) | Férias e licença-prêmio: meus, agendar, alterar, cancelar, aprovar/recusar, aprovações, painel, exportar | [rh-afastamentos.md](endpoints/rh-afastamentos.md) |
| `GET` `POST` `PUT` `DELETE` | `/api/rh/feriados[/{feriado_id}]` | Leitura: autenticado; gravação: CGP | Feriados e pontos facultativos | [rh-afastamentos.md](endpoints/rh-afastamentos.md#feriados-e-pontos-facultativos-apirhferiados) |
| `GET` `POST` `PUT` `DELETE` | `/api/rh/admissoes[/…]`, `/api/rh/modelos[/…]`, `/api/rh/checklists[/…]` | ACL `rh` = Controle total | Trilha de admissão (chamado no GLPI, documentos, resolução, Protocolo, publicação, e-mail, posse), modelos editáveis e checklists | [rh-admissao.md](endpoints/rh-admissao.md) |
| `GET` `POST` `PUT` | `/api/rh/boas-vindas[/confirmar]`, `/api/rh/minha-bio`, `/api/rh/minha-ficha` | Autenticado (só sobre si) | Boas-vindas do primeiro acesso, bio opcional e ficha cadastral dos legados | [rh-admissao.md](endpoints/rh-admissao.md#boas-vindas-bio-e-ficha-da-própria-pessoa) |
| `GET` `POST` `PUT` `DELETE` | `/api/rh/pre-cadastros[/…]` | ACL `rh` = Controle total | Fichas de pré-cadastro, checagem do login proposto no SGI e no AD e ficha por planilha XLSX, um formulário por pessoa (`importacao/modelo`, `importacao/previa`, `importacao`) | [rh-cargos.md](endpoints/rh-cargos.md) |
| `GET` `POST` `PUT` `DELETE` | `/api/rh/{tipos-cargo,cargos,cargos-a-reconciliar,organograma}` (organograma: qualquer usuário, vagas só RH e liderança) e `/api/rh/usuarios/{id}/historico[.pdf]` | ACL `rh` (Leitura, Modificação, Controle total) | Cargos como vagas por setor, ocupações, organograma e histórico funcional | [rh-cargos.md](endpoints/rh-cargos.md) |
| `POST` | `/api/rh/afastamentos/lancamento` | CGP | Lançar afastamento em nome do servidor | [rh-afastamentos.md](endpoints/rh-afastamentos.md) |
| `GET` | `/api/rh/relatorios/saldos` | CGP | Relatório de saldos (XLSX/PDF) | [rh-afastamentos.md](endpoints/rh-afastamentos.md) |
| `GET` `POST` | `/api/rh/cadastro/funcionais/importacao[/modelo\|/previa]` | CGP | Carga em lote dos dados funcionais por planilha | [rh-cadastro.md](endpoints/rh-cadastro.md) |
| `POST` | `/api/rh/cadastro/alteracoes/validar-lote` | CGP | Validar alterações em lote | [rh-cadastro.md](endpoints/rh-cadastro.md) |
| `GET` | `/api/portal`, `/api/noticias/publicas[/…]` | **Público (sem token)** | Página inicial do portal, arquivo e detalhe das notícias publicadas, capas e atalhos | [noticias.md](endpoints/noticias.md) |
| `GET` `POST` `PUT` `DELETE` | `/api/noticias[/…]`, `/api/portal/configuracao`, `/api/portal/atalhos[/…]` | Autenticado + ACL `noticias` (MODIFICACAO redator, CONTROLE_TOTAL aprovador) | Gestão editorial: notícias, aprovação, capa 2:1, anexos, categorias, atalhos e configuração do slider | [noticias.md](endpoints/noticias.md) |
| `GET` `POST` `PUT` `DELETE` | `/api/tarefas[/…]` | Autenticado (permissões por tarefa e equipe) | Módulo Tarefas: listas, pipeline, prazo, transferência, comentários, linha do tempo, agenda da pessoa, equipes e marcadores | [tarefas.md](endpoints/tarefas.md) |
| `GET` `PUT` | `/api/sla/politicas` | ACL `sla` (≥ LEITURA lê; ≥ MODIFICACAO grava) | Política de SLA de prazos (dias úteis de resposta e resolução) de Tarefas e Melhorias | [sla.md](endpoints/sla.md) |
| `GET` `POST` `PUT` | `/api/melhorias[/…]` | Autenticado (triagem: SuperRoot ou CONTROLE_TOTAL em `melhorias`) | Módulo Melhorias: envio de sugestões com prints, minhas sugestões, triagem, conversão em tarefa, XLSX e PDF | [melhorias.md](endpoints/melhorias.md) |
| `GET` `POST` `PUT` `PATCH` `DELETE` | `/api/diretorio[/…]` | Autenticado | Módulo Diretório: ramais em cartões, filtros, favoritos, vCard/QR Code, aniversariantes dia/semana/mês, mural de parabéns, foto e opt-out | [diretorio.md](endpoints/diretorio.md) |
| `GET` | `/api/painel-executivo[/…]` | SuperRoot ou regra no recurso ACL `painel-executivo` (sem regras: só SuperRoot) | Painel Executivo: slides de contratos, RH e tarefas, PDF e `acesso` | [painel-executivo.md](endpoints/painel-executivo.md) |
| `GET` | `/api/rh/folha-ponto[/competencias]` | Autenticado (só a própria) | Folha de ponto em PDF / competências disponíveis | [rh-folha-ponto.md](endpoints/rh-folha-ponto.md) |
| `GET`, `POST` | `/api/assinatura-email/{dados,previa,png,html}` | Autenticado | Assinatura de e-mail institucional: dados do perfil, prévia, PNG e HTML | [assinatura-email.md](endpoints/assinatura-email.md) |
| `GET`, `POST`, `PUT`, `DELETE` | `/api/protocolo/...` | ACL `protocolo` (LEITURA / MODIFICACAO / CONTROLE_TOTAL) | Numeração institucional: tipos, sequências por exercício, números, anexo, sigilo, painel e exportação | [protocolo.md](endpoints/protocolo.md) |
| `GET`, `POST`, `PUT`, `DELETE` | `/api/patrimonio/...` | ACL `patrimonio` (LEITURA / MODIFICACAO / CONTROLE_TOTAL) | Patrimônio mobiliário: localizações, bens, histórico, movimentações, inservíveis/extraviados, baixas, painel e exportação | [patrimonio.md](endpoints/patrimonio.md) |
| `GET`, `POST`, `PUT`, `DELETE` | `/api/reserva-espacos/...` | Autenticado (recurso ACL `reserva-espacos`; papel de fiscal; SuperRoot na configuração) | Reserva de espaços: agenda, solicitação com recorrência, análise dos fiscais, cancelamento, espaços, painel e exportação | [reserva-espacos.md](endpoints/reserva-espacos.md) |
| `GET`, `POST`, `PUT`, `DELETE` | `/api/contratacoes/...` | ACL `contratacoes` (LEITURA / MODIFICACAO / CONTROLE_TOTAL) e papel no documento (criador, editor, revisor) | ETP e TR: árvore de itens, revisões, versões e histórico, conferência, vínculo com contrato, exportação Word/PDF e importação de Word | [contratacoes.md](endpoints/contratacoes.md) |
| `GET`, `POST` | `/api/contratos/{id}/itens/correcoes`, `…/previa`, `…/{correcao_id}/confirmar\|recusar\|cancelar`, `…/itens/historico` | ACL `contratos` (LEITURA para ler; gestor titular ou SuperRoot propõe; outra pessoa confirma) | Correção de itens com competências geradas: prévia, dois olhos, sincronização das competências abertas e histórico | [contratos-correcao-itens.md](endpoints/contratos-correcao-itens.md) |
| `GET` `PUT` | `/api/rh/parametros` | Leitura: autenticado; gravação: CGP | Regras de agendamento | [rh-afastamentos.md](endpoints/rh-afastamentos.md) |
| `GET` | `/api/notificacoes/resumo` | Autenticado | Contador do sino e janela a abrir | [notificacoes.md](endpoints/notificacoes.md) |
| `GET` `POST` | `/api/notificacoes` | Autenticado (setores: ACL `notificacoes-setores`) | Caixa de entrada / envia mensagem avulsa | [notificacoes.md](endpoints/notificacoes.md) |
| `GET` | `/api/notificacoes/{entrega_id}` | Autenticado (só a própria) | Abre a mensagem (marca lida) | [notificacoes.md](endpoints/notificacoes.md) |
| `POST` | `/api/notificacoes/{entrega_id}/ciencia` | Autenticado (só a própria) | Registra ciência | [notificacoes.md](endpoints/notificacoes.md) |
| `GET` | `/api/notificacoes/destinatarios` | Autenticado | Usuários e setores para o envio | [notificacoes.md](endpoints/notificacoes.md) |
| `GET` | `/api/notificacoes/enviadas[/{notificacao_id}]` | Autor ou SuperRoot | Acompanhamento das enviadas | [notificacoes.md](endpoints/notificacoes.md) |
| `POST` | `/api/notificacoes/enviadas/{notificacao_id}/lembrar` | Autor ou SuperRoot | E-mail de lembrete a quem não deu ciência | [notificacoes.md](endpoints/notificacoes.md) |
| `GET` `PUT` | `/api/notificacoes/preferencias` | Autenticado (só a própria) | Canais (e-mail, navegador, desktop) por evento, frequência do e-mail, não perturbe, situação do navegador e silenciados | [notificacoes.md](endpoints/notificacoes.md) |
| `POST` | `/api/notificacoes/navegador/inscricoes[/remover]` | Autenticado | Inscreve ou remove este navegador (Web Push) | [notificacoes.md](endpoints/notificacoes.md) |
| `POST` | `/api/notificacoes/testar` | Autenticado | Testa um canal (e-mail, navegador ou desktop) | [notificacoes.md](endpoints/notificacoes.md) |
| `POST` `DELETE` | `/api/notificacoes/silenciar`, `/api/notificacoes/silenciados/{silenciado_id}` | Autenticado | Silencia um contrato ou tarefa pelos canais externos / volta a avisar | [notificacoes.md](endpoints/notificacoes.md) |
| `POST` | `/api/notificacoes/ciencia-por-token` | Token do pop-up | Ciência pelo botão "Ciente" do pop-up do navegador | [notificacoes.md](endpoints/notificacoes.md) |
| `GET` `POST` `DELETE` | `/api/notificacoes/obrigatorias[/{obrigatoria_id}]` | SuperRoot ou ACL `notificacoes-obrigatorias` (CONTROLE_TOTAL) | Eventos e canais obrigatórios por setor ou usuário | [notificacoes.md](endpoints/notificacoes.md) |
| `GET` | `/api/notificacoes/painel-entregas` | Conta root | Entregas por e-mail e navegador, falhas e inscrições com problema | [notificacoes.md](endpoints/notificacoes.md) |
| `GET` | `/api/mensagens`, `/api/mensagens/resumo` | Autenticado | Compatibilidade permanente com o SGI Alertas (Windows): formato antigo, só entregas com o canal Desktop | [notificacoes.md](endpoints/notificacoes.md) |
| `POST` | `/api/notificacoes/changelog/contagem` | Conta root | Quantos da seleção receberão o e-mail de changelog | [notificacoes-changelog.md](endpoints/notificacoes-changelog.md) |
| `GET` | `/api/notificacoes/changelog/rascunho` | Conta root | Rascunho do e-mail de changelog a partir do CHANGELOG.md | [notificacoes-changelog.md](endpoints/notificacoes-changelog.md) |
| `POST` | `/api/notificacoes/changelog/previa` | Conta root | Prévia do e-mail no layout oficial | [notificacoes-changelog.md](endpoints/notificacoes-changelog.md) |
| `GET` `POST` | `/api/notificacoes/changelog/envios` | Conta root | Histórico / envia (todos ou teste) | [notificacoes-changelog.md](endpoints/notificacoes-changelog.md) |

| `GET` `POST` | `/api/contratos/empresas` | ACL `contratos` ≥ LEITURA / ≥ MODIFICACAO | Lista / cadastra empresas | [contratos-empresas.md](endpoints/contratos-empresas.md) |
| `GET` | `/api/contratos/empresas/opcoes` | ACL `contratos` ≥ LEITURA | Empresas para o cadastro de contrato | [contratos-empresas.md](endpoints/contratos-empresas.md#get-apicontratosempresasopcoes) |
| `GET` `PUT` `DELETE` | `/api/contratos/empresas/{empresa_id}` | LEITURA / MODIFICACAO / CONTROLE_TOTAL | Consulta / altera / exclui empresa | [contratos-empresas.md](endpoints/contratos-empresas.md) |
| `POST` | `/api/contratos/empresas/{empresa_id}/prepostos` | ACL `contratos` ≥ MODIFICACAO | Cadastra preposto | [contratos-empresas.md](endpoints/contratos-empresas.md) |
| `PUT` `DELETE` | `/api/contratos/empresas/{empresa_id}/prepostos/{preposto_id}` | ACL `contratos` ≥ MODIFICACAO | Altera / exclui preposto | [contratos-empresas.md](endpoints/contratos-empresas.md) |
| `GET` `POST` | `/api/contratos` | ACL `contratos` ≥ LEITURA / ≥ MODIFICACAO | Carteira / cadastra contrato | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `GET` | `/api/contratos/proximo-numero` | ACL `contratos` ≥ LEITURA | Próximo número do ano | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `GET` | `/api/contratos/opcoes-usuarios` | ACL `contratos` ≥ MODIFICACAO | Usuários para a equipe | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `GET` `PUT` `DELETE` | `/api/contratos/{contrato_id}` | LEITURA / pode editar (2) / CONTROLE_TOTAL | Detalhe / altera / exclui contrato | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `GET` | `/api/contratos/{contrato_id}/itens/pdf` | ACL `contratos` ≥ LEITURA | Relatório da aba Itens em PDF | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `GET` | `/api/contratos/{contrato_id}/historico` | ACL `contratos` ≥ LEITURA | Histórico por campo | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `GET` | `/api/contratos/{contrato_id}/documentos` | ACL `contratos` ≥ LEITURA | Documentos importantes | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `POST` | `/api/contratos/{contrato_id}/documentos/{codigo}` | Pode editar (2) | Anexa documento importante | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `DELETE` | `/api/contratos/{contrato_id}/documentos/{codigo}` | Pode editar (2) | Limpa documento importante (retira o PDF) | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `GET` | `/api/contratos/{contrato_id}/documentos/{codigo}/arquivo` | ACL `contratos` ≥ LEITURA | Baixa documento importante | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
| `GET` | `/api/contratos/painel` | ACL `contratos` ≥ LEITURA | Painel: pendências, alertas, execução orçamentária | [contratos-painel.md](endpoints/contratos-painel.md) |
| `GET` `POST` | `/api/contratos/verificar-documento` | ACL `contratos` ≥ LEITURA | Verifica um PDF autenticado pelo sistema (avaliação e memória de cálculo) pelo código ou pelo arquivo | [contratos-painel.md](endpoints/contratos-painel.md) |
| `GET` | `/api/contratos/calendario` | ACL `contratos` ≥ LEITURA | Calendário de vencimentos: vigência, reajuste, NF, validade de documentos, empenho e tarefas dos contratos por data | [contratos-painel.md](endpoints/contratos-painel.md) |
| `GET` | `/api/contratos/painel/vigencias` | ACL `contratos` ≥ LEITURA | Painel de vigências: vigência de cada contrato vigente, do que vence primeiro | [contratos-painel.md](endpoints/contratos-painel.md) |
| `GET` | `/api/contratos/relatorios/notas-empenho` | SuperRoot | Relatório Executivo de NEs (XLSX/PDF) | [contratos-painel.md](endpoints/contratos-painel.md) |
| `GET` | `/api/contratos/relatorios/previsao-orcamentaria` | SuperRoot | Previsão consolidada com cenários | [contratos-painel.md](endpoints/contratos-painel.md) |
| `GET` `POST` `PUT` `DELETE` | `/api/contratos/modelos[/{modelo_id}]`, `/modelos/portaria/placeholders` | LEITURA / SuperRoot (portaria: ou controle total) | Modelos globais de checklist e formulário e máscaras de portaria e da prorrogação (`/modelos/prorrogacao/placeholders`) | [contratos-painel.md](endpoints/contratos-painel.md) |
| `GET` `POST` | `/api/contratos/{contrato_id}/diario` | LEITURA / edição do contrato | Diário de bordo: lista / registra ocorrência (e-mail à equipe e ao preposto) | [contratos-diario.md](endpoints/contratos-diario.md) |
| `POST` | `/api/contratos/{contrato_id}/diario/{ocorrencia_id}/reenviar` | Edição do contrato | Reenvia o e-mail da ocorrência | [contratos-diario.md](endpoints/contratos-diario.md) |
| `GET` | `/api/contratos/{contrato_id}/diario/{ocorrencia_id}/anexos/{anexo_id}` | LEITURA | Baixa um anexo da ocorrência | [contratos-diario.md](endpoints/contratos-diario.md) |
| `GET` `PUT` `DELETE` | `/api/contratos/{contrato_id}/rascunhos/{tipo}` | LEITURA / edição do contrato | Rascunho compartilhado do diário, da avaliação e da medição (botão Salvar rascunho) | [contratos-rascunhos.md](endpoints/contratos-rascunhos.md) |
| `GET` | `/api/contratos/{contrato_id}/diario/pdf` | LEITURA | Diário de bordo em PDF | [contratos-diario.md](endpoints/contratos-diario.md) |
| `POST` | `/api/contratos/{contrato_id}/competencias/{competencia_id}/medicao/reemitir` | Edição do contrato | Reemite o documento executivo e o e-mail único da medição (contestação aceita) | [contratos-execucao.md](endpoints/contratos-execucao.md) |
| `POST` | `/api/contratos/{contrato_id}/competencias/{competencia_id}/avaliacao/enviar` | Edição do contrato | Gera o relatório de avaliação e envia a Medição e a Avaliação à contratada (e-mail único) | [contratos-execucao.md](endpoints/contratos-execucao.md) |
| `POST` | `/api/contratos/{contrato_id}/competencias/{competencia_id}/reenviar-email-avaliacao` | Edição do contrato | Reenvia o relatório de avaliação à contratada | [contratos-execucao.md](endpoints/contratos-execucao.md) |
| `POST` | `/api/contratos/{contrato_id}/competencias/{competencia_id}/ordem-bancaria/sigeo` | Edição do contrato ou ação "Lançar ordem bancária" | Busca agora a OB da competência no SIGEO (contrato com Processo Financeiro) e conclui se o mês e o líquido baterem | [contratos-execucao.md](endpoints/contratos-execucao.md) |
| `PUT` | `/api/contratos/{contrato_id}/competencias/{competencia_id}/retencao` | Financeiro, equipe ou SuperRoot | Retenção de tributos (conferência da NF lida do XML) | [contratos-execucao.md](endpoints/contratos-execucao.md) |
| `POST` | `/api/contratos/{contrato_id}/competencias/{competencia_id}/reenviar-email-nf` | Edição do contrato | Reenvia o e-mail da NF ao Financeiro | [contratos-execucao.md](endpoints/contratos-execucao.md) |
| `POST` | `/api/contratos/{contrato_id}/competencias/{competencia_id}/reenviar-email-retencao` | Financeiro, equipe ou SuperRoot | Reenvia o e-mail da retenção à equipe | [contratos-execucao.md](endpoints/contratos-execucao.md) |
| `POST` | `/api/contratos/migracao-sgi/rascunho` | Conta root | Lê um contrato no SGI e devolve o rascunho do cadastro (nada é gravado) | [contratos-migracao-sgi.md](endpoints/contratos-migracao-sgi.md) |
| `GET` `POST` | `/api/contratos/migracao-sgi` | SuperRoot | Importação completa dos contratos do SGI SPI (estado / iniciar; sem uso na tela) | [contratos-migracao-sgi.md](endpoints/contratos-migracao-sgi.md) |
| `POST` | `/api/contratos/importacao-xlsx/previa` | `contratos` ≥ MODIFICACAO | Prévia da importação de contrato por planilha XLSX | [contratos-importacao-xlsx.md](endpoints/contratos-importacao-xlsx.md) |
| `POST` | `/api/contratos/importacao-xlsx` | `contratos` ≥ MODIFICACAO | Importa o contrato da planilha | [contratos-importacao-xlsx.md](endpoints/contratos-importacao-xlsx.md) |
| `GET` | `/api/contratos/importacao-xlsx/modelo` | `contratos` ≥ MODIFICACAO | Baixa a planilha modelo | [contratos-importacao-xlsx.md](endpoints/contratos-importacao-xlsx.md) |
| `GET` `POST` | `/api/contratos/{contrato_id}/{recurso}/importacao-xlsx/{modelo|previa}` | `contratos` ≥ MODIFICACAO e poder editar o contrato | Modelo e prévia da importação de checklist (`checklists`) ou formulário (`formularios`) por XLSX | [contratos-importacao-modelos-xlsx.md](endpoints/contratos-importacao-modelos-xlsx.md) |
| `POST` | `/api/contratos/{contrato_id}/checklists/importacao-xlsx` | idem | Cria versão inativa do checklist a partir da planilha | [contratos-importacao-modelos-xlsx.md](endpoints/contratos-importacao-modelos-xlsx.md) |
| `POST` | `/api/contratos/{contrato_id}/formularios/importacao-xlsx` | idem | Cria versão inativa do formulário de avaliação a partir da planilha | [contratos-importacao-modelos-xlsx.md](endpoints/contratos-importacao-modelos-xlsx.md) |
| `GET` `POST` | `/api/contratos/modelos/importacao-xlsx/{tipo}[/modelo|/previa]` | SuperRoot | Modelo, prévia e criação de modelo global (checklist/formulário) por XLSX | [contratos-importacao-modelos-xlsx.md](endpoints/contratos-importacao-modelos-xlsx.md) |
| `GET` | `/api/contratos/{contrato_id}/exportacao-xlsx` | ACL `contratos` ≥ LEITURA | Baixa o contrato em XLSX, já preenchido, no formato da importação | [contratos-exportacao-xlsx.md](endpoints/contratos-exportacao-xlsx.md) |
| `GET` | `/api/contratos/{contrato_id}/checklists/{checklist_id}/xlsx` | ACL `contratos` ≥ LEITURA | Baixa uma versão do checklist em XLSX | [contratos-exportacao-xlsx.md](endpoints/contratos-exportacao-xlsx.md) |
| `GET` | `/api/contratos/{contrato_id}/formularios/{formulario_id}/xlsx` | ACL `contratos` ≥ LEITURA | Baixa uma versão do formulário de avaliação em XLSX | [contratos-exportacao-xlsx.md](endpoints/contratos-exportacao-xlsx.md) |
| `GET` `PUT` | `/api/contratos/parametros` | LEITURA / controle total | Parâmetros do módulo (cortes de alertas, prazos, regras e limites) | [contratos-parametros.md](endpoints/contratos-parametros.md) |
| `GET` `PUT` | `/api/contratos/{contrato_id}/previsao[/{sequencia_vigencia}]` | LEITURA / pode editar (2) | Previsão orçamentária | [contratos-orcamento.md](endpoints/contratos-orcamento.md) |
| `GET` | `/api/contratos/{contrato_id}/previsao/{sequencia_vigencia}/xlsx` | ACL `contratos` ≥ LEITURA | Exporta a previsão | [contratos-orcamento.md](endpoints/contratos-orcamento.md) |
| `GET` `POST` `PUT` `DELETE` | `/api/contratos/{contrato_id}/notas-empenho[/{nota_id}]` | LEITURA / pode editar (2) | Notas de Empenho | [contratos-orcamento.md](endpoints/contratos-orcamento.md) |
| vários | `/api/contratos/{contrato_id}/checklists/*`, `/formularios/*` | LEITURA / pode editar (2) | Versões de checklist e de formulário | [contratos-execucao.md](endpoints/contratos-execucao.md) |
| `POST` | `/api/contratos/{contrato_id}/competencias/{competencia_id}/retencao/recusar` e `…/recusas/{recusa_id}/reenviar-email` | Financeiro (ACL `contratos` ≥ LEITURA) | Recusa da nota fiscal na retenção (reabre a etapa da nota) e reenvio do e-mail da recusa | [contratos-execucao.md](endpoints/contratos-execucao.md) |
| `POST` | `/api/contratos/{contrato_id}/competencias/{competencia_id}/checklist/{documento_id}/reaproveitar` e `…/checklist/reaproveitar-todos` | pode editar (2) | Traz o documento da empresa, ainda válido, de outro contrato da mesma empresa (com confirmação) | [contratos-execucao.md](endpoints/contratos-execucao.md) |
| vários | `/api/contratos/{contrato_id}/execucao*`, `/competencias/*` | LEITURA / pode editar (2) / SuperRoot (reabrir) | Competências e etapas 1 a 7 | [contratos-execucao.md](endpoints/contratos-execucao.md) |
| vários | `/api/contratos/{contrato_id}/prorrogacao*`, `/prorrogacoes/*` | LEITURA / pode editar (2) | Prorrogação | [contratos-alteracoes.md](endpoints/contratos-alteracoes.md#prorrogação) |
| vários | `/api/contratos/{contrato_id}/vigencias-retroativas*` | LEITURA / pode editar (2) | Vigência retroativa | [contratos-alteracoes.md](endpoints/contratos-alteracoes.md#vigência-retroativa) |
| vários | `/api/contratos/{contrato_id}/reajustes/*` | LEITURA / pode editar (2) | Reajuste | [contratos-alteracoes.md](endpoints/contratos-alteracoes.md#reajuste) |
| vários | `/api/contratos/{contrato_id}/alteracoes/*` | LEITURA / pode editar (2) | Aditamento e supressão | [contratos-alteracoes.md](endpoints/contratos-alteracoes.md#aditamento--supressão) |
| vários | `/api/contratos/{contrato_id}/portarias*`, `/api/portarias/ciencias`, `/api/portarias/{portaria_id}/ciencia`, `/api/portarias/autoridades*` | LEITURA / equipe ou CONTROLE_TOTAL (criar) / autoridade signatária / nomeado (ciência) / CONTROLE_TOTAL (autoridades) | Portaria de designação (nomeações, ciência, autoridade, aceite; publicada ao anexar o D.O.E., pelo Protocolo ou pela aba Equipe), único caminho para mudar a equipe | [contratos-portarias.md](endpoints/contratos-portarias.md) |
| `GET` | `/api/contratos/{contrato_id}/pagamentos` | LEITURA | "Pagamento MM/AAAA" em Documentos Importantes: consolidado e OB/PD da competência, com a data da juntada | [contratos-cadastro.md](endpoints/contratos-cadastro.md) |
(1) Funciona mesmo com o perfil institucional pendente. Todos os demais endpoints autenticados exigem perfil em dia, exceto para o SuperRoot.

(2) **Pode editar** o contrato: ACL `contratos` ≥ MODIFICACAO **e** ser SuperRoot, ter **controle total** em Contratos (qualquer contrato), criador do contrato ou integrante vigente da equipe (gestor, fiscais e suplentes). Sem vínculo: `403 acesso_negado`.

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

O mesmo código aparece no cabeçalho `X-Correlacao` e na linha do log `sgi_spi.erros` com o rastreamento completo.

### Tratamento no Angular

- `401` em chamada autenticada: o `interceptadorAutenticacao` encerra a sessão e redireciona para `/login?sessao=expirada`.
- `403` com `revisao_perfil_obrigatoria`: o interceptador atualiza a sessão e leva à página `/perfil`.
- As telas exibem o `detalhe` recebido. Em `0` (sem conexão) ou `5xx`: "Serviço indisponível. Tente novamente em instantes."
