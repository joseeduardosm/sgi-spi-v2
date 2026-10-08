# Manuais do BookStack (`/api/manuais`, `/api/integracao-bookstack`)

Tags no OpenAPI: **Manuais (BookStack)** e **Integração BookStack**. Implementação:
- `backend/app/api/routes/manuais.py`, `backend/app/services/servico_manuais.py`, `backend/app/schemas/manuais.py`;
- `backend/app/services/bookstack/cliente_bookstack.py` (cliente httpx) e `sanitizacao.py` (HTML seguro);
- `backend/app/api/routes/integracao_bookstack.py`, `backend/app/services/servico_integracao_bookstack.py`, `backend/app/models/integracao_bookstack.py` (tabela `integracao_bookstack`, migração `d7a1c5e9b3f2`);
- frontend: `core/manuais/manuais.service.ts`, `features/manuais/` (estantes, livro, página) e `features/administracao/bookstack/` (rota `/admin/bookstack`).

Os manuais continuam sendo **escritos no BookStack** (https://instrucoes.spi.sp.gov.br); o portal só **lê**, com uma **conta de serviço somente leitura** (token de API cifrado no banco, como no GLPI). O usuário não precisa de conta no BookStack.

## Acesso

- Leitura (`/api/manuais/*`): ACL `manuais` ≥ LEITURA. O recurso nasce **sem regras** (aberto a todo usuário autenticado); o SuperRoot pode restringir em Controle de acesso.
- Configuração (`/api/integracao-bookstack`): só SuperRoot. O token (ID e segredo) nunca é devolvido; ID/segredo vazios no `PUT` preservam os gravados.
- Erros: `503 manuais_indisponivel` (integração desligada ou sem token), `502 bookstack_indisponivel` (BookStack fora do ar ou token recusado), `404 nao_encontrado`, `400 invalido` (imagem), formato `{"detalhe", "codigo"}`.

## Endpoints de leitura

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/manuais` | Estantes com seus livros e `livros_avulsos` (sem estante), em ordem alfabética; `url_origem` = endereço do BookStack |
| `GET` | `/api/manuais/livros/{livro_id}` | Sumário do livro: `sumario` (capítulos com `paginas` e páginas soltas, na ordem do BookStack), `primeira_pagina_id`, `url_origem` |
| `GET` | `/api/manuais/paginas/{pagina_id}` | Página: `html` **sanitizado**, `livro_id/nome`, `capitulo_id/nome`, `atualizado_em`, `anterior`/`proxima` na ordem de leitura e `url_origem` (para editar no BookStack) |
| `GET` | `/api/manuais/busca?q=` | Busca do BookStack (até 30 resultados: página, capítulo, livro). Menos de 2 caracteres → lista vazia. `trecho` traz o termo em `<strong>`; `rota` é a tela do portal |
| `GET` | `/api/manuais/imagem?caminho=` | Repassa uma imagem de `/uploads/...` do BookStack (cache privado de 1 h). Caminho fora de `/uploads/`, com `..`, `//` ou esquema → `400` |

Listas, sumários e páginas ficam em **cache em memória por 5 minutos** (salvar a configuração limpa o cache); a busca e as imagens vão direto ao BookStack.

### Regras do HTML da página

- Lista fechada de marcações (títulos, listas, tabelas, código, imagens, `div/span` com `class`/`id`); sem `script`, `iframe`, `style` nem eventos (`on*`), e só links `http`, `https` e `mailto`.
- **Imagens** da própria instância perdem o `src` e ganham `data-caminho`: o navegador não envia o token ao carregar `<img src>`, então a tela baixa cada imagem por `/api/manuais/imagem` e a exibe. Imagens de outros sites são removidas.
- **Links** para páginas do BookStack (`/link/{id}` ou `/books/{livro}/page/{pagina}`) viram links do portal (`/manuais/paginas/{id}`); os demais abrem em nova aba (`rel="noopener noreferrer"`).

## `GET`/`PUT /api/integracao-bookstack` e `POST /api/integracao-bookstack/testar` (SuperRoot)

- `GET`: `{ativo, url_base, possui_token, configurada, livros_permitidos, atualizado_em, atualizado_por}`.
- `PUT`: corpo `{ativo, url_base, token_id?, token_segredo?, livros_permitidos?}`; grava cifrado, audita (`integracao_bookstack.salvar`, sem o token) e limpa o cache.
- `POST /testar`: lista os livros com a configuração gravada; sempre `200` com `{sucesso, mensagem, latencia_ms, livros_visiveis}` (quantos livros a conta de serviço enxerga).

## Livros exibidos (`livros_permitidos`)

Lista de ids de livros separados por vírgula (ex.: `147`). Com ela preenchida, o portal **só mostra esses livros**: estantes sem eles somem, `GET /api/manuais/livros/{id}` e `/paginas/{id}` de outros livros respondem `404` e a busca descarta resultados de outros livros. Valor com letras → `422`. **Vazio = nenhum livro** (o portal nunca mostra "todos"). Na tela, se sobrar um único livro, o item **Manuais** abre direto nele. Migração `e8b2d6f0a4c3`.

## Como preparar o BookStack

1. Crie um usuário de serviço com um papel **só de leitura** (ver livros, capítulos, páginas e estantes) e a permissão **"Acessar a API do sistema"**.
2. Em *Meu perfil › Tokens de API*, gere um token (ID e segredo).
3. No SGI, **Administração › Integração BookStack**: endereço, ID e segredo, marque "ativa", salve e use "Testar conexão".

O portal mostra a todos os usuários logados **somente os livros de `livros_permitidos`**, mesmo que a conta de serviço enxergue mais.
