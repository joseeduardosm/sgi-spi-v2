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
- **Modelo de face travado** (decisão do usuário): o modelo é escolhido na criação e **não muda depois** (`409 modelo_travado`); para trocar,
  exclui-se o equipamento e cadastra-se de novo. Só o equipamento antigo que ficou sem modelo pode recebê-lo uma vez. O tipo também não passa de
  patch panel para os demais (nem o contrário): `409 tipo_travado`. A **grade de um modelo em uso** (linhas, colunas, numeração e portas extras)
  não muda (`409 modelo_em_uso`, crie outro modelo); nome, fabricante e altura continuam editáveis. A edição do equipamento entra na auditoria
  (`rede.equipamento.alterar`).
- **Equipamento**: ao criar, as portas são criadas pelo modelo. IP de gerência
  validado. Bem do Patrimônio e sala opcionais. Fica num **rack já cadastrado** (`rack_id`) e numa posição U (`posicao_u`, o U mais baixo; a
  altura vem do modelo): precisa caber no rack (400) e não pode sobrepor outro equipamento (`409 posicao_ocupada`). **Rack e U são obrigatórios**
  (decisão do usuário, 17/11/2026) em todo equipamento, menos o **access point** (que costuma ficar no teto): `400 sem_rack`, na criação e na
  edição. A importação do inventário LLDP não exige (não sabe onde o equipamento está montado). No cadastro, ao escolher o rack, a tela desenha o
  rack com os equipamentos e os U livres: clicar num U livre (onde o equipamento cabe inteiro) pergunta "Sim/Não" e preenche a posição.
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

  **Descrição gerada pelo sistema** (decisão do usuário, 12/11/2026): ninguém digita a descrição da porta. Ela diz o que está ligado
  (ex.: "SW-DIST · 1", "Impressora (chapa 012345)", "Telefone da recepção"); no patch panel, os dois lados ("Terminal Punch Down: VOIP 08395 ·
  Conector RJ45: SW-5A · 7"; na API os lados continuam `fundo` = Terminal Punch Down e `frente` = Conector RJ45, nomes de tela decididos em 13/11/2026); sem nada ligado, **"Desligado"**. É refeita a cada ligar e desligar. O texto livre da porta é a **`observacao`** (opcional).
  **Porta sem nada ligado fica em branco**: só `down` ou `desativada` (outro status: `409 porta_sem_ligacao`), sem configuração (modo `access`,
  sem VLAN, voz, IP, velocidade e duplex); só a situação e a observação mudam. **Porta com algo ligado fica `up`** (outro status:
  `409 porta_com_equipamento`) e é aí que a configuração vale. **Porta de patch panel não tem parte lógica**: só a observação (modo diferente de
  `access`, VLAN, IP, velocidade ou duplex dão 400). A leitura da porta traz `equipamento_tipo`.
  Combinação fora da tabela: 400. A mesma VLAN não passa com e sem tag na mesma porta. VLAN usada como voz conta como em uso.
- **Fundo e frente do patch panel** (decisão do usuário): cada porta de patch panel tem dois lados físicos, cada um com uma ligação: o cabo do
  **fundo** e o da **frente** (`rede_conexoes.lado_a`/`lado_b`). Ligar ou desligar numa porta de patch panel exige o `lado`; nas demais portas o
  lado não existe (400). A leitura da porta traz `fundo` e `frente` (e `conexao` = a primeira que houver). O lado é físico: o sentido até o core
  sai dos equipamentos em cada ponta, não do nome do lado.
- **Ligação**: cada porta (ou lado, no patch panel) em no máximo uma ligação (`409 porta_ocupada`); o outro lado é uma porta (com o lado, se for
  patch panel), um bem do Patrimônio ou uma descrição. Ligar passa as pontas a `up` e refaz a descrição delas.
- **Dispositivos em cascata na mesma porta** (switch → telefone IP → PC): o primeiro é a ligação (bem ou descrição); os de trás ficam numa lista
  ordenada (`atras`), cada um bem ou descrição. Só existe "atrás" quando a porta (ou o lado) tem um primeiro dispositivo (`409 sem_dispositivo`);
  o mesmo bem duas vezes: `409 duplicado`. Tirar um faz os seguintes subirem; desligar tira todos. O cadastro do bem mostra a porta, o lado e
  "atrás de …"; ali, "Desligar" tira só aquele bem. A topologia conta os bens de trás também.
- **Desligar** (decisão do usuário): a ponta que fica **sem nada ligado** (no patch panel, sem nada nos dois lados) passa a `down` e fica em
  branco; a porta de patch panel com o outro lado ainda ligado continua `up`, só com a descrição refeita. **Nenhum equipamento fica sem cabo para
  quem está acima dele** (`409 unica_ligacao_para_cima`). A conferência segue os cabos para cima **até o core** (`chega_ao_topo`): com acesso
  em cascata, dois acessos ligados só um no outro não contam como ligados para cima. Para trocar a porta, liga-se a nova antes e depois desliga-se a antiga. Vale também ao
  desligar um dos lados do patch panel por onde passa esse cabo e ao **excluir** um equipamento (ex.: a distribuição com acessos pendurados só nela).
- **Trocar a ligação** (decisão do usuário, 13/11/2026): `POST /portas/{id}/conexao/trocar` troca o que está ligado na porta (ou no lado do
  patch panel) por outra coisa **numa operação só**, sem passar por um momento sem cabo para cima. Com `religar_antigo`, quando o novo destino é
  um lado de patch panel e o antigo era outra porta, o outro lado daquela porta do patch panel é ligado no destino antigo: é como se põe um patch
  panel no meio de um cabo que já existia (CORE 48 ↔ DIST 1 vira CORE 48 ↔ PP frente e PP fundo ↔ DIST 1). A configuração da porta fica. Se, depois
  da troca, alguém ficar sem cabo para cima: `409 unica_ligacao_para_cima` e nada muda.
- **Cadastro em cadeia** (decisão do usuário, 12/11/2026): a rede é cadastrada de cima para baixo. Sem core, não entra distribuição; sem core e
  distribuição, não entra acesso; sem acesso, não entram access point, roteador, firewall, servidor e "outro"; o core secundário pede o primário
  (`409 cadeia_incompleta`). Todo equipamento, menos o **core primário** (o topo) e o **patch panel**, já entra com o cabo para quem fica acima
  dele (`ligacao`, `400 sem_ligacao` se faltar): a porta dele, a porta do outro e a configuração das duas. Quem pode ficar acima: core secundário →
  core primário; distribuição → um core ou **outra distribuição** (cascata, decisão do usuário de 17/11/2026); acesso → distribuição, core ou **outro acesso** (cascata, decisão do usuário de 17/11/2026); access point,
  roteador, firewall, servidor e "outro" → switch de acesso (`409 cadeia_invalida`). O equipamento de cima precisa ter caminho até o core (`409 cadeia_invalida`).
  O cabo pode chegar num **lado de patch panel**, desde que o **outro lado daquela mesma porta** leve (atravessando quantos patch panels houver) a
  quem pode ficar acima: cada porta do patch panel é um cabo independente (a porta 1 com o Terminal Punch Down no core só leva ao core pelo Conector
  RJ45 da porta 1; a porta 2 não conversa com ela). As demais portas nascem `down` e "Desligado". A **função** é só do switch (AP, roteador, firewall, servidor e "outro" ficam sem função) e, com o tipo e o
  modelo de face, **não muda depois de criado** (`409 funcao_travada`, `409 tipo_travado`, `409 modelo_travado`).
- **Leitura do equipamento por SSH — DESATIVADA por enquanto** (decisão do usuário, 13/11/2026: vai ser lapidada). O código fica; a chave
  `LEITURA_SSH_ATIVA` (backend `servico_leitura.py` e frontend `rede.models.ts`) está desligada: as rotas de leitura respondem
  `409 leitura_desativada` e o cadastro não pede usuário e senha. Como funciona quando ligada (decisão do usuário, 13/11/2026): switch, AP e roteador podem ter um **acesso SSH só leitura por equipamento**
  (`acesso_usuario`, `acesso_senha` cifrada com Fernet, `acesso_porta`; a senha nunca volta na API, só `tem_acesso`). O SGI entra com o Netmiko,
  **detecta o fabricante** (e, se não der, tenta Huawei VRP/YunShan, Dell OS6, H3C Comware e Cisco IOS) e roda **só comandos de consulta**
  (`display`/`show`; trava em `leitura_ssh._so_consulta`). Para cada informação há várias tentativas (ex.: `display device esn` ou `display esn`;
  `display port vlan` ou `display current-configuration`); a que falhar é pulada e vira aviso, e se nada funcionar a leitura vem vazia. Lê nome,
  modelo, série, versão, portas (link, velocidade, duplex, descrição, modo, PVID, VLANs com e sem tag), VLANs e vizinhos LLDP. A interface vira
  porta da face pelo rótulo da porta extra (ex.: `25GE1/0/1`) ou pelo último número dentro da grade (`MultiGE1/0/5` → 5); interfaces lógicas
  (Vlanif, Eth-Trunk, LoopBack…) ficam de fora. Prazo de 45 s (o nginx corta a API em 60 s). Use uma conta só leitura no equipamento.
  - **No cadastro**: "Testar e ler o equipamento" (`POST /leitura/testar`) não grava nada; preenche nome e série vazios e **sugere o cabo de
    subida** pelo LLDP (vizinho já cadastrado que pode ficar acima, com a porta livre).
  - **Depois**: `POST /equipamentos/{id}/leitura` lê com o acesso gravado, **liga sozinho os vizinhos LLDP** (vizinho cadastrado pelo nome e as
    duas portas livres; o que não der fica no resumo com o motivo) e guarda a leitura em `rede_leituras`.
  - **Resumo e aplicar**: o que mais a leitura traz (série, VLANs que o SGI não tem, portas com link e descrição no switch sem nada em "Ligado a",
    configuração das portas) aparece em grupos marcados; `POST /equipamentos/{id}/leitura/aplicar` grava só os marcados. A configuração só vale
    em porta ligada (ou ligada pela descrição no mesmo passo); "todas as VLANs" do switch (`1-4094`) não vira lista.
- **Cargas automáticas desativadas** (decisão do usuário): a carga por LLDP e a carga da Rede pelo GLPI recusam rodar (`carga_desativada`),
  porque criariam equipamentos e cabos fora da cadeia.
- **Ponto de rede**: código único como na tomada (gravado em maiúsculas); chega em uma porta (de patch panel) e uma porta só tem um ponto.
  O `caminho` segue ponto → porta do patch panel → ligações → porta do switch (até 4 saltos).
- **Topologia**: montada na hora a partir das conexões entre portas de equipamentos ativos (nada é desenhado à mão). Cada grupo de equipamentos
  ligados entre si (uma "rede ligada") é arrumado à parte e pode ter o seu núcleo. **Os cores do grupo ficam no topo, lado a lado, cada um com a
  sua árvore, na ordem da função**: o Core primário primeiro; se o ping der o primário **fora do ar**, o secundário passa à frente (`assumiu`), sem
  mudar o cadastro. Quantidade de cabos e ordem alfabética não decidem entre os cores. Grupo sem core marcado: a raiz é o equipamento da camada
  mais alta (distribuição antes de acesso; **patch panel nunca é a raiz**); no empate, o que tem mais switches/roteadores vizinhos, depois menos
  coisa de ponta, o roteador e o nome. `raiz_id` só muda a visão (põe aquele equipamento como raiz única do grupo).
  **Árvore por camadas (decisão do usuário):** Core → Distribuição → Acesso → demais (sem função). Um equipamento só fica embaixo de alguém de
  camada mais alta; o **patch panel** aparece entre duas camadas quando o cabo passa por ele (ex.: distribuição → patch panel → acesso) e no fim do
  ramo quando só serve aquele switch. Quem só se liga a equipamentos da mesma camada ou de baixo (cadastro incompleto, ex.: acesso empilhado)
  fica embaixo do primeiro a que se liga. Filhos em ordem de camada, com os patch panels por último, depois o nome. Cada equipamento aparece uma
  vez; um cabo a mais para outro ramo (uplink redundante, anel) aparece em `tambem_ligado`. Quem não tem cabo para outro equipamento vai
  para `sem_ligacao`, a pendência do cadastro.
- **Chamados**: o chamado pode apontar `rede_porta_id` ou `rede_ponto_id` na abertura (`POST /api/chamados`); a porta mostra os chamados
  dela e do ponto que chega nela, filtrados pela visibilidade dos Chamados.

## Endpoints

| Método e caminho | Quem | Descrição |
|---|---|---|
| `GET /api/rede/contexto` | Logado | `{ver, editar, administrar}` (200 mesmo sem papel) |
| `GET /api/rede/indicadores` | Leitura | Cards do topo: `{portas_alteradas, portas_patch_um_lado}` (portas de patch panel com um lado ligado e o outro vazio) |
| `GET /api/rede/portas-alteradas` · `GET /api/rede/portas-patch-um-lado` | Leitura | Listas dos cards: `[{porta_id, equipamento_id, equipamento_nome, porta, numero_logico, descricao, alterado_por, alterado_em}]` (a última alteração de cada porta; da mais recente para a mais antiga) |
| `GET /api/rede/equipamentos?busca=&tipo=` | Leitura | `[{id, nome, tipo, modelo_face_id, modelo_nome, altura_u, bem_id, localizacao_id, sala, rack_id, rack_nome, posicao_u, ip_gerencia, numero_serie, observacao, ativo, funcao, portas_total, portas_up, portas_down, portas_desativadas, ping_situacao, ping_verificado_em, ping_mudou_em, cadastro_incompleto}]` |
| `POST /api/rede/equipamentos` | Controle total | `{nome, tipo, funcao, modelo_face_id, bem_id, localizacao_id, rack_id, posicao_u, ip_gerencia, numero_serie, observacao, ativo, acesso_usuario, acesso_senha, acesso_porta, ligacao}` (`acesso_senha` só na escrita; vazia na edição mantém a gravada) → `201` com a face. **Cadastro em cadeia**: `ligacao = {porta_numero, destino_porta_id, destino_lado, config, config_destino}` (obrigatória menos no core primário e no patch panel: `400 sem_ligacao`); `config`/`config_destino` no formato do `PUT` da porta. Fora da cadeia: `409 cadeia_incompleta` / `409 cadeia_invalida`; porta ou lado ocupado: `409 porta_ocupada`. Sem IP (menos patch panel) ou switch sem função: 400. Sem rack e U (menos access point): `400 sem_rack` (vale também no `PUT`) |
| `GET /api/rede/equipamentos/destinos-cadastro?tipo=&funcao=` | Controle total | Passo Conexão do cadastro (decisão do usuário, 17/11/2026: "Conectado em" só com os elegíveis): `[{equipamento_id, portas[{porta_id, lado}]}]`, os equipamentos que podem ficar acima de um novo deste tipo e função e, de cada um, as portas livres que servem. Switch: `pode_ficar_acima` + caminho até o core + porta livre. Patch panel: o lado livre de uma porta cujo **outro lado da mesma porta** leva (atravessando patch panels) a quem pode ficar acima e chega ao core. Só leitura; o `POST` confere tudo de novo |
| `POST /api/rede/leitura/testar` | Controle total | `{ip, usuario, senha, porta, modelo_face_id, tipo, funcao}` → `{tipo_acesso, nome, modelo, serie, versao, portas, vlans, vizinhos[], avisos[], sugestao{porta_numero, destino_equipamento_id, destino_porta_id, texto}}`, sem gravar nada. Acesso recusado ou sem resposta: `409 leitura_falhou` |
| `POST` · `GET /api/rede/equipamentos/{id}/leitura` | Controle total / Leitura | Lê agora (liga sozinho os vizinhos LLDP e guarda a leitura; `400 sem_acesso`, `409 leitura_falhou`) / a última leitura (nula se nunca lido). Respondem o resumo `{id, lido_em, lido_por, aplicada_em, tipo_acesso, equipamento{serie_lida, serie_cadastro, modelo, versao, nome_lido}, vlans_novas[], lldp[{…, situacao, motivo}], descricoes[], configuracao[{interface, porta, atual, lida, ligada}], avisos[]}` |
| `POST /api/rede/equipamentos/{id}/leitura/aplicar` | Controle total | `{equipamento, vlans[], descricoes[], configuracao[]}` → grava os marcados da última leitura e responde a face |
| `GET /api/rede/equipamentos/{id}` | Leitura | Face: a alteração mais recente entre as portas do equipamento (`alterado_por`, `alterado_em`, `alterado_porta_id`, `alterado_porta`; nulos se nenhuma), mostrada como "Última alteração em porta: nome - dd/mm/aaaa hh:mm:ss (porta N)"; o resumo + `modelo`, `posicoes` (número → `[linha, coluna]`) e `portas[{id, numero_logico, nome, descricao, mac, velocidade_mbps, duplex, status, modo, vlan_nativa(_id), vlans_tag(_ids), vlans_sem_tag(_ids), vlan_voz(_id), ip_interface, ultima_mudanca, erros_entrada, erros_saida, conexao{tipo, lado, outro_lado, texto, porta_id, equipamento_id, bem_id, atras}, fundo, frente, observacao, ponto, chamados_abertos}]` (`fundo`/`frente`: as ligações de cada lado, só no patch panel) |
| `PUT` · `DELETE /api/rede/equipamentos/{id}` | Controle total | Altera (modelo, tipo e função travados: `409 modelo_travado` / `409 tipo_travado` / `409 funcao_travada`; auditado como `rede.equipamento.alterar`) / exclui (as portas e ligações vão junto, as portas do outro lado ficam em branco; os chamados ficam sem a porta; `409 unica_ligacao_para_cima` se outro equipamento ficaria sem cabo para cima) |
| `GET /api/rede/portas/{id}` | Leitura | A porta (mesmos campos da face) + `equipamento_id`, `equipamento_nome`, `equipamento_tipo`, `chamados` e a última alteração da porta (`alterado_por`, `alterado_em`; nulos se nunca foi alterada), mostrada na tela como "Última alteração: nome - dd/mm/aaaa hh:mm:ss" |
| `PUT /api/rede/portas/{id}` | Modificação | `{observacao, modo, vlan_nativa_id, vlans_tag[], vlans_sem_tag[], vlan_voz_id, ip_interface, velocidade_mbps, duplex, status}`. A **descrição não é gravada** (gerada pelo sistema). Sem nada ligado: só `down`/`desativada` e em branco (`409 porta_sem_ligacao`; o resto, menos a observação, é ignorado). Com algo ligado: `up` (`409 porta_com_equipamento`). Patch panel: só a observação (400 para o resto) |
| `POST /api/rede/portas/{id}/conexao/atras` · `DELETE …/atras/{dispositivo_id}` | Modificação | Põe (`{lado?, bem_id \| descricao}`; `lado` no patch panel) um dispositivo atrás do último da porta / tira um. Respondem a porta (`conexao.atras`, ou `fundo.atras`/`frente.atras` no patch panel) |
| `POST` · `DELETE /api/rede/portas/{id}/conexao` | Modificação | Liga (`{lado?, porta_id \| bem_id \| descricao, outro_lado?}`; `lado`/`outro_lado` obrigatórios em porta de patch panel e proibidos nas demais) / desliga (`?lado=` no patch panel). `409 porta_ocupada`; desligar: `409 unica_ligacao_para_cima`. A ponta sem nada ligado fica `down` e em branco; a descrição das pontas é refeita |
| `POST /api/rede/portas/{id}/conexao/trocar` | Modificação | Troca a ligação numa operação só: `{lado?, porta_id \| bem_id \| descricao, outro_lado?, religar_antigo?}`. Sem ligação: 404; alguém sem cabo para cima depois da troca: `409 unica_ligacao_para_cima` (nada muda). Responde a porta |
| `GET` · `POST /api/rede/modelos` · `PUT` · `DELETE …/{id}` | Leitura / Controle total | `{nome, fabricante, linhas, colunas, numeracao, portas_extras[{numero, rotulo, tipo}], altura_u}` (+ `equipamentos` na leitura). Em uso, a grade e as extras não mudam: `409 modelo_em_uso` |
| `GET` · `POST /api/rede/vlans` · `PUT` · `DELETE …/{id}` | Leitura / Controle total | `{numero (1–4094), nome, descricao, cor_indice?}` (+ `cor_indice` e `portas` na leitura); em uso: `409 em_uso`. `cor_indice` (0–11, paleta dos marcadores das Tarefas): ausente mantém a cor; na criação, sorteia de 1 a 11 |
| `GET` · `POST /api/rede/racks` · `PUT` · `DELETE …/{rack_id}` | Leitura / Controle total | `{nome, cor, localizacao_id, altura_u, observacao}` (+ `sala` e `equipamentos` na leitura) |
| `GET /api/rede/topologia?raiz_id=` | Leitura | `{raizes[NoTopologia], sem_ligacao[NoTopologia]}`; `NoTopologia` = `{id, nome, tipo, funcao, ping_situacao, assumiu, rack_nome, rack_cor, sala, ip_gerencia, portas_total, portas_up, portas_down, pontos, bens, porta_acima, porta_no_pai, cabos_com_pai, tambem_ligado[], filhos[]}` (`porta_acima`: porta deste equipamento que liga ao de cima; `porta_no_pai`: onde chega; sala vazia usa a do rack) |
| `GET /api/rede/portas/{id}/caminho` | Leitura | Do core até a porta: `{etapas[{tipo (equipamento\|ponto), nome, cabo, equipamento_id, tipo_equipamento, funcao, ping_situacao, porta_entrada, porta_saida, lado_entrada, lado_saida}], dispositivos[{texto, bem_id}], cabo_dispositivos, aviso}`. A subida é a mesma árvore da topologia; depois o caminho **segue o fio da porta**: no patch panel, entra por um lado (`lado_entrada`) e sai pelo outro (`lado_saida`). Porta de patch panel sobe pelo lado que leva ao equipamento mais alto; se nenhum lado leva a um switch, para nela com o `aviso` (nunca usa o cabo de outra porta do mesmo patch panel). Porta que é a subida do próprio equipamento para nele |
| `GET` · `PUT /api/rede/parametros` | Controle total | `{ping_intervalo_min}` (1 a 60; fora disso, 422). Vale a partir da próxima rodada |
| `GET /api/rede/salas?busca=&todas=` | Leitura | Até 20 salas do Patrimônio pelo código ou nome; com `todas=true`, todas as salas ativas por andar. `[{id, codigo, nome, rotulo, andar}]`. O cadastro do rack usa a lista inteira num campo único que filtra enquanto se digita (o mesmo campo de sala do Patrimônio) |
| `GET /api/rede/bens?busca=` | Leitura | Até 20 bens do Patrimônio (não baixados) pela chapa ou descrição, para ligar numa porta: `[{id, chapa, descricao, sala}]` |
| `GET /api/rede/bens/{bem_id}/portas` | Leitura | Em qual equipamento e porta o bem está ligado (aparece no cadastro do bem): `[{porta_id, porta_nome, equipamento_id, equipamento_nome, lado, atras_de, dispositivo_id}]` (`lado` no patch panel; atrás de outro dispositivo: `atras_de` e o `dispositivo_id` para tirar só ele) |
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
- **Cadastro do equipamento** (`/rede/equipamentos/novo`, página própria, decisão do usuário): passo a passo com a trilha **Dados → Conexão →
  Revisão**. Em Dados: nome, tipo, **função** (só switch), modelo de face, IP de gerência (menos patch panel), rack e posição, com `*` nos
  obrigatórios (nome, tipo, função, modelo, rack e U; rack e U não no access point). Ao escolher o rack, ele é desenhado logo abaixo com os
  equipamentos montados e os U livres: clicar num U onde o equipamento cabe inteiro abre a pergunta **Sim/Não** e preenche a posição. Em
  Conexão (pedidos do usuário, 17/11/2026): a **porta deste equipamento** é escolhida clicando na face (desenhada pelo modelo); **"Conectado em"**
  continua uma lista, só com os elegíveis (`GET /equipamentos/destinos-cadastro`); a **porta do outro equipamento** é escolhida na face dele,
  com o nome no cabeçalho, e só as portas que servem ficam clicáveis (no patch panel, o lado que leva acima já vem escolhido quando é um só).
  Embaixo, os dois cartões de configuração das portas (a de Y vem com a configuração que já tiver): velocidade escolhida em fichas (10 Mb a
  100 Gb) e, quando a outra porta já está preenchida, o botão **"Copiar da porta …"** no canto do cartão repete a configuração dela. Core primário e patch panel pulam a conexão. **Edição** em `/rede/equipamentos/:id/editar` (botão vermelho
  **Editar** na tela do equipamento): os mesmos dados, com tipo, função e modelo travados, e o **Excluir equipamento**. A lista e a tela do
  equipamento mostram a função, o selo **No ar / Fora do ar** e **Cadastro incompleto** nos que ainda não têm IP (ou switch sem função).
- **Indicadores** (topo de `/rede`, no estilo do Painel de chamados; cada card abre `/rede/portas-lista/alteradas` ou `/rede/portas-lista/patch-um-lado`
  com equipamento | porta | descrição | quem alterou - dd/mm/aaaa hh:mm:ss e uma busca):
  - **Portas alteradas nos últimos 7 dias** (janela móvel, decisão do usuário): portas com **qualquer** alteração — configurar, ligar ou desligar
    (as duas pontas), pôr ou tirar dispositivo atrás, ponto de rede ligado/desligado da porta e a carga LLDP (situação, interface ou cabo novo,
    autor `sistema:carga-lldp`). Cada alteração grava uma auditoria com `alvo_tipo = rede_porta` e `alvo_id` = id da porta
    (`rede.porta.configurar`, `.ligar`, `.desligar`, `.atras`, `.ponto`, `.carga_lldp`). A migração `b7d9f1a3c5e8` ligou à porta as configurações
    auditadas antes (que só tinham o texto "EQUIPAMENTO · número"). "Quem alterou" mostra o nome completo do usuário (ou o autor técnico).
  - **Patch panel com um lado só**: portas de patch panel com o fundo ou a frente ligado e o outro vazio (o cabo para no meio do caminho).
- **Navegação**: a trilha mostra Rede › equipamento › porta; da porta, o nome do equipamento volta para a face dele.
- **Equipamento** (`/rede/equipamentos/:id`): a **face** desenhada pelo modelo (grade + portas extras). **Verde = ligada, vermelho =
  desligada**, tracejado = desativada ou sem informação; bolinha âmbar = chamado aberto. Clicar na porta abre o detalhe dela. Abaixo, a lista
  de portas (no patch panel, a coluna "Ligado a" mostra o fundo e a frente). Quem administra vê o botão **Editar**, que abre a página de edição.
- **Porta** (`/rede/portas/:id`): primeiro o cartão **Ligado a** (no patch panel, dois blocos: **Fundo** e **Frente**, cada um com o que está
  ligado e o Desligar, ou o formulário para ligar; ligando em outro patch panel, escolhe-se também o lado da porta dele). Depois a configuração:
  a **descrição é só leitura** (gerada pelo sistema), a **observação** é livre, e modo/VLANs/IP/velocidade só aparecem com algo ligado (sem
  nada, só a situação Desligada ou Desativada). No patch panel, Terminal Punch Down (`fundo`) e Conector RJ45 (`frente`) ficam lado a lado e o formulário só abre no lado escolhido
  ("Ligar"); "O que está ligado" é escolhido em botões (no patch panel, só bem ou equipamento de rede). O que está ligado aparece num cartão com
  "Abrir porta", "Trocar" e "Desligar"; "Trocar" abre o mesmo formulário e, indo para um lado de patch panel, oferece religar o outro lado no
  destino de hoje. No patch panel, a lateral não mostra velocidade e erros, e o cartão de configuração vira só a observação. VLANs com tag e sem tag em dois campos de busca com selos, como os
  marcadores das Tarefas: o selo mostra só o número, na cor da VLAN, com o nome ao passar o mouse e na busca; "Todas" e "Limpar" ao lado do
  rótulo; embaixo, o resumo em faixas, ex.: "Com tag: 2469–2483 (15 VLANs)"; quem tem Controle total clica no selo e troca a **cor** e o
  **nome** da VLAN, que valem em todas as portas e na aba VLANs (migração `c8e0a2b4d6f9`: as VLANs existentes ganham cor pelo número);
  em patch panel, só a observação), ponto de rede e chamados, com "Abrir chamado desta porta". O caminho mostra, em cada patch panel, por qual
  lado o cabo entra e sai.
- **Cadastro do bem** (Patrimônio): para quem tem acesso à Rede, o quadro "Rede" mostra em qual equipamento e porta o bem está ligado (com o
  lado, no patch panel); quem edita a rede liga (escolhendo o lado, se for patch panel) ou desliga dali mesmo. É a mesma ligação da porta: o que se faz num lugar aparece no outro.
