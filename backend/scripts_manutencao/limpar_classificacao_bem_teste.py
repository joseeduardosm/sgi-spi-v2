# Criado por José Eduardo Santana Martins
# Este arquivo serve para apagar, uma única vez, o histórico de classificação (inservível/extraviado) de um bem de teste e devolvê-lo a Ativo.
"""Limpeza única do bem PGOV009361 (id 38a471c2-ad3a-4e1d-8f16-dab49668cd24).

O histórico do patrimônio é protegido por gatilho (não pode ser alterado nem apagado), então o gatilho é desligado só durante esta transação e
religado antes do commit. O que é feito:
- apaga os eventos de classificação do bem (`classificacao_pendente`, `classificacao_recusada` e `classificou`); o evento "cadastrou" fica;
- apaga os itens dele nas listas de classificação e as listas que ficarem vazias;
- devolve o bem a Ativo, sem classificação pendente.

Por padrão é um ENSAIO: mostra o que seria feito e desfaz tudo. Para valer: `--aplicar`.
Uso: cd backend && .venv/bin/python scripts_manutencao/limpar_classificacao_bem_teste.py [--aplicar]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402

BEM = "38a471c2-ad3a-4e1d-8f16-dab49668cd24"
TIPOS = ("classificacao_pendente", "classificacao_recusada", "classificou")
APLICAR = "--aplicar" in sys.argv

with FabricaSessao() as s:
    bem = s.execute(text("select chapa, situacao, classificacao_pendente from patrimonio_bens where id = :b"), {"b": BEM}).one_or_none()
    if bem is None:
        sys.exit("Bem não encontrado.")
    print("Bem:", bem)
    gatilhos = [r[0] for r in s.execute(text("select tgname from pg_trigger where tgrelid='patrimonio_eventos'::regclass and not tgisinternal"))]
    for g in gatilhos:
        s.execute(text(f'alter table patrimonio_eventos disable trigger "{g}"'))
    eventos = s.execute(text("delete from patrimonio_eventos where bem_id = :b and tipo = any(:t)"), {"b": BEM, "t": list(TIPOS)}).rowcount
    listas = [r[0] for r in s.execute(text("select classificacao_id from patrimonio_itens_classificacao where bem_id = :b"), {"b": BEM})]
    itens = s.execute(text("delete from patrimonio_itens_classificacao where bem_id = :b"), {"b": BEM}).rowcount
    vazias = 0
    for lista in set(listas):
        if not s.execute(text("select 1 from patrimonio_itens_classificacao where classificacao_id = :c limit 1"), {"c": lista}).first():
            vazias += s.execute(text("delete from patrimonio_classificacoes where id = :c"), {"c": lista}).rowcount
    s.execute(text("update patrimonio_bens set situacao = 'ativo', classificacao_pendente = false where id = :b"), {"b": BEM})
    for g in gatilhos:
        s.execute(text(f'alter table patrimonio_eventos enable trigger "{g}"'))
    restantes = s.execute(text("select tipo from patrimonio_eventos where bem_id = :b order by ocorrido_em"), {"b": BEM}).all()
    print(f"Eventos apagados: {eventos} | itens de lista apagados: {itens} | listas vazias apagadas: {vazias}")
    print("Eventos que restam no bem:", [r[0] for r in restantes])
    if not APLICAR:
        s.rollback()
        print("ENSAIO: nada foi alterado. Rode de novo com --aplicar para valer.")
    else:
        s.commit()
        print("Aplicado.")

with FabricaSessao() as s:
    print("Gatilhos (O = ligado):", s.execute(text("select tgname, tgenabled from pg_trigger where tgrelid='patrimonio_eventos'::regclass and not tgisinternal")).all())
    print("Bem agora:", s.execute(text("select chapa, situacao, classificacao_pendente from patrimonio_bens where id = :b"), {"b": BEM}).one())
