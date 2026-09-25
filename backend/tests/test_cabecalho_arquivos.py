# Criado por José Eduardo Santana Martins
# Este arquivo serve para garantir que todo arquivo .py do backend tenha o cabeçalho padrão.
"""Todo arquivo .py do backend começa com o cabeçalho padrão: autor e finalidade do arquivo."""

from pathlib import Path

# Pasta backend/ (uma acima de tests/)
RAIZ = Path(__file__).resolve().parents[1]


def test_todo_arquivo_python_tem_cabecalho_padrao():
    """Percorre todos os .py (fora do .venv) e lista os que não começam com as duas linhas padrão."""
    sem_cabecalho = []
    for arquivo in sorted(RAIZ.rglob("*.py")):
        if ".venv" in arquivo.parts:
            continue
        linhas = arquivo.read_text(encoding="utf-8").splitlines()[:2]
        if len(linhas) < 2 or linhas[0] != "# Criado por José Eduardo Santana Martins" or not linhas[1].startswith(
            ("# Este arquivo serve para ", "# Este arquivo é para ")
        ):
            sem_cabecalho.append(str(arquivo.relative_to(RAIZ)))
    assert not sem_cabecalho, "Arquivos sem o cabeçalho padrão: " + ", ".join(sem_cabecalho)
