/**
 * =============================================================================
 * ARQUIVO: novidades.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Guardar as novidades do SGI SPI em linguagem de usuário final, dia a dia,
 * que alimentam a tela Changelog.
 *
 * RESUMO TÉCNICO:
 * Arquivo só de dados. Exporta MODULOS_NOVIDADE (lista fechada de módulos para
 * o selo), o tipo ModuloNovidade, as interfaces Novidade e DiaNovidades e a
 * constante NOVIDADES, ordenada da data mais recente para a mais antiga. O
 * texto separa parágrafos com duas quebras de linha.
 *
 * FINALIDADE DE NEGÓCIO:
 * Informa a quem usa o sistema o que mudou no seu trabalho (telas, regras,
 * fluxos, documentos gerados), sem termos técnicos. É diferente do
 * CHANGELOG.md, que é o registro técnico para a equipe de desenvolvimento.
 *
 * CONTEXTO NO SISTEMA:
 * Lido por changelog.component.ts. A data do primeiro dia precisa ser igual a
 * ULTIMA_NOVIDADE em core/changelog/ultima-novidade.ts (acende a bolinha do
 * menu); novidades.spec.ts confere a ordem, essa data e a linguagem.
 *
 * =============================================================================
 */

/**
 * Novidades do sistema para quem usa o SGI SPI, só dos dias com mudança de negócio (o que muda no trabalho de alguém).
 *
 * Diferente do CHANGELOG.md (técnico: endpoints, migrações, scripts), aqui o texto é para o usuário final: o que ele
 * passa a poder fazer, o que mudou na tela e por quê. Sem nomes de arquivo, rotas ou termos técnicos.
 *
 * Regras para acrescentar um dia:
 * - o dia mais recente fica no topo da lista (ordem decrescente de data, sem datas repetidas);
 * - atualize `ULTIMA_NOVIDADE` em `core/changelog/ultima-novidade.ts` com a mesma data (o teste confere);
 * - cada novidade diz o módulo, um título curto e o texto; `itens` é opcional, para listar detalhes.
 */

/**
 * Módulos aceitos no selo da novidade. O `as const` faz o TypeScript tratar a lista como valores fixos,
 * o que permite derivar o tipo ModuloNovidade logo abaixo (um módulo fora da lista não compila).
 */
export const MODULOS_NOVIDADE = [
  'Geral', 'Contratos', 'RH', 'Tarefas', 'Notícias', 'Patrimônio', 'Protocolo', 'Chamados', 'Rede',
  'Contratações', 'Melhorias', 'Ramais', 'Reserva de Espaços', 'Manuais', 'Notificações', 'Administração',
] as const;

/** Módulo da novidade (selo exibido na tela). */
export type ModuloNovidade = (typeof MODULOS_NOVIDADE)[number];

/** Uma novidade dentro de um dia: o selo do módulo, o título e a explicação. */
export interface Novidade {
  modulo: ModuloNovidade;
  titulo: string;
  /** Explicação em um ou dois parágrafos curtos (separe parágrafos com `\n\n`). */
  texto: string;
  /** Detalhes em tópicos, quando ajudam a leitura. */
  itens?: string[];
}

/** Um dia do Changelog com todas as novidades daquele dia. */
export interface DiaNovidades {
  /** AAAA-MM-DD. */
  data: string;
  /** Uma frase com o principal do dia (aparece na lista de dias). */
  resumo: string;
  novidades: Novidade[];
}

/** Lista de dias com novidade, do mais recente (primeiro) para o mais antigo. */
export const NOVIDADES: DiaNovidades[] = [
  {
    data: '2026-11-13',
    resumo: 'Contratos: tornar sem efeito e aba Eventos; cálculo manual ou automático na memória retroativa; Rede: Conector RJ45 e Terminal Punch Down',
    novidades: [
      {
        modulo: 'Contratos',
        titulo: 'Tornar sem efeito reajuste, repactuação, aditamento e prorrogação',
        texto: 'Um reajuste, uma repactuação, um aditamento ou supressão, uma prorrogação ou uma vigência retroativa já concluídos agora podem ser tornados sem efeito pelo botão "Tornar sem efeito", no histórico de cada tela. O sistema desfaz o que o evento aplicou: os preços e as quantidades voltam ao que eram, e a competência de diferença e o crédito que ele gerou saem. O motivo é obrigatório, e o evento continua no histórico com o selo "Sem efeito", com o seu nome, a data e o motivo.',
        itens: [
          'O botão fica desativado, com o motivo à vista, quando algo depende do evento. Por exemplo: um mês já foi medido com o preço novo, a competência de diferença já foi medida, o crédito já foi aplicado numa medição ou há outro reajuste concluído depois. Nesses casos, é preciso reabrir ou desfazer antes.',
          'Pode usar o botão quem é da equipe do contrato.',
        ],
      },
      {
        modulo: 'Contratos',
        titulo: 'Aba Eventos no contrato',
        texto: 'Quem administra contratos (Controle total) ganhou a aba "Eventos" no contrato. Ela mostra tudo o que aconteceu nele, com data, quem fez e o detalhe, separado em Alteram o contrato, Execução, Documentos, Equipe e cadastro e Sem efeito, com barra de pesquisa e colunas ordenáveis. Nas conclusões, o botão "Tornar sem efeito" também aparece por ali.',
      },
      {
        modulo: 'Contratos',
        titulo: 'Repactuação e reajuste: cálculo manual ou automático',
        texto: 'A memória retroativa da repactuação e do reajuste agora começa com a pergunta "Cálculo manual ou automático?". No automático, nada muda: o sistema calcula a diferença dos meses já medidos. No manual, o sistema não calcula nada sozinho: você informa a diferença de cada mês, e o total é a soma deles.',
        itens: [
          'No manual dá para informar qualquer mês da data de vigência até o mês atual, inclusive os já medidos no sistema e o mês em andamento.',
          'Cada mês mostra a situação: "Medido no SGI", "Sem medição no SGI" ou "Em andamento".',
          'Os meses informados ficam no preço antigo. Se o total for positivo, vira uma competência de diferença com uma linha por mês. Se for negativo, vira crédito da SPI.',
          'Justificativa e a memória feita fora do sistema (PDF) continuam obrigatórias. Trocar de manual para automático apaga os valores informados.',
        ],
      },
      {
        modulo: 'Contratos',
        titulo: 'Consolidado da repactuação com contracapa em cada documento',
        texto: 'No documento consolidado da repactuação, cada documento do checklist agora vem depois de uma contracapa. Ela mostra qual é o documento (por exemplo, "Documento 2 de 9"), o nome do item, o arquivo e quem enviou, como já acontece no consolidado da competência. Para ter as contracapas numa repactuação em andamento, gere o consolidado de novo.',
      },
      {
        modulo: 'Rede',
        titulo: 'Patch panel: Conector RJ45 e Terminal Punch Down',
        texto: 'Os dois lados da porta do patch panel mudaram de nome: a Frente agora se chama Conector RJ45 e o Fundo, Terminal Punch Down. Os nomes novos aparecem na tela da porta, na descrição automática e no caminho até o core. As ligações já cadastradas continuam as mesmas.',
      },
      {
        modulo: 'Rede',
        titulo: 'Trocar a ligação sem desligar antes',
        texto: 'O que está ligado numa porta ganhou o botão "Trocar": você escolhe o novo destino e o sistema troca numa operação só, sem deixar o equipamento sem caminho até o core. Para pôr um patch panel no meio de um cabo que já existe, escolha o lado da porta do patch panel e deixe marcado "Ligar o outro lado desta porta do patch panel no destino de hoje".',
        itens: [
          'No patch panel, o Fundo e a Frente aparecem lado a lado; o formulário só abre no lado em que você clicar em "Ligar".',
          'O tipo do que está ligado agora é escolhido em botões. No patch panel, as opções são bem do Patrimônio ou equipamento de rede.',
          'O que está ligado aparece num cartão, com os botões "Abrir porta", "Trocar" e "Desligar".',
        ],
      },
      {
        modulo: 'Geral',
        titulo: 'Changelog só com os módulos que você usa',
        texto: 'Esta página agora mostra apenas as novidades dos módulos a que você tem acesso. A bolinha vermelha do menu também só acende quando há novidade nesses módulos.',
      },
    ],
  },
  {
    data: '2026-11-12',
    resumo: 'Rede recomeçada: cadastro em cadeia, fundo e frente no patch panel e descrição automática',
    novidades: [
      {
        modulo: 'Rede',
        titulo: 'A Rede foi refeita para desenhar a topologia certa',
        texto: 'O cadastro da Rede recomeça do zero, agora de cima para baixo. Primeiro o core, depois a distribuição, o acesso e, por último, access points, roteadores e demais. Cada equipamento novo já entra dizendo onde está ligado: "este switch, na porta X, está conectado no switch Y, na porta Y", com a configuração das duas portas na mesma tela. Sem o core não dá para cadastrar a distribuição, e sem a distribuição não dá para cadastrar o acesso.\n\nO cadastro é feito passo a passo (Dados, Conexão e Revisão), em uma página própria. Para alterar um equipamento, use o botão vermelho "Editar" na tela dele. O tipo, a função e o modelo de face não mudam depois de cadastrados.',
        itens: [
          'Patch panel: cada porta tem dois lados, o Fundo e a Frente, e cada lado tem a sua ligação. O caminho até o core segue o cabo daquela porta, entrando por um lado e saindo pelo outro.',
          'O cabo do cadastro pode passar por um patch panel, desde que o outro lado daquela porta leve ao equipamento de cima.',
          'A descrição da porta agora é automática: mostra o que está ligado nela, ou "Desligado". Para anotações, use o campo Observação.',
          'Porta sem nada ligado fica desligada e em branco. A configuração (modo, VLANs, velocidade) aparece depois de ligar algo nela.',
          'Nenhum equipamento fica sem cabo para o equipamento de cima: para trocar de porta, ligue a nova antes de desligar a antiga.',
          'A topologia segue sempre as camadas: core no topo, depois distribuição, acesso e os demais.',
          'Novo indicador "Patch panel com um lado só": portas em que o cabo para no meio do caminho.',
        ],
      },
    ],
  },
  {
    data: '2026-11-11',
    resumo: 'Diário de bordo: ocorrências também para outros e-mails, guardados no contrato',
    novidades: [
      {
        modulo: 'Contratos',
        titulo: 'Diário de bordo: envie a ocorrência para outros e-mails além dos prepostos',
        texto: 'Ao marcar "Enviar por e-mail" numa ocorrência, aparece o campo "Outros e-mails desta ocorrência". Digite o endereço e aperte Enter (ou "Adicionar"): ele vira uma pílula e recebe o registro junto com a equipe e os prepostos escolhidos.\n\nOs e-mails usados ficam guardados no contrato. Nas próximas ocorrências dele, aparecem em "Usados antes neste contrato", desmarcados: basta clicar para incluir.',
        itens: [
          'Cada contrato tem a sua lista. O que é digitado num contrato não aparece nos outros.',
          'O "×" ao lado de um e-mail guardado tira ele da lista do contrato. As ocorrências já registradas não mudam.',
          '"Reenviar" agora manda para as mesmas pessoas escolhidas no registro (prepostos e outros e-mails), não mais para todos os prepostos.',
        ],
      },
    ],
  },
  {
    data: '2026-11-10',
    resumo: 'Diferença do reajuste informada à mão, créditos aplicados pelo gestor e esta página de novidades',
    novidades: [
      {
        modulo: 'Contratos',
        titulo: 'Meses pagos fora do sistema: informe a diferença do reajuste ou da repactuação',
        texto: 'O cálculo automático da diferença retroativa só enxerga os meses com medição concluída no SGI. Agora, quando houver meses já encerrados sem medição (por exemplo, pagos antes da implantação do sistema), o reajuste e a repactuação perguntam: "Deseja inserir o valor da diferença manualmente?".\n\nNo "Sim", você marca os meses pagos fora do sistema e informa o valor total da diferença, a justificativa e o PDF da sua memória de cálculo. Esses meses ficam com o preço que foi pago de fato e não entram no cálculo automático.',
        itens: [
          'Valor positivo: vira uma competência complementar de uma linha, paga pelo fluxo normal (NE, nota fiscal, consolidado e OB).',
          'Valor negativo: vira um crédito da SPI, guardado no contrato.',
          'Todo documento que cita o valor traz a observação de quem informou, quando, quais meses e por quê.',
        ],
      },
      {
        modulo: 'Contratos',
        titulo: 'Créditos de reajuste e repactuação: você escolhe a medição',
        texto: 'Os créditos da SPI (desconto retroativo de reajuste ou de repactuação) não são mais descontados automaticamente na medição seguinte. Eles ficam guardados no contrato e aparecem no quadro "Créditos disponíveis" da medição.\n\nO gestor aplica cada crédito inteiro na medição que escolher, ou retira enquanto a medição estiver aberta. Se o crédito for maior que a medição, a sobra volta a ficar disponível. Nos documentos, cada crédito aparece com a origem, como "Crédito de Reajuste (ref. 01/2026)".',
      },
      {
        modulo: 'Geral',
        titulo: 'Nova página de novidades',
        texto: 'Esta página reúne, dia a dia, as mudanças que afetam o seu trabalho no SGI SPI, em linguagem simples. Quando houver novidade que você ainda não viu, aparece uma bolinha vermelha no item "Changelog" do menu.',
      },
    ],
  },
  {
    data: '2026-11-06',
    resumo: 'RDM nas Tarefas, atualização do sistema pela tela e indicadores da Rede',
    novidades: [
      {
        modulo: 'Tarefas',
        titulo: 'RDM: Requisição de Mudança dentro da tarefa',
        texto: 'Tarefas de equipe ganharam a RDM, no modelo de formulário da Prodesp: objetivo, justificativa, categorização, janela de implantação, plano de execução, comunicação e plano de retorno (rollback).\n\nAo enviar, a RDM recebe um número no Protocolo ("RDM SGI 00001/2026") e vai para a liderança aprovar ou reprovar. Aprovada, gera o PDF, que vai por e-mail para os responsáveis e fica no número do Protocolo. A cor do selo mostra a situação: pendente, aprovada, reprovada ou concluída. Há também uma lista com todas as RDMs.',
      },
      {
        modulo: 'Administração',
        titulo: 'Atualização do sistema pela tela',
        texto: 'Em Administração › Versões do sistema, o SuperRoot vê as versões aprovadas e instala a nova com um clique. Antes de instalar, o sistema faz um backup geral; se algo falhar, volta sozinho para a versão anterior.',
      },
      {
        modulo: 'Rede',
        titulo: 'Indicadores, histórico das portas e VLANs com cor',
        texto: 'A Rede ganhou indicadores no topo (portas alteradas nos últimos 7 dias e portas ativas sem descrição), histórico de quem alterou cada porta e VLANs com cor, como os marcadores das Tarefas.',
        itens: [
          'A porta mostra "Última alteração: nome - data e hora".',
          'A descrição da porta passou a ser obrigatória.',
          'O modelo de face do equipamento não muda depois de escolhido.',
        ],
      },
      {
        modulo: 'Contratos',
        titulo: 'Mês de virada da vigência fica cheio',
        texto: 'Numa prorrogação ou vigência retroativa sem interrupção, o mês da virada passa a ser um mês cheio, na vigência nova, com uma linha por item (antes eram dois trechos). Cadastrar ou desfazer uma vigência também ajusta sozinho as competências ainda não medidas.',
      },
    ],
  },
  {
    data: '2026-11-04',
    resumo: 'Repactuação de contrato pela Convenção Coletiva (CCT)',
    novidades: [
      {
        modulo: 'Contratos',
        titulo: 'Repactuação pela CCT',
        texto: 'Quando a Convenção Coletiva de Trabalho muda componentes de custo (vale-transporte, vale-alimentação, plano de saúde…), a diferença de cada um soma no preço dos itens do contrato vinculados a ele, a partir da data de vigência. Fica no contrato, aba Itens › Repactuação.',
        itens: [
          'A CCT vai para os Documentos importantes como "CCT mm/aaaa".',
          'Memória de cálculo em PDF e XLSX, com a nova base mensal.',
          'Retroativo como no reajuste: competências medidas recebem a diferença à parte; mês quebrado pro rata ou integral.',
          'Checklist próprio, documento consolidado e finalização com o apostilamento.',
        ],
      },
    ],
  },
  {
    data: '2026-11-03',
    resumo: 'Módulo Chamados (substitui o GLPI) e módulo Rede',
    novidades: [
      {
        modulo: 'Chamados',
        titulo: 'Chamados no próprio SGI',
        texto: 'O módulo Chamados substitui o GLPI: abrir com assunto e local ("Onde podemos te encontrar?"), acompanhar, conversar com quem atende e avaliar o atendimento. Quem atende tem fila por setor, prazos, respostas prontas, tarefas, aprovações e chamados recorrentes.',
        itens: [
          'Painel de TV com voz, que anuncia chamados novos, assumidos e resolvidos.',
          'Relatórios com indicadores, desempenho da equipe e satisfação, exportáveis em PDF e Excel.',
          'Nomeação e Exoneração do RH abrem chamados para cada serviço envolvido.',
        ],
      },
      {
        modulo: 'Rede',
        titulo: 'Plano de face da rede',
        texto: 'Novo módulo Rede: racks, switches com a face desenhada, portas, VLANs, pontos de rede e o que está ligado em cada porta (inclusive em cascata, como switch → telefone → computador). Mostra a topologia, o caminho de uma porta até o core e se cada equipamento está no ar.',
      },
      {
        modulo: 'Geral',
        titulo: 'Seus perfis de acesso somam',
        texto: 'Quem tem mais de um perfil de acesso passa a ter todos ao mesmo tempo, sem precisar trocar de perfil.',
      },
    ],
  },
  {
    data: '2026-10-30',
    resumo: 'Prorrogação no fluxo novo, reajuste com meses quebrados e backup geral',
    novidades: [
      {
        modulo: 'Contratos',
        titulo: 'Prorrogação em etapas',
        texto: 'A prorrogação ganhou um fluxo guiado: meses, meses quebrados (pro rata ou integral, lado a lado), itens sob demanda, memória de cálculo (PDF e XLSX com a tabela mês a mês), checklist e termo. Depois da assinatura, registra PNCP, DOE e garantia. Também dá para cadastrar vigências retroativas.',
      },
      {
        modulo: 'Contratos',
        titulo: 'Reajuste com meses quebrados',
        texto: 'Quando a data de efeito do reajuste cai no meio de um mês já medido, você escolhe uma vez, para todos esses meses, se a diferença é pro rata (só os dias depois do efeito) ou integral (o mês inteiro). As duas opções aparecem lado a lado com os valores.',
      },
      {
        modulo: 'Contratos',
        titulo: 'Outras melhorias em Contratos',
        texto: 'O item do contrato é cadastrado respondendo perguntas (tipo e faturamento). Os checklists da execução aceitam documentos incluídos durante o processo. Fica registrado quem pediu o processo financeiro ao DOF.',
      },
      {
        modulo: 'Contratações',
        titulo: 'Orientação por seção e cópia rápida',
        texto: 'ETP e TR ganharam sumário lateral, botão de copiar cada seção, a orientação da IN SEGES/ME 58/2022 em cada seção (só na tela) e a opção de reabrir um documento concluído para edição.',
      },
      {
        modulo: 'Administração',
        titulo: 'Backup geral',
        texto: 'O SuperRoot gera um arquivo com todo o banco e os anexos, e pode importar o backup de outro servidor, com uma janela que mostra o andamento.',
      },
    ],
  },
  {
    data: '2026-10-28',
    resumo: 'Correção na diferença do reajuste',
    novidades: [
      {
        modulo: 'Contratos',
        titulo: 'Itens "sempre integral" com o mês cheio na diferença do reajuste',
        texto: 'Quando a data de efeito do reajuste caía no meio de um mês já medido, itens com faturamento sempre integral tinham a diferença calculada só pelos dias restantes. Agora recebem a diferença do mês todo, como devem.',
      },
    ],
  },
  {
    data: '2026-10-25',
    resumo: 'Menu configurável, painel do RH e curtidas nos cartões de contato',
    novidades: [
      {
        modulo: 'Administração',
        titulo: 'Menu lateral configurável',
        texto: 'O administrador ordena, agrupa, renomeia e oculta itens do menu, e cria grupos e links para todos. Ocultar um item tira ele do menu e da busca, sem mudar quem tem acesso.',
      },
      {
        modulo: 'RH',
        titulo: 'Entrada única do RH',
        texto: 'O RH abre num painel com as telas agrupadas por finalidade: Estrutura, Entrada de pessoas, Vida funcional e Configuração.',
      },
      {
        modulo: 'Ramais',
        titulo: 'Curtir o cartão e cartão redesenhado',
        texto: 'Dá para curtir o cartão de contato de um colega; só o dono vê quem curtiu e recebe um aviso. O cartão ficou mais largo, em duas colunas, com LinkedIn e WhatsApp como botões.',
      },
      {
        modulo: 'Tarefas',
        titulo: 'Menos tarefas por competência de contrato',
        texto: 'As competências deixaram de gerar as tarefas "Subir no SEI" e "Despachar".',
      },
    ],
  },
  {
    data: '2026-10-23',
    resumo: 'RH reestruturado: cargos, organograma, pré-cadastro e admissão',
    novidades: [
      {
        modulo: 'RH',
        titulo: 'Cargos, organograma e histórico funcional',
        texto: 'Os setores passam a ser geridos no RH. Os cargos viram vagas, com ocupações e histórico. O organograma mostra a árvore da SPI com foto e cartão de cada pessoa, e cada servidor tem o seu histórico funcional.',
      },
      {
        modulo: 'RH',
        titulo: 'Pré-cadastro e admissão em 7 etapas',
        texto: 'A entrada de uma pessoa começa no pré-cadastro (ficha completa, também por planilha) e segue numa admissão guiada: formulário, documentos por checklist, resolução, número no Protocolo, publicação, posse e acesso ao SGI. Ao entrar, a pessoa recebe boas-vindas e pode completar o próprio cadastro.',
      },
      {
        modulo: 'Contratos',
        titulo: 'Quem é o Financeiro passa a ser definido no Controle de acesso',
        texto: 'Quem confere a retenção de tributos e recebe os avisos da nota fiscal agora é definido pelo Controle de acesso (recurso Financeiro), e não mais por um setor fixo.',
      },
      {
        modulo: 'Protocolo',
        titulo: 'Faixa reservada e setores por tipo',
        texto: 'A faixa reservada passa a ser da Coordenadoria de Gestão e Infraestrutura (CGI), cada tipo de documento tem o setor que pode usar os números, e a resolução do RH pode ficar sem número.',
      },
    ],
  },
  {
    data: '2026-10-20',
    resumo: 'E-mail único da medição, prazo em dias úteis e baixa de bens',
    novidades: [
      {
        modulo: 'Contratos',
        titulo: 'Um só e-mail da medição para a contratada',
        texto: 'A contratada recebe um único e-mail com a medição (e, quando houver, o relatório de avaliação para assinar), pedindo a nota fiscal em PDF e XML no valor líquido a faturar, ou a contestação, em até N dias úteis. A escolha dos prepostos e do prazo é obrigatória.',
        itens: [
          'O prazo conta em dias úteis (sem fins de semana e feriados), com uma barra de progresso; anexar a nota fiscal encerra o prazo.',
          'O documento executivo da medição mostra o valor líquido a faturar.',
          'Quem cadastrou o contrato também pode conduzir a portaria de designação.',
        ],
      },
      {
        modulo: 'Patrimônio',
        titulo: 'Baixa de bens pela lista aprovada e dados do SAM',
        texto: 'A baixa parte de uma lista de inservíveis aprovada, aguarda o aceite da autoridade e conclui quando alguém com controle total anexa o de acordo ou o D.O.E. Os bens também passaram a mostrar os dados do SAM (contas, depreciação, incorporação).',
      },
      {
        modulo: 'Reserva de Espaços',
        titulo: 'Quem solicita e quem aprova',
        texto: 'O Controle de acesso separa quem pode solicitar reservas, quem pode aprovar e quem administra os espaços.',
      },
      {
        modulo: 'Geral',
        titulo: 'Trilha de etapas igual em todo o sistema',
        texto: 'Os processos com várias etapas (competência, reajuste, prorrogação, portaria, baixa de bens, férias e outros) mostram o andamento com a mesma trilha numerada.',
      },
    ],
  },
  {
    data: '2026-10-19',
    resumo: 'Portaria de designação em etapas e perfis de acesso',
    novidades: [
      {
        modulo: 'Contratos',
        titulo: 'Portaria de designação em etapas',
        texto: 'A equipe do contrato só muda por portaria: nomeações, ciência de cada nomeado (no sino e por e-mail), escolha da autoridade com o número reservado no Protocolo, aceite e publicação. Ao publicar, a equipe é aplicada sozinha. A equipe não é mais editável no "Editar" do contrato.',
      },
      {
        modulo: 'Contratos',
        titulo: 'Diário de bordo em PDF e rascunhos compartilhados',
        texto: 'O PDF do diário de bordo virou um diário de verdade (uma página por dia, com os anexos no fim). A equipe compartilha rascunhos do contrato, e os e-mails de CADIN e de pagamento seguem modelos.',
      },
      {
        modulo: 'Geral',
        titulo: 'Perfis de acesso',
        texto: 'O Controle de acesso ganhou perfis com ações por módulo, que podem ser dados a uma pessoa ou a um setor inteiro.',
      },
      {
        modulo: 'Patrimônio',
        titulo: 'Colaboradores e categorias do inservível',
        texto: 'As listas e a baixa aceitam colaboradores. O inservível ganhou categorias (ocioso, recuperável, antieconômico, irrecuperável) e a justificativa usa editor de texto.',
      },
      {
        modulo: 'Tarefas',
        titulo: 'Comentários com texto formatado',
        texto: 'Histórico e comentários aceitam texto formatado, e concluir a tarefa mãe conclui as subtarefas.',
      },
    ],
  },
  {
    data: '2026-10-15',
    resumo: 'Despacho de pagamento, nova ordem das etapas e empenho na aba Principal',
    novidades: [
      {
        modulo: 'Contratos',
        titulo: 'Despacho de pagamento pronto para copiar',
        texto: 'Na etapa Download, abaixo do consolidado, aparece o despacho de pagamento já preenchido (contrato, competência, equipe e autoridade), com o botão "Copiar despacho". O modelo fica em Contratos › Modelos, e a autoridade do despacho é definida no contrato.',
      },
      {
        modulo: 'Contratos',
        titulo: 'CADIN por último e empenho à vista',
        texto: 'Depois da nota fiscal, a retenção e o checklist correm juntos; o CADIN passa a ser a última etapa antes do Download. A aba Principal mostra o cartão "Empenho do exercício" (empenhado, comprometido, utilizado e saldo livre). O diário de bordo usa editor de texto.',
      },
      {
        modulo: 'Patrimônio',
        titulo: 'Número nas listas e a sala inteira de uma vez',
        texto: 'Listas de inservíveis, de extraviados e baixas ganham número. Escolher uma sala oferece incluir todos os bens dela, e as barras do painel abrem a lista de bens.',
      },
      {
        modulo: 'Tarefas',
        titulo: 'Subtarefas herdam os responsáveis',
        texto: 'Quem entra ou sai da tarefa mãe entra ou sai também das subtarefas abertas.',
      },
    ],
  },
  {
    data: '2026-10-13',
    resumo: 'Módulo Patrimônio, Notificações e NE de cancelamento',
    novidades: [
      {
        modulo: 'Patrimônio',
        titulo: 'Novo módulo Patrimônio',
        texto: 'Bens com chapa, cadastro avulso e em lote, leitura de código de barras e QR pela câmera, salas com QR na porta, movimentações, inservíveis e extraviados, baixa, histórico, relatórios em PDF e Excel e uso no celular, inclusive sem internet.',
      },
      {
        modulo: 'Notificações',
        titulo: 'Notificações com preferências e aviso no navegador',
        texto: 'A caixa de mensagens virou Notificações: você escolhe por onde quer ser avisado de cada assunto e pode receber avisos no navegador.',
      },
      {
        modulo: 'Contratos',
        titulo: 'NE de cancelamento e acerto de centavos',
        texto: 'Uma Nota de Empenho pode ser cancelada total ou parcialmente por uma NE de cancelamento. Na medição, a coluna "Acerto (R$)" corrige diferenças de centavos por item. Pendências e alertas mostram só os contratos de quem recebe.',
      },
      {
        modulo: 'Tarefas',
        titulo: 'Subtarefas, Gantt e editor de texto',
        texto: 'A descrição aceita texto formatado. Subtarefas ganharam quadro próprio e dependências, e a equipe tem a visão Gantt e a visão Atividade (o que aconteceu a cada dia).',
      },
      {
        modulo: 'Geral',
        titulo: 'Visual novo e colunas personalizáveis',
        texto: 'O sistema ganhou a nova identidade visual, nos temas claro e escuro, e cada pessoa escolhe as colunas das listagens.',
      },
    ],
  },
  {
    data: '2026-10-09',
    resumo: 'Portarias de designação e marcadores da competência na carteira',
    novidades: [
      {
        modulo: 'Contratos',
        titulo: 'Portaria de designação da gestão e fiscalização',
        texto: 'O contrato passou a gerar a portaria de designação, com o número reservado no Protocolo, o texto vindo de modelos editáveis e o aceite da autoridade. O PDF publicado fica no Protocolo e nos Documentos importantes.',
      },
      {
        modulo: 'Contratos',
        titulo: 'Carteira mostra a competência de cada contrato',
        texto: 'A carteira ganhou a coluna Competência, com a etapa em aberto (medição, nota fiscal, retenção…), "Atrasada" ou "Em dia". Um clique abre a execução.',
      },
      {
        modulo: 'Tarefas',
        titulo: 'Dias em aberto e memorial da tarefa',
        texto: 'O cartão mostra há quantos dias a tarefa está aberta, e o detalhe gera o memorial em PDF ou Excel com todo o histórico. As subtarefas saíram do quadro principal e têm quadro próprio.',
      },
    ],
  },
  {
    data: '2026-10-08',
    resumo: 'Despesas variáveis, calendário de vencimentos e Tarefas mais completas',
    novidades: [
      {
        modulo: 'Contratos',
        titulo: 'Despesas variáveis na medição',
        texto: 'Marque os itens que são despesa variável: a medição mostra o subtotal da medição, o das despesas e o total. Na nota fiscal, junte também a nota de débito, recibo ou outro documento da despesa.',
      },
      {
        modulo: 'Contratos',
        titulo: 'Calendário de vencimentos e PDFs autenticados',
        texto: 'Nova tela com os vencimentos dos contratos (vigência, reajuste, pagamento, documentos, empenho) por mês ou semana. Avaliação, memória e consolidado ganharam código de verificação, conferível numa tela própria.',
      },
      {
        modulo: 'Tarefas',
        titulo: 'Repetição, desempenho, marcadores e marcos',
        texto: 'As Tarefas ganharam várias ferramentas para as equipes:',
        itens: [
          'Repetição automática (dia, semana, mês ou ano).',
          'Tela Desempenho para a liderança, com gráficos explicados.',
          'Marcadores coloridos, subtarefas e dependências.',
          'Etapas próprias por equipe.',
          'Atividades agendadas, seguir uma tarefa e menção com @login.',
          'Marcos com data-alvo e atualizações de status da equipe.',
          'As tarefas de contratos ficam na equipe Contratos.',
        ],
      },
      {
        modulo: 'Geral',
        titulo: 'Prazos em dias úteis e Ctrl+K',
        texto: 'Tarefas e Melhorias têm metas de resposta e de resolução em dias úteis. A paleta de comandos (Ctrl+K) reúne ações rápidas, telas e busca numa só janela.',
      },
    ],
  },
  {
    data: '2026-10-06',
    resumo: 'Manuais dentro do portal e recusa da nota fiscal pelo Financeiro',
    novidades: [
      {
        modulo: 'Manuais',
        titulo: 'Manuais do sistema dentro do portal',
        texto: 'O novo item Manuais mostra as instruções do livro "SGI SPI" do BookStack no próprio portal, com sumário e página anterior/próxima, sem precisar de conta no BookStack.',
      },
      {
        modulo: 'Contratos',
        titulo: 'O Financeiro pode recusar a nota fiscal',
        texto: 'Na retenção, o Financeiro recusa a nota com justificativa: a etapa da nota fiscal reabre, a equipe e os prepostos recebem o PDF da recusa e o ciclo se repete até a nota certa. O consolidado mostra a trilha das notas.',
      },
      {
        modulo: 'Geral',
        titulo: 'Horário de Brasília e busca de empresas',
        texto: 'Datas e horas dos PDFs e relatórios saem no horário de Brasília. A busca global também encontra as empresas contratadas.',
      },
    ],
  },
  {
    data: '2026-10-05',
    resumo: 'Abrir chamado pelo SGI, busca global e reaproveitamento de documentos',
    novidades: [
      {
        modulo: 'Geral',
        titulo: 'Abrir chamado pelo SGI',
        texto: 'O item "Abrir Chamado" do menu abre o chamado no GLPI em seu nome, com seus dados já preenchidos e até 5 anexos (inclusive print colado com Ctrl+V).',
      },
      {
        modulo: 'Geral',
        titulo: 'Busca global, favoritos e recentes',
        texto: 'A busca no topo (Ctrl+K ou /) encontra contratos, tarefas, pessoas, setores e telas. Dá para favoritar itens do menu, e o menu mostra as últimas telas visitadas. Links digitados nos textos viram links clicáveis.',
      },
      {
        modulo: 'Contratos',
        titulo: 'Documentos da empresa reaproveitados entre contratos',
        texto: 'Certidões marcadas como "Documento da empresa" anexadas num contrato podem ser usadas nos outros contratos da mesma empresa, enquanto valerem. A carteira tem todas as colunas ordenáveis.',
      },
      {
        modulo: 'Tarefas',
        titulo: 'Aviso diário das tarefas atrasadas',
        texto: 'A liderança recebe um aviso por dia com a tabela das tarefas atrasadas da equipe, em vez de um e-mail por tarefa.',
      },
    ],
  },
  {
    data: '2026-10-04',
    resumo: 'Tema escuro e índice clicável no consolidado',
    novidades: [
      {
        modulo: 'Geral',
        titulo: 'Tema escuro',
        texto: 'No menu do usuário, escolha o tema Claro, Escuro ou Auto (segue o computador). A escolha acompanha você em outros aparelhos.',
      },
      {
        modulo: 'Contratos',
        titulo: 'Consolidado com índice clicável e importação de checklists',
        texto: 'O documento consolidado começa pelo índice, e cada item leva direto ao documento. Checklists e formulários de avaliação podem ser importados por planilha.',
      },
      {
        modulo: 'Ramais',
        titulo: 'Ramais em tela cheia',
        texto: 'A página de Ramais usa toda a largura da tela e mostra mais contatos por página.',
      },
    ],
  },
  {
    data: '2026-10-02',
    resumo: 'Módulos Contratações e Protocolo',
    novidades: [
      {
        modulo: 'Contratações',
        titulo: 'ETP e TR no SGI',
        texto: 'O módulo Contratações escreve o ETP e o TR com editor de texto, revisores que comentam e propõem mudanças, versões que mostram o que mudou (com restauração), exportação em Word e PDF e importação de Word. Cada documento é visto só por quem o criador compartilhou.',
      },
      {
        modulo: 'Protocolo',
        titulo: 'Numeração institucional',
        texto: 'O módulo Protocolo numera ofícios, portarias e resoluções por tipo e ano, com próximo número, histórico, sigilo, vínculo com contrato, painel e exportação.',
      },
    ],
  },
  {
    data: '2026-10-01',
    resumo: 'Preço unitário com até 4 casas decimais',
    novidades: [
      {
        modulo: 'Contratos',
        titulo: 'Valor unitário com até 4 casas',
        texto: 'O preço unitário dos itens aceita até 4 casas decimais (ex.: R$ 0,075 por página), no cadastro, na importação, na medição, no reajuste e no aditamento. Subtotais e totais continuam em centavos.',
      },
    ],
  },
  {
    data: '2026-09-30',
    resumo: 'Portal de notícias, Melhorias, Tarefas e novo endereço do sistema',
    novidades: [
      {
        modulo: 'Notícias',
        titulo: 'Portal de notícias como página inicial',
        texto: 'A página inicial do SGI é o portal de notícias da SPI, com destaques, arquivo e atalhos. Redatores escrevem e aprovadores publicam, com agendamento, aviso a setores e comunicados com ciência.',
      },
      {
        modulo: 'Tarefas',
        titulo: 'Módulo Tarefas',
        texto: 'Quadro estilo Trello, lista, calendário e visão por pessoa, com validação da entrega pela liderança, prazos com justificativa, comentários, anexos e avisos por e-mail. As tarefas do sistema antigo foram trazidas.',
      },
      {
        modulo: 'Melhorias',
        titulo: 'Botão "Sugerir melhoria"',
        texto: 'Em qualquer tela, o botão "Sugerir melhoria" envia a sua sugestão com prints. Você acompanha a resposta em Módulos › Melhorias.',
      },
      {
        modulo: 'Contratos',
        titulo: 'Diário de bordo com anexos e impacto na avaliação',
        texto: 'Ocorrências aceitam até 5 anexos e podem ser ligadas a itens da avaliação de qualidade; nesses itens, nota máxima exige justificativa. O relatório de avaliação vai por e-mail à contratada.',
      },
      {
        modulo: 'Geral',
        titulo: 'Novo endereço: portal.spi.sp.gov.br',
        texto: 'O sistema passa a ser acessado por https://portal.spi.sp.gov.br. Os endereços antigos redirecionam para o novo.',
      },
    ],
  },
  {
    data: '2026-09-29',
    resumo: 'Módulo RH: férias, licença-prêmio, folha de ponto e atualização cadastral',
    novidades: [
      {
        modulo: 'RH',
        titulo: 'Férias e licença-prêmio',
        texto: 'Peça férias e licença-prêmio pelo calendário, com o saldo visível. O autorizador aprova ou recusa, e há painel do setor com exportação. As férias seguem o período aquisitivo, com avisos de férias a vencer.',
      },
      {
        modulo: 'RH',
        titulo: 'Folha de ponto em PDF',
        texto: 'No menu do usuário, baixe a folha de ponto do mês no modelo de frequência da SPI, já com feriados, pontos facultativos e afastamentos aprovados.',
      },
      {
        modulo: 'RH',
        titulo: 'Atualização cadastral mensal',
        texto: 'Uma vez por mês o sistema pede para confirmar ou atualizar seus dados, com o superior imediato obrigatório. A CGP valida cada alteração.',
      },
      {
        modulo: 'Geral',
        titulo: 'Agora é SGI SPI – Sistema de Gestão Integrada',
        texto: 'O sistema passou a se chamar SGI SPI. Os setores foram reorganizados pela estrutura oficial da SPI, e os e-mails ganharam o layout oficial com o brasão.',
      },
    ],
  },
  {
    data: '2026-09-28',
    resumo: 'Caixa de mensagens, vigências e reajuste com desconto por item',
    novidades: [
      {
        modulo: 'Notificações',
        titulo: 'Caixa de mensagens e avisos dos contratos',
        texto: 'O sino no topo mostra as pendências. Mensagens podem pedir ciência, e os contratos avisam sozinhos sobre medição, nota fiscal, retenção, vencimento e conclusão de prorrogação, reajuste e aditamento. Quem entra na equipe de um contrato recebe um aviso.',
      },
      {
        modulo: 'Contratos',
        titulo: 'Reajuste com percentual por item',
        texto: 'Cada item tem o seu percentual: positivo reajusta, negativo dá desconto. A diferença das competências já medidas vira competência a pagar ou crédito da SPI.',
      },
      {
        modulo: 'Contratos',
        titulo: 'Linha do tempo das vigências e número livre',
        texto: 'A aba Vigências mostra, por contrato, quanto da vigência já passou, as prorrogações e os reajustes. O número do contrato aceita qualquer formato (ex.: CT-45/2025). A aba Itens gera relatório em PDF.',
      },
    ],
  },
  {
    data: '2026-09-26',
    resumo: 'Importação de contrato por planilha e uma ciência basta',
    novidades: [
      {
        modulo: 'Contratos',
        titulo: 'Importar contrato por planilha',
        texto: 'A carteira importa a planilha "Checklist de Alimentação do Sistema de Contratos", com prévia dos erros antes de cadastrar. Os itens ganharam a Unidade de Fornecimento (UF).',
      },
      {
        modulo: 'Contratos',
        titulo: 'Uma ciência já basta',
        texto: 'Medição, aditamento/supressão e ateste da avaliação avançam com a ciência de um integrante da equipe. A avaliação do gestor só é pedida quando alguma nota fica abaixo da máxima.',
      },
      {
        modulo: 'Contratos',
        titulo: 'Consolidado na ordem da execução',
        texto: 'O documento consolidado segue a ordem das etapas, com contracapa em cada documento enviado e páginas numeradas. O módulo Contratos passa a abrir no painel.',
      },
    ],
  },
  {
    data: '2026-09-25',
    resumo: 'Diário de bordo e retenção de tributos',
    novidades: [
      {
        modulo: 'Contratos',
        titulo: 'Diário de bordo do contrato',
        texto: 'A equipe registra ocorrências, com glosa quando houver. Cada ocorrência vai por e-mail para a equipe e os prepostos, e a medição não passa do saldo descontadas as glosas.',
      },
      {
        modulo: 'Contratos',
        titulo: 'Retenção de tributos pelo XML da nota',
        texto: 'A nota fiscal é enviada com o XML; os valores aparecem na etapa de retenção, que o Financeiro confere. Depois da nota, retenção, CADIN e checklist ficam abertos ao mesmo tempo.',
      },
    ],
  },
  {
    data: '2026-09-24',
    resumo: 'Lançamento do sistema com o módulo Contratos',
    novidades: [
      {
        modulo: 'Contratos',
        titulo: 'Primeira versão no ar',
        texto: 'O sistema entrou no ar com o módulo Contratos completo: carteira, cadastro, empresas e prepostos, documentos importantes, previsão orçamentária, Notas de Empenho, checklists e avaliação, execução mensal, prorrogação, reajuste, aditamento/supressão, painel e relatórios. Os contratos do sistema antigo foram trazidos.',
      },
      {
        modulo: 'Geral',
        titulo: 'Entrar com o login da rede',
        texto: 'O acesso usa o mesmo login e senha da rede da SPI, com perfil institucional e controle de acesso por módulo.',
      },
    ],
  },
];
