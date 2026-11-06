# Criado por José Eduardo Santana Martins
# Este arquivo serve para a atualização do SGI pela tela (Administração › Versões): a homologação aprova versões e a produção as instala.
"""Versões do SGI SPI pelo GitHub (decisões do usuário, 06/11/2026).

- A **homologação** acompanha um ramo do GitHub (`ATUALIZACAO_RAMO`, padrão `estado-atual-servidor`): "Atualizar homologação" leva ao
  último commit dele. Testada, "Aprovar esta versão" cria uma **tag anotada** `vAAAA.MM.DD[.N]` no commit em execução e a envia ao GitHub.
- A **produção** só enxerga as tags aprovadas mais novas que a versão em execução e instala uma delas.
- Instalar não roda dentro da API (ela é reiniciada no fim): a API grava o **pedido** em `dados/atualizacao/pedido.json` e liga a unidade
  `sgi-spi-atualizar.service` (`sudo -n systemctl start --no-block …`, liberado no sudoers do instalador). Quem executa é
  `scripts/atualizar-versao.py`: backup geral, código, dependências, migrações, build, reinício e, se falhar, **volta sozinho**
  (código anterior e banco do backup). O andamento fica em `dados/atualizacao/andamento.json`, no formato do backup geral.

O Git é chamado sem shell e com tempo-limite; qualquer falha vira `ErroVersoes` (400 na API).
"""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

from app.core.banco import agora_utc
from app.core.configuracao import DIRETORIO_BACKEND, obter_configuracao
from app.services import servico_backup

RAIZ = DIRETORIO_BACKEND.parent
PEDIDO = "pedido.json"
ANDAMENTO = "andamento.json"
LOG = "ultima-atualizacao.log"
# Tags de versão aprovada: v2026.11.06 ou v2026.11.06.2 (segunda aprovação no mesmo dia)
PADRAO_TAG = re.compile(r"^v\d{4}\.\d{2}\.\d{2}(\.\d+)?$")
# Etapas da atualização, na ordem (as mesmas da trilha da tela)
ETAPAS = ("conferir", "backup", "codigo", "dependencias", "migracoes", "build", "reiniciar")
CONFIRMACAO = "ATUALIZAR"


class ErroVersoes(Exception):
    """Regra da atualização violada ou falha do Git (vira 400 com a mensagem)."""


# ---------------------------------------------------------------------------------------------
# Git (isolado: os testes usam um repositório temporário)
# ---------------------------------------------------------------------------------------------

def raiz() -> Path:
    """Pasta do projeto (com o .git). Os testes trocam por um repositório temporário."""
    return RAIZ


def git(*args: str, tempo: int = 60) -> str:
    """Roda `git -C <raiz> …` e devolve a saída; falha vira `ErroVersoes` com a mensagem do Git."""
    try:
        r = subprocess.run(["git", "-C", str(raiz()), *args], capture_output=True, text=True, timeout=tempo)
    except (OSError, subprocess.SubprocessError) as erro:
        raise ErroVersoes(f"Não foi possível executar o Git: {erro}") from erro
    if r.returncode != 0:
        raise ErroVersoes(f"O Git recusou ({' '.join(args[:2])}): {(r.stderr or r.stdout).strip()[:400]}")
    return r.stdout.strip()


def versao_atual() -> str:
    """Versão em execução no disco: a tag (ou "tag-N-gcommit"), ou o commit curto se não houver tag."""
    return git("describe", "--tags", "--always")


def arvore_limpa() -> bool:
    """Sem alteração local em arquivo versionado (a atualização não pode passar por cima de trabalho não commitado)."""
    return not git("status", "--porcelain", "--untracked-files=no")


def _e_ancestral(ref: str) -> bool:
    """`ref` já está contido no código em execução (instalar seria voltar ou ficar igual)."""
    try:
        git("merge-base", "--is-ancestor", ref, "HEAD")
        return True
    except ErroVersoes:
        return False


def buscar() -> None:
    """Traz do GitHub os commits e as tags novos (não muda o código em execução)."""
    git("fetch", "--tags", "--force", "origin", tempo=120)


# ---------------------------------------------------------------------------------------------
# O que há para instalar
# ---------------------------------------------------------------------------------------------

def versoes_aprovadas() -> list[dict]:
    """Tags aprovadas mais novas que a versão em execução (da mais recente para a mais antiga), com quem aprovou e quando."""
    formato = "%(refname:short)%09%(taggername)%09%(taggerdate:iso-strict)%09%(objectname:short)"
    itens = []
    for linha in git("for-each-ref", "refs/tags", "--sort=-creatordate", f"--format={formato}").splitlines():
        partes = linha.split("\t")
        if len(partes) < 4 or not PADRAO_TAG.match(partes[0]) or _e_ancestral(partes[0]):
            continue
        tag, quem, quando, _ = partes
        itens.append({"alvo": tag, "aprovada_por": quem or None, "aprovada_em": datetime.fromisoformat(quando) if quando else None,
                      "mensagem": git("tag", "-l", "--format=%(contents)", tag).strip(), "novidades": novidades(tag),
                      "commits": commits_entre("HEAD", tag)})
    return itens


def commits_entre(de: str, ate: str, limite: int = 50) -> list[dict]:
    """Commits que `ate` tem e `de` não tem (os que a atualização traria), do mais recente para o mais antigo."""
    saida = git("log", f"--max-count={limite}", "--format=%h%x09%s%x09%an%x09%aI", f"{de}..{ate}")
    commits = []
    for linha in saida.splitlines():
        partes = linha.split("\t")
        if len(partes) == 4:
            commits.append({"commit": partes[0], "titulo": partes[1], "autor": partes[2], "data": datetime.fromisoformat(partes[3])})
    return commits


def novidades(alvo: str) -> str:
    """O que o CHANGELOG.md ganhou entre a versão em execução e `alvo` (as linhas acrescentadas, sem os marcadores do diff)."""
    try:
        diff = git("diff", "--unified=0", "HEAD", alvo, "--", "CHANGELOG.md")
    except ErroVersoes:
        return ""
    return "\n".join(l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")).strip()


def ramo_remoto() -> str:
    return f"origin/{obter_configuracao().atualizacao_ramo}"


# ---------------------------------------------------------------------------------------------
# Andamento e pedido (dados/atualizacao)
# ---------------------------------------------------------------------------------------------

def pasta() -> Path:
    destino = obter_configuracao().atualizacao_diretorio
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def andamento() -> dict:
    """Situação da última atualização: {"operacao": "atualizar", "situacao": em_andamento|concluido|erro|reiniciando, "etapa",
    "percentual", "mensagem", "de", "para", "atualizado_em"} (vazio se nunca houve)."""
    try:
        return json.loads((pasta() / ANDAMENTO).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def registrar_andamento(situacao: str, mensagem: str, etapa: str | None = None, percentual: float | None = None, **extras) -> None:
    """Grava o andamento num temporário e troca de uma vez (a tela nunca lê um JSON pela metade). Mantém `de`/`para` já gravados."""
    anterior = andamento()
    dados = {"operacao": "atualizar", "de": anterior.get("de"), "para": anterior.get("para"), **extras, "situacao": situacao, "mensagem": mensagem,
             "etapa": etapa, "percentual": None if percentual is None else round(min(max(percentual, 0), 100), 1),
             "atualizado_em": agora_utc().isoformat()}
    temporario = pasta() / (ANDAMENTO + ".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False))
    temporario.replace(pasta() / ANDAMENTO)


def ocupado() -> bool:
    """Atualização, backup ou importação em andamento (uma operação dessas por vez)."""
    return andamento().get("situacao") in ("em_andamento", "reiniciando") or servico_backup.ocupado()


def situacao() -> dict:
    """Painel da tela: ambiente, versão em execução, árvore limpa, andamento e o que há para instalar (sem ir ao GitHub)."""
    config = obter_configuracao()
    dados = {"homologacao": config.modo_homologacao, "versao": config.versao_aplicacao, "versao_no_disco": versao_atual(),
             "commit": git("rev-parse", "--short", "HEAD"), "arvore_limpa": arvore_limpa(), "ramo": config.atualizacao_ramo,
             "andamento": andamento(), "versoes": [], "commits_novos": [], "aprovada": None}
    if config.modo_homologacao:
        try:
            dados["commits_novos"] = commits_entre("HEAD", ramo_remoto())
        except ErroVersoes:
            dados["commits_novos"] = []
        # A versão em execução já foi aprovada? (alguma tag de versão aponta para o commit atual)
        tags = [t for t in git("tag", "--points-at", "HEAD").splitlines() if PADRAO_TAG.match(t)]
        dados["aprovada"] = tags[0] if tags else None
    else:
        dados["versoes"] = versoes_aprovadas()
    return dados


# ---------------------------------------------------------------------------------------------
# Aprovar (homologação) e pedir a atualização
# ---------------------------------------------------------------------------------------------

def _nome_da_tag() -> str:
    """vAAAA.MM.DD; se já houver uma no dia, vAAAA.MM.DD.2, .3…"""
    base = f"v{datetime.now().astimezone():%Y.%m.%d}"
    existentes = set(git("tag", "-l", f"{base}*").splitlines())
    if base not in existentes:
        return base
    n = 2
    while f"{base}.{n}" in existentes:
        n += 1
    return f"{base}.{n}"


def aprovar(nome_autor: str) -> str:
    """Homologação: cria a tag anotada no commit em execução e a envia ao GitHub. Devolve o nome da tag."""
    if not obter_configuracao().modo_homologacao:
        raise ErroVersoes("Só a homologação aprova versões (MODO_HOMOLOGACAO=true).")
    if not arvore_limpa():
        raise ErroVersoes("Há alterações locais não commitadas neste servidor: aprove só código que está no GitHub.")
    buscar()
    if not git("branch", "-r", "--contains", "HEAD"):
        raise ErroVersoes("O código em execução não está no GitHub (commit só local): envie-o antes de aprovar.")
    if [t for t in git("tag", "--points-at", "HEAD").splitlines() if PADRAO_TAG.match(t)]:
        raise ErroVersoes("Esta versão já foi aprovada.")
    tag = _nome_da_tag()
    mensagem = f"Aprovada em homologação por {nome_autor} em {datetime.now().astimezone():%d/%m/%Y %H:%M}"
    texto_novidades = novidades_desde_ultima_tag()
    git("-c", f"user.name={nome_autor}", "-c", "user.email=sgi-spi@localhost", "tag", "-a", tag, "-m", mensagem + ("\n\n" + texto_novidades if texto_novidades else ""))
    try:
        git("push", "origin", tag, tempo=120)
    except ErroVersoes as erro:
        # Sem a tag no GitHub a produção não a vê: desfaz a local e explica (geralmente falta a chave de deploy com escrita)
        git("tag", "-d", tag)
        raise ErroVersoes(f"Não foi possível enviar a tag ao GitHub (a chave de deploy da homologação tem permissão de escrita?). {erro}") from erro
    return tag


def novidades_desde_ultima_tag() -> str:
    """O que o CHANGELOG.md ganhou desde a última versão aprovada (para a mensagem da tag)."""
    tags = [t for t in git("tag", "-l", "--sort=-creatordate").splitlines() if PADRAO_TAG.match(t)]
    if not tags:
        return ""
    try:
        diff = git("diff", "--unified=0", tags[0], "HEAD", "--", "CHANGELOG.md")
    except ErroVersoes:
        return ""
    return "\n".join(l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")).strip()


def disparar_unidade() -> None:
    """Liga a unidade que executa a atualização fora da API (os testes trocam por um registro)."""
    r = subprocess.run(["sudo", "-n", "systemctl", "start", "--no-block", "sgi-spi-atualizar.service"], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise ErroVersoes("Não foi possível iniciar a atualização (a unidade sgi-spi-atualizar e o sudoers vêm do scripts/instalar.sh: rode-o "
                          f"uma vez neste servidor). {r.stderr.strip()[:300]}")


def pedir_atualizacao(alvo: str, confirmacao: str, login: str, usuario_id: int, nome: str) -> dict:
    """Confere e grava o pedido; liga a unidade. Produção: só uma tag aprovada mais nova. Homologação: só o ramo acompanhado."""
    if confirmacao != CONFIRMACAO:
        raise ErroVersoes(f"Para confirmar, digite {CONFIRMACAO}.")
    if ocupado():
        raise ErroVersoes("Já há uma atualização, backup ou importação em andamento.")
    if not arvore_limpa():
        raise ErroVersoes("Há alterações locais não commitadas neste servidor: a atualização passaria por cima delas.")
    config = obter_configuracao()
    buscar()
    if config.modo_homologacao:
        if alvo != config.atualizacao_ramo:
            raise ErroVersoes(f"Na homologação, a atualização é para o último commit do ramo {config.atualizacao_ramo}.")
        ref = git("rev-parse", ramo_remoto())
        if _e_ancestral(ref):
            raise ErroVersoes("A homologação já está no último commit do ramo.")
    else:
        if not PADRAO_TAG.match(alvo) or alvo not in [v["alvo"] for v in versoes_aprovadas()]:
            raise ErroVersoes("Versão inválida: escolha uma versão aprovada mais nova que a atual.")
        ref = alvo
    pedido = {"alvo": alvo, "ref": ref, "de": versao_atual(), "de_commit": git("rev-parse", "HEAD"), "pedido_por": login,
              "pedido_por_id": usuario_id, "pedido_por_nome": nome, "pedido_em": agora_utc().isoformat()}
    (pasta() / PEDIDO).write_text(json.dumps(pedido, ensure_ascii=False))
    registrar_andamento("em_andamento", "Aguardando o início da atualização…", etapa="conferir", percentual=0, de=pedido["de"], para=alvo)
    try:
        disparar_unidade()
    except ErroVersoes as erro:
        registrar_andamento("erro", str(erro), etapa="conferir")
        raise
    return pedido


def log() -> str:
    """Final do log da última atualização (para a tela mostrar quando dá erro)."""
    try:
        return (pasta() / LOG).read_text(errors="replace")[-6000:]
    except FileNotFoundError:
        return ""
