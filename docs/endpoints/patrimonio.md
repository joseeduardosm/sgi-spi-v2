# Patrimônio: bens móveis do prédio SPI (`/api/patrimonio`)

Tag no OpenAPI: **Patrimônio**. Implementação:
- rotas: `backend/app/api/routes/patrimonio.py`; schemas: `backend/app/schemas/patrimonio.py`;
- regras: `backend/app/services/patrimonio/` (`servico_localizacoes`, `servico_bens`, `servico_movimentacoes`, `servico_classificacoes`, `servico_baixas`, `servico_paineis`, `servico_parametros`, `depreciacao`, `exportacao`, `base`);
- modelos: `backend/app/models/patrimonio.py` (`patrimonio_localizacoes`, `patrimonio_grupos`, `patrimonio_bens`, `patrimonio_fotos`, `patrimonio_eventos`, `patrimonio_movimentacoes`, `patrimonio_itens_movimentacao`, `patrimonio_classificacoes`, `patrimonio_itens_classificacao`, `patrimonio_baixas`, `patrimonio_itens_baixa`, `patrimonio_parametros`); migração `a1c4e7b9d2f6`.

## Finalidade

Controla o patrimônio mobiliário do prédio SPI: onde cada bem está, por onde passou, quem o cadastrou e alterou, quanto vale hoje e se ainda está em garantia. O levantamento é feito em campo, **pelo celular** (leitura de QR code ou código de barras, cadastro rápido, uso com sinal fraco). Cobre cadastro, movimentação entre salas, classificação como inservível ou extraviado e baixa. Ficam de fora os bens imóveis, os bens de consumo do almoxarifado e a integração com o SAM.

## Permissões (recurso ACL `patrimonio`)

O recurso é criado pela migração **sem regras** (só o SuperRoot acessa até a administração conceder os níveis).

| Nível | O que pode |
|---|---|
| `LEITURA` | Ver bens, locais, histórico, trajeto, movimentações, painéis e exportar |
| `MODIFICACAO` | Cadastrar e editar bens (avulso e em lote) e **solicitar** movimentações, classificações (inservível/extraviado) e baixas. Não aprova nenhuma e não muda o local de um bem diretamente |
| `CONTROLE_TOTAL` (ou SuperRoot) | Autorizar, recusar e confirmar o recebimento das movimentações; aprovar ou recusar classificações e baixas; cadastrar salas e grupos; ajustar a UFESP; **mudar o local de um bem sem movimentação** (motivo obrigatório); devolver inservível/extraviado a Ativo |

**Quem solicita nunca aprova a própria solicitação** (`403 auto_aprovacao`), mesmo com controle total.

## Localizações

Árvore de até cinco níveis: prédio SPI, andar (-1 = subsolo, 0 = térreo, até 13), lado (A ou B), sala e um nível reservado. A migração gera tudo (15 salas por lado). O código da sala junta andar, lado e número: `05A01` a `05B15`, `00A01` a `00B15`, `-1A01` a `-1B15`; é único. Na tela a sala aparece curta: `5º andar › 05A03 — Setor Financeiro`.

Setor e responsável são informados **no primeiro cadastro de bem feito na sala**: sem eles, o cadastro devolve `409 sala_sem_responsavel` e a tela pede os dados (`PUT /localizacoes/{id}/dados`, com MODIFICACAO enquanto faltam; depois só CONTROLE_TOTAL). **Trocar o responsável** atualiza todos os bens da sala, com evento no histórico de cada um; ao ser movimentado, o bem passa ao responsável da sala de destino. Sala com bens não é excluída, só inativada. O depósito de inservíveis é uma sala cujo setor se chama **"Depósito inservível"**.

## Rotas

| Método e caminho | Quem | Descrição |
|---|---|---|
| `GET /acesso` | LEITURA | `{ usuario_id, pode_operar, pode_administrar }` |
| `GET /opcoes-setores`, `GET /opcoes-usuarios?busca=` | MODIFICACAO | Setores ativos e usuários (até 20) para informar setor e responsável da sala |
| `GET /localizacoes` | LEITURA | Lista plana com `pai_id`, código, rótulo curto, setor, responsável, `deposito_inservivel` e total de bens |
| `POST /localizacoes/lados/{lado_id}/salas` | CONTROLE_TOTAL | `{ numero }`: cria a sala (`409` se o código existir) |
| `PUT /localizacoes/{id}/dados` | MODIFICACAO (só se faltam) / CONTROLE_TOTAL | `{ setor_id, responsavel_id }` |
| `PUT /localizacoes/{id}`, `DELETE /localizacoes/{id}` | CONTROLE_TOTAL | Renomear/inativar; excluir (`409` com bens) |
| `POST /localizacoes/andares/{andar_id}/areas-comuns` | CONTROLE_TOTAL | `{ nome, sigla? }`: cria uma **área comum** (hall dos elevadores, copa, escada...) direto no andar, **fora da numeração A/B e sem lado**. O código junta o andar e a sigla (`05H`, `-1H`; padrão `H`, 1 a 4 letras); `409` se já existir; `400` se o nó não for um andar. Como toda sala, precisa de setor e responsável antes do primeiro bem (`409 sala_sem_responsavel`). Na tela de Locais, botão **+ Área comum** em cada andar |
| `GET /grupos`, `POST /grupos`, `PUT /grupos/{id}`, `DELETE /grupos/{id}` | LEITURA / CONTROLE_TOTAL | Grupos de material com `vida_util_meses`, `residual_percentual` e `deprecia` |
| `GET /prefixos`, `POST /prefixos`, `PUT /prefixos/{id}`, `DELETE /prefixos/{id}` | LEITURA / CONTROLE_TOTAL | Prefixos da chapa (SPI, SLT, DERSA, ARTESP, ARSESP e outros criados em Parâmetros). `GET` traz os ativos (`todos=true` inclui inativos), o padrão primeiro. `POST` cria (só letras e números, em maiúsculas; `409` se já existe). `PUT` troca `padrao` ou `ativo` (o padrão precisa estar ativo e não pode ser desmarcado: escolha outro; `409`). `DELETE`: o padrão e prefixos com bens só podem ser inativados (`409`) |
| `GET /parametros`, `PUT /parametros` | LEITURA / CONTROLE_TOTAL | `{ ufesp }` |
| `GET /bens` | LEITURA | Paginada; filtro `q` = **busca em qualquer informação do bem**: chapa, série, descrição, marca, modelo, fornecedor, nota fiscal, UGE/UA/divisão, observações, grupo, responsável e **local** (código ou nome da sala, do andar, do lado ou do prédio: traz tudo o que está dentro). Várias palavras separadas por espaço se somam (todas precisam aparecer, em qualquer campo: `notebook dell 05A01`); outros filtros:  `situacao`, `localizacao_id` (andar, lado ou sala), `grupo_id`, `conservacao`, `garantia`, `contabeis_pendentes`, `incluir_baixados`; ordem `ordenar_por` (chapa, descricao, sala, situacao, conservacao, grupo, valor_aquisicao, valor_atual, data_aquisicao, garantia, responsavel, marca, modelo, numero_serie, uge, ua, divisao, nota_fiscal, fornecedor, criado_em) e `direcao` (asc/desc); coluna inválida: `400` |
| `POST /bens` | MODIFICACAO | Cadastra (`201`; `200` no reenvio de um `id_cliente`) |
| `GET /bens/sugestoes-descricao?q=` | LEITURA | Descrições já cadastradas que casam com o texto (mínimo de 2 caracteres, até 8; começam pelo texto e as mais usadas primeiro), para o autocompletar do cadastro |
| `GET /bens/chapa/{chapa}` | LEITURA | Leitura de QR/código de barras (`404`: a tela abre o cadastro com a chapa preenchida) |
| `GET /bens/{id}`, `PUT /bens/{id}` | LEITURA / MODIFICACAO | Detalhe; altera só os campos enviados (um evento por campo) |
| `POST /bens/{id}/localizar` | MODIFICACAO | `{ localizacao_id }`: levantamento inicial. Informa a sala de um bem que ainda está em "NECESSÁRIO ATUALIZAR" (sem local), sem movimentação nem aprovação; evento `localizou` no histórico e no trajeto. Bem que já tem sala: `409 bem_ja_localizado`; sala sem setor e responsável: `409 sala_sem_responsavel`; extraviado, baixado, com classificação pendente ou em movimentação: `409` |
| `POST /bens/{id}/local` | CONTROLE_TOTAL | `{ localizacao_id, motivo }`: ajuste direto do local |
| `POST /bens/{id}/reverter` | CONTROLE_TOTAL | `{ justificativa, localizacao_id? }`: devolve inservível/extraviado a Ativo (o extraviado informa a sala do achado) |
| `POST /bens/{id}/fotos`, `DELETE /bens/{id}/fotos/{foto}`, `GET /bens/{id}/fotos/{foto}/arquivo` | MODIFICACAO / LEITURA | Até 3 fotos PNG/JPG (`409 limite_fotos`) |
| `GET /bens/{id}/historico?campo=` | LEITURA | Linha do tempo, ou só o histórico de um campo |
| `GET /bens/{id}/trajeto` | LEITURA | Locais por onde passou, com quem pediu e quem autorizou |
| `GET /movimentacoes`, `GET /movimentacoes/{id}` | LEITURA | Filtros `status`, `de`, `ate`, `solicitante_id`, `origem_id`, `destino_id` |
| `POST /movimentacoes` | MODIFICACAO | `{ bens_ids[], chapas[], destino_id, motivo, id_cliente? }` (`chapas` serve ao pedido feito sem sinal; chapa desconhecida: `404`) |
| `POST /movimentacoes/{id}/autorizar`, `/recusar` | CONTROLE_TOTAL | A recusa exige `{ motivo }` |
| `POST /movimentacoes/{id}/cancelar` | Solicitante | Só enquanto pendente |
| `POST /movimentacoes/{id}/receber`, `/concluir` | CONTROLE_TOTAL | `{ bem_id }`: o bem muda de local na hora; concluir encerra o recebimento |
| `GET /classificacoes`, `GET /classificacoes/{id}` | LEITURA | Listas de inservíveis/extraviados. `?solicitante_id=` traz as listas que a pessoa montou **e** as compartilhadas com ela. A lista traz `colaboradores[]` (`id`, `nome`) |
| `POST /classificacoes` | MODIFICACAO | `{ tipo: inservivel\|extraviado, id_cliente? }`: começa o rascunho |
| `POST /classificacoes/{id}/bens`, `DELETE .../bens/{item}` | MODIFICACAO | `{ chapa }` ou `{ bem_id }` |
| `POST /classificacoes/{id}/justificativa` | MODIFICACAO | `{ itens_ids[], justificativa, categoria? }`: **`categoria` obrigatória na lista de inservíveis** (`ocioso`, `recuperavel`, `antieconomico` ou `irrecuperavel`, a classificação do desfazimento do Decreto 9.373/2018; `400` se faltar e na lista de extraviados não se informa); vale para todos os itens marcados. Enviar exige justificativa **e** categoria em todos (`409 sem_justificativa`). Ao aprovar, o bem ganha `categoria_inservivel` (marcador "Inservível · Antieconômico" na lista e na ficha; some ao reverter a Ativo; os inservíveis antigos ficam sem categoria) e o histórico do bem registra `[Categoria] justificativa`. A justificativa: **HTML do editor rico** (sanitizado pela API) ou texto simples; o texto, sem as tags, precisa ter de **10 a 2000 caracteres** (`400` fora disso). Grava a mesma justificativa em cada item marcado, substituindo a anterior. Nos relatórios (PDF/Excel) e no histórico do bem, a justificativa vai como texto puro |
| `POST /classificacoes/{id}/justificativa/remover` | MODIFICACAO | `{ itens_ids[] }`: **exclui a justificativa e a categoria** dos itens (só em rascunho, por quem monta ou colabora; `409` depois de enviada, `403` para os demais). **Editar** é gravar de novo com `POST …/justificativa` (substitui texto e categoria). Na tela: "Editar justificativa" e "Excluir justificativa" em cada bem e "Excluir justificativa" em lote nos selecionados; sem justificativa a lista não pode ser enviada |
| `PUT /classificacoes/{id}/colaboradores` | MODIFICACAO | `{ usuarios_ids[] }`: **compartilha a lista** (só em rascunho e só quem a montou; `403`/`409` nos demais casos). Substitui os colaboradores; lista vazia deixa de compartilhar. Quem recebe faz **tudo o que o solicitante faz** (incluir e tirar bens, justificar, anexar, **enviar para aprovação** e descartar), recebe o aviso `patrimonio.classificacao_compartilhada` e **não pode aprovar a lista** (`403 auto_aprovacao`), nem o solicitante. O resultado da decisão é avisado ao solicitante e aos colaboradores |
| `POST/GET /classificacoes/{id}/itens/{item}/anexo` | MODIFICACAO / LEITURA | Extraviado: boletim, e-mail ou foto; inservível: foto |
| `POST /classificacoes/{id}/enviar` | MODIFICACAO | Os bens ficam com "Classificação pendente" |
| `POST /classificacoes/{id}/decisao` | CONTROLE_TOTAL | `{ aprovados_ids[], motivo_recusa? }`: aprova tudo, parte ou recusa |
| `DELETE /classificacoes/{id}` | MODIFICACAO | Descarta o rascunho |
| `GET /baixas`, `GET /baixas/{id}`, `POST /baixas`, `DELETE /baixas/{id}` | LEITURA / MODIFICACAO | `POST` exige `{ classificacao_id }`: a baixa **herda os bens aprovados de uma lista de inservíveis/extraviados já aprovada**, uma baixa por lista (`409 lista_nao_aprovada`, `409 conflito`, `409 sem_bens`; `422` sem a lista). Status: `rascunho` → `aguardando_aceite` → `concluida` (ou `recusada`) |
| `POST /baixas/{id}/bens`, `DELETE .../bens/{item}` | MODIFICACAO | Só em baixas antigas (sem lista de origem); nas novas, `POST` responde `409` e `DELETE` tira um bem do rascunho (a lista precisa ficar com ao menos um) |
| `POST /baixas/{id}/motivo` | MODIFICACAO | `{ itens_ids[], motivo (alienacao, doacao, transferencia, inutilizacao, extravio), processo }` |
| `POST /baixas/{id}/enviar` | MODIFICACAO | Exige motivo e processo em todos os itens (`409 sem_motivo`); **gera o termo em PDF** (para o SEI) e deixa a baixa `aguardando_aceite` (aceite da autoridade, **externa**); avisa o controle total |
| `POST /baixas/{id}/conclusao` | CONTROLE_TOTAL | `multipart` com `arquivo` (PDF do **de acordo da autoridade**, na maioria das vezes a publicação no D.O.E.): conclui a baixa e os bens viram **Baixado**. Quem montou a baixa também pode (a decisão é externa); `409` se não aguarda aceite; `400` se não for PDF |
| `POST /baixas/{id}/recusa` | CONTROLE_TOTAL | `{ motivo }`: a autoridade não deu o aceite; os bens seguem inservíveis e a lista pode receber outra baixa |
| `GET /baixas/{id}/conclusao` | LEITURA | PDF do de acordo / D.O.E. anexado (`404` antes de concluir) |
| `GET /baixas/{id}/termo` | LEITURA | Termo de baixa (PDF) |
| `GET /classificacoes/{id}/relatorio`, `GET /baixas/{id}/relatorio` | LEITURA | `?formato=pdf` (padrão) ou `xlsx`. Relatório das listas de inservíveis, extraviados e da baixa (rascunho, pendente ou decidida). Ver "Relatórios consolidados" abaixo |
| `GET /painel` | LEITURA | `agrupar_por` (andar, sala, setor, grupo), `situacao`, `conservacao`, `garantia` |
| `GET /painel/grupo?agrupar_por=&chave=` | LEITURA | Bens de uma barra do gráfico |
| `GET /exportar/{relatorio}?formato=xlsx\|pdf` | LEITURA | `bens`, `fora-garantia`, `painel`, `movimentacoes` (mesmos filtros) |

## Regras de negócio

- **Cadastro:** obrigatórios a chapa (qualquer formato; única sem diferenciar maiúsculas) **ou, se o bem não tem patrimônio, o número de série**, descrição, sala, conservação (1 péssimo a 5 ótimo), situação (**Ativo** ou **Em manutenção**) e origem (próprio ou terceiros). Opcionais: grupo, UGE, UA, divisão, valor de aquisição e atual, data de aquisição, meses de garantia, marca, modelo, número de série, nota fiscal, fornecedor, fotos e observações. O responsável vem da sala.
- **Garantia:** `garantia_fim` = data de aquisição + meses; sem a data a garantia é `indefinida`.
- **Dados contábeis pendentes:** sem grupo, valor ou data de aquisição. O bem entra na contagem, fica fora dos totais de valor e aparece em lista própria. Valor abaixo de 45 UFESP e vida útil menor que dois anos: aviso de que o bem não é patrimoniável.
- **Histórico:** `patrimonio_eventos` é só de inserção (campo, anterior, novo, autor, origem = IP e canal do cabeçalho `X-Canal`: `web`, `celular` ou `offline`); no PostgreSQL um gatilho barra UPDATE e DELETE.
- **Movimentação:** solicitação → autorização → recebimento (parcial) → conclusão. Bem em movimentação, com classificação pendente, extraviado ou baixado não entra em outra (`409`). Inservível só vai para sala do setor "Depósito inservível" (`409 destino_invalido`). Os que não chegaram ficam na origem, e o histórico registra `nao_chegou`.
- **Inservível/extraviado:** só bens Ativos ou Em manutenção. Aprovados mudam de situação; recusados voltam ao que eram. O inservível continua onde está; o extraviado guarda a última sala e não se movimenta.
- **Baixa:** herda uma lista aprovada de inservíveis/extraviados (uma baixa por lista), aguarda o aceite externo da autoridade e conclui com o PDF do de acordo/D.O.E. anexado por quem tem controle total (migração `a2d7b9e1c5f3`: baixas antigas `pendente` viram `aguardando_aceite` e `aprovada`/`parcial` viram `concluida`, sem PDF); baixado sai dos painéis e nunca é excluído, nem editado nem movimentado (`409 bem_baixado`). A baixa no módulo não baixa o bem no SAM: o termo serve para isso.
- **Depreciação** (Política de Bens Móveis da SEFAZ-SP): linear, mês a mês, a partir do mês seguinte à disponibilidade; depreciação mensal = (custo − residual) ÷ vida útil; para no residual (10%) e o bem continua ativo. Bens de terceiros e culturais não depreciam. Nos painéis vale o valor atual informado; sem ele, o calculado. A vida útil por grupo é parâmetro editável (a tabela oficial ainda será obtida; mobiliário provisório de 10 anos).
- **Idempotência (uso offline):** bens, movimentações, classificações e baixas aceitam `id_cliente`; o reenvio devolve o registro existente com `200`.

### Erros

| HTTP | `codigo` | Causa |
|---|---|---|
| `400` | `invalido` | Campos inválidos, justificativa curta, motivo vazio, arquivo recusado |
| `403` | `acl_negado` / `auto_aprovacao` | Sem o nível exigido, ou aprovando a própria solicitação |
| `404` | `nao_encontrado` | Bem, local, lista, movimentação ou arquivo inexistente |
| `409` | `conflito`, `sala_sem_responsavel`, `sala_inativa`, `em_movimentacao`, `classificacao_pendente`, `bem_extraviado`, `bem_baixado`, `bem_invalido`, `destino_invalido`, `sem_justificativa`, `sem_motivo`, `limite_fotos` | Regra de estado violada |

## Avisos e auditoria

- **Avisos** (mensagens do sistema): quem autoriza é avisado das movimentações, classificações e baixas pendentes (categoria `pendencia`); o solicitante, das decisões.
- **Trilha:** o histórico do bem (`patrimonio_eventos`) é a trilha de auditoria do módulo: guarda o que mudou, quem, quando e de onde, e não se apaga.

## Consumo no Angular

**Inservíveis e Extraviados separados (telas).** Cada um tem a sua aba e as suas listas: `/patrimonio/inserviveis` e `/patrimonio/extraviados` (a lista de uma aba só mostra o próprio tipo; links antigos de `/inserviveis/{id}` de uma lista de extraviados redirecionam para a aba certa, e os avisos ao controle total já apontam para a aba do tipo). A API é a mesma (`/classificacoes`, `tipo` = `inservivel` ou `extraviado`). **Só inservíveis e extraviados entram na baixa** (`409 bem_invalido` para os demais). O filtro `situacao` de `GET /bens` aceita **uma ou várias situações separadas por vírgula** (ex.: `inservivel,extraviado`; valor desconhecido: `400`).

**Relatórios consolidados (inservíveis, extraviados e baixa).** O **PDF** segue a estratégia dos documentos consolidados de Contratos (identidade do Governo de SP, A4 paisagem, páginas numeradas em sequência "Página X de N"): 1) **índice** clicável na primeira página; 2) o **relatório**, com as colunas *Item* (1, 2, 3...), *Chapa / Série*, *Descrição* (descrição - marca - modelo), *Local*, *Fotos (últimas)* (até 3 miniaturas, com **data, hora e quem registrou** a última, e o link "Ampliar fotos"), *Justificativa* (na baixa: motivo e processo) e *Anexo* (link "Anexo N" que leva ao anexo daquele item), mais as linhas de assinatura; 3) uma página de **fotos em tamanho grande** por bem (cada foto com nome, data, hora e quem registrou); 4) o **anexo de cada item** (boletim de ocorrência, e-mail ou foto do extravio ou do inservível), cada um com contracapa; PDF enviado entra como está, imagem vira página, formato não exibível fica só com a contracapa avisando. Na **baixa**, o anexo de cada bem é o da classificação aprovada (extraviado ou inservível) que a originou. **Extraviado tem espaço para anexo**: um por item (`POST /classificacoes/{id}/itens/{item}/anexo`: boletim de ocorrência, e-mail ou foto); no inservível o anexo é uma foto. O **Excel** traz as mesmas colunas, com a miniatura da última foto na célula (link "Ampliar" para a aba **Fotos**, com as fotos grandes, data, hora e quem registrou) e o nome do anexo; os arquivos anexos seguem no PDF. Na tela, os botões **Relatório PDF** e **Relatório Excel** ficam no topo de cada lista e de cada baixa.

**Busca com sugestões (combobox).** Nos campos "chapa ou número de série" da solicitação de movimentação, das listas de inservíveis e extraviados e da baixa (`app-busca-bem`), ao digitar 2 ou mais caracteres a tela chama `GET /bens?q=<trecho>&tamanho=8` (a busca já olha chapa, número de série e descrição) e mostra os bens para clicar; escolher um inclui o bem **pelo id** (vale para bem sem chapa ou com número de série repetido). Enter sem escolher uma sugestão manda o texto como estava (o servidor confere a chapa ou o número de série). As linhas das listas de inservíveis e baixa mostram também `Série <número>` quando o bem tem chapa e número de série (`numero_serie` nos itens). Sem conexão, o campo segue como texto livre.

**Chapa ou número de série em tudo.** `GET /bens/chapa/{codigo}`, a solicitação de movimentação (`chapas`), a inclusão nas listas de inservíveis/extraviados e na baixa, e a leitura de código no recebimento aceitam **a chapa ou o número de série** (sem diferenciar maiúsculas). Vale primeiro a chapa (com o prefixo padrão para só dígitos); depois o número de série. Se o número de série existir em mais de um bem, a API responde `409` (`ambiguo`) pedindo a chapa; sem nenhum, `404`. Os itens da movimentação trazem `numero_serie` para conferir o recebimento por leitura do número de série (bem sem chapa).

**Ler o código da porta para escolher a sala.** O campo de sala (cadastro avulso e em lote, destino da movimentação, ajuste de local e sala da lista de inservíveis) tem um **botão de câmera** dentro dele: lê o código ou QR da porta (`05A03`; aceita `5a3`, `05-A-03`, `-1A1`, e o endereço, se o QR trouxer um) e escolhe a sala, respeitando as regras do campo (sala inativa, depósito de inservíveis e sala de origem são recusadas com aviso). Sem mudança de API: a leitura usa o código da sala já devolvido por `GET /localizacoes`.

**Tela de edição igual à de adicionar.** Em `/patrimonio/bens/{id}` › **Editar**, o formulário segue o desenho do cadastro: identificação com `[prefixo ▾][número][câmera]` para a chapa e `[campo][câmera]` para o número de série (o leitor lê QR code e código de barras e separa o prefixo quando ele vem no código), descrição, **botões de escolha** para conservação (1 a 5), situação e origem, e "Mais dados" aberto. A chapa é separada em prefixo e número ao abrir (chapa antiga sem prefixo fica em "Sem prefixo") e, ao salvar, só vai se mudou: `PUT /bens/{id}` com `chapa` (o número) e `prefixo`; o servidor junta e completa com zeros. Situação de inservível e extraviado não se edita aqui (só pela reversão).

**Tela de cadastro compacta (celular primeiro).** "Adicionar bem" e "Cadastro em lote" usam campos de 42 px (fonte de 16 px para o celular não ampliar a tela). Chapa = `[prefixo ▾][número][câmera]` e número de série = `[campo][câmera]`, cada um numa linha só, com o botão de ler código como ícone. Estado de conservação (1 a 5), Situação e Origem são **botões de escolha** lado a lado (um toque, sem abrir lista). A barra Salvar/Cancelar fica fixa no rodapé. Sem mudança de API.

**Prefixo e número da chapa.** `POST /bens` e `PUT /bens/{id}` aceitam `prefixo` junto com `chapa`: com prefixo, `chapa` é só o número e o servidor **junta ao salvar**. Número só com dígitos ganha zeros à esquerda até 6 (`231` → `000231`, resultando em `SPI000231`); texto que não é só número (letras, hífen) é aceito como foi digitado, depois do prefixo (`SLTAB-9`); se o número já começa com o prefixo (código lido da etiqueta), o prefixo não repete. Prefixo inexistente ou inativo: `404`. Sem `prefixo`, a chapa é gravada como veio (compatível com chamadas antigas). A unicidade vale para a chapa completa (`SPI000231` e `SLT000231` são bens diferentes). `GET /bens/chapa/{chapa}` com só dígitos (etiqueta antiga) tenta também com o prefixo padrão. A migração `a2c8e4f6b1d9` criou a tabela `patrimonio_prefixos` com os cinco prefixos (SPI padrão) e passou as chapas só numéricas já existentes para `SPI` + 6 dígitos, com um evento "alterou" no histórico de cada bem. Na tela, o cadastro traz o prefixo padrão selecionado; **no cadastro em lote** o prefixo escolhido **permanece** de um bem para o outro e pode ser trocado no meio do lote.

Rota `/patrimonio` (item "Patrimônio" na barra lateral; `guardaAcl` com `acl: 'patrimonio'`), com telas pensadas primeiro para o **celular**: bens, cadastro avulso e em lote, leitura de código pela câmera, movimentações (solicitar, autorizar, receber), inservíveis e extraviados, baixa, localizações, grupos/parâmetros, painel e relatórios. Funciona com sinal fraco: guarda no aparelho (IndexedDB) e envia quando a conexão volta.

## Bens sem chapa e importação do GLPI

- A `chapa` é opcional: o bem sem patrimônio se identifica pelo número de série. Nas respostas (`BemLeitura`, itens de movimentação, classificação e baixa, linhas dos painéis), `chapa` vem `null` nesses bens e o campo **`rotulo`** traz o texto para exibir: a chapa ou `S/N <número de série>` (ou "Sem identificação"). Sem chapa e sem série, o cadastro devolve `400`.
- `PUT /bens/{id}` com `chapa` vazia remove a chapa, desde que o bem tenha número de série. Movimentar, classificar ou baixar um bem sem chapa é feito por `bem_id` (não há chapa para ler).
- Os ativos do GLPI (computadores, monitores, impressoras, telefones, periféricos e equipamentos de rede) são trazidos por `scripts/importar-glpi.py` (simulação por padrão; `--aplicar` grava; repetir não duplica, pelo `id_cliente` `glpi:<tipo>:<id>`). Vêm só três informações: o patrimônio vira a chapa (vazio ou "N/C" = sem chapa; repetido fica só no primeiro), o número de série vai para o campo próprio e a descrição é o tipo (Notebook, Switch, Desktop, Monitor...) seguido de marca e modelo. Nada vai para as observações, e todos os bens entram na localização "NECESSÁRIO ATUALIZAR" (sem andar), para ajuste posterior por movimentação.
- **Colunas da lista de bens:** a visão em lista mostra as colunas que o usuário escolheu, na ordem que escolheu, guardadas na conta (`/api/preferencias/colunas/patrimonio.bens`, ver [navegacao.md](navegacao.md)). Qualquer dado do bem pode virar coluna (inclusive número de série, marca, modelo, observações, quem cadastrou e datas). `BemLeitura` ganhou `criado_por_nome`, e `ordenar_por` aceita também `origem`, `observacoes`, `atualizado_em` e `baixado_em`.
- **Levantamento inicial:** os bens vindos do GLPI ficam na localização "NECESSÁRIO ATUALIZAR" (sala de código `ATUALIZAR`, sem andar). Na tela de cadastro, ao digitar a chapa de um bem assim, a tela carrega os dados e, no **Salvar**, pergunta "Esse bem já está no sistema. Confirmar que ele está na sala X?"; o **Sim** chama `POST /bens/{id}/localizar`. Se o bem já tem sala diferente da escolhida, a pergunta é a de registrar movimentação; se for a mesma sala, só avisa. Exige internet.

## Importação das planilhas do SAM (Visão Geral)

- `scripts/importar-patrimonio-sam.py` cadastra os bens das planilhas `apoio/patrimonio/VisaoGeral_ATIVOS.xlsx` e `VisaoGeral_BAIXADOS.xlsx` (simulação por padrão; `--aplicar` grava; repetir não duplica, pelo `id_cliente` `sam:<chapa>`). A chapa é a sigla do SAM mais o número com 6 dígitos (`2835` → `SPI002835`). Bem cuja chapa já existe só recebe os dados do SAM que ainda não tinha (descrição, sala, situação e conservação não mudam); constar na planilha de baixados marca o bem como `baixado`. Bens novos entram na sala "NECESSÁRIO ATUALIZAR"; cada código de grupo do SAM vira um grupo de material (`SAM-<código>`, com a vida útil mais comum). Conservação: Novo e Ótimo = 5, Bom = 4, Antieconômico = 2; baixados = 1. O texto original fica em `sam.estado_sam`. Cada bem ganha um evento `cadastrou` (origem "importação SAM").
- Novo objeto **`sam`** em `BemLeitura` (`DadosSam`, `null` nos bens sem dados do SAM): `item_codigo`, `uo`, `tipo_sam`, `conta_contabil`, `conta_depreciacao`, `depreciacao_acumulada`, `depreciacao_mensal`, `vida_util_meses`, `meses_depreciados` (o `8` de `8/120`), `ultima_depreciacao_ref` (AAAAMM), `data_incorporacao`, `empenho`, `numero_documento`, `ultimo_historico`, `data_ultimo_historico`, `estado_sam`, `destino_uge` e `responsavel_sam`. São só leitura (não há campo de edição) e aparecem na seção "Dados do SAM" do detalhe do bem.

**Número das relações (`#n`).** Cada lista de inservíveis, de extraviados e cada baixa recebe o campo `numero` (inteiro, único e crescente, a mesma sequência para os três: `#12` nunca se repete entre eles), devolvido em `ClassificacaoLeitura` e `BaixaLeitura`. A numeração é atribuída na criação (`POST /classificacoes`, `POST /baixas`); as já existentes foram numeradas pela data de criação na migração `e6a2c4d8b1f3`. As telas mostram o número como `#n` nos cartões e no topo da relação.

**Relacionar uma sala inteira.** Nas telas de inservíveis, extraviados e baixa, o campo "Relacionar todos os bens de uma sala" lista (`GET /bens?localizacao_id=…&tamanho=200`) os bens que a relação aceita e abre a confirmação "Você deseja relacionar os X ativos da sala Y?" com chapa, série e descrição. Ao confirmar, a tela inclui um a um (`POST /classificacoes/{id}/bens` ou `/baixas/{id}/bens` com `bem_id`); os que a API recusar são contados num aviso. Não há endpoint novo.

**Lista de inservíveis/extraviados: pesquisar e selecionar.** O campo de adicionar usa a busca acima (qualquer informação do bem). Na lista em rascunho, a pesquisa interna filtra os bens já incluídos por chapa, série, descrição, marca, modelo, grupo, responsável, nota fiscal, fornecedor, observações, sala e justificativa (várias palavras se somam); "Selecionar todos" marca os visíveis, e o seletor "Selecionar a sala…" marca de uma vez todos os bens de uma sala da lista. Os itens da lista (`itens[]`) trazem `marca`, `modelo`, `grupo_nome`, `responsavel_nome`, `nota_fiscal`, `fornecedor` e `observacoes` para isso.

**Baixa compartilhada.** `PUT /baixas/{id}/colaboradores` (`{ usuarios_ids[] }`, só quem montou a baixa, só em rascunho) funciona como nas listas de inservíveis e extraviados: quem recebe faz tudo o que o solicitante faz (incluir e tirar bens, motivo e processo, enviar, descartar), é avisado e não pode aprovar a baixa (`403 auto_aprovacao`); `GET /baixas?solicitante_id=` traz as que a pessoa montou e as compartilhadas com ela; `colaboradores[]` na leitura.
