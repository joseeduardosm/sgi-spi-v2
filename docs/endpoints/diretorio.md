# Módulo Diretório (`/api/diretorio`)

Tag no OpenAPI: **Diretório**. Implementação:
- rotas: `backend/app/api/routes/diretorio.py`;
- regras: `backend/app/services/servico_diretorio.py`;
- parabéns automático: `backend/app/services/agendador_aniversarios.py`;
- modelos: `backend/app/models/diretorio.py` e colunas novas em `usuarios` (migração `44f539651816`).

Trazido do diretório de **Ramais** e dos **Aniversariantes** do servidor 10.23.1.243, com cartões de visita, aniversariantes do dia/semana/mês, mural de parabéns, favoritos, vCard/QR Code, foto e selo de férias.

## Quem pode o quê

Todas as rotas exigem login (perfil em dia). Não há ACL própria: qualquer usuário consulta o diretório. Cada pessoa altera só a própria foto, as próprias preferências, os próprios favoritos e os próprios recados.

## Regras

- **Quem aparece nos ramais:** usuários **ativos** com nome completo e ramal preenchidos. A foto é opcional (o cartão mostra as iniciais).
- **Busca (`q`):** ignora acentos e maiúsculas; várias palavras = todas precisam aparecer em nome, cargo, setor, ramal, e-mail, andar, prédio ou login. Filtros: `setor` (departamento), `andar`, `predio`, `favoritos` e `em_ferias`.
- **Ordem:** favoritos do usuário logado primeiro, depois ordem alfabética. Paginação `pagina` (1..) e `tamanho` (1 a 200, padrão 24).
- **Selo de férias (automático, sem ação do servidor):** `ferias_inicio` e `ferias_fim` vêm preenchidos enquanto existir um afastamento do tipo `ferias` com situação **`aprovado`** que cobre a data de hoje. Antes do início ou depois do último dia os campos voltam nulos. Pedidos pendentes não geram selo. Só as datas são expostas, nunca o motivo.
- **Chefia e equipe:** `GET /ramais/{id}` traz a chefia (`gestor_id` do perfil) e a equipe (usuários ativos que têm a pessoa como gestor).
- **Aniversariantes:** `periodo=dia` (hoje), `semana` (hoje + 6 dias, inclusive na virada de mês/ano) ou `mes` (todo o mês corrente, inclusive dias que já passaram, com `dias_restantes` negativo). Quem nasceu em 29/02 comemora em 28/02 nos anos comuns. **O ano de nascimento nunca é devolvido.**
- **Opt-out (LGPD):** com `ocultar_aniversario = true` a pessoa some das listas, não tem mural e não recebe o parabéns automático.
- **Mural de parabéns:** um recado (até 500 caracteres) por autor e por ano, aberto para novos recados **somente no dia do aniversário** (depois, o mural continua visível para leitura). Não é possível escrever no próprio mural (`400`), em outro dia (`400`) nem repetir (`409`). O aniversariante recebe um aviso na caixa de Mensagens (link `/`). Quem escreveu pode apagar o próprio recado.
- **Parabéns automático:** uma vez por dia, depois da hora `HORA_PARABENS_ANIVERSARIO` (padrão 8; `-1` desativa), cada aniversariante recebe a mensagem institucional "Feliz aniversário!" na caixa de Mensagens e por e-mail. A chave `aniversario:<usuário>:<data>` e um advisory lock do PostgreSQL impedem repetição entre workers e reinícios.
- **Foto:** `PUT /foto` aceita PNG ou JPG (conferidos pelo conteúdo, até 5 MB); a imagem é recortada em quadrado e reduzida a 400 × 400 em JPEG. Na sincronização do LDAP, a `thumbnailPhoto` do AD é importada **só** para quem não enviou nem removeu a própria foto (`foto_origem = upload` nunca é sobrescrito) e não é regravada se não mudou. As fotos são servidas só a quem está logado.

## Rotas

| Método | Rota | Descrição | Respostas |
|---|---|---|---|
| `GET` | `/api/diretorio/ramais` | Lista paginada de cartões (`PaginaContatos`) | 200, 401, 403, 422 |
| `GET` | `/api/diretorio/filtros` | Setores, andares e prédios existentes (`OpcoesFiltro`) | 200 |
| `GET` | `/api/diretorio/ramais/{contato_id}` | Cartão completo com chefia e equipe (`ContatoDetalhe`) | 200, 404 |
| `GET` | `/api/diretorio/ramais/{contato_id}/vcard` | Arquivo `.vcf` (vCard 3.0) | 200, 404 |
| `GET` | `/api/diretorio/ramais/{contato_id}/qrcode` | PNG de um QR Code com o vCard | 200, 404 |
| `PUT` `DELETE` | `/api/diretorio/favoritos/{contato_id}` | Fixa / solta um contato (idempotente) | 204, 404 |
| `GET` | `/api/diretorio/aniversariantes?periodo=dia\|semana\|mes` | Aniversariantes (`Aniversariante[]`) | 200, 422 |
| `GET` | `/api/diretorio/aniversariantes/{id}/parabens` | Lê o mural (`Parabens[]`) | 200, 404 |
| `POST` | `/api/diretorio/aniversariantes/{id}/parabens` | Deixa um recado (`GravacaoParabens`) | 201, 400, 404, 409, 422 |
| `DELETE` | `/api/diretorio/aniversariantes/{id}/parabens` | Apaga o próprio recado | 204, 404 |
| `GET` `PATCH` | `/api/diretorio/preferencias` | Foto atual e opt-out de aniversário (`Preferencias`) | 200, 422 |
| `PUT` `DELETE` | `/api/diretorio/foto` | Envia (multipart, campo `arquivo`) / remove a própria foto | 200, 400, 422 |
| `GET` | `/api/diretorio/fotos/{contato_id}` | Imagem JPEG 400×400 (cache privado de 1 dia) | 200, 404 |

Erros no formato `{"detalhe", "codigo"}` (`nao_encontrado`, `invalido`, `conflito`, `validacao`...).

## Schemas principais

- **`Contato`**: `id`, `nome`, `cargo`, `ramal`, `foto_url`, `setor`, `email`, `celular`, `whatsapp_url`, `linkedin`, `andar`, `predio`, `local`, `favorito`, `ferias_inicio`, `ferias_fim`.
- **`ContatoDetalhe`**: `Contato` + `chefia` (`ContatoResumo` ou nulo) + `equipe[]`.
- **`Aniversariante`**: `id`, `nome`, `cargo`, `setor`, `ramal`, `email`, `foto_url`, `dia`, `mes`, `e_hoje`, `dias_restantes`, `total_parabens`, `ja_parabenizei`, `pode_parabenizar`.
- **`Parabens`**: `id`, `autor_id`, `autor_nome`, `texto`, `criado_em`, `meu`.
- **`Preferencias`**: `foto_url`, `foto_origem` (`upload` ou `ldap`), `ocultar_aniversario`.

## Banco

| Tabela / coluna | Uso |
|---|---|
| `diretorio_favoritos` | Contatos fixados por usuário |
| `diretorio_parabens` | Recados do mural (único por aniversariante, autor e ano) |
| `usuarios.foto_anexo_id`, `usuarios.foto_origem` | Foto do cartão (anexo em disco) e sua origem |
| `usuarios.ocultar_aniversario` | Opt-out de aniversário |
| `usuarios.linkedin` | Link do LinkedIn do perfil (atalho no cartão de ramais) |

## Configuração

`HORA_PARABENS_ANIVERSARIO` (padrão `8`; `-1` desativa o parabéns automático).
