#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para cadastrar no Patrimônio os bens das planilhas "Visão Geral" do SAM (ativos e baixados).
"""Importa as planilhas VisaoGeral_ATIVOS.xlsx e VisaoGeral_BAIXADOS.xlsx (apoio/patrimonio) para o Patrimônio.

- Chapa = SPI + 6 dígitos. Bem com a chapa já cadastrada recebe só os dados do SAM (descrição, sala e foto ficam como estão).
- Bem novo entra na sala "NECESSÁRIO ATUALIZAR"; o da planilha de baixados entra com situação "baixado".
- Grupo do material: um por código do SAM (criado se não existir, com a vida útil mais comum da planilha).
- Idempotente: bem novo leva `id_cliente` = `sam:<chapa>`; rodar de novo não duplica e não sobrescreve.

Uso (da raiz do projeto):
  backend/.venv/bin/python scripts/importar-patrimonio-sam.py            # simulação: só mostra os números
  backend/.venv/bin/python scripts/importar-patrimonio-sam.py --aplicar  # grava no banco
"""
import sys
import uuid
import warnings
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import openpyxl

RAIZ = Path(__file__).resolve().parent.parent
# Permite importar o pacote `app` do backend ao rodar o script da raiz do projeto
sys.path.insert(0, str(RAIZ / "backend"))

from sqlalchemy import select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.patrimonio import Bem, EventoPatrimonio, GrupoMaterial, Localizacao  # noqa: E402
from app.services.patrimonio.importacao_glpi import CODIGO_SALA_ATUALIZAR, SALA_ATUALIZAR  # noqa: E402
from app.services.patrimonio.importacao_sam import ORIGEM_IMPORTACAO, montar_bem  # noqa: E402

APLICAR = "--aplicar" in sys.argv
PASTA = RAIZ / "apoio" / "patrimonio"
ARQUIVOS = (("VisaoGeral_ATIVOS.xlsx", False), ("VisaoGeral_BAIXADOS.xlsx", True))


def ler(arquivo: str) -> list[dict]:
    """Linhas da planilha como dicionários (cabeçalho → valor)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        planilha = openpyxl.load_workbook(PASTA / arquivo, read_only=True).active
    linhas = list(planilha.iter_rows(values_only=True))
    return [dict(zip(linhas[0], l)) for l in linhas[1:] if any(c not in (None, "") for c in l)]


def sala_atualizar(sessao) -> Localizacao:
    """Sala "NECESSÁRIO ATUALIZAR" (criada direto no prédio se ainda não existir)."""
    sala = sessao.scalar(select(Localizacao).where(Localizacao.codigo == CODIGO_SALA_ATUALIZAR))
    if sala is None:
        predio = sessao.scalar(select(Localizacao).where(Localizacao.tipo == "predio"))
        sala = Localizacao(id=uuid.uuid4(), pai_id=predio.id, tipo="sala", nome=SALA_ATUALIZAR, codigo=CODIGO_SALA_ATUALIZAR, ativo=True)
        sessao.add(sala)
        sessao.flush()
    return sala


def grupos_do_sam(sessao, linhas_por_baixado: list[tuple[dict, bool]]) -> dict[str, GrupoMaterial]:
    """Um grupo por código do SAM (código "SAM-71"); a vida útil é a mais comum entre os bens do grupo."""
    existentes = {g.codigo: g for g in sessao.scalars(select(GrupoMaterial))}
    vidas: dict[str, Counter] = {}
    for linha, baixado in linhas_por_baixado:
        codigo = str(linha.get("Grupo do Material") or "").strip()
        if codigo:
            vidas.setdefault(codigo, Counter())[montar_bem(linha, baixado)["vida_util_meses"]] += 1
    resultado = {}
    for codigo, contagem in vidas.items():
        chave = f"SAM-{codigo}"
        if chave not in existentes and APLICAR:
            vida = next((v for v, _ in contagem.most_common() if v), None)
            grupo = GrupoMaterial(id=uuid.uuid4(), codigo=chave, nome=f"Grupo {codigo} do SAM", vida_util_meses=vida, ativo=True)
            sessao.add(grupo)
            existentes[chave] = grupo
        if chave in existentes:
            resultado[codigo] = existentes[chave]
    if APLICAR:
        sessao.flush()
    return resultado


def main() -> None:
    todas = [(l, baixado) for arquivo, baixado in ARQUIVOS for l in ler(arquivo)]
    print(f"Planilhas: {len(todas)} linhas ({sum(1 for _, b in todas if b)} baixados)")
    resumo: Counter = Counter()
    agora = datetime.now(timezone.utc)
    with FabricaSessao() as sessao:
        existentes = {b.chapa_chave: b for b in sessao.scalars(select(Bem).where(Bem.chapa_chave.is_not(None)))}
        sala = sala_atualizar(sessao) if APLICAR else None
        grupos = grupos_do_sam(sessao, todas)
        for linha, baixado in todas:
            dados = montar_bem(linha, baixado)
            grupo = grupos.get(str(linha.get("Grupo do Material") or "").strip())
            bem = existentes.get(dados["chapa_chave"])
            if bem is not None:
                resumo["já existia: completa com dados do SAM"] += 1
                if APLICAR:
                    # Só preenche o que o bem ainda não tem; descrição, sala, situação e conservação ficam como estão
                    for campo, valor in dados.items():
                        if campo not in ("id_cliente", "chapa", "chapa_chave", "descricao", "conservacao", "situacao", "origem") and getattr(bem, campo, None) in (None, ""):
                            setattr(bem, campo, valor)
                    bem.grupo_id = bem.grupo_id or (grupo.id if grupo else None)
                    if baixado and bem.situacao != "baixado":  # constar na planilha de baixados vale mais que constar na de ativos
                        bem.situacao, bem.baixado_em, bem.conservacao = "baixado", agora, dados["conservacao"]
                    sessao.add(EventoPatrimonio(id=uuid.uuid4(), bem_id=bem.id, tipo="alterou", autor_nome="Sistema", origem=ORIGEM_IMPORTACAO,
                                                texto="Dados do SAM acrescentados ao bem", dados={"sam": dados["id_cliente"]}))
                continue
            resumo["baixado novo" if baixado else "ativo novo"] += 1
            if not APLICAR:
                continue
            novo = Bem(id=uuid.uuid4(), localizacao_id=sala.id, grupo_id=grupo.id if grupo else None, baixado_em=agora if baixado else None, **dados)
            sessao.add(novo)
            sessao.flush()
            sessao.add(EventoPatrimonio(id=uuid.uuid4(), bem_id=novo.id, tipo="cadastrou", autor_nome="Sistema", origem=ORIGEM_IMPORTACAO,
                                        texto=f"Importado do SAM ({'baixado' if baixado else 'ativo'}) para {SALA_ATUALIZAR}",
                                        dados={"sala_id": str(sala.id), "sala": sala.codigo, "sam": dados["id_cliente"]}))
            existentes[dados["chapa_chave"]] = novo
        if APLICAR:
            sessao.commit()
    print(("GRAVADO" if APLICAR else "SIMULAÇÃO (nada foi gravado; use --aplicar)") + f": {dict(resumo)}")


if __name__ == "__main__":
    main()
