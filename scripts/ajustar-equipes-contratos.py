#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para ajustar em lote a equipe (gestor, gestor suplente e fiscal técnico) dos contratos, conforme a planilha de distribuição.
"""Ajusta a equipe dos contratos conforme a planilha "Distribuição de gestores, fiscais e suplentes".

Em cada contrato listado ficam só `gestor`, `gestor_suplente` (ou nenhum, quando a planilha deixa em branco) e `fiscal_tecnico`;
os demais papéis (fiscal administrativo, suplentes de fiscal) são encerrados. Segue a regra de `_aplicar_equipe`
(`servico_contratos.py`): encerra a designação vigente (`valido_ate`) e abre, ou reabre, a nova. Não envia mensagem nem e-mail.
Idempotente. Número que não existe no sistema interrompe o script antes de gravar.

Uso (na pasta backend):
    .venv/bin/python ../scripts/ajustar-equipes-contratos.py                   # ensaio: mostra o que mudaria e desfaz
    .venv/bin/python ../scripts/ajustar-equipes-contratos.py --gravar --backup /caminho/backup.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.banco import FabricaSessao, agora_utc  # noqa: E402
from app.models.contratos import PAPEIS_EQUIPE  # noqa: E402
from app.models.contratos.contrato import Contrato, DesignacaoEquipe  # noqa: E402
from app.models.tarefas import EquipeTarefas  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.services.contratos.servico_contratos import designacoes_vigentes  # noqa: E402
from app.services.contratos.servico_tarefas_contratos import NOME_EQUIPE, sincronizar_membros  # noqa: E402
from app.services.servico_auditoria import auditar  # noqa: E402

TI = ("gslima", "adias", "jesmartins")
VR = ("drodrigues", "jgaldino", "mbrito")
# número do contrato no sistema -> (gestor, gestor suplente ou None, fiscal técnico), por login
PLANILHA: dict[str, tuple[str, str | None, str]] = {
    # Mão de obra
    "007/2024": ("rosemeire.cruz", "stefanny.carreira", "kcorradi"),
    "013/2024": ("rosemeire.cruz", "stefanny.carreira", "atakao"),
    "016/2025": ("rosemeire.cruz", "alan.moreira", "kcorradi"),  # "016/2024 Vigilância Patrimonial - Jumper" na planilha
    "034/2025": ("rosemeire.cruz", "kcorradi", "stefanny.carreira"),
    "047/2025": ("rosemeire.cruz", "kcorradi", "stefanny.carreira"),
    "015/2026": ("rosemeire.cruz", "stefanny.carreira", "kcorradi"),
    # TI
    **{numero: TI for numero in ("008/2024", "010/2024", "014/2024", "018/2024", "002/2025", "004/2025", "036/2025")},
    # Infraestrutura
    "001/2024": ("fsilva", "rosemeire.cruz", "atakao"),
    "003/2024": ("rosemeire.cruz", "fsilva", "atakao"),
    "005/2024": ("fsilva", "rosemeire.cruz", "jesmartins"),
    "006/2024": ("fsilva", "stefanny.carreira", "atakao"),
    "009/2024": ("stefanny.carreira", "alan.moreira", "atakao"),
    "019/2024": ("stefanny.carreira", "rosemeire.cruz", "kcorradi"),
    "022/2024": ("stefanny.carreira", "kcorradi", "atakao"),
    "024/2024": ("fsilva", "stefanny.carreira", "atakao"),
    "003/2025": ("fsilva", "valquiria.torres", "mateus.almgren"),
    # Gestão de pessoas
    **{numero: VR for numero in ("026/2025", "027/2025", "028/2025", "029/2025", "030/2025")},
    # Administrativo
    "006/2023": ("micheli.leite", "stefanny.carreira", "marcus.moura"),
    "011/2023": ("marcio.sousa", "gamato", "murilo.campos"),
    "048/2025": ("mateus.almgren", "alan.moreira", "stefanny.carreira"),
    "099/2025": ("alan.moreira", "mateus.almgren", "atakao"),  # ENEL
    "004/2025-validar": ("alan.moreira", "mateus.almgren", "atakao"),  # SABESP (010/2026 na planilha)
    "019/2026": ("kcorradi", None, "rosemeire.cruz"),
    "020/2026": ("kcorradi", None, "rosemeire.cruz"),
}


def alvo_por_papel(gestor: str, suplente: str | None, fiscal: str, usuarios: dict[str, Usuario]) -> dict[str, int | None]:
    """Usuário (id) de cada papel da equipe; papel fora da planilha fica vazio."""
    ids = {p: None for p in PAPEIS_EQUIPE}
    ids["gestor"] = usuarios[gestor].id
    ids["gestor_suplente"] = usuarios[suplente].id if suplente else None
    ids["fiscal_tecnico"] = usuarios[fiscal].id
    return ids


def aplicar(contrato: Contrato, alvo: dict[str, int | None], usuarios_por_id: dict[int, Usuario]) -> dict:
    """Mesma regra de `_aplicar_equipe`: encerra a vigente e abre ou reabre a nova. Devolve {papel: {de, para}}."""
    agora = agora_utc()
    vigentes = {d.papel: d for d in designacoes_vigentes(contrato, agora)}
    mudancas: dict = {}
    for papel in PAPEIS_EQUIPE:
        novo_id = alvo[papel]
        atual = vigentes.get(papel)
        if (atual.usuario_id if atual else None) == novo_id:
            continue
        if atual:
            atual.valido_ate = agora
        nome_novo = None
        if novo_id is not None:
            usuario = usuarios_por_id[novo_id]
            nome_novo = usuario.nome_completo or usuario.login
            existente = next((d for d in contrato.equipe if d.usuario_id == novo_id and d.papel == papel), None)
            if existente:
                existente.valido_de, existente.valido_ate, existente.nome_usuario = agora, None, nome_novo
            else:
                contrato.equipe.append(DesignacaoEquipe(usuario_id=novo_id, papel=papel, nome_usuario=nome_novo, valido_de=agora))
        mudancas[f"equipe.{papel}"] = {"de": atual.nome_usuario if atual else None, "para": nome_novo}
    return mudancas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gravar", action="store_true", help="Grava (sem isso, é só um ensaio).")
    parser.add_argument("--backup", help="Arquivo JSON para guardar as designações vigentes antes da troca (obrigatório com --gravar).")
    args = parser.parse_args()
    if args.gravar and not args.backup:
        sys.exit("Informe --backup com o caminho do arquivo ao gravar.")
    with FabricaSessao() as sessao:
        logins = {l for linha in PLANILHA.values() for l in linha if l}
        usuarios = {u.login: u for u in sessao.scalars(select(Usuario).where(Usuario.login.in_(logins)))}
        faltam = sorted(logins - set(usuarios))
        inativos = sorted(l for l, u in usuarios.items() if not u.ativo)
        contratos = {c.numero: c for c in sessao.scalars(select(Contrato).where(Contrato.numero.in_(PLANILHA)))}
        sem_contrato = sorted(set(PLANILHA) - set(contratos))
        if faltam or inativos or sem_contrato:
            sys.exit(f"Interrompido. Usuários inexistentes: {faltam}; inativos: {inativos}; contratos não encontrados: {sem_contrato}.")
        por_id = {u.id: u for u in usuarios.values()}
        backup, total = [], 0
        for numero in sorted(PLANILHA, key=lambda n: (n.split("/")[1][:4], n)):
            contrato = contratos[numero]
            backup += [{"contrato": numero, "papel": d.papel, "usuario": d.nome_usuario, "valido_de": str(d.valido_de)} for d in designacoes_vigentes(contrato)]
            mudancas = aplicar(contrato, alvo_por_papel(*PLANILHA[numero], usuarios), por_id)
            if mudancas:
                total += 1
                contrato.versao += 1
                auditar(sessao, "script", "contrato.equipe.ajustar", f"Contrato {numero}", "Ajuste em lote conforme a planilha de distribuição",
                        alvo_tipo="contrato", alvo_id=contrato.id, dados=mudancas)
            print(f"{numero:17} {contrato.apelido[:34]:34}" + ("" if mudancas else " (já estava certo)"))
            for papel, m in mudancas.items():
                print(f"    {papel.removeprefix('equipe.'):28} {m['de'] or '—'}  →  {m['para'] or '—'}")
        sessao.flush()
        equipe = sessao.scalar(select(EquipeTarefas).where(EquipeTarefas.nome == NOME_EQUIPE, EquipeTarefas.ativa.is_(True)))
        entraram = sincronizar_membros(sessao, equipe) if equipe else 0
        print(f"\n{total} contrato(s) {'alterado(s)' if args.gravar else 'seriam alterados (ensaio)'}; {entraram} pessoa(s) a mais na equipe de tarefas Contratos.")
        if args.gravar:
            Path(args.backup).write_text(json.dumps(backup, ensure_ascii=False, indent=1), encoding="utf-8")
            sessao.commit()
        else:
            sessao.rollback()


if __name__ == "__main__":
    main()
