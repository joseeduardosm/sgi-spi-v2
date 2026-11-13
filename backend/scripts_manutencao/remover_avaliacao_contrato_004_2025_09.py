"""
===============================================================================
ARQUIVO: remover_avaliacao_contrato_004_2025_09.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Script de manutenção, de uso único, que exclui a avaliação de qualidade feita
na competência 2026-09 do contrato 004/2025 (Telefonia), a pedido do
solicitante, e retira os reflexos dela na competência.

RESUMO TÉCNICO:
Abre uma sessão (FabricaSessao), localiza o contrato pelo UUID fixo e a
competência "2026-09", recusa o caso se a avaliação já foi concluída, tem via
assinada ou se a nota fiscal já foi juntada. Descarta logicamente o PDF gerado
(o arquivo continua em disco para auditoria), apaga a avaliação, faz flush e
recalcula a etapa com servico_competencias.proxima_etapa (a medição segue
direto para a nota fiscal, com 100% do valor medido). Registra auditoria e faz
commit numa única transação: se algo falhar, nada é gravado. Por fim reabre a
sessão e imprime a situação final.
Uso: cd backend && .venv/bin/python scripts_manutencao/remover_avaliacao_contrato_004_2025_09.py

FINALIDADE DE NEGÓCIO:
A avaliação estava em andamento (notas iniciais, ciência do gestor e PDF, sem
via assinada, sem conclusão e sem e-mail). Mantém a medição, a memória de
cálculo, as ciências da medição, as glosas e o diário de bordo, e o formulário
ativo do contrato (as próximas competências continuam copiando o formulário).
Competência = mês de execução do contrato que está sendo medido e pago.

CONTEXTO NO SISTEMA:
Usa os modelos Contrato e Usuario, o serviço de anexos (descartar), o serviço
de competências (proxima_etapa, etapas_da_competencia, percentual_liberado,
valor_autorizado) e o serviço de auditoria. Só mexe nessa competência.

===============================================================================
"""
import sys
import uuid
from pathlib import Path

# Coloca a pasta backend/ no caminho de import, para "app" ser encontrado ao rodar o script direto.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.contratos import Contrato  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.services import servico_anexos  # noqa: E402
from app.services.contratos import servico_competencias as sc  # noqa: E402
from app.services.servico_auditoria import auditar  # noqa: E402

# Alvo fixo da manutenção: contrato 004/2025 e a competência (mês) afetada.
CONTRATO_ID = uuid.UUID("96a9edb2-7dee-41f5-947b-9bf74fd44047")
COMPETENCIA = "2026-09"

# Bloco 1: tudo numa única sessão; só o commit no fim grava (se algo falhar, nada vai ao banco).
with FabricaSessao() as s:
    contrato = s.get(Contrato, CONTRATO_ID)
    competencia = next((c for c in contrato.competencias if f"{c.competencia:%Y-%m}" == COMPETENCIA), None) if contrato else None
    if competencia is None or competencia.avaliacao is None:
        sys.exit("Competência ou avaliação não encontradas: nada foi alterado.")
    avaliacao = competencia.avaliacao
    # Trava de segurança: o script só trata a avaliação ainda em andamento.
    if avaliacao.concluida_em is not None or avaliacao.pdf_assinado_anexo_id is not None or competencia.nf_concluida_em is not None:
        sys.exit("A avaliação já foi concluída ou a nota fiscal já foi juntada: este script não trata esse caso. Nada foi alterado.")
    # A operação é auditada em nome do primeiro SuperRoot (administrador) ativo.
    autor = s.scalar(select(Usuario).where(Usuario.superusuario.is_(True), Usuario.ativo.is_(True)).order_by(Usuario.id))
    print("Contrato:", contrato.numero, "| competência:", COMPETENCIA, "| etapa antes:", competencia.etapa_atual, "| autor da operação:", autor.login)
    resumo = {"avaliador_inicial_id": avaliacao.avaliador_inicial_id, "assinaturas": [a.get("nome") for a in avaliacao.assinaturas],
              "pdf": str(avaliacao.pdf_gerado_anexo_id) if avaliacao.pdf_gerado_anexo_id else None}
    # Exclusão lógica do PDF: o registro do anexo é descartado, mas o arquivo fica em disco.
    if avaliacao.pdf_gerado_anexo is not None:
        servico_anexos.descartar(avaliacao.pdf_gerado_anexo)
    competencia.avaliacao = None
    s.flush()  # a exclusão precisa ir ao banco antes de mudar a etapa (há uma avaliação por competência)
    competencia.etapa_atual = sc.proxima_etapa(competencia, "medicao")  # sem avaliação: a próxima etapa da medição é a nota fiscal
    auditar(s, autor.login, "contrato.execucao.avaliacao.excluir", f"Contrato {contrato.numero} - competência {COMPETENCIA}", autor_id=autor.id,
            alvo_tipo="contrato", alvo_id=contrato.id, dados={"avaliacao_excluida": resumo, "origem": "Excluída a pedido de jesmartins"})
    s.commit()

with FabricaSessao() as s:
    contrato = s.get(Contrato, CONTRATO_ID)
    competencia = next(c for c in contrato.competencias if f"{c.competencia:%Y-%m}" == COMPETENCIA)
    print("Depois: etapa", competencia.etapa_atual, "| avaliação:", competencia.avaliacao, "| etapas:", sc.etapas_da_competencia(competencia),
          "| % liberado:", sc.percentual_liberado(competencia), "| valor autorizado:", sc.valor_autorizado(competencia))
