#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para limpar as especificações das portas dos equipamentos que não estão em rack, como se nunca tivessem sido alimentadas.
"""Limpeza das portas dos equipamentos fora de rack (pedido do usuário em 05/11/2026).

Para todo equipamento sem rack (`rack_id` vazio), cada porta volta ao estado de recém-criada pelo modelo de face:
- nome da interface volta ao do modelo (o número, ou o rótulo da porta extra);
- descrição, MAC, IP da interface, velocidade, duplex, situação, data da última mudança e erros ficam vazios/zerados;
- modo volta a `access`, sem VLAN (nativa, voz, com e sem tag);
- as ligações (cabos, bens e descrições ligados) dessas portas saem, com os dispositivos atrás delas. A porta do outro lado (ex.: a do switch
  do rack) perde só a ligação, como no "Desligar" da tela.
Equipamentos, portas, pontos e chamados continuam. A auditoria anterior não é apagada; a limpeza grava um registro só (`rede.limpeza_fora_de_rack`).

Antes de gravar, salva um backup em JSON de tudo que vai mudar (portas, VLANs das portas, ligações e dispositivos atrás).

Uso (na pasta backend):
    .venv/bin/python ../scripts/limpar-portas-fora-de-rack.py                         # ENSAIO: mostra o que mudaria e desfaz
    .venv/bin/python ../scripts/limpar-portas-fora-de-rack.py --gravar --backup ARQ   # grava (o backup é obrigatório)
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import delete, or_, select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.rede import ConexaoRede, DispositivoAtrasRede, EquipamentoRede, PortaRede, PortaVlanRede  # noqa: E402
from app.services.servico_auditoria import auditar  # noqa: E402

# Colunas guardadas no backup de cada tabela
CAMPOS_PORTA = ("id", "equipamento_id", "numero_logico", "nome", "descricao", "mac", "velocidade_mbps", "duplex", "status", "modo", "vlan_nativa_id",
                "vlan_voz_id", "ip_interface", "ultima_mudanca", "erros_entrada", "erros_saida")


def _linha(objeto, campos) -> dict:
    """Linha do backup: os campos pedidos como texto (UUID e datas viram texto)."""
    return {c: (None if getattr(objeto, c) is None else str(getattr(objeto, c)) if not isinstance(getattr(objeto, c), (int, str)) else getattr(objeto, c))
            for c in campos}


def main() -> int:
    parser = argparse.ArgumentParser(description="Limpa as portas dos equipamentos fora de rack.")
    parser.add_argument("--gravar", action="store_true", help="Grava de verdade (sem isto, é ensaio).")
    parser.add_argument("--backup", type=Path, help="Arquivo JSON do backup (obrigatório com --gravar).")
    args = parser.parse_args()
    if args.gravar and not args.backup:
        print("ERRO: informe --backup ARQUIVO.json para gravar.")
        return 1
    with FabricaSessao() as sessao:
        equipamentos = list(sessao.scalars(select(EquipamentoRede).where(EquipamentoRede.rack_id.is_(None))))
        portas = [p for e in equipamentos for p in e.portas]
        ids = [p.id for p in portas]
        conexoes = list(sessao.scalars(select(ConexaoRede).where(or_(ConexaoRede.porta_a_id.in_(ids), ConexaoRede.porta_b_id.in_(ids))))) if ids else []
        atras = list(sessao.scalars(select(DispositivoAtrasRede).where(DispositivoAtrasRede.conexao_id.in_([c.id for c in conexoes])))) if conexoes else []
        vlans = list(sessao.scalars(select(PortaVlanRede).where(PortaVlanRede.porta_id.in_(ids)))) if ids else []
        print(f"Equipamentos fora de rack: {len(equipamentos)} | portas: {len(portas)} | com situação: {sum(1 for p in portas if p.status)} | "
              f"ligações: {len(conexoes)} (dispositivos atrás: {len(atras)}) | VLANs em portas: {len(vlans)}")

        if args.gravar:
            backup = {
                "portas": [_linha(p, CAMPOS_PORTA) for p in portas],
                "portas_vlans": [_linha(v, ("porta_id", "vlan_id", "com_tag")) for v in vlans],
                "conexoes": [_linha(c, ("id", "porta_a_id", "porta_b_id", "bem_id", "descricao")) for c in conexoes],
                "dispositivos_atras": [_linha(d, ("id", "conexao_id", "ordem", "bem_id", "descricao")) for d in atras],
            }
            args.backup.parent.mkdir(parents=True, exist_ok=True)
            args.backup.write_text(json.dumps(backup, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"Backup salvo em {args.backup}")

        # Ligações e dispositivos atrás saem (os dispositivos também saem pela cascata; explícito para o ensaio contar igual)
        if conexoes:
            sessao.execute(delete(DispositivoAtrasRede).where(DispositivoAtrasRede.conexao_id.in_([c.id for c in conexoes])))
            sessao.execute(delete(ConexaoRede).where(ConexaoRede.id.in_([c.id for c in conexoes])))
        if ids:
            sessao.execute(delete(PortaVlanRede).where(PortaVlanRede.porta_id.in_(ids)))
        for e in equipamentos:
            # Nome como o modelo cria: o rótulo da porta extra ou o próprio número
            rotulos = {x["numero"]: x.get("rotulo") or str(x["numero"]) for x in (e.modelo_face.portas_extras or [])} if e.modelo_face else {}
            for p in e.portas:
                p.nome = rotulos.get(p.numero_logico, str(p.numero_logico))
                p.descricao, p.mac, p.ip_interface = "", "", ""
                p.velocidade_mbps, p.duplex, p.status, p.ultima_mudanca = None, None, None, None
                p.modo, p.vlan_nativa_id, p.vlan_voz_id = "access", None, None
                p.erros_entrada, p.erros_saida = 0, 0
        auditar(sessao, "sistema:limpeza-fora-de-rack", "rede.limpeza_fora_de_rack", f"{len(equipamentos)} equipamento(s) fora de rack",
                dados={"equipamentos": len(equipamentos), "portas": len(portas), "ligacoes": len(conexoes), "dispositivos_atras": len(atras),
                       "vlans_em_portas": len(vlans), "backup": str(args.backup) if args.backup else None})
        if args.gravar:
            sessao.commit()
            print("GRAVADO.")
        else:
            sessao.rollback()
            print("ENSAIO: nada foi gravado (use --gravar --backup ARQUIVO.json).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
