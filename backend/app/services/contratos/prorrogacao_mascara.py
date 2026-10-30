# Criado por José Eduardo Santana Martins
# Este arquivo serve para validar e preencher as máscaras (modelos) das minutas e despachos da prorrogação contratual.
"""Máscaras da prorrogação: HTML do editor rico com placeholders de uma **lista fechada** (`#nome`, `#nome#` ou `##nome##`).

Dois tipos de placeholder:
- **do SGI**: o sistema sabe o valor (contrato, empresa, nova vigência, valor, autoridades dos parâmetros);
- **digitados**: a equipe preenche na própria prorrogação (testemunhas, nº dos documentos do SEI, dotação…), guardados em `dados_minuta`.

Placeholder sem valor **não some**: vira `[rótulo]` no texto e entra na lista de lacunas mostrada na tela. Os **condicionais** (`#se…`) decidem se
o parágrafo inteiro aparece (cláusulas opcionais do termo aditivo): com a condição desligada o parágrafo é omitido; ligada, só o marcador é retirado.
Os valores são sempre escapados. Mesma sintaxe do despacho (`despacho_mascara`).
"""

from html import escape

from lxml import html as lxml_html

from app.services.contratos import despacho_mascara

# Documentos que o módulo gera: variante → título mostrado na tela
VARIANTES: dict[str, str] = {
    "despacho_instrucao": "Despacho de instrução (CCC/DGA → SSGC)",
    "declaracao_atendimento_licitacao": "Declaração de Atendimento — contrato de licitação (Anexo II)",
    "declaracao_atendimento_direta": "Declaração de Atendimento — dispensa ou inexigibilidade (Anexo III)",
    "minuta_aditivo": "Minuta do Termo de Aditamento (Anexo I)",
    "termo_ciencia": "Termo de Ciência e de Notificação (TCE-SP)",
    "declaracao_tce": "Declaração de documentos à disposição do TCE-SP",
    "despacho_autorizacao": "Despacho de autorização da prorrogação (autoridade competente)",
}

# Placeholders cujo valor o SGI calcula: nome → descrição
DO_SGI: dict[str, str] = {
    "nrocontrato": "Número do contrato (ex.: 018/2024)",
    "anocontrato": "Ano do contrato",
    "objetodocontrato": "Objeto do contrato",
    "razaosocialempresa": "Razão social da contratada",
    "cnpjempresa": "CNPJ da contratada",
    "enderecoempresa": "Endereço da contratada",
    "representantenome": "Representante legal da contratada (preposto marcado como representante legal)",
    "representantefuncao": "Cargo do representante legal da contratada",
    "representantecpf": "CPF do representante legal da contratada",
    "processogestao": "Número do processo SEI de gestão do contrato",
    "vigenciainicialmeses": "Vigência inicial do contrato, em meses por extenso (ex.: 12 (doze) meses)",
    "vigenciainicialinicio": "Início da vigência inicial (dd/mm/aaaa)",
    "vigenciainicialfim": "Fim da vigência inicial (dd/mm/aaaa)",
    "vigenciaatualfim": "Fim da vigência atual, antes da prorrogação (dd/mm/aaaa)",
    "nrotermo": "Número do termo aditivo (próximo da sequência de prorrogações; ex.: 2º)",
    "mesesprorrogacao": "Prazo da prorrogação, em meses por extenso (ex.: 12 (doze) meses)",
    "inicioprorrogacao": "Primeiro dia da prorrogação (dd/mm/aaaa)",
    "fimprorrogacao": "Último dia da prorrogação (dd/mm/aaaa)",
    "valorprorrogacao": "Valor total da prorrogação em reais (calculado pelos itens; pode ser corrigido na tela)",
    "valorprorrogacaoextenso": "Valor total da prorrogação por extenso",
    "valoresporexercicio": "Valor da prorrogação em cada exercício financeiro, em texto corrido",
    "modalidade": "Origem da contratação (licitação, dispensa ou inexigibilidade)",
    "prazopncp": "Prazo para divulgar no PNCP, em dias úteis (parâmetro: licitação ou contratação direta)",
    "mesanoatual": "Mês e ano de hoje, por extenso (ex.: novembro de 2026)",
    "gestor": "Nome do gestor do contrato",
    "ssgcnome": "Nome do Subsecretário de Gestão Corporativa (Parâmetros de Contratos)",
    "ssgccpf": "CPF do Subsecretário de Gestão Corporativa",
    "secretarionome": "Nome do Secretário (Parâmetros de Contratos)",
    "secretariocpf": "CPF do Secretário",
    "autoridadenome": "Autoridade competente que autoriza a prorrogação (Parâmetros de Contratos)",
    "autoridadecargo": "Cargo da autoridade competente",
    "parecerreferencial": "Parecer Referencial aplicável (ex.: NLC nº 1/2026)",
}

# Placeholders que a equipe digita na prorrogação: nome → (rótulo curto da lacuna, descrição, multilinha?). Os nomes só têm letras (a sintaxe não aceita dígitos nem acento)
DIGITADOS: dict[str, tuple[str, str, bool]] = {
    "testemunhaanome": ("nome da 1ª testemunha", "Nome da 1ª testemunha", False),
    "testemunhaacpf": ("CPF da 1ª testemunha", "CPF da 1ª testemunha", False),
    "testemunhabnome": ("nome da 2ª testemunha", "Nome da 2ª testemunha", False),
    "testemunhabcpf": ("CPF da 2ª testemunha", "CPF da 2ª testemunha", False),
    "baserepresentacao": ("base da representação", "Base da representação do contratado (ex.: atos constitutivos do fornecedor, ou procuração apresentada nos autos)", False),
    "assinaturadocontrato": ("data de assinatura do contrato", "Data de assinatura do contrato original (dd/mm/aaaa)", False),
    "clausulavigencia": ("cláusula da vigência", "Cláusula do contrato que trata da vigência (ex.: Quinta)", False),
    "numeroprocesso": ("processo SEI da prorrogação", "Processo SEI da prorrogação (se vazio, usa o processo de gestão do contrato)", False),
    "dotacao": ("classificação funcional e categoria econômica", "Classificação funcional programática e categoria econômica da despesa", False),
    "nrone": ("nota de empenho", "Nota de empenho da prorrogação", False),
    "notareserva": ("nota de reserva", "Nota de reserva orçamentária (ex.: 2026NR00123)", False),
    "valorempenho": ("valor do empenho", "Valor da nota de empenho (R$)", False),
    "anoempenho": ("exercício do empenho", "Exercício a que se destina o empenho", False),
    "efeitoscustos": ("data de efeito da eliminação de custos", "Data a partir da qual a eliminação dos custos não renováveis produz efeitos", False),
    "periodosrepactuacao": ("períodos da repactuação", "Períodos pretéritos resguardados para repactuação (mão de obra e demais custos)", True),
    "tratamentoreajuste": ("tratamento do reajuste", "Como o reajuste/repactuação foi tratado (ou o texto-padrão de resguardo de direitos)", True),
    "aferiprecos": ("aferição de preços", "Nota Técnica ou despacho de aferição de preços", False),
    "responsavelnome": ("responsável pela instrução", "Nome de quem assina a instrução", False),
    "responsavelcargo": ("cargo do responsável pela instrução", "Cargo/unidade de quem assina a instrução", False),
    "coordenadornome": ("coordenador da CCC", "Nome do Coordenador da Coordenadoria de Contratação e Convênios", False),
    "diretornome": ("diretor(a) da DGA", "Nome do(a) Diretor(a) de Gestão Administrativa", False),
    "docparecerreferencial": ("nº do doc. do Parecer Referencial", "Nº do documento no SEI: cópia do Parecer Referencial", False),
    "docjustificativa": ("nº do doc. da justificativa do gestor", "Nº do documento no SEI: relatório e justificativa do gestor", False),
    "docaceite": ("nº do doc. do aceite da contratada", "Nº do documento no SEI: consulta e aceite da contratada", False),
    "docproposta": ("nº do doc. da proposta atualizada", "Nº do documento no SEI: proposta atualizada da contratada", False),
    "docpesquisa": ("nº do doc. da pesquisa de preços", "Nº do documento no SEI: pesquisa de preços e quadro comparativo", False),
    "docvantajosidade": ("nº do doc. da vantajosidade", "Nº do documento no SEI: declaração de vantajosidade", False),
    "docplanilha": ("nº do doc. da planilha orçamentária", "Nº do documento no SEI: planilha orçamentária", False),
    "docreserva": ("nº do doc. da nota de reserva", "Nº do documento no SEI: nota de reserva", False),
    "docminuta": ("nº do doc. da minuta do aditivo", "Nº do documento no SEI: minuta do termo aditivo", False),
    "docdeclaracao": ("nº do doc. da declaração de atendimento", "Nº do documento no SEI: declaração de atendimento ao Parecer Referencial", False),
    "docchecklist": ("nº do doc. do checklist", "Nº do documento no SEI: checklist do Parecer Referencial", False),
    "dochabilitacao": ("nº do doc. das certidões", "Nº do documento no SEI: certidões e documentos de habilitação", False),
    "docdespacho": ("nº do doc. do despacho de instrução", "Nº do documento no SEI: despacho de instrução (CCC/DGA)", False),
}

# Condicionais: nome → descrição. O parágrafo com o marcador só aparece quando a condição vale
CONDICIONAIS: dict[str, str] = {
    "secustosnaorenovaveis": "Mantém o parágrafo só se houver custos não renováveis já amortizados (cláusula 1.2)",
    "sedemandavariavel": "Mantém o parágrafo só se o contrato tiver itens sob demanda (valor estimativo, cláusula 2.2)",
    "serepactuacao": "Mantém o parágrafo só se houver resguardo de repactuação (cláusula 2.3)",
}

PLACEHOLDERS: dict[str, str] = DO_SGI | {n: d for n, (_r, d, _m) in DIGITADOS.items()} | CONDICIONAIS

_TOKEN = despacho_mascara._TOKEN  # noqa: SLF001 - mesma sintaxe do despacho


def usados(html: str) -> set[str]:
    """Placeholders (minúsculos) presentes no HTML."""
    return {m.group(1).lower() for m in _TOKEN.finditer(html or "") if m.group(1)}


def invalidos(html: str) -> list[str]:
    """Trechos `#...` que não são placeholders permitidos (inclui `#` solto)."""
    ruins = [m.group(0) or "#" for m in _TOKEN.finditer(html or "") if m.group(1).lower() not in PLACEHOLDERS]
    return list(dict.fromkeys(ruins))


def preencher(html: str, valores: dict[str, str], condicoes: dict[str, bool]) -> tuple[str, list[str]]:
    """(HTML preenchido, lacunas). Parágrafo com condicional desligado é omitido; placeholder sem valor vira `[rótulo]` e entra nas lacunas."""
    raiz = lxml_html.fragment_fromstring(html or "", create_parent="div")
    for el in list(raiz):
        if any(n in CONDICIONAIS and not condicoes.get(n) for n in usados(lxml_html.tostring(el, encoding="unicode"))):
            raiz.remove(el)
    corpo = "".join(lxml_html.tostring(el, encoding="unicode") for el in raiz)
    lacunas: list[str] = []

    def trocar(m) -> str:
        nome = m.group(1).lower()
        if nome in CONDICIONAIS:
            return ""
        if nome not in PLACEHOLDERS:
            return m.group(0)
        valor = (valores.get(nome) or "").strip()
        if valor:
            return escape(valor).replace("\n", "<br/>")
        rotulo = DIGITADOS[nome][0] if nome in DIGITADOS else DO_SGI[nome].split(" (")[0].rstrip(".")
        if rotulo not in lacunas:
            lacunas.append(rotulo)
        return f"[{escape(rotulo)}]"

    return _TOKEN.sub(trocar, corpo), lacunas
