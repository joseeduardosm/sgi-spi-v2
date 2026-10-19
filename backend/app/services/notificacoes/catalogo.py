# Criado por José Eduardo Santana Martins
# Este arquivo serve para listar todos os eventos que geram notificação (módulo, rótulo, quem recebe e canais possíveis).
"""Catálogo de eventos das Notificações.

Cada notificação automática nasce de um **evento** (chave estável `modulo.evento`). É por evento que o usuário escolhe os canais
(e-mail, navegador e desktop) na tela de Preferências; a caixa (o sino) sempre recebe. `notificar(..., evento=...)` confere a chave
aqui: um erro de digitação falha no teste, em vez de virar um aviso que ninguém consegue configurar.

Para acrescentar um evento novo: inclua-o em `_MODULOS` (rótulo curto e "quem recebe e quando") e use a chave na chamada de `notificar`.
"""

from dataclasses import dataclass

CANAL_EMAIL = "email"
CANAL_NAVEGADOR = "navegador"
CANAL_DESKTOP = "desktop"
CANAIS = (CANAL_EMAIL, CANAL_NAVEGADOR, CANAL_DESKTOP)
ROTULOS_CANAL = {CANAL_EMAIL: "E-mail", CANAL_NAVEGADOR: "Navegador", CANAL_DESKTOP: "Desktop"}


@dataclass(frozen=True)
class Evento:
    """Um tipo de notificação: o que é, quem recebe e por quais canais pode sair."""

    chave: str
    modulo: str
    rotulo: str
    descricao: str
    canais_disponiveis: tuple[str, ...] = CANAIS


# (chave do módulo, rótulo do módulo, [(evento, rótulo, descrição, canais_disponiveis opcional)])
_MODULOS: list[tuple[str, str, list[tuple]]] = [
    ("comunicados", "Comunicados", [
        ("mensagem", "Comunicado de colega ou setor", "Você recebe quando alguém envia uma notificação a você ou ao seu setor."),
        ("lembrete_ciencia", "Lembrete de ciência pendente", "Você recebe quando um comunicado importante continua sem a sua ciência (lembrete do remetente ou automático, no 3º dia)."),
    ]),
    ("sistema", "Sistema", [
        ("novidades", "Novidades do SGI SPI", "Você recebe o e-mail de novidades (changelog) enviado pela administração.", (CANAL_EMAIL,)),
        ("teste", "Teste de canal", "Notificação que você mesmo envia pelo botão Testar da tela de Preferências."),
    ]),
    ("contratos", "Contratos", [
        ("equipe_incluido", "Incluído na equipe de um contrato", "Você recebe quando alguém cadastra você como gestor, fiscal ou outro papel de um contrato."),
        ("ocorrencia_diario", "Ocorrência no diário do contrato", "A equipe do contrato recebe quando uma ocorrência é registrada no diário."),
        ("medicao_concluida", "Medição concluída", "A equipe do contrato recebe quando uma medição mensal é concluída."),
        ("medicao_adicional", "Medição adicional incluída", "A equipe do contrato recebe quando uma medição adicional é incluída."),
        ("conferir_retencao", "Conferir retenção de tributos", "O Financeiro recebe quando a nota fiscal é juntada e a retenção precisa ser conferida."),
        ("nota_recusada", "Nota fiscal recusada", "A equipe do contrato recebe quando a nota fiscal é recusada e precisa ser reenviada."),
        ("retencao_conferida", "Retenção conferida", "A equipe do contrato recebe quando a retenção de tributos é conferida e a etapa seguinte pode seguir."),
        ("alteracao_concluida", "Prorrogação, reajuste ou alteração concluídos", "A equipe do contrato recebe quando uma prorrogação, um reajuste ou uma alteração é concluída."),
        ("vencimento_contrato", "Vencimento do contrato (90, 60 e 30 dias)", "A equipe do contrato recebe quando faltam 90, 60 e 30 dias para o fim da vigência."),
        ("medicao_atrasada", "Medição atrasada", "A equipe do contrato recebe quando a medição de uma competência está atrasada."),
        ("correcao_itens", "Correção de itens do contrato", "A equipe do contrato recebe quando uma correção de itens é proposta, aplicada ou recusada."),
        ("portaria", "Portaria de designação", "Você recebe quando uma portaria de designação precisa do seu aceite ou muda de situação."),
        ("portaria_nomeacao", "Nomeação em portaria (ciência)", "Você recebe quando é indicado em uma portaria de designação e precisa dar ciência."),
        ("portaria_dados_rh", "Dados do RH pendentes para uma nomeação", "O RH (CGP) recebe quando alguém indicado em uma portaria de designação está com RS/PV, RG/CIN ou cargo em branco."),
    ]),
    ("tarefas", "Tarefas", [
        ("atribuida", "Tarefa atribuída a você", "Você recebe quando uma tarefa é criada para você, quando entra como responsável ou quando ela é transferida a você."),
        ("prazo_alterado", "Prazo alterado", "Os envolvidos recebem quando o prazo de uma tarefa muda."),
        ("aguardando_validacao", "Aguardando sua validação", "Quem valida recebe quando uma entrega aguarda validação, e de novo quando ela fica parada."),
        ("entrega_validada", "Entrega validada", "Os responsáveis recebem quando a entrega é validada."),
        ("entrega_devolvida", "Entrega devolvida", "Os responsáveis recebem quando a entrega é devolvida para ajustes."),
        ("reaberta", "Tarefa reaberta", "Os responsáveis recebem quando uma tarefa é reaberta."),
        ("concluida", "Tarefa concluída", "Os responsáveis e a liderança recebem quando a tarefa é concluída."),
        ("mencao", "Menção a você", "Você recebe quando alguém menciona você em uma tarefa."),
        ("comentario", "Comentário em tarefa", "Os envolvidos recebem quando alguém comenta em uma tarefa."),
        ("vence_amanha", "Tarefa vence amanhã", "Os envolvidos recebem na véspera do prazo."),
        ("atrasada", "Tarefa atrasada", "Os envolvidos recebem quando o prazo passa sem a tarefa estar concluída."),
        ("escalonada", "Tarefas atrasadas das suas equipes", "A liderança recebe, uma vez por dia, a tabela das tarefas atrasadas das suas equipes."),
        ("marco_atingido", "Marco atingido", "A liderança e os membros recebem quando todas as tarefas de um marco são concluídas."),
        ("status_equipe", "Status da equipe", "A liderança e os membros recebem quando o status da equipe é atualizado."),
        ("lembrete_status", "Lembrete para atualizar o status", "A liderança recebe quando a equipe está há uma semana sem atualização de status."),
        ("recorrencia_pausada", "Recorrência pausada", "O criador recebe quando uma tarefa recorrente é pausada por erro."),
        ("atividade_agendada", "Atividade agendada para você", "Você recebe quando uma atividade é agendada para você."),
        ("atividade_concluida", "Atividade concluída", "O criador recebe quando a atividade que ele agendou é concluída."),
        ("atividade_lembrete", "Atividade para hoje ou atrasada", "Você recebe quando uma atividade vence hoje ou está atrasada."),
    ]),
    ("rh", "RH", [
        ("afastamento_aprovacao", "Afastamento aguardando aprovação", "Os aprovadores recebem quando um servidor agenda férias ou outro afastamento."),
        ("afastamento_ciencia", "Afastamento aguardando seu ciente e de acordo", "O superior imediato recebe quando o servidor agenda um afastamento."),
        ("afastamento_situacao", "Situação do seu afastamento", "Você recebe quando o seu pedido de afastamento é aprovado, recusado ou alterado."),
        ("afastamento_cancelado", "Afastamento cancelado", "Os envolvidos recebem quando um afastamento é cancelado."),
        ("boas_vindas", "Boas-vindas no retorno", "Você recebe quando volta de um afastamento."),
        ("afastamento_lembrete", "Pedido de afastamento parado", "Os aprovadores recebem quando um pedido fica parado há 3 dias."),
        ("cadastro_validacao", "Alteração de cadastro aguardando validação", "A CGP recebe quando um servidor altera o cadastro."),
        ("cadastro_recusado", "Alteração do seu cadastro recusada", "Você recebe quando a CGP recusa uma alteração do seu cadastro."),
        ("folha_ponto_bloqueada", "Folha de ponto bloqueada", "A CGP recebe quando um servidor tenta baixar a folha de ponto, mas tem cadastro pendente ou incompleto."),
        ("periodo_ferias", "Novo período de férias", "Você recebe quando começa um novo período aquisitivo."),
        ("prazo_ferias", "Prazo para usar as férias", "Você e quem aprova recebem quando o saldo de férias está perto de expirar."),
    ]),
    ("reserva_espacos", "Reserva de espaços", [
        ("nova_solicitacao", "Nova solicitação de reserva", "Os fiscais do espaço recebem quando uma reserva é solicitada."),
        ("registrada_em_seu_nome", "Reserva registrada em seu nome", "Você recebe quando alguém registra uma reserva em seu nome."),
        ("resposta", "Reserva deferida ou indeferida", "Quem solicitou e o responsável recebem a decisão do fiscal."),
        ("cancelada", "Reserva cancelada", "Os fiscais, o solicitante e o responsável recebem quando uma reserva é cancelada."),
        ("lembrete_vespera", "Lembrete da véspera da reserva", "Quem solicitou e o responsável recebem na véspera da reserva."),
    ]),
    ("contratacoes", "Contratações", [
        ("revisao_nova", "Nova proposta ou comentário em documento", "O criador e os envolvidos recebem quando alguém registra uma proposta de alteração ou um comentário."),
        ("proposta_aplicada", "Proposta de alteração aplicada", "O autor da proposta recebe quando ela é aplicada ao documento."),
        ("revisao_parada", "Revisão parada", "O criador do documento recebe quando uma revisão fica sem resposta."),
    ]),
    ("noticias", "Notícias", [
        ("aguardando_aprovacao", "Notícia aguardando aprovação", "Os aprovadores recebem quando uma notícia é enviada para aprovação."),
        ("aprovada", "Notícia aprovada", "O autor recebe quando a notícia é aprovada."),
        ("devolvida", "Notícia devolvida para ajustes", "O autor recebe quando a notícia é devolvida."),
        ("publicada", "Notícia ou comunicado publicado", "Os destinatários escolhidos recebem quando a notícia ou o comunicado é publicado."),
    ]),
    ("melhorias", "Melhorias", [
        ("nova_sugestao", "Nova sugestão de melhoria", "Quem faz a triagem recebe quando alguém envia uma sugestão."),
        ("andamento", "Andamento da sua sugestão", "O autor recebe quando a sugestão muda de situação."),
    ]),
    ("protocolo", "Protocolo", [
        ("documento_pendente", "Documento pendente no Protocolo", "Quem reservou um número recebe quando o documento continua sem anexo."),
    ]),
    ("patrimonio", "Patrimônio", [
        ("movimentacao_pendente", "Movimentação aguardando autorização", "Quem administra o Patrimônio recebe quando uma movimentação é solicitada."),
        ("movimentacao_decidida", "Movimentação autorizada, recusada ou concluída", "Quem solicitou recebe a decisão e a conclusão da movimentação."),
        ("classificacao_pendente", "Classificação aguardando aprovação", "Quem administra o Patrimônio recebe quando uma lista de inservíveis ou extraviados é enviada."),
        ("classificacao_decidida", "Classificação decidida", "Quem enviou a lista (e quem colaborou nela) recebe a decisão."),
        ("classificacao_compartilhada", "Lista compartilhada com você", "Você recebe quando alguém compartilha uma lista de inservíveis, de extraviados ou uma baixa para você ajudar a montar."),
        ("baixa_pendente", "Baixa aguardando aprovação", "Quem administra o Patrimônio recebe quando uma baixa é enviada."),
        ("baixa_decidida", "Baixa decidida", "Quem enviou a baixa recebe a decisão."),
    ]),
    ("diretorio", "Diretório", [
        ("recado_aniversario", "Recado de aniversário", "Você recebe quando um colega deixa um recado no seu aniversário."),
        ("feliz_aniversario", "Feliz aniversário", "Você recebe a mensagem automática no dia do seu aniversário."),
    ]),
]

# Eventos que existem para o sistema, mas não aparecem na tela de Preferências
OCULTOS = {"sistema.teste"}

EVENTOS: dict[str, Evento] = {}
ROTULOS_MODULO: dict[str, str] = {}
for _modulo, _rotulo_modulo, _eventos in _MODULOS:
    ROTULOS_MODULO[_modulo] = _rotulo_modulo
    for _item in _eventos:
        _nome, _rotulo, _descricao, *_canais = _item
        _chave = f"{_modulo}.{_nome}"
        EVENTOS[_chave] = Evento(_chave, _modulo, _rotulo, _descricao, _canais[0] if _canais else CANAIS)


def evento_valido(chave: str | None) -> bool:
    return chave in EVENTOS


def por_modulo() -> list[tuple[str, str, list[Evento]]]:
    """(chave do módulo, rótulo, eventos) na ordem do catálogo, para montar a matriz da tela de preferências."""
    return [(m, r, [EVENTOS[f"{m}.{item[0]}"] for item in itens if f"{m}.{item[0]}" not in OCULTOS]) for m, r, itens in _MODULOS]
