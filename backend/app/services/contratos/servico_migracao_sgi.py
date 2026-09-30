# Criado por José Eduardo Santana Martins
# Este arquivo serve para importar para este sistema os dados do módulo de contratos do SGI SPI.
"""Importação do Módulo de Contratos do SGI SPI pela tela (botão do SuperRoot em /contratos).

O SuperRoot digita duas senhas: a do usuário do SGI (origem, `MIGRACAO_SGI_*`) e a deste servidor
(destino, `MIGRACAO_LOCAL_*`). As duas são conferidas por SSH antes de começar; a de origem também precisa
servir para o `sudo` de lá (a extração lê o banco como `postgres`). Nenhuma senha é gravada: a de origem
passa ao processo de extração só pela variável de ambiente dele.

A execução roda num processo à parte (a extração leva minutos), que registra o andamento em
`MIGRACAO_DIRETORIO/estado.json`; a API tem mais de um worker, por isso o estado fica em arquivo.
Etapas: extração somente leitura (`scripts/extrair-contratos-sgi.py`) e carga com substituição
(`scripts/migrar-contratos-sgi.py --gravar --substituir`). Ver docs/migracao-sgi.md.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import paramiko
from sqlalchemy import func, select

from app.core.banco import FabricaSessao, agora_utc
from app.core.configuracao import obter_configuracao
from app.models.contratos import Contrato, EmpresaContratada
from app.models.usuario import Usuario
from app.services.servico_auditoria import auditar

# Raiz do projeto (quatro pastas acima deste arquivo) e os scripts que fazem o trabalho pesado
RAIZ_PROJETO = Path(__file__).resolve().parents[4]
SCRIPT_EXTRACAO = RAIZ_PROJETO / "scripts" / "extrair-contratos-sgi.py"
SCRIPT_CARGA = RAIZ_PROJETO / "scripts" / "migrar-contratos-sgi.py"
# Quantas linhas finais do log são mostradas na tela
LINHAS_DE_LOG = 40


class ErroMigracao(Exception):
    """Erro conhecido da importação, com o código e o status HTTP que a rota deve devolver."""
    def __init__(self, mensagem: str, codigo: str, status_code: int = 400) -> None:
        super().__init__(mensagem)
        self.codigo, self.status_code = codigo, status_code


def _diretorio() -> Path:
    """Pasta de trabalho da migração, criada se preciso e acessível só ao dono (dados sensíveis)."""
    pasta = Path(obter_configuracao().migracao_diretorio)
    pasta.mkdir(parents=True, exist_ok=True)
    os.chmod(pasta, 0o700)
    return pasta


def _arquivo_estado() -> Path:
    """Arquivo JSON com o estado da importação (compartilhado entre os workers da API)."""
    return _diretorio() / "estado.json"


def _arquivo_log() -> Path:
    """Arquivo de log da execução (as últimas linhas aparecem na tela)."""
    return _diretorio() / "execucao.log"


def _ler_bruto() -> dict[str, Any]:
    """Lê o estado gravado; sem arquivo (ou com arquivo inválido), considera "ociosa"."""
    try:
        return json.loads(_arquivo_estado().read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"situacao": "ociosa"}


def _gravar_estado(**campos: Any) -> dict[str, Any]:
    """Mescla os campos no estado e grava de forma atômica (arquivo temporário + troca de nome)."""
    estado = {**_ler_bruto(), **campos}
    temporario = _arquivo_estado().with_suffix(".tmp")
    temporario.write_text(json.dumps(estado, ensure_ascii=False, default=str))
    temporario.replace(_arquivo_estado())
    return estado


def _processo_vivo(pid: int | None) -> bool:
    """Indica se o processo `pid` ainda existe (o sinal 0 só testa, não interrompe o processo)."""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def ler_estado() -> dict[str, Any]:
    """Estado da última importação, com o fim do log. Execução sem processo vivo vira erro (interrompida)."""
    estado = _ler_bruto()
    if estado.get("situacao") == "executando" and not _processo_vivo(estado.get("pid")):
        estado = _gravar_estado(situacao="erro", mensagem="A importação foi interrompida (o serviço foi reiniciado?).", concluida_em=agora_utc())
    # Anexa as últimas linhas do log e os endereços de origem e destino (só para exibição)
    try:
        estado["log"] = _arquivo_log().read_text(errors="replace").splitlines()[-LINHAS_DE_LOG:]
    except FileNotFoundError:
        estado["log"] = []
    configuracao = obter_configuracao()
    estado["origem"] = f"{configuracao.migracao_sgi_usuario}@{configuracao.migracao_sgi_host}"
    estado["destino"] = f"{configuracao.migracao_local_usuario}@{configuracao.migracao_local_host}"
    return estado


def _conectar(host: str, usuario: str, senha: str, rotulo: str) -> paramiko.SSHClient:
    """Abre uma conexão SSH com senha; erros viram `ErroMigracao` com mensagem clara."""
    # Aceita a chave do servidor sem perguntar (conexões para servidores internos conhecidos)
    cliente = paramiko.SSHClient()
    cliente.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        cliente.connect(host, username=usuario, password=senha, timeout=10, allow_agent=False, look_for_keys=False)
    except paramiko.AuthenticationException as erro:
        raise ErroMigracao(f"Senha incorreta para {usuario}@{host} ({rotulo}).", "senha_invalida") from erro
    except (OSError, paramiko.SSHException) as erro:
        raise ErroMigracao(f"Não foi possível conectar a {host} ({rotulo}): {erro}", "servidor_inacessivel", 502) from erro
    return cliente


def validar_senhas(senha_origem: str, senha_destino: str) -> None:
    """Confere as duas senhas por SSH antes de começar (e o sudo na origem)."""
    configuracao = obter_configuracao()
    origem = _conectar(configuracao.migracao_sgi_host, configuracao.migracao_sgi_usuario, senha_origem, "origem")
    try:
        # A extração lê o banco do SGI como postgres: a senha precisa valer também no sudo de lá
        # `sudo -S -v` lê a senha pela entrada padrão e só valida, sem executar nada
        entrada, saida, _ = origem.exec_command("sudo -S -p '' -v", timeout=15)
        entrada.write(senha_origem + "\n")
        entrada.channel.shutdown_write()
        if saida.channel.recv_exit_status() != 0:
            raise ErroMigracao(
                f"A senha de {configuracao.migracao_sgi_usuario} não foi aceita pelo sudo em {configuracao.migracao_sgi_host}.", "senha_invalida"
            )
    finally:
        origem.close()
    # Destino: basta conseguir entrar
    _conectar(configuracao.migracao_local_host, configuracao.migracao_local_usuario, senha_destino, "destino").close()


def iniciar(senha_origem: str, senha_destino: str, autor: Usuario) -> dict[str, Any]:
    """Valida as senhas e dispara a importação em um processo separado; devolve o estado inicial."""
    if ler_estado().get("situacao") == "executando":
        raise ErroMigracao("Já existe uma importação em andamento.", "conflito", 409)
    validar_senhas(senha_origem, senha_destino)
    configuracao = obter_configuracao()
    _arquivo_log().write_text("")
    _gravar_estado(situacao="executando", etapa="iniciando", mensagem="Iniciando a importação.", iniciada_em=agora_utc(),
                   concluida_em=None, iniciada_por=autor.nome_completo or autor.login, resultado=None, avisos=[], pid=None)
    # A senha de origem vai só para o ambiente do processo filho (nunca para disco)
    ambiente = {**os.environ, "SGI_SENHA": senha_origem, "SGI_HOST": configuracao.migracao_sgi_host,
                "SGI_USUARIO": configuracao.migracao_sgi_usuario}
    # O processo roda este próprio módulo (ver o bloco `__main__` no fim) e continua sozinho, desligado da API
    processo = subprocess.Popen(
        [sys.executable, "-m", "app.services.contratos.servico_migracao_sgi", str(autor.id), autor.login],
        cwd=RAIZ_PROJETO / "backend", env=ambiente, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    _gravar_estado(pid=processo.pid)
    with FabricaSessao() as sessao:
        auditar(sessao, autor.login, "contrato.migracao_sgi.iniciar", f"SGI {configuracao.migracao_sgi_host}", autor_id=autor.id,
                alvo_tipo="migracao", alvo_id="sgi")
        sessao.commit()
    return ler_estado()


# --- Processo à parte ----------------------------------------------------------------------------

def _rodar(etapa: str, mensagem: str, comando: list[str], ambiente: dict[str, str]) -> str:
    """Executa um script da importação, grava a saída no log e devolve o texto; falha vira RuntimeError."""
    _gravar_estado(etapa=etapa, mensagem=mensagem)
    with open(_arquivo_log(), "a") as log:
        log.write(f"==> {mensagem}\n")
        log.flush()
        resultado = subprocess.run(comando, cwd=RAIZ_PROJETO / "backend", env=ambiente, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)
        # Avisos internos do SQLAlchemy não interessam a quem acompanha pela tela
        saida = "\n".join(linha for linha in resultado.stdout.splitlines() if "Warning" not in linha and not linha.startswith("  sessao."))
        log.write(saida + "\n")
    if resultado.returncode != 0:
        ultima = next((linha for linha in reversed(saida.splitlines()) if linha.strip()), "sem detalhes")
        raise RuntimeError(f"Falha na etapa '{etapa}': {ultima}")
    return saida


def executar(autor_id: int, autor_login: str) -> None:
    """Corpo do processo separado: extrai do SGI, carrega aqui e registra o resultado."""
    ambiente = {**os.environ}
    pacote = _diretorio() / f"pacote-{datetime.now():%Y%m%d-%H%M%S}"
    acao, dados = "contrato.migracao_sgi.falhar", None
    try:
        _rodar("extraindo", "Extraindo os dados do SGI (somente leitura)…", [sys.executable, str(SCRIPT_EXTRACAO), str(pacote)], ambiente)
        # A senha de origem não é mais necessária depois da extração
        ambiente.pop("SGI_SENHA", None)
        saida = _rodar("carregando", "Carregando e conferindo os dados neste servidor…",
                       [sys.executable, str(SCRIPT_CARGA), str(pacote), "--gravar", "--substituir"], ambiente)
        # O script de carga imprime uma linha "Carga: {...}" com as quantidades importadas, e linhas "aviso: ..."
        carga = re.search(r"^Carga: (\{.*\})$", saida, re.M)
        resultado = json.loads(carga.group(1)) if carga else None
        avisos = [linha.strip().removeprefix("aviso:").strip() for linha in saida.splitlines() if linha.strip().startswith("aviso:")]
        _gravar_estado(situacao="concluida", etapa="concluida", mensagem="Importação concluída.", resultado=resultado, avisos=avisos,
                       concluida_em=agora_utc())
        acao, dados = "contrato.migracao_sgi.concluir", resultado
    except Exception as erro:  # noqa: BLE001 - qualquer falha precisa chegar à tela
        _gravar_estado(situacao="erro", mensagem=str(erro), concluida_em=agora_utc())
        dados = {"erro": str(erro)}
    finally:
        # O pacote tem dados pessoais e documentos contratuais: não fica no disco
        shutil.rmtree(pacote, ignore_errors=True)
    # Registra na auditoria o sucesso ou a falha
    with FabricaSessao() as sessao:
        auditar(sessao, autor_login, acao, "SGI", autor_id=autor_id, alvo_tipo="migracao", alvo_id="sgi", dados=dados)
        sessao.commit()


# Ponto de entrada quando o módulo é executado como processo separado (ver `iniciar`)
if __name__ == "__main__":
    executar(int(sys.argv[1]), sys.argv[2])


# --- Rascunho de um contrato (botão "Importar do SGI" da conta root) ----------------------------

PAPEIS_SGI = {
    "Manager": "gestor", "ManagerSubstitute": "gestor_suplente",
    "AdministrativeInspector": "fiscal_administrativo", "AdministrativeInspectorSubstitute": "fiscal_administrativo_suplente",
    "TechnicalInspector": "fiscal_tecnico", "TechnicalInspectorSubstitute": "fiscal_tecnico_suplente",
}
PERIODICIDADES_SGI = {"Monthly": 1, "Bimonthly": 2, "Quarterly": 3, "Semiannual": 6, "Semiannually": 6, "Annual": 12, "Yearly": 12}
TIPOS_ITEM_SGI = {"Continuous": "continuo", "OnDemand": "sob_demanda"}

# Uma consulta, numa transação somente leitura: o contrato, a empresa, os prepostos ativos, os itens,
# a equipe vigente e quantas prorrogações, competências e NEs ficam de fora
CONSULTA_RASCUNHO = """begin transaction read only;
select json_build_object(
  'contrato', row_to_json(c),
  'empresa', (select row_to_json(e) from sgi.contract_companies e where e."Id" = c."CompanyId"),
  'prepostos', (select coalesce(json_agg(r order by r."Name"), '[]') from sgi.company_representatives r where r."CompanyId" = c."CompanyId" and r."Active"),
  'itens', (select coalesce(json_agg(i order by i."Order"), '[]') from sgi.contract_items i where i."ContractId" = c."Id"),
  'equipe', (select coalesce(json_agg(a order by a."ValidFrom"), '[]') from sgi.contract_role_assignments a
             where a."ContractId" = c."Id" and (a."ValidUntil" is null or a."ValidUntil" > now())),
  'prorrogacoes', (select count(*) from sgi.contract_term_extensions t where t."ContractId" = c."Id"),
  'competencias', (select count(*) from sgi.contract_execution_competences p where p."ContractId" = c."Id"),
  'notas_empenho', (select count(*) from sgi.contract_commitment_notes n where n."ContractId" = c."Id")
) from sgi.contracts c where c."Sequence" = {sequencial} and c."Year" = {ano};
commit;
"""

# Lê só os usuários pedidos do portal-data.json do SGI (sem senhas nem hashes)
LEITURA_USUARIOS = """
import json, sys
pedidos = set(sys.argv[1:])
d = json.load(open('/var/lib/sgi-spi/portal-data.json', encoding='utf-8'))
print(json.dumps({str(u.get('Id')): {'login': u.get('Username') or '', 'externo': u.get('ExternalId') or '',
                  'nome': (u.get('Profile') or {}).get('FullName') or ''} for u in d.get('Users', []) if str(u.get('Id')) in pedidos}))
"""


def _executar(cliente: paramiko.SSHClient, comando: str, entrada: str) -> str:
    """Roda o comando no SGI com a entrada padrão e devolve a saída (erro → `ErroMigracao`)."""
    stdin, stdout, stderr = cliente.exec_command(comando, timeout=60)
    stdin.write(entrada)
    stdin.channel.shutdown_write()
    saida = stdout.read().decode()
    if stdout.channel.recv_exit_status() != 0:
        detalhe = stderr.read().decode().strip().splitlines()
        if any("try again" in d or "incorrect password" in d for d in detalhe):
            raise ErroMigracao("A senha do SGI não foi aceita pelo sudo de lá.", "senha_invalida")
        raise ErroMigracao(f"Falha ao ler o SGI: {detalhe[-1] if detalhe else 'erro desconhecido'}", "sgi_indisponivel", 502)
    return saida


def _decimal_texto(valor: Any) -> str:
    """Número do JSON do SGI como texto decimal sem zeros à direita (ex.: 12.5000 → 12.5)."""
    texto_valor = format(float(valor or 0), "f") if not isinstance(valor, str) else valor
    return texto_valor.rstrip("0").rstrip(".") if "." in texto_valor else texto_valor


def rascunho_contrato(sessao, numero: str, senha_origem: str) -> dict[str, Any]:
    """Lê no SGI (somente leitura) o contrato `NNN/AAAA` e monta o rascunho do cadastro. Nada é gravado aqui."""
    sequencial, ano = (int(p) for p in numero.strip().split("/"))
    numero_padrao = f"{sequencial:03d}/{ano}"
    existente = sessao.scalar(select(Contrato).where(func.lower(Contrato.numero) == numero_padrao.lower()))
    if existente is not None:
        raise ErroMigracao(f"O contrato {numero_padrao} já está cadastrado neste sistema.", "conflito", 409)

    configuracao = obter_configuracao()
    cliente = _conectar(configuracao.migracao_sgi_host, configuracao.migracao_sgi_usuario, senha_origem, "SGI")
    try:
        # O psql lê a senha do sudo e, em seguida, o script, pela entrada padrão
        bruto = _executar(cliente, "sudo -S -p '' -u postgres psql -d sgi_spi -X -q -v ON_ERROR_STOP=1 -At -f -",
                          senha_origem + "\n" + CONSULTA_RASCUNHO.format(sequencial=sequencial, ano=ano))
        # O json_agg quebra linhas entre os elementos: o JSON é a saída inteira (sem contrato, sai vazia)
        inicio = bruto.find("{")
        if inicio < 0:
            raise ErroMigracao(f"O contrato {numero_padrao} não foi encontrado no SGI.", "nao_encontrado", 404)
        dados = json.loads(bruto[inicio:])
        ids_usuarios = sorted({str(a["UserId"]) for a in dados["equipe"] if a.get("UserId") is not None})
        usuarios_sgi = json.loads(_executar(cliente, "python3 - " + " ".join(ids_usuarios), LEITURA_USUARIOS) or "{}") if ids_usuarios else {}
    finally:
        cliente.close()

    c, e = dados["contrato"], dados["empresa"] or {}
    avisos: list[str] = []

    # Empresa: a daqui com o mesmo CNPJ, se houver
    cnpj = "".join(filter(str.isdigit, e.get("Cnpj") or ""))
    local = sessao.scalar(select(EmpresaContratada).where(EmpresaContratada.cnpj == cnpj)) if cnpj else None
    empresa = {"id": str(local.id) if local else None, "cnpj": cnpj, "razao_social": e.get("CorporateName") or "",
               "nome_fantasia": e.get("TradeName") or "", "endereco": e.get("Address") or "", "ativa_aqui": bool(local.ativa) if local else True}
    if local is None:
        avisos.append("A empresa não está cadastrada aqui: cadastre-a pelo botão da tela (os dados vêm do SGI) antes de salvar.")
    elif not local.ativa:
        avisos.append(f"A empresa {local.razao_social} está inativa aqui: reative-a em Empresas antes de salvar.")

    # Equipe vigente: casa o login ou o id externo (AD) com os usuários daqui
    locais = list(sessao.scalars(select(Usuario)))
    por_login = {u.login.lower(): u for u in locais}
    por_externo = {u.id_externo.lower(): u for u in locais if u.id_externo}
    equipe, papeis_usados = [], set()
    for a in dados["equipe"]:
        papel = PAPEIS_SGI.get(a.get("Role"))
        origem = usuarios_sgi.get(str(a.get("UserId")), {})
        nome = a.get("UserDisplayName") or origem.get("nome") or origem.get("login") or "?"
        usuario = por_login.get((origem.get("login") or "").lower()) or por_externo.get((origem.get("externo") or "").lower())
        if papel is None or papel in papeis_usados:
            continue
        if usuario is None or not usuario.ativo:
            avisos.append(f"{nome} ({papel.replace('_', ' ')}) não tem conta ativa aqui: escolha a pessoa na equipe.")
            continue
        papeis_usados.add(papel)
        equipe.append({"papel": papel, "usuario_id": usuario.id, "login": usuario.login, "nome": usuario.nome_completo or usuario.login})

    itens = [{
        "descricao": i.get("Description") or "", "tipo": TIPOS_ITEM_SGI.get(i.get("Type"), "continuo"),
        "calcula_pro_rata": bool(i.get("CalculatesProRata")), "codigo_classe": i.get("ClassCode") or "",
        "codigo_natureza_despesa": i.get("ExpenseNatureCode") or "", "codigo_siafisico": i.get("SiafisicoCode") or "",
        "codigo_catmat_catser": i.get("CatmatCatserCode") or "", "quantidade_mensal": _decimal_texto(i.get("MonthlyQuantity")),
        "quantidade_total": _decimal_texto(i.get("TotalQuantity")), "valor_unitario": _decimal_texto(i.get("UnitPrice")),
    } for i in dados["itens"]]
    if itens:
        avisos.append("O SGI não tem a Unidade de Fornecimento (UF) dos itens: informe-a em cada item.")
    if dados["prorrogacoes"]:
        avisos.append(f"O SGI tem {dados['prorrogacoes']} prorrogação(ões) registrada(s): depois de salvar, registre-as em Prorrogação.")
    if dados["competencias"] or dados["notas_empenho"]:
        avisos.append(f"Não são importados: {dados['competencias']} competência(s) e {dados['notas_empenho']} nota(s) de empenho do SGI (só o cadastro).")

    periodicidade = c.get("ExecutionPeriodicity")
    return {
        "numero": numero_padrao, "apelido": c.get("Nickname") or "", "objeto": c.get("Object") or "",
        "data_inicio": (c.get("StartDate") or "")[:10], "vigencia_inicial_meses": int(c.get("InitialTermMonths") or 12),
        "vigencia_maxima_meses": int(c.get("MaximumTermMonths") or 60),
        "periodicidade_meses": int(periodicidade) if str(periodicidade).isdigit() else PERIODICIDADES_SGI.get(periodicidade, 1),
        "mes_reajuste": int(c.get("AdjustmentMonth") or 1),
        "sei_gestao_numero": c.get("ManagementSeiNumber") or "", "sei_gestao_link": c.get("ManagementSeiUrl") or "",
        "sei_execucao_numero": c.get("ExecutionSeiNumber") or "", "sei_execucao_link": c.get("ExecutionSeiUrl") or "",
        "empresa": empresa,
        "prepostos": [{"cpf": "".join(filter(str.isdigit, p.get("Cpf") or "")), "nome": p.get("Name") or "", "telefone": p.get("Phone") or "",
                       "email": p.get("Email") or "", "cargo": p.get("JobTitle") or ""} for p in dados["prepostos"]],
        "equipe": equipe, "itens": itens, "avisos": avisos,
    }
