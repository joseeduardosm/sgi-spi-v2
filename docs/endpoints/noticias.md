# Módulo Notícias e portal (`/api/noticias`, `/api/portal`)

Tag no OpenAPI: **Notícias e portal**. Implementação:
- rotas: `backend/app/api/routes/noticias.py`;
- regras: `backend/app/services/noticias/servico_noticias.py`, com `imagens.py` (capa 2:1) e `sanitizacao.py` (HTML);
- modelos: `backend/app/models/noticias.py` (migração `aef1af3a69ff`).

Portal de notícias da intranet, que substitui o app de notícias do 10.23.1.243. Tem uma parte **pública** (sem login), que é a página inicial do sistema, e uma **gestão editorial** com aprovação.

## Papéis (recurso `noticias` da ACL)

| Nível | Papel | Pode |
|---|---|---|
| `MODIFICACAO` | **Redator** | Criar notícias; editar os próprios rascunhos e devolvidas; enviar para aprovação (imediata ou agendada) |
| `CONTROLE_TOTAL` | **Aprovador** | Tudo do redator; aprovar, devolver, publicar direto, editar publicadas, arquivar; categorias, atalhos e configuração do portal |
| SuperRoot | Aprovador | Idem, e excluir qualquer notícia |

**Sem nenhuma regra cadastrada no recurso, só o SuperRoot escreve.** Isso é diferente dos outros módulos, onde um recurso sem regras fica aberto. O recurso é criado pela migração; o administrador cadastra redatores e aprovadores na tela de Controle de acesso.

Leitura pública: qualquer pessoa, sem login, vê as notícias **publicadas**.

## Fluxo editorial

`rascunho` → `em_revisao` → `aprovada` (ou `devolvida` → corrige → `em_revisao`); `aprovada` ↔ `arquivada`.

| Ação | Rota | Efeito e avisos |
|---|---|---|
| Criar | `POST /api/noticias` | Rascunho; versão 1 no histórico |
| Enviar para aprovação | `POST /{id}/enviar-revisao` | Exige título, texto, capa e texto alternativo. `publicar_em` vazio = imediata; data passada vira imediata. **Caixa + e-mail aos aprovadores** (chave `noticia-aprovacao:{id}:{versao}`) |
| Aprovar | `POST /{id}/aprovar` `{publicar_em?}` | Aprovada; publica agora ou na data. Encerra a pendência dos aprovadores e avisa o autor (`noticia-aprovada:…`). Vale também de rascunho: o aprovador publica direto |
| Devolver | `POST /{id}/devolver` `{motivo}` | Motivo obrigatório; avisa o autor (`noticia-devolvida:…`) |
| Arquivar / desarquivar | `POST /{id}/arquivar`, `/desarquivar` | Tira do portal / devolve ao portal |
| Excluir | `DELETE /{id}` | Autor (rascunho/devolvida), aprovador (não publicada) ou SuperRoot |

- **Visibilidade:** a notícia aparece no portal quando está `aprovada` e `publicar_em` ≤ agora. É calculada na leitura, então o agendamento não depende de rotina.
- **Aviso ao público:** se a notícia tem `usuarios_aviso`/`setores_aviso`, quando ela aparece no portal os escolhidos recebem caixa de mensagens + e-mail oficial com o link (`noticia-aviso:{id}`).
  - Os setores incluem os setores abaixo deles (membros ou quem tem o setor como Departamento).
  - Se já estiver visível na aprovação, o aviso sai na hora. Se for agendada, sai pela rotina `app.tarefas.mensageria emails` (timer de 2 minutos), que chama `processar_publicacoes`.
- **Comunicado com ciência** (`exige_ciencia`): o aviso sai com prioridade alta e abre em janela; `GET /{id}/ciencias` mostra quem registrou ciência.
- **Histórico:** cada gravação e cada passo do fluxo gravam uma revisão (`GET /{id}/revisoes`). Tudo é auditado (`noticias.*`, `portal.*`).
- **Concorrência:** `versao` no `PUT` → `409 conflito` se outra pessoa salvou antes.

## Capa 2:1

`POST /api/noticias/{id}/capa` (`multipart/form-data`):

| Campo | Descrição |
|---|---|
| `arquivo` | JPG, PNG ou WebP, até 15 MB, conferido pelo conteúdo. Opcional se só mudar o recorte ou o modo |
| `modo` | `recortar` (usa o retângulo) ou `inteira` (arte inteira sobre fundo desfocado dela mesma, sem cortes; bom para cartazes) |
| `recorte` | JSON `{x, y, largura, altura}` em pixels do original. É ajustado para 2:1 dentro da imagem. Vazio = maior retângulo central |

- O original é guardado e são geradas as versões **WebP 1600×800, 800×400 e 400×200** (`capa` na resposta: URL de cada uma). Um novo recorte gera novos arquivos.
- O texto alternativo (`capa_alt`) é obrigatório para enviar para aprovação.

## Texto

`corpo_html` é **sanitizado no servidor** (`nh3`). Só passam `p, br, strong, b, em, i, u, s, h2, h3, h4, ul, ol, li, blockquote, a, hr, table, thead, tbody, tr, th, td`. Links só `http(s)` e `mailto`, com `rel="noopener noreferrer"`. Scripts, estilos, eventos e iframes são removidos.

## Endpoints públicos (sem token)

| Método e caminho | Descrição |
|---|---|
| `GET /api/portal` | `PortalLeitura`: `configuracao`, `slides`, `cartoes` (sem repetir os slides), `atalhos` ativos, `categorias` ativas |
| `GET /api/portal/atalhos/{id}/imagem` | Imagem do atalho (WebP, cache de 1 dia) |
| `GET /api/noticias/publicas` | `PaginaNoticias`. `busca` (título, linha fina e texto), `categoria_id`, `ano`, `mes`, `pagina`, `tamanho` (padrão 12, máx. 48) |
| `GET /api/noticias/publicas/{slug}` | `NoticiaPublica` (conta uma visualização): corpo, anexos e `leia_tambem` (mesma categoria ou mais recentes). Não publicada → `404` |
| `GET /api/noticias/publicas/{slug}/arquivos/{anexo_id}` | Versão da capa ou anexo, exibido no navegador (`inline`, cache de 1 dia) |

**Slider:** `criterio_slider = automatico` usa as fixadas primeiro e depois as mais recentes; `curadoria` usa a ordem manual (`ordem_slider`). Em ambos, notícias com `destaque_ate` vencido ficam fora do slider, mas continuam no arquivo.

## Endpoints da gestão (login)

| Método e caminho | Quem | Descrição |
|---|---|---|
| `GET /api/noticias/papel` | autenticado | `{nivel, redator, aprovador, aguardando_aprovacao, contagem}` |
| `GET /api/noticias/opcoes-setores` · `GET /api/noticias/opcoes-usuarios?busca=` | redator | Opções do público do aviso (setores ativos; usuários ativos, até 20) |
| `GET /api/noticias` | redator | Lista (`situacao`, `busca`). Redator: as próprias + aprovadas/arquivadas; aprovador: todas |
| `POST /api/noticias` | redator | `GravacaoNoticia` → `201 NoticiaGestao` |
| `GET /api/noticias/{id}` / `PUT` / `DELETE` | redator/aprovador | Detalhe (com `acoes` permitidas), edição, exclusão |
| `POST /{id}/enviar-revisao`, `/aprovar`, `/devolver`, `/arquivar`, `/desarquivar` | ver fluxo | |
| `POST /{id}/capa` | quem edita | Ver "Capa 2:1" |
| `POST /{id}/anexos` · `DELETE /{id}/anexos/{anexo_id}` | quem edita | Até 10 anexos (PDF, Office/LibreOffice, TXT, CSV, PNG, JPG), conferidos pelo conteúdo |
| `GET /{id}/arquivos/{anexo_id}` | quem vê na gestão | Capa original, versões e anexos (com token) |
| `GET /{id}/revisoes` · `GET /{id}/ciencias` | quem vê na gestão | Histórico; ciência do aviso |
| `GET /api/noticias/categorias` · `POST` · `PUT /{categoria_id}` | autenticado / aprovador | Categorias (nome único, cor, ordem, ativa) |
| `GET` / `PUT /api/portal/configuracao` | aprovador | Parâmetros do slider (`quantidade_slides` 1–10, `segundos_por_slide` 3–60, `passagem_automatica`, `criterio_slider`, `titulo_sobreposto`, `quantidade_cartoes` 0–12, `exibir_atalhos`, `exibir_todas`, título e subtítulo) e `curadoria` (ids em ordem). O `GET` traz também as `candidatas` |
| `GET /api/portal/atalhos` · `POST` · `PUT /{id}` · `DELETE /{id}` · `POST /ordem` | aprovador (leitura: autenticado) | Atalhos (`multipart`: `titulo`, `url` `http(s)://` ou `/…`, `ativo`, `nova_aba`, `imagem`) |

**`GravacaoNoticia`:** `titulo` (obrigatório), `linha_fina`, `corpo_html`, `categoria_id`, `publicar_em` (vazio = imediata), `destaque_ate`, `fixada`, `exige_ciencia`, `usuarios_aviso`, `setores_aviso`, `capa_alt` e `versao`.

## Erros

| HTTP | `codigo` | Causa |
|---|---|---|
| `400` | `invalido` | Campo obrigatório para enviar, imagem ou anexo recusado, motivo vazio, datas incoerentes |
| `403` | `sem_permissao` | Ação fora do nível ou da situação |
| `404` | `nao_encontrado` | Notícia inexistente, não publicada (rotas públicas) ou fora da visão do redator |
| `409` | `conflito` | `versao` desatualizada ou categoria repetida |
| `422` | `validacao` | Campos fora do formato |

## Consumo no Angular

Código em `frontend/src/app/features/noticias/` (`noticias-api.service.ts`, `noticias.models.ts`, `publico/`, `gestao/`).

| Tela | Rota | Quem |
|---|---|---|
| **Página inicial = portal** (slider, cartões, atalhos) | `/` | Visitante: layout público (`LayoutPortalComponent`, com "Entrar no SGI SPI"). Logado: dentro do layout com barra lateral. A escolha é por `canMatch` em `app.routes.ts` |
| Todas as notícias (busca, categoria, mês na URL, "Carregar mais") | `/noticias` | Público |
| Notícia (capa, texto, anexos com PDF incorporado, "Leia também", copiar link) | `/noticias/:slug` | Público |
| Gestão: lista com abas por situação | `/noticias/gestao` | Redator/aprovador (Módulos › Notícias). Visitante vai ao login |
| Editor: texto formatado, capa com recorte 2:1 (arrastar e zoom) ou imagem inteira, publicação imediata/agendada, aviso a setores e pessoas, ciência, anexos, prévia, aprovar (verde) / devolver (vermelho claro), histórico | `/noticias/gestao/nova`, `/noticias/gestao/:id` | Redator/aprovador |
| Configurar portal: parâmetros e prévia do slider, curadoria, atalhos, categorias | `/noticias/gestao/portal` | Aprovador |

- As imagens e anexos da gestão exigem token: a diretiva `appImagemAutenticada` baixa como blob. As do portal são URLs públicas com cache.
- O recorte enviado ao servidor está em pixels da imagem original (`RecorteCapaComponent`).

## Migração do 10.23.1.243

```bash
SGI243_SENHA=... backend/.venv/bin/python scripts/extrair-noticias-243.py <pacote>      # somente leitura: tabelas por \copy read only e arquivos por SFTP
cd backend && ANEXOS_DIRETORIO=/tmp/ensaio .venv/bin/python ../scripts/migrar-noticias-243.py <pacote>   # ensaio
cd backend && .venv/bin/python ../scripts/migrar-noticias-243.py <pacote> --gravar     # grava (--substituir recarrega)
```

- `PUBLICADA` → `aprovada` com a data original (aprovador "Migração 10.23.1.243", autor "Portal 10.23.1.243"); `RASCUNHO` → `rascunho`.
- Texto puro em parágrafos, com os endereços viram links.
- **Capa:** proporção entre 1,9 e 2,1 → recorte 2:1 central; demais → "imagem inteira".
- Categoria sugerida pelo título; atalhos com endereço relativo ganham o domínio da intranet antiga.
- **Carga de 30/09/2026:** 23 notícias (22 publicadas, 1 rascunho), 3 anexos, 4 atalhos, 13 capas recortadas e 10 inteiras. Nenhum aviso foi disparado e nada foi alterado no 243.
