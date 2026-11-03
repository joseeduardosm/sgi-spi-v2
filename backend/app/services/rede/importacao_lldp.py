# Criado por José Eduardo Santana Martins
# Este arquivo serve para carregar no plano de face da rede o inventário levantado por LLDP nos switches (equipamentos, portas e cabos).
"""Carga da Rede a partir de um inventário LLDP (JSON), feito com comandos só de leitura nos switches.

O inventário (ex.: `dados/rede/inventario-lldp-2026-11-03.json`, fora do Git) traz:
- `equipamentos[{nome, tipo, ip, funcao, modelo, fabricante?, portas{interface: up|down|desativada}}]`;
- `ligacoes[{a, porta_a, b, porta_b}]`: um cabo entre duas interfaces, como o LLDP mostrou;
- `excluir[nome]`: equipamentos a apagar antes (cadastros de teste).

Regras (decisões do usuário em 03/11/2026):
- modelos de face criados se faltarem: Huawei S5755-H (grade 2×24 por coluna, MultiGE1/0/1–48; extras 49–52 = 25GE1/0/1–4 e 53–54 = 100GE1/0/1–2),
  AirEngine 6700 (1 porta, MultiGE0/0/0) e um genérico de 48 portas para os Dell e o 3Com (a porta é o último número do nome);
- cada porta guarda o nome real da interface e o status lido (`display interface brief`);
- equipamento já cadastrado (mesmo nome) é atualizado (IP, função, tipo e modelo, se não tinha); rack, sala e o resto ficam como estão;
- cabo já cadastrado é pulado; porta ocupada por outra coisa no SGI não é mexida (vira aviso no relatório).
Pode rodar de novo: o que já está igual é pulado.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.rede import ConexaoRede, EquipamentoRede, ModeloFaceRede, PortaRede
from app.services.rede import servico
from app.services.rede.servico import DadosEquipamento, ErroRede

HUAWEI_S5755 = "Huawei S5755-H48UM4Y2CZ"
AIRENGINE = "Huawei AirEngine 6700"
GENERICO_48 = "Switch genérico 48 portas"

# nome → (fabricante, linhas, colunas, numeração, extras, altura)
MODELOS = {
    HUAWEI_S5755: ("Huawei", 2, 24, "coluna",
                   [{"numero": 48 + n, "rotulo": f"25GE1/0/{n}", "tipo": "fibra"} for n in range(1, 5)]
                   + [{"numero": 52 + n, "rotulo": f"100GE1/0/{n}", "tipo": "fibra"} for n in range(1, 3)], 1),
    AIRENGINE: ("Huawei", 1, 1, "linha", [], 1),
    GENERICO_48: ("", 2, 24, "coluna", [], 1),
}


def numero_da_porta(modelo: str, interface: str) -> int | None:
    """Número lógico da porta no modelo, a partir do nome da interface (None se não couber no modelo)."""
    if modelo == HUAWEI_S5755:
        m = re.fullmatch(r"(MultiGE|25GE|100GE)1/0/(\d+)", interface)
        if not m:
            return None
        n = int(m.group(2))
        return {"MultiGE": n if n <= 48 else None, "25GE": 48 + n if n <= 4 else None, "100GE": 52 + n if n <= 2 else None}[m.group(1)]
    if modelo == AIRENGINE:
        return 1
    m = re.search(r"(\d+)$", interface)
    return int(m.group(1)) if m and 1 <= int(m.group(1)) <= 48 else None


@dataclass
class Relatorio:
    contagem: Counter = field(default_factory=Counter)
    avisos: list[str] = field(default_factory=list)

    def texto(self) -> str:
        nomes = {"modelo_criado": "Modelos de face criados", "excluido": "Equipamentos excluídos (testes)", "criado": "Equipamentos criados",
                 "atualizado": "Equipamentos atualizados", "porta_status": "Portas com status/nome gravados", "cabo_criado": "Cabos criados",
                 "cabo_existente": "Cabos que já existiam"}
        linhas = [f"{rotulo}: {self.contagem[chave]}" for chave, rotulo in nomes.items()]
        if self.avisos:
            linhas.append(f"\nAvisos ({len(self.avisos)}):")
            linhas += [f"  - {a}" for a in self.avisos]
        return "\n".join(linhas)


def _por_nome(sessao: Session, classe, nome: str):
    return sessao.scalar(select(classe).where(func.lower(classe.nome) == nome.lower()))


def _modelo(sessao: Session, nome: str, r: Relatorio, fabricante: str = "") -> ModeloFaceRede:
    existente = _por_nome(sessao, ModeloFaceRede, nome)
    if existente:
        return existente
    fab, linhas, colunas, numeracao, extras, altura = MODELOS[nome]
    r.contagem["modelo_criado"] += 1
    return servico.salvar_modelo(sessao, None, nome, fabricante or fab, linhas, colunas, numeracao, extras, altura)


def carregar(sessao: Session, inventario: dict) -> Relatorio:
    """Aplica o inventário. Sem commit (o script decide entre ensaio e gravação)."""
    r = Relatorio()
    for nome in inventario.get("excluir", []):
        e = _por_nome(sessao, EquipamentoRede, nome)
        if e:
            servico.excluir_equipamento(sessao, e.id)
            r.contagem["excluido"] += 1

    # Equipamentos e as portas de cada um, pelo nome da interface
    portas: dict[tuple[str, str], PortaRede] = {}
    modelo_de: dict[str, str] = {}
    for item in inventario["equipamentos"]:
        modelo = _modelo(sessao, item["modelo"], r, item.get("fabricante", ""))
        modelo_de[item["nome"]] = item["modelo"]
        atual = _por_nome(sessao, EquipamentoRede, item["nome"])
        if atual is None:
            dados = DadosEquipamento(nome=item["nome"], tipo=item["tipo"], modelo_face_id=modelo.id, ip_gerencia=item["ip"], funcao=item["funcao"])
            r.contagem["criado"] += 1
        else:
            dados = DadosEquipamento(nome=atual.nome, tipo=item["tipo"], modelo_face_id=atual.modelo_face_id or modelo.id, bem_id=atual.bem_id,
                                     localizacao_id=atual.localizacao_id, rack_id=atual.rack_id, posicao_u=atual.posicao_u, ip_gerencia=item["ip"],
                                     numero_serie=atual.numero_serie, observacao=atual.observacao, ativo=atual.ativo, funcao=item["funcao"])
            r.contagem["atualizado"] += 1
        try:
            e = servico.salvar_equipamento(sessao, atual.id if atual else None, dados)
        except ErroRede as erro:
            r.avisos.append(f"{item['nome']}: não gravado ({erro})")
            continue
        sessao.refresh(e, ["portas"])
        por_numero = {p.numero_logico: p for p in e.portas}
        for interface, status in item.get("portas", {}).items():
            n = numero_da_porta(item["modelo"], interface)
            if n in por_numero:
                p = por_numero[n]
                p.nome, p.status = interface, status
                portas[(item["nome"], interface)] = p
                r.contagem["porta_status"] += 1
        # Lados das ligações que não vieram na lista de portas (AP, Dell, 3Com): acha pelo número
        for lig in inventario["ligacoes"]:
            for lado, interface in ((lig["a"], lig["porta_a"]), (lig["b"], lig["porta_b"])):
                if lado == item["nome"] and (lado, interface) not in portas:
                    n = numero_da_porta(item["modelo"], interface)
                    if n in por_numero:
                        por_numero[n].nome = interface[:40]
                        portas[(lado, interface)] = por_numero[n]
    sessao.flush()

    # Cabos
    for lig in inventario["ligacoes"]:
        a, b = portas.get((lig["a"], lig["porta_a"])), portas.get((lig["b"], lig["porta_b"]))
        rotulo = f"{lig['a']} {lig['porta_a']} ↔ {lig['b']} {lig['porta_b']}"
        if a is None or b is None:
            r.avisos.append(f"{rotulo}: porta não encontrada no modelo de face")
            continue
        ja = sessao.scalar(select(ConexaoRede).where(((ConexaoRede.porta_a_id == a.id) & (ConexaoRede.porta_b_id == b.id))
                                                      | ((ConexaoRede.porta_a_id == b.id) & (ConexaoRede.porta_b_id == a.id))))
        if ja is not None:
            r.contagem["cabo_existente"] += 1
            continue
        try:
            servico.conectar(sessao, a.id, b.id, None, "", forcar=True)
            r.contagem["cabo_criado"] += 1
        except ErroRede as erro:
            r.avisos.append(f"{rotulo}: não ligado ({erro})")
    sessao.flush()
    return r
