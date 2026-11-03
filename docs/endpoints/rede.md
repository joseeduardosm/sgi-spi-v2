# Plano de face da rede (`/api/rede`)

Switches, patch panels e roteadores, com a **face** de cada um (as portas na posição real), a **configuração lógica** de cada porta,
as **VLANs**, o que está **ligado** em cada porta, os **pontos de rede** (tomadas) e os **chamados** de cada porta.
O SGI **não fala com os equipamentos**: tudo aqui é cadastro (a carga inicial vem do inventário do GLPI; coleta SNMP contínua fica para depois).

## Acesso (recurso `rede` da ACL)

Fechado até haver regras ou perfis (dados de infraestrutura): sem nenhuma regra, **só o SuperRoot** entra.

| Nível | O que libera |
|---|---|
| Leitura (ver) | Equipamentos, faces, portas, VLANs, conexões, pontos e os chamados de cada porta (só os que a pessoa já vê nos Chamados) |
| Modificação (editar) | Configurar portas, ligar e desligar conexões, cadastrar/alterar/excluir pontos |
| Controle total (administrar) | Modelos de face, equipamentos (com função e IP de gerência) e VLANs (criar, alterar, excluir) e os parâmetros (intervalo do ping) |

Erros: `{"detalhe", "codigo"}`; `403 acesso_negado` sem o nível; `404 nao_encontrado`; `409 duplicado`, `em_uso`, `porta_ocupada` ou `porta_com_equipamento`.

## Regras

- **Modelo de face**: grade de 1 a 8 linhas × 1 a 64 colunas. Numeração `coluna` (1 em cima, 2 embaixo, 3 em cima... como a maioria dos
  switches) ou `linha` (1..N na primeira linha, como patch panels). Portas extras (uplink, fibra) têm número maior que as da grade, um nome (o da interface, até 20 caracteres, ex.: `25GE1/0/3`; vazio = o número)
  e o tipo (fibra ou cobre). Na tela, cada porta extra é uma linha (número, nome, tipo) com "Adicionar porta extra" e "Remover".
  Modelo usado por equipamento não é excluído (`409 em_uso`).
- **Rack**: nome único, cor (`preto`, `cinza`, `azul`, `verde`, `amarelo`, `laranja`, `vermelho`), sala do Patrimônio e altura (1–60U). Rack com
  equipamento não é excluído e não encolhe para deixar equipamento de fora (`409 em_uso`). Os racks que estavam escritos à mão nos equipamentos
  viraram cadastro na migração `e1a3c5d7f9b2`.
- **Equipamento**: ao criar (ou trocar o modelo), as portas que faltam são criadas pelo modelo; nenhuma porta é apagada. IP de gerência
  validado. Bem do Patrimônio e sala opcionais. Fica num **rack já cadastrado** (`rack_id`) e numa posição U (`posicao_u`, o U mais baixo; a
  altura vem do modelo): precisa caber no rack (400) e não pode sobrepor outro equipamento (`409 posicao_ocupada`).
  Tipos: `switch`, `roteador`, `access_point`, `outro` e `patch_panel`. **Todo tipo menos o patch panel exige o IP de gerência e a função na
  topologia** (`core_primario`, `core_secundario`, `distribuicao`, `acesso`; 400 sem um deles); no patch panel a função é ignorada. Os cadastrados
  antes dessa regra continuam valendo e aparecem com `cadastro_incompleto` até a próxima edição, que exige os dois. Trocar o IP zera o resultado
  do ping.
- **Ping (monitoramento)**: a tarefa `python -m app.tarefas.rede ping` (timer `sgi-spi-rede-ping`, chamado a cada minuto) testa o IP de gerência
  de todo equipamento ativo menos patch panel, no intervalo dos parâmetros (`ping_intervalo_min`, 1 a 60 minutos; padrão 1). **Fora do ar** só
  depois de **3 falhas seguidas**; a primeira resposta volta a **no ar**. O resultado fica em `ping_situacao` (`no_ar`, `fora` ou vazio = sem teste),
  `ping_verificado_em` e `ping_mudou_em`.
- **Porta (modos das marcas em uso: Cisco, Huawei, 3Com/H3C)**. A VLAN principal fica em `vlan_nativa_id`; o que mais cada modo aceita:

  | Modo | Onde existe | VLAN principal | Com tag | Sem tag extra | Voz | IP |
  |---|---|---|---|---|---|---|
  | `access` | todas | a VLAN | não | não | sim | não |
  | `trunk` | todas | nativa (sem tag) | sim | não | não | não |
  | `hybrid` | Huawei, 3Com/H3C | PVID | sim | sim | sim | não |
  | `dot1q_tunnel` (QinQ) | Cisco, Huawei | VLAN externa | não | não | não | não |
  | `dinamico_auto` / `dinamico_desejavel` (DTP) | Cisco | VLAN quando access | sim | não | sim | não |
  | `roteada` (L3: `no switchport` / `undo portswitch`) | Cisco, Huawei | não tem | não | não | não | sim (`10.23.0.1/30`, validado) |

  Combinação fora da tabela: 400. A mesma VLAN não passa com e sem tag na mesma porta. VLAN usada como voz conta como em uso. Status `up`,
  `down` ou `desativada`. Na carga do GLPI, porta com VLANs com e sem tag que não cabem em access/trunk vira `hybrid` (com aviso para conferir).
- **Conexão**: cada porta em no máximo uma conexão, de qualquer lado (`409 porta_ocupada`); o outro lado é uma porta, um bem do
  Patrimônio ou uma descrição.
- **Porta com equipamento fica ligada** (decisão do usuário): ligar qualquer coisa numa porta (outra porta, bem ou descrição) passa as duas pontas
  ao status `up`, e enquanto houver algo ligado o status não muda para `down`, `desativada` ou vazio (`409 porta_com_equipamento`): primeiro se
  retira o equipamento. A migração `f4b6d8e0a2c3` passou a `up` as portas que já tinham ligação (as dos APs, Dell e 3Com da carga LLDP).
- **Dispositivos em cascata na mesma porta** (switch → telefone IP → PC): o primeiro é a conexão (bem ou descrição); os de trás ficam numa lista
  ordenada (`atras`), cada um bem ou descrição. Só existe "atrás" quando a porta tem um primeiro dispositivo (`409 sem_dispositivo`); o mesmo bem
  duas vezes na porta: `409 duplicado`. Tirar um faz os seguintes subirem; desligar a porta tira todos. O cadastro do bem mostra "atrás de …" e,
  ali, "Desligar" tira só aquele bem. A topologia conta os bens de trás também. A ligação confere as **duas pontas** (origem e destino). Na ligação porta ↔ porta, uma porta **descrita no switch**
  (ex.: "Sala 05B05 - Impressora") indica um dispositivo nela: `409 porta_com_dispositivo`, com a porta e a descrição na mensagem; a tela pede
  confirmação e reenvia com `forcar: true` (a descrição pode ser a do próprio uplink). Na lista de portas do outro lado, a descrição aparece ao lado
  do número.
- **Ponto de rede**: código único como na tomada (gravado em maiúsculas); chega em uma porta (de patch panel) e uma porta só tem um ponto.
  O `caminho` segue ponto → porta do patch panel → conexão → porta do switch (até 4 saltos).
- **Topologia**: montada na hora a partir das conexões entre portas de equipamentos ativos (nada é desenhado à mão). Cada grupo de equipamentos
  ligados entre si (uma "rede ligada") é arrumado à parte e pode ter o seu núcleo. **Os cores do grupo ficam no topo, lado a lado, cada um com a
  sua árvore, na ordem da função**: o Core primário primeiro; se o ping der o primário **fora do ar**, o secundário passa à frente (`assumiu`), sem
  mudar o cadastro. Quantidade de cabos e ordem alfabética não decidem entre os cores. Grupo sem core marcado continua com o núcleo automático
  (o equipamento com mais switches/roteadores vizinhos; no empate, o que tem menos coisa de ponta, depois o roteador e o nome). `raiz_id` só muda a
  visão (põe aquele equipamento como raiz única do grupo). Filhos em ordem de camada: distribuição, acesso, sem função e, por último, patch panels;
  depois o nome. Cada equipamento aparece uma vez, embaixo do primeiro a que se liga (busca
  em largura); um cabo a mais para outro ramo (uplink redundante, anel) aparece em `tambem_ligado`. Quem não tem cabo para outro equipamento vai
  para `sem_ligacao`, a pendência do cadastro.
- **Chamados**: o chamado pode apontar `rede_porta_id` ou `rede_ponto_id` na abertura (`POST /api/chamados`); a porta mostra os chamados
  dela e do ponto que chega nela, filtrados pela visibilidade dos Chamados.

## Endpoints

| Método e caminho | Quem | Descrição |
|---|---|---|
| `GET /api/rede/contexto` | Logado | `{ver, editar, administrar}` (200 mesmo sem papel) |
| `GET /api/rede/equipamentos?busca=&tipo=` | Leitura | `[{id, nome, tipo, modelo_face_id, modelo_nome, altura_u, bem_id, localizacao_id, sala, rack_id, rack_nome, posicao_u, ip_gerencia, numero_serie, observacao, ativo, funcao, portas_total, portas_up, portas_down, portas_desativadas, ping_situacao, ping_verificado_em, ping_mudou_em, cadastro_incompleto}]` |
| `POST /api/rede/equipamentos` | Controle total | `{nome, tipo, funcao, modelo_face_id, bem_id, localizacao_id, rack_id, posicao_u, ip_gerencia, numero_serie, observacao, ativo}` → `201` com a face; sem IP ou sem função (menos patch panel): 400 |
| `GET /api/rede/equipamentos/{id}` | Leitura | Face: o resumo + `modelo`, `posicoes` (número → `[linha, coluna]`) e `portas[{id, numero_logico, nome, descricao, mac, velocidade_mbps, duplex, status, modo, vlan_nativa(_id), vlans_tag(_ids), vlans_sem_tag(_ids), vlan_voz(_id), ip_interface, ultima_mudanca, erros_entrada, erros_saida, conexao{tipo, texto, porta_id, equipamento_id, bem_id}, ponto, chamados_abertos}]` |
| `PUT` · `DELETE /api/rede/equipamentos/{id}` | Controle total | Altera / exclui (as portas e conexões vão junto; os chamados ficam sem a porta) |
| `GET /api/rede/portas/{id}` | Leitura | A porta + `equipamento_id`, `equipamento_nome` e `chamados[{numero, titulo, status_base, aberto_em}]` |
| `PUT /api/rede/portas/{id}` | Modificação | Com algo ligado, `status` só `up` (`409 porta_com_equipamento`). `{descricao, modo, vlan_nativa_id, vlans_tag[], vlans_sem_tag[], vlan_voz_id, ip_interface, velocidade_mbps, duplex, status}`; a leitura da porta traz também `vlans_sem_tag(_ids)`, `vlan_voz(_id)` e `ip_interface` |
| `POST /api/rede/portas/{id}/conexao/atras` · `DELETE …/atras/{dispositivo_id}` | Modificação | Põe (`{bem_id \| descricao}`) um dispositivo atrás do último da porta / tira um. Respondem a porta (`conexao.atras[{id, ordem, texto, bem_id}]`) |
| `POST` · `DELETE /api/rede/portas/{id}/conexao` | Modificação | Liga (`{porta_id \| bem_id \| descricao, forcar?}`) / desliga. `409 porta_ocupada` (já ligada) ou `409 porta_com_dispositivo` (porta descrita; repita com `forcar`) |
| `GET` · `POST /api/rede/modelos` · `PUT` · `DELETE …/{id}` | Leitura / Controle total | `{nome, fabricante, linhas, colunas, numeracao, portas_extras[{numero, rotulo, tipo}], altura_u}` (+ `equipamentos` na leitura) |
| `GET` · `POST /api/rede/vlans` · `PUT` · `DELETE …/{id}` | Leitura / Controle total | `{numero (1–4094), nome, descricao}` (+ `portas` na leitura); em uso: `409 em_uso` |
| `GET` · `POST /api/rede/racks` · `PUT` · `DELETE …/{rack_id}` | Leitura / Controle total | `{nome, cor, localizacao_id, altura_u, observacao}` (+ `sala` e `equipamentos` na leitura) |
| `GET /api/rede/topologia?raiz_id=` | Leitura | `{raizes[NoTopologia], sem_ligacao[NoTopologia]}`; `NoTopologia` = `{id, nome, tipo, funcao, ping_situacao, assumiu, rack_nome, rack_cor, sala, ip_gerencia, portas_total, portas_up, portas_down, pontos, bens, porta_acima, porta_no_pai, cabos_com_pai, tambem_ligado[], filhos[]}` (`porta_acima`: porta deste equipamento que liga ao de cima; `porta_no_pai`: onde chega; sala vazia usa a do rack) |
| `GET /api/rede/portas/{id}/caminho` | Leitura | Do core até a porta: `{etapas[{tipo (equipamento\|ponto), nome, cabo, equipamento_id, tipo_equipamento, funcao, ping_situacao, porta_entrada, porta_saida}], dispositivos[{texto, bem_id}], cabo_dispositivos, aviso}`. A subida é a mesma árvore da topologia; `cabo` = "porta de cima ↔ porta deste"; `porta_entrada`/`porta_saida` = a porta deste equipamento no cabo que sobe / no que desce (leitura completa, como na face). Porta de patch panel sobe pelo switch em que ela chega e termina no ponto; porta que é a subida do próprio equipamento para nele (a tela destaca o quadradinho da porta aberta); `aviso` só quando o equipamento não tem cabo até o core |
| `GET` · `PUT /api/rede/parametros` | Controle total | `{ping_intervalo_min}` (1 a 60; fora disso, 422). Vale a partir da próxima rodada |
| `GET /api/rede/salas?busca=&todas=` | Leitura | Até 20 salas do Patrimônio pelo código ou nome; com `todas=true`, todas as salas ativas por andar. `[{id, codigo, nome, rotulo, andar}]`. O cadastro do rack usa a lista inteira num campo único que filtra enquanto se digita (o mesmo campo de sala do Patrimônio) |
| `GET /api/rede/bens?busca=` | Leitura | Até 20 bens do Patrimônio (não baixados) pela chapa ou descrição, para ligar numa porta: `[{id, chapa, descricao, sala}]` |
| `GET /api/rede/bens/{bem_id}/portas` | Leitura | Em qual switch e porta o bem está ligado (aparece no cadastro do bem): `[{porta_id, porta_nome, equipamento_id, equipamento_nome, atras_de, dispositivo_id}]` (atrás de outro dispositivo: `atras_de` e o `dispositivo_id` para tirar só ele) |
| `GET /api/rede/pontos?busca=&localizacao_id=` · `POST` · `PUT` · `DELETE …/{id}` | Leitura / Modificação | `{codigo, localizacao_id, porta_id, observacao}` (+ `sala` e `caminho[]` na leitura) |

## Carga inicial pelo GLPI

`scripts/migrar-rede-glpi.py <dump.sql> [--gravar]` (mesmo dump da importação dos chamados; ensaio por padrão; idempotente).
Traz modelos (grade **sugerida**: confira cada um), equipamentos de rede, portas Ethernet e de fibra, VLANs (a sem tag vira a nativa) e as
conexões entre equipamentos de rede. Ver [importacao-glpi-chamados.md](../importacao-glpi-chamados.md).

## Carga pelo inventário LLDP

`scripts/importar-rede-lldp.py <inventario.json> [--gravar]` (ensaio por padrão; pode rodar de novo). Regras em
`app/services/rede/importacao_lldp.py`. O inventário (fora do Git, em `dados/rede/`) é montado só com comandos de leitura nos switches
(`display interface brief`, `display lldp neighbor`) e traz equipamentos (nome, tipo, IP, função, modelo, status de cada porta), cabos (as duas
interfaces de cada ponta) e os cadastros de teste a excluir. Cria os modelos de face que faltam (Huawei S5755-H: 2×24 por coluna + 25GE nas
portas 49–52 e 100GE nas 53–54; AirEngine 6700: 1 porta; genérico de 48 portas para Dell e 3Com), grava em cada porta o nome real da interface e o
status, atualiza o equipamento que já existe com o mesmo nome (sem mexer em rack e sala) e pula o cabo que já existe. Porta ocupada por outra
coisa no SGI não é mexida: vira aviso no relatório.

## Telas (frontend)

- **Rede** (`/rede`), visão **Racks** (padrão): cada rack cadastrado (inclusive vazio), com a cor, a sala, a numeração dos U (U1 embaixo) e os
  equipamentos na posição (`posicao_u`) e na altura do modelo (`altura_u`), com o número de portas ligadas e desligadas. Quem administra
  cadastra racks e equipamentos (já escolhendo o rack e a posição) na mesma tela. Clicar no equipamento abre a face dele.
  Equipamento sem rack ou sem posição aparece em lista à parte. A visão **Lista** tem a busca e o filtro por tipo.
- **Topologia** (`/rede/topologia`): a árvore da rede no desenho do Organograma do RH (zoom, arrasto, formatos Árvore e Vertical). Começa com o
  núcleo e o primeiro nível; o **+** de cada equipamento abre o nível de baixo ("Expandir tudo" e "Recolher" na barra). Cada caixa mostra tipo,
  rack (faixa na cor dele), IP, sala, por qual porta sobe e onde chega, portas ligadas/desligadas, pontos e bens; clicar abre a face. O grupo
  "Sem ligação" junta os equipamentos ainda sem cabo. Cada caixa tem os selos da função e do ping; o core secundário que passou à frente leva
  "Assumiu: primário fora do ar". "Núcleo" (padrão "Pela função") só muda a visão e fica lembrado neste navegador.
- **Caminho até o core** (tela da porta e cadastro do bem no Patrimônio): caixas em cascata, como as da Topologia, do core até a porta; entre
  duas caixas, o cabo liga o quadradinho da porta que desce (canto inferior direito, igual ao da face, com a cor do status) ao da porta que sobe
  na caixa seguinte (canto superior direito), sem texto no traço (as portas estão nos quadradinhos); passar o mouse no quadradinho mostra a mesma dica da face e clicar abre a porta; o quadradinho da porta aberta tem contorno vermelho; o patch panel e o ponto entram se estiverem cadastrados (o LLDP não os enxerga);
  os dispositivos da porta (telefone → computador) ficam lado a lado na última linha. Cada caixa abre o equipamento ou o bem.
- **Ligar um bem na porta**: um campo só ("Bem do Patrimônio") que busca pela chapa ou descrição e mostra a lista logo abaixo (mesmo campo do
  Patrimônio, buscando por `/api/rede/bens`).
- **Pontos, VLANs e modelos** (`/rede/cadastros`), aba **Monitoramento** (só Controle total): o intervalo entre os pings.
- **Cadastro do equipamento**: o campo **Função na topologia** aparece em todo tipo menos patch panel, e o IP de gerência fica obrigatório. A lista
  e a tela do equipamento mostram a função, o selo **No ar / Fora do ar** e **Cadastro incompleto** nos que ainda não têm IP ou função.
- **Equipamento** (`/rede/equipamentos/:id`): a **face** desenhada pelo modelo (grade + portas extras). **Verde = ligada, vermelho =
  desligada**, tracejado = desativada ou sem informação; bolinha âmbar = chamado aberto. Clicar na porta abre o detalhe dela. Abaixo, a lista
  de portas e, para quem administra, os dados do equipamento.
- **Porta** (`/rede/portas/:id`): configuração, situação, o que está ligado (outro equipamento, **um bem do Patrimônio** buscado pela chapa ou uma
  descrição), ponto de rede e chamados, com "Abrir chamado desta porta".
- **Cadastro do bem** (Patrimônio): para quem tem acesso à Rede, o quadro "Rede" mostra em qual switch e porta o bem está ligado; quem edita a
  rede liga ou desliga dali mesmo. É a mesma ligação da porta: o que se faz num lugar aparece no outro.
