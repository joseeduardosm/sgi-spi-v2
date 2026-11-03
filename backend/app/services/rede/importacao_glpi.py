# Criado por José Eduardo Santana Martins
# Este arquivo serve para a carga inicial do plano de face a partir do dump do GLPI (equipamentos de rede, portas, VLANs e conexões).
"""Carga inicial da rede pelo dump do GLPI (o mesmo arquivo da importação dos chamados; nunca o GLPI em produção).

- cada **modelo** de equipamento de rede vira um modelo de face com grade sugerida (2 linhas, numeração por coluna; as portas acima de 48
  que sejam de fibra ou de uplink ficam como extras). **Revise os modelos** depois: a grade real de cada switch é conferida olhando para ele;
- cada **equipamento de rede** vira um switch, com o número de série, a sala (pelo nome completo da localização do GLPI, se já existir no
  Patrimônio) e o bem do Patrimônio (pela chapa = `otherserial`, se houver);
- **portas** Ethernet e de fibra do equipamento, com nome, MAC, velocidade, duplex, status, descrição (ifAlias), erros e trunk;
- **VLANs** e as VLANs de cada porta (a sem tag vira a nativa);
- **conexões** porta ↔ porta entre equipamentos de rede.
Idempotente pelo id do GLPI (`origem_glpi_id`): rodar de novo só traz o que falta. Sem commit: o script grava ou desfaz (ensaio).
"""

import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.banco import FUSO_SAO_PAULO
from app.models.patrimonio import Bem, Localizacao
from app.models.rede import ConexaoRede, EquipamentoRede, ModeloFaceRede, PortaRede, PortaVlanRede, VlanRede
from app.services.chamados.importacao_glpi import Relatorio

TABELAS_REDE = {
    "glpi_configs", "glpi_networkequipments", "glpi_networkequipmentmodels", "glpi_networkports", "glpi_vlans", "glpi_networkports_vlans",
    "glpi_networkports_networkports", "glpi_locations",
}
# ifOperStatus do SNMP: 1 up, 2 down; ifAdminStatus (ifinternalstatus) 2 = desligada pelo administrador
_STATUS = {1: "up", 2: "down"}
_DUPLEX = {2: "half", 3: "full"}


def _data(valor) -> datetime | None:
    if not valor or str(valor).startswith("0000"):
        return None
    try:
        return datetime.fromisoformat(str(valor)).replace(tzinfo=FUSO_SAO_PAULO).astimezone(UTC)
    except ValueError:
        return None


def _int(valor) -> int:
    try:
        return int(valor or 0)
    except (TypeError, ValueError):
        return 0


def carregar(sessao: Session, dados: dict[str, list[dict]]) -> Relatorio:
    rel = Relatorio()
    rel.versao = next((str(c["value"]) for c in dados.get("glpi_configs", []) if c.get("context") == "core" and c.get("name") == "version"), "desconhecida")
    portas_glpi = [p for p in dados.get("glpi_networkports", []) if p.get("itemtype") == "NetworkEquipment" and not p.get("is_deleted")]
    portas_por_equip = defaultdict(list)
    for p in portas_glpi:
        portas_por_equip[p["items_id"]].append(p)

    # Modelos de face (grade sugerida pelo maior número de porta dos equipamentos daquele modelo)
    existentes_m = {m.origem_glpi_id: m for m in sessao.scalars(select(ModeloFaceRede).where(ModeloFaceRede.origem_glpi_id.is_not(None)))}
    nomes_m = {m.nome.lower() for m in sessao.scalars(select(ModeloFaceRede))}
    maior_por_modelo: Counter = Counter()
    for e in dados.get("glpi_networkequipments", []):
        numeros = [_int(p.get("logical_number")) for p in portas_por_equip[e["id"]]]
        maior_por_modelo[e.get("networkequipmentmodels_id") or 0] = max(maior_por_modelo[e.get("networkequipmentmodels_id") or 0], max(numeros, default=0))
    modelos: dict[int, ModeloFaceRede] = {}
    for m in dados.get("glpi_networkequipmentmodels", []):
        rel.origem["modelos de face"] += 1
        if m["id"] in existentes_m:
            modelos[m["id"]] = existentes_m[m["id"]]
            rel.pulados["modelos de face"] += 1
            continue
        maior = maior_por_modelo.get(m["id"], 0)
        grade = 48 if maior > 48 else (24 if maior > 12 else max(maior, 2))
        grade += grade % 2
        extras = [{"numero": n, "rotulo": f"Uplink {n - grade}", "tipo": "fibra"} for n in range(grade + 1, min(maior, grade + 8) + 1)]
        nome = (str(m.get("name") or f"Modelo {m['id']}").strip() or f"Modelo {m['id']}")[:140]
        if nome.lower() in nomes_m:
            nome = f"{nome} (GLPI {m['id']})"
        nomes_m.add(nome.lower())
        modelo = ModeloFaceRede(id=uuid.uuid4(), nome=nome, linhas=2, colunas=max(1, grade // 2), numeracao="coluna", portas_extras=extras, origem_glpi_id=m["id"])
        sessao.add(modelo)
        modelos[m["id"]] = modelo
        rel.destino["modelos de face"] += 1
    sessao.flush()

    # VLANs
    existentes_v = {v.origem_glpi_id: v for v in sessao.scalars(select(VlanRede).where(VlanRede.origem_glpi_id.is_not(None)))}
    por_numero = {v.numero: v for v in sessao.scalars(select(VlanRede))}
    vlans: dict[int, VlanRede] = {}
    for v in dados.get("glpi_vlans", []):
        rel.origem["VLANs"] += 1
        tag = _int(v.get("tag"))
        if v["id"] in existentes_v or tag in por_numero:
            vlans[v["id"]] = existentes_v.get(v["id"]) or por_numero[tag]
            rel.pulados["VLANs"] += 1
            continue
        if not 1 <= tag <= 4094:
            rel.avisos.append(f"VLAN \"{v.get('name')}\" com número inválido ({tag}): não importada.")
            continue
        vlan = VlanRede(id=uuid.uuid4(), numero=tag, nome=(str(v.get("name") or f"VLAN {tag}"))[:120], descricao=str(v.get("comment") or ""), origem_glpi_id=v["id"])
        sessao.add(vlan)
        vlans[v["id"]] = por_numero[tag] = vlan
        rel.destino["VLANs"] += 1
    sessao.flush()

    # Equipamentos e portas
    locais_glpi = {loc["id"]: str(loc.get("completename") or loc.get("name") or "") for loc in dados.get("glpi_locations", [])}
    salas = {x.nome.lower(): x.id for x in sessao.scalars(select(Localizacao))}
    bens = {(b.chapa or "").lower(): b.id for b in sessao.scalars(select(Bem).where(Bem.chapa.is_not(None)))}
    existentes_e = {x for (x,) in sessao.execute(select(EquipamentoRede.origem_glpi_id).where(EquipamentoRede.origem_glpi_id.is_not(None)))}
    existentes_p = {p for (p,) in sessao.execute(select(PortaRede.origem_glpi_id).where(PortaRede.origem_glpi_id.is_not(None)))}
    portas: dict[int, PortaRede] = {}
    for e in dados.get("glpi_networkequipments", []):
        if e.get("is_template"):
            continue
        rel.origem["equipamentos"] += 1
        if e["id"] in existentes_e or e.get("is_deleted"):
            rel.pulados["equipamentos"] += 1
            continue
        local = locais_glpi.get(e.get("locations_id") or 0, "")
        sala = salas.get(local.split(">")[-1].strip().lower()) if local else None
        if local and sala is None:
            rel.avisos.append(f"Equipamento \"{e.get('name')}\": a localização \"{local}\" não está no Patrimônio (ficou sem sala).")
        equipamento = EquipamentoRede(
            id=uuid.uuid4(), nome=(str(e.get("name") or f"Equipamento {e['id']}"))[:150], tipo="switch", modelo_face=modelos.get(e.get("networkequipmentmodels_id") or 0),
            bem_id=bens.get(str(e.get("otherserial") or "").lower()), localizacao_id=sala, numero_serie=str(e.get("serial") or "")[:120],
            observacao=str(e.get("comment") or ""), origem_glpi_id=e["id"], portas=[],
        )
        sessao.add(equipamento)
        rel.destino["equipamentos"] += 1
        usados: set[int] = set()
        for p in sorted(portas_por_equip[e["id"]], key=lambda x: (_int(x.get("logical_number")), x["id"])):
            rel.origem["portas"] += 1
            if p["id"] in existentes_p:
                rel.pulados["portas"] += 1
                continue
            numero = _int(p.get("logical_number")) or (max(usados, default=0) + 1)
            if numero in usados:
                rel.avisos.append(f"{equipamento.nome}: porta {p.get('name')} repete o número {numero} (ficou com o próximo livre).")
                numero = max(usados) + 1
            usados.add(numero)
            status = "desativada" if _int(p.get("ifinternalstatus")) == 2 else _STATUS.get(_int(p.get("ifstatus")))
            velocidade = _int(p.get("ifspeed")) // 1_000_000 or None
            porta = PortaRede(
                id=uuid.uuid4(), numero_logico=numero, nome=str(p.get("name") or numero)[:120], descricao=str(p.get("ifalias") or "")[:250],
                mac=str(p.get("mac") or "")[:17], velocidade_mbps=velocidade, duplex=_DUPLEX.get(_int(p.get("portduplex"))), status=status,
                modo="trunk" if _int(p.get("trunk")) == 1 else "access", ultima_mudanca=_data(p.get("lastup")),
                erros_entrada=_int(p.get("ifinerrors")), erros_saida=_int(p.get("ifouterrors")), origem_glpi_id=p["id"],
            )
            equipamento.portas.append(porta)
            portas[p["id"]] = porta
            rel.destino["portas"] += 1
    sessao.flush()

    # VLANs de cada porta: a primeira sem tag vira a nativa/PVID; as com tag, a lista da porta. Porta não-trunk com VLAN com tag, ou com mais
    # de uma sem tag, é o que Huawei e 3Com/H3C chamam de hybrid: vira hybrid em vez de perder VLAN
    for pv in dados.get("glpi_networkports_vlans", []):
        porta, vlan = portas.get(pv["networkports_id"]), vlans.get(pv["vlans_id"])
        if porta is None or vlan is None:
            continue
        rel.origem["VLANs nas portas"] += 1
        com_tag = bool(_int(pv.get("tagged")))
        if not com_tag and porta.vlan_nativa_id is None:
            porta.vlan_nativa_id = vlan.id
        else:
            if (com_tag and porta.modo == "access") or (not com_tag and porta.modo != "hybrid"):
                porta.modo = "hybrid"
                rel.avisos.append(f"Porta {porta.nome}: VLANs com e sem tag no GLPI; ficou como hybrid (confira).")
            sessao.add(PortaVlanRede(porta_id=porta.id, vlan_id=vlan.id, com_tag=com_tag))
        rel.destino["VLANs nas portas"] += 1
    sessao.flush()

    # Conexões entre portas de equipamentos de rede (as que envolvem computadores e telefones ficam para o cadastro manual)
    ocupadas = {x for (x,) in sessao.execute(select(ConexaoRede.porta_a_id))} | {x for (x,) in sessao.execute(select(ConexaoRede.porta_b_id)) if x}
    for c in dados.get("glpi_networkports_networkports", []):
        a, b = portas.get(c["networkports_id_1"]), portas.get(c["networkports_id_2"])
        if a is None or b is None:
            continue
        rel.origem["conexões"] += 1
        if a.id in ocupadas or b.id in ocupadas:
            rel.pulados["conexões"] += 1
            continue
        sessao.add(ConexaoRede(porta_a_id=a.id, porta_b_id=b.id, origem_glpi_id=c["id"]))
        ocupadas |= {a.id, b.id}
        rel.destino["conexões"] += 1
    sessao.flush()
    total = sessao.scalar(select(func.count()).select_from(EquipamentoRede)) or 0
    rel.avisos.append(f"Confira a grade de cada modelo de face (sugerida pelo maior número de porta): hoje há {total} equipamento(s) no plano de face.")
    return rel
