# Criado por José Eduardo Santana Martins
# Este arquivo serve para excluir a avaliação de qualidade da competência 09/2026 do contrato 004/2025 (Telefonia) e tirar os reflexos dela.
"""Exclusão da avaliação de qualidade feita na competência 2026-09 do contrato 004/2025, a pedido do solicitante.

A avaliação estava em andamento (notas iniciais, ciência do gestor e PDF gerado, sem a via assinada nem conclusão e sem e-mail enviado).
Efeitos retirados:
- a avaliação é apagada (notas, ciência, PDF); o arquivo do PDF é excluído logicamente (continua em disco para a auditoria);
- a competência deixa de ter a etapa de avaliação: a medição já concluída segue direto para a nota fiscal, com 100% do valor medido
  (sem % liberado pela avaliação), sem desconto nem pendência da avaliação.
Mantém: a medição, a memória de cálculo, as ciências da medição, as glosas e o diário de bordo (que não dependem da avaliação), e o formulário
ativo do contrato (as próximas competências continuam copiando o formulário ao concluir a medição).
Só mexe nessa competência. Tudo vai numa única sessão: se algo falhar, nada é gravado.

Uso: cd backend && .venv/bin/python scripts_manutencao/remover_avaliacao_contrato_004_2025_09.py
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.contratos import Contrato  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.services import servico_anexos  # noqa: E402
from app.services.contratos import servico_competencias as sc  # noqa: E402
from app.services.servico_auditoria import auditar  # noqa: E402

CONTRATO_ID = uuid.UUID("96a9edb2-7dee-41f5-947b-9bf74fd44047")
COMPETENCIA = "2026-09"

with FabricaSessao() as s:
    contrato = s.get(Contrato, CONTRATO_ID)
    competencia = next((c for c in contrato.competencias if f"{c.competencia:%Y-%m}" == COMPETENCIA), None) if contrato else None
    if competencia is None or competencia.avaliacao is None:
        sys.exit("Competência ou avaliação não encontradas: nada foi alterado.")
    avaliacao = competencia.avaliacao
    if avaliacao.concluida_em is not None or avaliacao.pdf_assinado_anexo_id is not None or competencia.nf_concluida_em is not None:
        sys.exit("A avaliação já foi concluída ou a nota fiscal já foi juntada: este script não trata esse caso. Nada foi alterado.")
    autor = s.scalar(select(Usuario).where(Usuario.superusuario.is_(True), Usuario.ativo.is_(True)).order_by(Usuario.id))
    print("Contrato:", contrato.numero, "| competência:", COMPETENCIA, "| etapa antes:", competencia.etapa_atual, "| autor da operação:", autor.login)
    resumo = {"avaliador_inicial_id": avaliacao.avaliador_inicial_id, "assinaturas": [a.get("nome") for a in avaliacao.assinaturas],
              "pdf": str(avaliacao.pdf_gerado_anexo_id) if avaliacao.pdf_gerado_anexo_id else None}
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
