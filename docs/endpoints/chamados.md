# Chamados pelo SGI (`/api/chamados`) e integração com o GLPI (`/api/integracao-glpi`)

Tags no OpenAPI: **Chamados (GLPI)** e **Integração GLPI**. Implementação:
- rotas: `backend/app/api/routes/chamados.py` e `backend/app/api/routes/integracao_glpi.py`;
- regras: `backend/app/services/servico_chamados.py`, `servico_integracao_glpi.py` e o cliente `backend/app/services/glpi/cliente_glpi.py`;
- modelos: `backend/app/models/integracao_glpi.py` (tabelas `integracao_glpi` e `chamados_glpi`, migração `d1f4b8a2e6c9`).

O item **Abrir Chamado** da barra lateral abre um modal com **Assunto** e **Descrição do problema**. O restante vem do cadastro do usuário (nome, setor, superior imediato, e-mail, telefone = ramal, celular só se preenchido, andar - lado) e o chamado termina com a assinatura **"Aberto pelo SGI"**. O chamado é criado no GLPI (chamados.spi.sp.gov.br) pela **API REST**, com o próprio usuário como solicitante; o servidor do SGI fala com o GLPI, o navegador nunca vê os tokens.

## Como o chamado é montado (igual ao formulário "Informática", id 3, do GLPI)
O chamado do SGI reproduz o que o formulário `https://chamados.spi.sp.gov.br/front/form/form.form.php?id=3` faz (lido do GLPI em 05/10/2026):

| Item | No formulário do GLPI | No chamado aberto pelo SGI |
|---|---|---|
| Título | `Informática \| <assunto>` | `<prefixo> \| <assunto>` (prefixo configurável, padrão "Informática") |
| Perguntas | Assunto, Descrição de Problema e **Local do Problema** (lista de localizações), todas obrigatórias | Assunto, Descrição e **Local do problema** (lista do GLPI, obrigatória; sugerido pelo andar e lado do cadastro) |
| Conteúdo | `1) Assunto … 2) Descrição de Problema … 3) Local do Problema …` | o mesmo formato, seguido da tabela "Dados do solicitante" e de "Aberto pelo SGI" |
| Requerente | quem preenche | o próprio usuário (achado pelo login, depois pelo e-mail), com aviso por e-mail ligado; sem cadastro no GLPI: e-mail alternativo |
| Atribuído a | grupo SUPORTE (id 4) | grupo configurável (padrão 4); o chamado nasce **"Em atendimento (atribuído)"** |
| Observador | do modelo (nenhum) | nenhum |
| Tratativas (acompanhamentos/tarefas), validação | nenhuma | nenhuma |
| Tipo / urgência / impacto / origem | incidente / 3 / 3 / Helpdesk | iguais |
| Categoria | nenhuma (a TI classifica) | nenhuma |
| SLA | atendimento (id 2) e solução (id 1) | configuráveis (padrão 2 e 1); o GLPI calcula os prazos (+15 min e +4 h) |
| Localização | a do "Local do Problema" | a escolhida no modal |
| Entidade | a do usuário (raiz) | raiz |

Chamadas à API REST: `initSession` (user_token + App-Token) → `GET /search/Location` (lista de locais) → `GET /search/User` (login, depois e-mail) → `POST /Ticket` (multipart com `_filename` quando há anexos) → `killSession`. O chamado fica registrado em `chamados_glpi` e auditado (`chamado.abrir`).

## Quem pode o quê
- **Abrir chamado:** ACL `abrir-chamado` ≥ LEITURA. O recurso foi criado **sem regras**, e na ACL recurso sem regras fica aberto a **todo usuário autenticado**. O SuperRoot pode restringir depois em Controle de acesso.
- **Configurar a integração:** só SuperRoot.

## `GET /api/chamados/solicitante`
Dados do cadastro que vão no chamado: `nome`, `setor`, `superior_imediato`, `email`, `telefone`, `celular` (vazio se não informado), `andar_lado` (ex.: `5º andar - A`) e `aguardando_validacao` (lista de campos).
- **Dados temporários:** vale o que o usuário **informou por último**. Se há alteração do perfil ainda **aguardando validação da CGP**, o valor proposto é usado (no primeiro cadastro, tudo está pendente, e o chamado já sai completo); sem proposta, vale o valor em vigor. Os campos nessa situação vêm em `aguardando_validacao`, a tela os marca como "temporário" e o texto do chamado avisa que alguns dados aguardam validação da CGP.
- O bloqueio do perfil (preencher no primeiro acesso e a cada 30 dias) continua valendo para o resto do sistema; as ACLs de setor só passam a valer quando a CGP/administrador **valida** o Departamento (ver [setores.md](setores.md)).

## `POST /api/chamados`
`multipart/form-data`: `dados` (JSON `{"assunto", "descricao", "local_id"}`; assunto de 3 a 200 caracteres, descrição de 10 a 5000 e o local obrigatório) e até **5 `arquivos`** (imagens coladas com Ctrl+V ou escolhidas, PDF, Word `.docx`, Excel `.xlsx` ou CSV; **5 MB** cada; extensão e **assinatura do conteúdo** conferidas). Resposta `201`: `{"glpi_id", "assunto", "url", "aberto_em", "anexos_enviados", "anexos_com_falha"}`.
- **Anexos no GLPI:** o chamado é criado já com os arquivos (envio multipart com `_filename`, como a tela do GLPI faz), porque o perfil da conta de serviço não tem direito de ligar documentos depois. Se o GLPI recusar os anexos, o chamado é aberto **sem eles** e os nomes vêm em `anexos_com_falha` (a tela avisa).

| Erro | Código | Quando |
|---|---|---|
| `401` / `403` | `nao_autenticado` / `acl_negado` | sem login, ou ACL restringida pelo SuperRoot |
| `422` | `validacao` / `anexo_invalido` | assunto ou descrição fora dos limites; anexo de formato não aceito, vazio, grande, falso ou mais de 5 |
| `429` | `limite_excedido` | mais de **5 chamados por hora** do mesmo usuário |
| `502` | `glpi_indisponivel` | GLPI fora do ar ou recusou o pedido (a tela mantém o texto digitado) |
| `503` | `integracao_desativada` | integração desligada ou sem credenciais |

## `GET /api/chamados/locais`
Localizações do GLPI para a lista obrigatória "Local do problema": `{"itens": [{"id", "nome"}]}`, nome completo em ordem alfabética (ex.: `05º Andar > Lado B`). Mesmos erros do `POST` (`502`, `503`).

## `GET /api/chamados`
Últimos 20 chamados que o usuário abriu pelo SGI (`glpi_id`, `assunto`, `url`, `aberto_em`).

## `GET`/`PUT /api/integracao-glpi` e `POST /api/integracao-glpi/testar` (SuperRoot)
- `GET`: `ativo`, `url_base`, `possui_app_token`, `possui_user_token`, `configurada`, `atualizado_em`, `atualizado_por`. **Os tokens nunca são devolvidos.**
- `PUT`: `{"ativo", "url_base", "app_token"?, "user_token"?, "prefixo_titulo"?, "grupo_atribuido_id"?, "sla_atendimento_id"?, "sla_solucao_id"?, "template_id"?}`. Token vazio ou ausente **preserva** o gravado; nos ids, `0` = nenhum e nulo mantém. O `GET` também devolve esses cinco campos. Os tokens ficam **cifrados** no banco (`app/core/criptografia.py`, a mesma chave da senha de bind do LDAP).
- `POST /testar`: abre e encerra uma sessão no GLPI com o que está gravado; sempre responde `200` com `{sucesso, mensagem, latencia_ms}`.
- Tela: **Administração › Integração GLPI** (`/admin/glpi`).

## O que foi alterado no GLPI (05/10/2026) e como desfazer
Estado anterior guardado: `enable_api = 0`; um único cliente de API ("full access from localhost"); sem a conta `sgi.integracao`; 1.357 chamados e 10.733 notificações na fila. Tudo foi feito pelas **classes do próprio GLPI** (sem SQL direto nos dados do GLPI).
- `enable_api` passou a **1** (`php bin/console config:set enable_api 1`, como `www-data`). Desfazer: `config:set enable_api 0`.
- Cliente de API **"SGI SPI (servidor do SGI)"** (`glpi_apiclients`, id 2), liberado **só para o IP 10.23.0.254**, com `app_token` aleatório (cifrado pelo GLPI; o mesmo valor está cifrado na configuração do SGI). Desfazer: desativar o cliente.
- Conta de serviço **`sgi.integracao`** (usuário id 408, autenticação local, senha aleatória que ninguém conhece), com o perfil **SGI INTEGRAÇÃO** (id 25) na entidade raiz: cópia dos direitos do TECNOLOGIA (que não foi alterado) mais **leitura de Localizações**, necessária para a lista "Local do problema". Desfazer: desativar o usuário e apagar o perfil e `user_token` (chave de API) gerado pelo caminho normal do GLPI ("Regenerar"). O token fica cifrado na configuração do SGI. Desfazer: desativar o usuário.
- O cartão "Helpdesk" da página inicial do portal (`portal_atalhos`, id 9) foi removido.

Testes feitos: sessão aberta e encerrada na API, busca de usuário por login e **um chamado de teste** (#1478, "[TESTE SGI] pode apagar"), criado com a própria conta de serviço como solicitante e **apagado em seguida** (`force_purge`): não gerou notificação na fila e os totais voltaram aos de antes. Depois, um chamado de teste no formato do formulário (grupo "Teste", sem membros, para não enviar e-mail): status 2, SLAs e prazos, localização, requerente e conteúdo conferidos contra o chamado #1477 do formulário; apagado em seguida. **Não validados no GLPI real:** a chave `tickettemplates_id` (modelo de chamado) e o "criado por" assumir o requerente (`users_id_recipient`); se o GLPI ignorar algum, é descartado sem dano.

## Detalhes da API do GLPI 11 que importam
- O login não casa com `equals` na busca de usuário; o SGI busca por `contains` e só aceita o resultado **idêntico** (sem diferenciar maiúsculas).
- O GLPI usa a CA interna do órgão: o cliente do SGI confere o certificado com o repositório **do sistema** (não com o pacote `certifi`).
