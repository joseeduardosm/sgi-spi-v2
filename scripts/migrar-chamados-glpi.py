#!/usr/bin/env python3
# Criado por José Eduardo Santana Martins
# Este arquivo serve para importar o histórico de chamados do GLPI (10 ou 11) para o módulo Chamados, a partir de um dump.
"""Importa o histórico do GLPI para o módulo Chamados (regras em `app/services/chamados/importacao_glpi.py`).

Nunca fala com o GLPI em produção. A entrada é:
- o **dump do banco** com dados (`mysqldump --single-transaction helpdesk > glpi.sql`), feito pela equipe do GLPI;
- opcional, uma **cópia da pasta `files/`** do GLPI, para trazer os anexos.

Uso (na pasta backend):
    .venv/bin/python ../scripts/migrar-chamados-glpi.py preparar glpi.sql de-para/
        → escreve de-para/usuarios.csv, grupos.csv e etiquetas.csv com sugestões. Revise a última coluna de cada um.
    .venv/bin/python ../scripts/migrar-chamados-glpi.py carregar glpi.sql de-para/ --setor-padrao "Suporte TI" [--arquivos files/]
        → ENSAIO: carrega, mostra o relatório (origem × destino e avisos) e desfaz tudo.
    ... carregar ... --gravar
        → grava de verdade. Pode rodar de novo: o que já veio é pulado (idempotente).

O relatório também é gravado em de-para/relatorio-<etapa>.txt.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import func, select  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402
from app.models.setor import Setor  # noqa: E402
from app.services.chamados import importacao_glpi  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa o histórico do GLPI para o módulo Chamados.")
    parser.add_argument("etapa", choices=["preparar", "carregar"])
    parser.add_argument("dump", type=Path, help="Arquivo .sql do mysqldump (com dados).")
    parser.add_argument("de_para", type=Path, help="Pasta dos arquivos de-para (criada na etapa preparar).")
    parser.add_argument("--setor-padrao", help="Setor dos chamados sem grupo e das categorias raiz sem grupo (obrigatório em carregar).")
    parser.add_argument("--arquivos", type=Path, help="Cópia da pasta files/ do GLPI (para os anexos).")
    parser.add_argument("--gravar", action="store_true", help="Grava de verdade (sem isto, é ensaio e nada fica no banco).")
    args = parser.parse_args()

    print(f"Lendo {args.dump} ...", flush=True)
    try:
        dados = importacao_glpi.ler_dump(args.dump)
    except (OSError, importacao_glpi.ErroImportacao) as erro:
        print(f"ERRO: {erro}")
        return 1
    print(f"GLPI {importacao_glpi.versao(dados)}: {len(dados.get('glpi_tickets', []))} chamados no dump.")

    with FabricaSessao() as sessao:
        try:
            if args.etapa == "preparar":
                relatorio = importacao_glpi.preparar(sessao, dados, args.de_para)
                sessao.rollback()
                print(f"De-para escrito em {args.de_para}/. Revise a última coluna de usuarios.csv, grupos.csv e etiquetas.csv.")
            else:
                if not args.setor_padrao:
                    print("ERRO: informe --setor-padrao (nome do setor dos chamados sem grupo).")
                    return 1
                setor = sessao.scalar(select(Setor).where(func.lower(Setor.nome) == args.setor_padrao.lower()))
                if setor is None:
                    print(f"ERRO: setor \"{args.setor_padrao}\" não encontrado.")
                    return 1
                if args.arquivos is not None and not args.arquivos.is_dir():
                    print(f"ERRO: a pasta {args.arquivos} não existe.")
                    return 1
                relatorio = importacao_glpi.carregar(sessao, dados, args.de_para, setor.id, args.arquivos)
                if args.gravar:
                    sessao.commit()
                else:
                    sessao.rollback()
        except importacao_glpi.ErroImportacao as erro:
            sessao.rollback()
            print(f"ERRO: {erro}")
            return 1
    texto = relatorio.texto()
    print(texto)
    args.de_para.mkdir(parents=True, exist_ok=True)
    (args.de_para / f"relatorio-{args.etapa}.txt").write_text(texto + "\n", encoding="utf-8")
    if args.etapa == "carregar":
        print("\nGRAVADO." if args.gravar else "\nENSAIO: nada foi gravado. Rode de novo com --gravar para valer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
