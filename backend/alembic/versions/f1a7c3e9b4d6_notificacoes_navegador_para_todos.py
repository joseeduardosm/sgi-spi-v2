# Criado por José Eduardo Santana Martins
# Este arquivo serve para ligar o canal Navegador, em todos os eventos que o aceitam, para os usuários que já existem.
"""notificacoes: navegador ligado para todos

Insere em `notificacoes_preferencias` o canal `navegador` de cada usuário para cada evento que aceita esse canal (sem duplicar o que já
existe). Cada pessoa continua podendo desmarcar na tela de Preferências. Usuários criados depois começam desmarcados, como antes.

Revision ID: f1a7c3e9b4d6
Revises: e5f9b2d7a3c1
Create Date: 2026-10-13 16:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f1a7c3e9b4d6'
down_revision: Union[str, Sequence[str], None] = 'e5f9b2d7a3c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Eventos que aceitam o canal navegador na data desta migração (cópia fixa: o catálogo pode mudar depois)
EVENTOS = [
    'comunicados.mensagem', 'comunicados.lembrete_ciencia', 'sistema.teste', 'contratos.equipe_incluido', 'contratos.ocorrencia_diario',
    'contratos.medicao_concluida', 'contratos.medicao_adicional', 'contratos.conferir_retencao', 'contratos.nota_recusada',
    'contratos.retencao_conferida', 'contratos.alteracao_concluida', 'contratos.vencimento_contrato', 'contratos.medicao_atrasada',
    'contratos.correcao_itens', 'contratos.portaria', 'tarefas.atribuida', 'tarefas.prazo_alterado', 'tarefas.aguardando_validacao',
    'tarefas.entrega_validada', 'tarefas.entrega_devolvida', 'tarefas.reaberta', 'tarefas.concluida', 'tarefas.mencao', 'tarefas.comentario',
    'tarefas.vence_amanha', 'tarefas.atrasada', 'tarefas.escalonada', 'tarefas.marco_atingido', 'tarefas.status_equipe',
    'tarefas.lembrete_status', 'tarefas.recorrencia_pausada', 'tarefas.atividade_agendada', 'tarefas.atividade_concluida',
    'tarefas.atividade_lembrete', 'rh.afastamento_aprovacao', 'rh.afastamento_ciencia', 'rh.afastamento_situacao', 'rh.afastamento_cancelado',
    'rh.boas_vindas', 'rh.afastamento_lembrete', 'rh.cadastro_validacao', 'rh.cadastro_recusado', 'rh.folha_ponto_bloqueada',
    'rh.periodo_ferias', 'rh.prazo_ferias', 'reserva_espacos.nova_solicitacao', 'reserva_espacos.registrada_em_seu_nome',
    'reserva_espacos.resposta', 'reserva_espacos.cancelada', 'reserva_espacos.lembrete_vespera', 'contratacoes.revisao_nova',
    'contratacoes.proposta_aplicada', 'contratacoes.revisao_parada', 'noticias.aguardando_aprovacao', 'noticias.aprovada',
    'noticias.devolvida', 'noticias.publicada', 'melhorias.nova_sugestao', 'melhorias.andamento', 'protocolo.documento_pendente',
    'patrimonio.movimentacao_pendente', 'patrimonio.movimentacao_decidida', 'patrimonio.classificacao_pendente',
    'patrimonio.classificacao_decidida', 'patrimonio.baixa_pendente', 'patrimonio.baixa_decidida', 'diretorio.recado_aniversario',
    'diretorio.feliz_aniversario',
]


def upgrade() -> None:
    conexao = op.get_bind()
    usuarios = [linha[0] for linha in conexao.execute(sa.text('SELECT id FROM usuarios'))]
    linhas = [{'usuario_id': u, 'evento': e, 'canal': 'navegador'} for u in usuarios for e in EVENTOS]
    for inicio in range(0, len(linhas), 2000):
        conexao.execute(
            sa.text('INSERT INTO notificacoes_preferencias (usuario_id, evento, canal) VALUES (:usuario_id, :evento, :canal) '
                    'ON CONFLICT ON CONSTRAINT uq_notificacoes_preferencias_usuario_evento_canal DO NOTHING'),
            linhas[inicio:inicio + 2000],
        )


def downgrade() -> None:
    # Não há como separar o que foi inserido aqui do que a pessoa marcou depois; mantém os dados
    pass
