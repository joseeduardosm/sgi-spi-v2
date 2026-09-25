# Criado por José Eduardo Santana Martins
# Este arquivo serve para garantir que todo arquivo .py do backend e .ts do frontend tenha o cabeçalho padrão.
"""Todo arquivo .py do backend e .ts do frontend começa com o cabeçalho padrão: autor e finalidade do arquivo."""

from pathlib import Path

import pytest

# Pasta backend/ (uma acima de tests/)
RAIZ = Path(__file__).resolve().parents[1]
# Código-fonte do frontend Angular, que fica ao lado do backend no mesmo repositório
FONTES_FRONTEND = RAIZ.parent / "frontend" / "src"

AUTOR = "Criado por José Eduardo Santana Martins"
FINALIDADES = ("Este arquivo serve para ", "Este arquivo é para ")


def _sem_cabecalho(arquivos: list[Path], comentario: str, base: Path) -> list[str]:
    """Arquivos cujas duas primeiras linhas não são o cabeçalho padrão (`comentario` = "#" ou "//")."""
    faltando = []
    for arquivo in arquivos:
        linhas = arquivo.read_text(encoding="utf-8").splitlines()[:2]
        if len(linhas) < 2 or linhas[0] != f"{comentario} {AUTOR}" or not linhas[1].startswith(
            tuple(f"{comentario} {f}" for f in FINALIDADES)
        ):
            faltando.append(str(arquivo.relative_to(base)))
    return faltando


def test_todo_arquivo_python_tem_cabecalho_padrao():
    """Percorre todos os .py (fora do .venv) e lista os que não começam com as duas linhas padrão."""
    arquivos = [a for a in sorted(RAIZ.rglob("*.py")) if ".venv" not in a.parts]
    sem_cabecalho = _sem_cabecalho(arquivos, "#", RAIZ)
    assert not sem_cabecalho, "Arquivos sem o cabeçalho padrão: " + ", ".join(sem_cabecalho)


@pytest.mark.skipif(not FONTES_FRONTEND.is_dir(), reason="frontend ausente nesta cópia do projeto")
def test_todo_arquivo_typescript_tem_cabecalho_padrao():
    """Mesma regra para os .ts do frontend, com comentários no formato `//`."""
    sem_cabecalho = _sem_cabecalho(sorted(FONTES_FRONTEND.rglob("*.ts")), "//", FONTES_FRONTEND)
    assert not sem_cabecalho, "Arquivos .ts sem o cabeçalho padrão: " + ", ".join(sem_cabecalho)
