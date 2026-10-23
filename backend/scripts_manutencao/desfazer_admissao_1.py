# Criado por José Eduardo Santana Martins
# Este arquivo serve para desfazer a admissão 1 (teste da nomeação de José Martia) e os efeitos dela dentro do SGI, a pedido do solicitante.
"""Desfaz a admissão 1 e o que ela deixou no SGI:

- o número **RESOLUÇÕES SPI 1/2026** do Protocolo volta a **livre** (sem reserva, finalidade, responsável, uso nem documento); o PDF anexado é excluído logicamente (continua em
  disco para a auditoria) e o histórico do número ganha o evento "liberou";
- a foto da admissão (anexo) é excluída logicamente;
- a admissão e os seus documentos são apagados;
- o registro do chamado #1661 (do fluxo antigo de chamado único) é retirado de "meus chamados" do SGI.

NÃO mexe: nos chamados do GLPI (#1661 e #1662 a #1670: o SGI não apaga chamados da TI), no e-mail já enviado, nem na ficha de pré-cadastro de José Martia (continua aguardando a conta).
Tudo numa única sessão: se algo falhar, nada é gravado.

Uso: cd backend && .venv/bin/python scripts_manutencao/desfazer_admissao_1.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.anexo import Anexo  # noqa: E402
from app.models.integracao_glpi import ChamadoGlpi  # noqa: E402
from app.models.protocolo import NumeroProtocolo  # noqa: E402
from app.models.rh_admissao import Admissao  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.services import servico_anexos  # noqa: E402
from app.services.servico_auditoria import auditar  # noqa: E402
from app.services.servico_protocolo import _evento  # noqa: E402

ADMISSAO_ID = 1
MOTIVO = "Admissão de teste desfeita a pedido do solicitante: número devolvido ao Protocolo."

with FabricaSessao() as s:
    admissao = s.get(Admissao, ADMISSAO_ID)
    if admissao is None:
        sys.exit("Admissão 1 não encontrada: nada foi alterado.")
    autor = s.scalar(select(Usuario).where(Usuario.superusuario.is_(True), Usuario.ativo.is_(True)).order_by(Usuario.id))
    resumo = {"admissao": admissao.id, "status": admissao.status, "numero_protocolo_id": str(admissao.numero_protocolo_id), "chamado_glpi_id": admissao.chamado_glpi_id,
              "foto": str(admissao.foto_anexo_id), "documentos": len(admissao.documentos)}
    print("Antes:", json.dumps(resumo, ensure_ascii=False))

    # 1. Número do Protocolo: volta a livre (histórico mantido, com o evento "liberou")
    numero = s.get(NumeroProtocolo, admissao.numero_protocolo_id) if admissao.numero_protocolo_id else None
    if numero is not None:
        antes = {"numero": numero.numero, "finalidade": numero.finalidade, "reservado_por": numero.reservado_por_nome, "reservado_em": str(numero.reservado_em),
                 "usado_em": str(numero.usado_em), "anexo": numero.anexo.nome_original if numero.anexo else None}
        if numero.anexo is not None:
            servico_anexos.descartar(numero.anexo)
        _evento(numero, "liberou", autor, MOTIVO, antes)
        numero.finalidade, numero.reservado_por_id, numero.reservado_por_nome, numero.reservado_em = "", None, "", None
        numero.contrato_id, numero.sigiloso, numero.anexo_id, numero.usado_em = None, False, None, None
        auditar(s, autor.login, "protocolo.liberar", f"{numero.sequencia.tipo.nome} {numero.sequencia.exercicio} nº {numero.numero}", autor_id=autor.id,
                alvo_tipo="protocolo_numero", alvo_id=numero.id, dados={"motivo": MOTIVO, "antes": antes})
        print("Número", numero.numero, "do Protocolo liberado.")

    # 2. Anexos da admissão (foto e comprovantes): exclusão lógica
    for anexo_id in [admissao.foto_anexo_id, *[d.comprovante_anexo_id for d in admissao.documentos]]:
        anexo = s.get(Anexo, anexo_id) if anexo_id else None
        if anexo is not None:
            servico_anexos.descartar(anexo)

    # 3. Registro do chamado único antigo (#1661) em "meus chamados" do SGI
    for chamado in s.scalars(select(ChamadoGlpi).where(ChamadoGlpi.glpi_id == 1661)):
        s.delete(chamado)

    # 4. A admissão (os documentos saem em cascata)
    auditar(s, autor.login, "rh.admissao.desfazer", f"Admissão {ADMISSAO_ID}", MOTIVO, autor_id=autor.id, dados=resumo)
    s.delete(admissao)
    s.commit()

with FabricaSessao() as s:
    print("Depois: admissões =", len(list(s.scalars(select(Admissao)))), "| chamado 1661 no SGI =", len(list(s.scalars(select(ChamadoGlpi).where(ChamadoGlpi.glpi_id == 1661)))))
    for n in s.scalars(select(NumeroProtocolo).where(NumeroProtocolo.numero == 1)):
        if n.sequencia.tipo.nome == "RESOLUÇÕES SPI":
            print("Depois: RESOLUÇÕES SPI nº", n.numero, "/", n.sequencia.exercicio, "| estado", n.estado, "| anexo", n.anexo_id, "| reservado_em", n.reservado_em)
