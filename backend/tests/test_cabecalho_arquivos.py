"""
===============================================================================
ARQUIVO: test_cabecalho_arquivos.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Garantir que todo arquivo de programação do projeto comece com o bloco de
cabeçalho padrão (ARQUIVO, AUTOR, FINALIDADE, RESUMO TÉCNICO, FINALIDADE DE
NEGÓCIO e CONTEXTO NO SISTEMA).

RESUMO TÉCNICO:
Percorre as pastas de código (backend, frontend/src, scripts e os
laboratórios dos manuais), lê o começo de cada arquivo e confere:
- se o bloco começa logo no início (depois do shebang, da linha de encoding
  ou do <!doctype html>, quando houver);
- se a linha "ARQUIVO:" traz o nome do próprio arquivo;
- se a linha "AUTOR:" e as quatro seções estão presentes.
Cada linguagem tem o seu comentário: docstring no Python, /** */ no
TypeScript, SCSS e JavaScript, <!-- --> no HTML e # no shell.

FINALIDADE DE NEGÓCIO:
O sistema é mantido por uma equipe pequena e, às vezes, por estagiários. Um
cabeçalho que explica o arquivo (técnica e negócio) reduz o tempo para
entender e manter o código sem depender de quem o escreveu.

CONTEXTO NO SISTEMA:
A regra está descrita em "Cabeçalho obrigatório e comentários didáticos"
no AGENTS.md. Este teste roda com a suíte do backend (pytest) e cobre também
o frontend, que fica no mesmo repositório.

===============================================================================
"""

from pathlib import Path

import pytest

# Pasta backend/ (uma acima de tests/) e raiz do repositório (uma acima de backend/)
RAIZ_BACKEND = Path(__file__).resolve().parents[1]
RAIZ_PROJETO = RAIZ_BACKEND.parent

AUTOR = "AUTOR: José Eduardo Santana Martins"
# Seções obrigatórias, na ordem em que aparecem no bloco
SECOES = ("FINALIDADE:", "RESUMO TÉCNICO:", "FINALIDADE DE NEGÓCIO:", "CONTEXTO NO SISTEMA:")
# Abertura do bloco em cada linguagem (a primeira linha útil do arquivo precisa ser esta)
ABERTURAS = {".py": '"""', ".ts": "/**", ".scss": "/**", ".mjs": "/**", ".js": "/**", ".html": "<!--", ".sh": "# ====="}
# Pastas que nunca entram: dependências, ambientes virtuais e saídas de build
IGNORAR = {".venv", "node_modules", "__pycache__", "dist", ".angular", "web", ".git"}

# Onde procurar e quais extensões valem em cada lugar
PASTAS = [
    (RAIZ_BACKEND, (".py",)),
    (RAIZ_PROJETO / "frontend" / "src", (".ts", ".html", ".scss")),
    (RAIZ_PROJETO / "frontend" / "scripts", (".mjs", ".js", ".sh")),
    (RAIZ_PROJETO / "scripts", (".py", ".sh", ".mjs", ".js")),
    (RAIZ_PROJETO / "docs" / "manuais", (".py", ".sh")),
    (RAIZ_PROJETO / "client", (".sh",)),
]


def _arquivos() -> list[Path]:
    """Lista todos os arquivos de programação que precisam do cabeçalho, sem pastas de dependência ou de build."""
    encontrados = []
    for pasta, extensoes in PASTAS:
        if not pasta.is_dir():
            continue  # cópia parcial do projeto (ex.: só o backend): pula a pasta
        for arquivo in sorted(pasta.rglob("*")):
            if arquivo.is_file() and arquivo.suffix in extensoes and not IGNORAR.intersection(arquivo.relative_to(RAIZ_PROJETO).parts):
                encontrados.append(arquivo)
    return encontrados


def _problema(arquivo: Path) -> str | None:
    """Devolve a descrição do problema no cabeçalho do arquivo, ou `None` quando está tudo certo."""
    linhas = arquivo.read_text(encoding="utf-8").splitlines()
    # Pula o que precisa ficar antes do bloco: shebang (#!), declaração de encoding do Python e doctype do HTML
    inicio = 0
    while inicio < len(linhas) and (linhas[inicio].startswith("#!") or linhas[inicio].startswith("# -*-")
                                     or linhas[inicio].lower().startswith("<!doctype")):
        inicio += 1
    if inicio >= len(linhas) or not linhas[inicio].strip().startswith(ABERTURAS[arquivo.suffix]):
        return "o bloco de cabeçalho não está no início"
    # As 120 primeiras linhas depois da abertura bastam para achar o bloco inteiro
    bloco = "\n".join(linhas[inicio:inicio + 120])
    if f"ARQUIVO: {arquivo.name}" not in bloco:
        return f'falta "ARQUIVO: {arquivo.name}"'
    if AUTOR not in bloco:
        return 'falta "AUTOR:"'
    faltando = [s for s in SECOES if s not in bloco]
    return f"faltam as seções {', '.join(faltando)}" if faltando else None


def test_todo_arquivo_de_programacao_tem_cabecalho_padrao():
    """Lista cada arquivo fora do padrão com o motivo, para facilitar a correção."""
    problemas = [f"{a.relative_to(RAIZ_PROJETO)}: {p}" for a in _arquivos() if (p := _problema(a))]
    assert not problemas, f"{len(problemas)} arquivo(s) sem o cabeçalho padrão:\n" + "\n".join(problemas)


@pytest.mark.parametrize("extensao", [".py", ".ts"])
def test_a_busca_encontra_arquivos(extensao):
    """Proteção contra um teste que passa por não achar nada (ex.: caminho errado depois de mover pastas)."""
    if extensao == ".ts" and not (RAIZ_PROJETO / "frontend" / "src").is_dir():
        pytest.skip("frontend ausente nesta cópia do projeto")
    assert any(a.suffix == extensao for a in _arquivos())
