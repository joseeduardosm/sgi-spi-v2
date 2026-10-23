# Criado por José Eduardo Santana Martins
# Este arquivo serve para reabrir a etapa "Formulário de nomeação no GLPI" da admissão 1, a pedido do RH, para testar o envio do formulário.
"""Reabre só a etapa 1 (formulário de nomeação no GLPI) da admissão 1.

O chamado antigo (#1661, criado pelo fluxo anterior de chamado único) fica no GLPI: o SGI não apaga chamados. Aqui só se limpa o registro do envio na admissão
(`chamado_em`, `chamado_glpi_id`, `chamado_url`, `chamado_links`, `solicitacoes`). Documentos, resolução e o número já reservado no Protocolo **não** são mexidos:
depois do novo envio a trilha segue da etapa em que estava. Auditado como `rh.admissao.reabrir_chamado`.

Uso: cd backend && .venv/bin/python scripts_manutencao/reabrir_etapa_chamado_admissao_1.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.rh_admissao import Admissao  # noqa: E402
from app.services.rh.servico_admissao import etapa_atual  # noqa: E402
from app.services.servico_auditoria import auditar  # noqa: E402

ADMISSAO_ID = 1


def main() -> None:
    with FabricaSessao() as sessao:
        admissao = sessao.get(Admissao, ADMISSAO_ID)
        if admissao is None or admissao.status != "andamento":
            print("Admissão 1 não encontrada ou não está em andamento: nada feito.")
            return
        anterior = (admissao.chamado_glpi_id, admissao.chamado_url)
        admissao.chamado_em = admissao.chamado_glpi_id = admissao.chamado_url = admissao.chamado_links = admissao.solicitacoes = None
        auditar(sessao, "sistema (pedido do RH)", "rh.admissao.reabrir_chamado", f"Admissão {ADMISSAO_ID}",
                f"Etapa do chamado reaberta para teste do formulário; chamado anterior #{anterior[0]} permanece no GLPI", dados={"admissao_id": ADMISSAO_ID})
        sessao.commit()
        sessao.refresh(admissao)
        print(f"Admissão {ADMISSAO_ID}: etapa atual agora é \"{etapa_atual(admissao)}\" (chamado anterior #{anterior[0]} segue no GLPI).")


if __name__ == "__main__":
    main()
