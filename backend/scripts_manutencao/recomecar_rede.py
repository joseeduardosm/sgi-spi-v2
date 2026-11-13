"""
===============================================================================
ARQUIVO: recomecar_rede.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Apagar, uma única vez, todo o cadastro físico da Rede (equipamentos, portas,
ligações, dispositivos atrás, pontos de rede e racks) para recomeçar o
cadastro em cadeia pela tela.

RESUMO TÉCNICO:
Apaga, nesta ordem, rede_dispositivos_atras, rede_conexoes, rede_pontos,
rede_portas_vlans, rede_portas, rede_equipamentos e rede_racks. Ficam as
VLANs (rede_vlans), os modelos de face (rede_modelos_face) e os parâmetros.
Chamados que apontavam para uma porta ou ponto ficam sem ela (as chaves
estrangeiras já fazem isso). Por padrão é um ENSAIO: mostra as quantidades e
desfaz tudo. Para valer: `--aplicar`.
Uso: cd backend && .venv/bin/python scripts_manutencao/recomecar_rede.py [--aplicar]

FINALIDADE DE NEGÓCIO:
Decisão do usuário (12/11/2026): o cadastro antigo tinha ligações sem lado
no patch panel e equipamentos fora da cadeia core → distribuição → acesso.
A cópia dele ficou na planilha apoio/redes/cadastro-rede-2026-11-12.xlsx.

CONTEXTO NO SISTEMA:
Rodar depois da migração f7a1c3e5b9d2 (lados do patch panel). Regras do
cadastro novo em app/services/rede/servico.py.

===============================================================================
"""
import sys
from pathlib import Path

# Deixa o "app" do backend importável quando o script roda direto pela linha de comando
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.core.banco import FabricaSessao  # noqa: E402

APLICAR = "--aplicar" in sys.argv
# Ordem de apagar: primeiro quem aponta para os outros
TABELAS = ("rede_dispositivos_atras", "rede_conexoes", "rede_pontos", "rede_portas_vlans", "rede_portas", "rede_equipamentos", "rede_racks")
FICAM = ("rede_vlans", "rede_modelos_face")

with FabricaSessao() as sessao:
    for tabela in TABELAS:
        apagadas = sessao.execute(text(f"DELETE FROM {tabela}")).rowcount
        print(f"{tabela}: {apagadas} apagada(s)")
    for tabela in FICAM:
        print(f"{tabela}: {sessao.execute(text(f'SELECT count(*) FROM {tabela}')).scalar()} (ficam)")
    if not APLICAR:
        sessao.rollback()
        print("ENSAIO: nada foi alterado. Rode de novo com --aplicar para valer.")
    else:
        sessao.commit()
        print("Aplicado.")
