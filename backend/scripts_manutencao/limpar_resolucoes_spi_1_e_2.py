# Criado por José Eduardo Santana Martins
# Este arquivo serve para limpar os números 1 e 2 de "RESOLUÇÕES SPI" (2026) do Protocolo, para a funcionária refazer a reserva corretamente.
"""Limpeza dos números 1 e 2 de RESOLUÇÕES SPI/2026 do Protocolo, a pedido do solicitante.

Eram registros de teste/migrados do SGI antigo: o nº 1 com um documento que não é uma resolução (minuta de termo de aditamento) e o nº 2 reservado como "testes".
Cada número volta a **livre**: sem reserva, finalidade, responsável, contrato, sigilo, uso nem documento. O arquivo anexado do nº 1 é excluído logicamente (continua em
disco para a auditoria), o histórico do número é mantido e ganha o evento "liberou". Só mexe nesses dois números.

Uso: cd backend && .venv/bin/python scripts_manutencao/limpar_resolucoes_spi_1_e_2.py
"""
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.protocolo import NumeroProtocolo, SequenciaProtocolo, TipoProtocolo  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.services import servico_anexos  # noqa: E402
from app.services.servico_auditoria import auditar  # noqa: E402
from app.services.servico_protocolo import _evento  # noqa: E402

MOTIVO = "Número limpo a pedido do solicitante, para o Protocolo refazer a reserva e o documento corretamente."

with FabricaSessao() as s:
    tipo = s.scalar(select(TipoProtocolo).where(TipoProtocolo.nome == "RESOLUÇÕES SPI"))
    sequencia = s.scalar(select(SequenciaProtocolo).where(SequenciaProtocolo.tipo_id == tipo.id, SequenciaProtocolo.exercicio == 2026))
    numeros = list(s.scalars(select(NumeroProtocolo).where(NumeroProtocolo.sequencia_id == sequencia.id, NumeroProtocolo.numero.in_([1, 2])).order_by(NumeroProtocolo.numero)))
    if [n.numero for n in numeros] != [1, 2]:
        sys.exit("Números 1 e 2 de RESOLUÇÕES SPI/2026 não encontrados: nada foi alterado.")
    autor = s.scalar(select(Usuario).where(Usuario.superusuario.is_(True), Usuario.ativo.is_(True)).order_by(Usuario.id))
    for n in numeros:
        antes = {"numero": n.numero, "finalidade": n.finalidade, "reservado_por": n.reservado_por_nome, "reservado_em": str(n.reservado_em), "usado_em": str(n.usado_em),
                 "anexo": n.anexo.nome_original if n.anexo else None, "contrato_id": str(n.contrato_id) if n.contrato_id else None}
        print("Antes:", json.dumps(antes, ensure_ascii=False))
        if n.anexo is not None:
            servico_anexos.descartar(n.anexo)
        _evento(n, "liberou", autor, MOTIVO, antes)
        n.finalidade, n.reservado_por_id, n.reservado_por_nome, n.reservado_em = "", None, "", None
        n.contrato_id, n.sigiloso, n.anexo_id, n.usado_em = None, False, None, None
        auditar(s, autor.login, "protocolo.liberar", f"RESOLUÇÕES SPI 2026 nº {n.numero}", autor_id=autor.id, alvo_tipo="protocolo_numero", alvo_id=n.id, dados={"motivo": MOTIVO, "antes": antes})
    s.commit()

with FabricaSessao() as s:
    for n in s.scalars(select(NumeroProtocolo).join(SequenciaProtocolo).join(TipoProtocolo).where(TipoProtocolo.nome == "RESOLUÇÕES SPI", NumeroProtocolo.numero.in_([1, 2]))):
        print("Depois: nº", n.numero, "| estado", n.estado, "| anexo", n.anexo_id, "| reservado_em", n.reservado_em)
