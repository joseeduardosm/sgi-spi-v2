"""
===============================================================================
ARQUIVO: prorrogacao_documentos.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Montar o texto das minutas e despachos da prorrogação: escolhe o modelo
ativo de cada variante, calcula o valor de cada placeholder e preenche.

RESUMO TÉCNICO:
`valores_e_condicoes` reúne os dados do contrato, da empresa, da nova
vigência (pela memória de cálculo do rascunho), dos parâmetros e o que a
equipe digitou (`dados_minuta`), além do estado dos parágrafos condicionais.
`listar`, `gerar`, `campos` e `panorama` devolvem os schemas usados pela
tela (passo "Minutas"). O preenchimento em si fica em `prorrogacao_mascara`.
Regra de precedência: o digitado vale mais que o calculado, para qualquer
placeholder (um valor calculado errado é corrigido na tela, sem mexer no
cadastro).

FINALIDADE DE NEGÓCIO:
Entrega à equipe os documentos da prorrogação prontos para copiar para o
SEI, mostrando o que ainda falta preencher (lacunas). A Declaração de
Atendimento certa (licitação ou contratação direta) sai da modalidade
cadastrada no contrato.

CONTEXTO NO SISTEMA:
Usa `ModeloGlobal` (modelos editados em Contratos > Modelos, tipo
"prorrogacao"), `ProcessoProrrogacao`, `memoria_prorrogacao`, `extenso`,
`servico_parametros` e `servico_contratos`. Chamado pelas rotas de
alterações/prorrogação do contrato.

===============================================================================
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contratos import Contrato, ModeloGlobal, ProcessoProrrogacao
from app.schemas.contratos.alteracoes import CampoMinuta, LeituraMinuta, LeituraMinutaResumo, LeituraMinutas
from app.services.contratos import calculos, extenso, prorrogacao_mascara as mascara, servico_parametros
from app.services.contratos.erros import RegistroNaoEncontrado
from app.services.contratos.servico_contratos import designacoes_vigentes, vigencias

# Modalidade cadastrada no contrato → texto usado no placeholder #modalidade
MODALIDADES = {"licitacao": "licitação", "dispensa": "dispensa de licitação", "inexigibilidade": "inexigibilidade de licitação"}


def _data(dia: date | None) -> str:
    """Data em dd/mm/aaaa; sem data, texto vazio (vira lacuna no documento)."""
    return f"{dia:%d/%m/%Y}" if dia else ""


def _cpf(digitos: str | None) -> str:
    """CPF com máscara 000.000.000-00; se não tiver 11 dígitos, devolve como veio."""
    d = digitos or ""
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}" if len(d) == 11 else d


def _cnpj(digitos: str) -> str:
    """CNPJ com máscara 00.000.000/0000-00; se não tiver 14 dígitos, devolve como veio."""
    return f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:]}" if len(digitos) == 14 else digitos


def _decimal(texto: str) -> Decimal | None:
    """Valor digitado no formato brasileiro (1.234,56) ou simples (1234.56)."""
    limpo = (texto or "").replace("R$", "").strip()
    if not limpo:
        return None
    # Com vírgula, é formato brasileiro: tira os pontos de milhar e troca a vírgula por ponto
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    try:
        return Decimal(limpo)
    except InvalidOperation:
        return None


def _valor_do_periodo(contrato: Contrato, sequencia: int, inicio: date, fim: date) -> Decimal | None:
    """Valor dos itens no período, com os preços vigentes; vazio se o cálculo não for possível (ex.: itens sob demanda sem previsão)."""
    # Import dentro da função para evitar importação circular entre os módulos de serviço
    from app.services.contratos import valores

    try:
        return valores.valor_global_vigencia(contrato, calculos.Vigencia(sequencia, inicio, fim))
    except Exception:  # noqa: BLE001 - minuta nunca derruba a tela: o valor vira lacuna e a equipe digita
        return None


def _por_exercicio_rascunho(contrato: Contrato, processo: ProcessoProrrogacao, inicio: date, fim: date) -> str:
    """O mesmo texto, para a prorrogação ainda em rascunho: a nova vigência não existe no contrato, então a conta vem da memória de cálculo.

    Gera, para cada ano coberto pela nova vigência, "R$ X (extenso) para o
    exercício de AAAA", separados por vírgula (placeholder #valoresporexercicio).
    """
    from app.services.contratos import memoria_prorrogacao

    partes = []
    for ano in range(inicio.year, fim.year + 1):
        valor = memoria_prorrogacao.valor_do_periodo(contrato, processo.meses, processo.plano_sob_demanda, processo.calculo_mes_quebrado, ano)
        partes.append(f"{extenso.real(valor)} ({extenso.reais(valor)}) para o exercício de {ano}")
    return ", ".join(partes)


def valores_e_condicoes(sessao: Session, contrato: Contrato, processo: ProcessoProrrogacao | None, ignorar_digitados: bool = False) -> tuple[dict[str, str], dict[str, bool]]:
    """Valor de cada placeholder (SGI + digitados) e o estado dos condicionais. `ignorar_digitados` devolve só o que o SGI calcula.

    Devolve `(valores, condicoes)`: `valores` é {placeholder: texto} e `condicoes`
    é {condicional: liga/desliga}. Não grava nada no banco.
    """
    from app.services.contratos.servico_prorrogacao import nova_vigencia

    meses = processo.meses if processo else None
    digitados = {} if ignorar_digitados else {k.lower(): (v or "").strip() for k, v in ((processo.dados_minuta if processo else None) or {}).items()}
    empresa = contrato.empresa
    # Representante legal: o primeiro preposto ativo marcado como tal (preposto = representante da empresa no contrato)
    representante = next((p for p in empresa.prepostos if p.ativo and p.representante_legal), None)
    # Vigência original (a primeira que não é retroativa), base dos placeholders de vigência inicial
    original = next(v for v in vigencias(contrato) if not v.retroativa)
    inicial_fim = calculos.calcular_data_fim(original.inicio, contrato.vigencia_inicial_meses)
    inicio, fim = nova_vigencia(contrato, meses)
    direta = contrato.modalidade_contratacao in ("dispensa", "inexigibilidade")
    gestor = next((d.nome_usuario for d in designacoes_vigentes(contrato) if d.papel == "gestor"), "")
    # Rascunho: a nova vigência ainda não existe no contrato, então o valor vem da memória de cálculo da prorrogação
    from app.services.contratos import memoria_prorrogacao

    total = memoria_prorrogacao.valor_do_periodo(contrato, meses, processo.plano_sob_demanda, processo.calculo_mes_quebrado) if fim and processo else None
    # O valor corrigido na tela tem prioridade sobre o calculado, inclusive para o texto por extenso
    corrigido = _decimal(digitados.get("valorprorrogacao", ""))
    if corrigido is not None:
        total = corrigido
    # Prazo de divulgação no PNCP (Portal Nacional de Contratações Públicas): parâmetro diferente para licitação e contratação direta
    pncp = servico_parametros.valor("pncp_dias_uteis_direta" if direta else "pncp_dias_uteis_licitacao") if contrato.modalidade_contratacao else None
    v: dict[str, str] = {
        "nrocontrato": contrato.numero, "anocontrato": str(contrato.ano or ""), "objetodocontrato": (contrato.objeto or "").strip().rstrip("."),
        "razaosocialempresa": empresa.razao_social, "cnpjempresa": _cnpj(empresa.cnpj), "enderecoempresa": empresa.endereco or "",
        "representantenome": representante.nome if representante else "", "representantefuncao": (representante.cargo or "") if representante else "",
        "representantecpf": _cpf(representante.cpf) if representante else "",
        "processogestao": contrato.sei_gestao_numero or "",
        "vigenciainicialmeses": extenso.meses(contrato.vigencia_inicial_meses), "vigenciainicialinicio": _data(original.inicio),
        "vigenciainicialfim": _data(inicial_fim), "vigenciaatualfim": _data(contrato.data_fim),
        "nrotermo": f"{len(contrato.prorrogacoes) + 1}º",
        "mesesprorrogacao": extenso.meses(meses) if meses else "", "inicioprorrogacao": _data(inicio), "fimprorrogacao": _data(fim),
        "valorprorrogacao": extenso.real(total) if total is not None else "", "valorprorrogacaoextenso": extenso.reais(total) if total is not None else "",
        "valoresporexercicio": _por_exercicio_rascunho(contrato, processo, inicio, fim) if fim and processo and corrigido is None else "",
        "modalidade": MODALIDADES.get(contrato.modalidade_contratacao, ""),
        "prazopncp": f"{pncp} ({extenso.inteiro(pncp)})" if pncp else "",
        "mesanoatual": extenso.mes_ano(date.today()), "gestor": gestor,
        "ssgcnome": servico_parametros.valor("ssgc_nome"), "ssgccpf": servico_parametros.valor("ssgc_cpf"),
        "secretarionome": servico_parametros.valor("secretario_nome"), "secretariocpf": servico_parametros.valor("secretario_cpf"),
        "autoridadenome": servico_parametros.valor("autoridade_competente_nome"), "autoridadecargo": servico_parametros.valor("autoridade_competente_cargo"),
        "parecerreferencial": "NLC nº 1/2026",
    }
    # Padrões dos digitados que o SGI sabe sugerir
    v["numeroprocesso"] = contrato.sei_gestao_numero or ""
    v["baserepresentacao"] = "conforme atos constitutivos do fornecedor ou procuração apresentada nos autos"
    # O que foi digitado vale mais do que tudo o que foi calculado
    # (o valor da prorrogação corrigido já entrou formatado, junto com o extenso)
    v.update({k: x for k, x in digitados.items() if x and k in mascara.PLACEHOLDERS and k != "valorprorrogacao"})
    # Condicionais: ligam os parágrafos opcionais do termo aditivo conforme o caso
    condicoes = {
        "secustosnaorenovaveis": bool(digitados.get("efeitoscustos")),
        "sedemandavariavel": any(i.tipo == "sob_demanda" for i in contrato.itens),
        "serepactuacao": bool(digitados.get("periodosrepactuacao")),
    }
    return v, condicoes


def _modelo_ativo(sessao: Session, variante: str) -> ModeloGlobal | None:
    """Modelo ativo da variante (o mais recentemente alterado, se por engano houver mais de um)."""
    modelos = sessao.scalars(select(ModeloGlobal).where(ModeloGlobal.tipo == "prorrogacao", ModeloGlobal.ativo.is_(True)).order_by(ModeloGlobal.atualizado_em.desc()))
    return next((m for m in modelos if m.conteudo.get("variante") == variante), None)


def variantes_do_contrato(contrato: Contrato) -> list[str]:
    """Documentos que valem para o contrato: a Declaração de Atendimento depende da modalidade (sem modalidade cadastrada, as duas)."""
    modalidade = contrato.modalidade_contratacao
    # Licitação descarta a declaração de contratação direta e vice-versa; sem modalidade, nenhuma é descartada
    descartada = None if not modalidade else ("declaracao_atendimento_licitacao" if modalidade in ("dispensa", "inexigibilidade") else "declaracao_atendimento_direta")
    return [v for v in mascara.VARIANTES if v != descartada]


def listar(sessao: Session, contrato: Contrato, processo: ProcessoProrrogacao | None) -> list[LeituraMinutaResumo]:
    """Documentos gerados para o contrato, com o que falta digitar em cada um.

    Variante sem modelo ativo aparece com `modelo_ativo=False` e sem lacunas.
    """
    valores, condicoes = valores_e_condicoes(sessao, contrato, processo)
    resumo = []
    for variante in variantes_do_contrato(contrato):
        modelo = _modelo_ativo(sessao, variante)
        lacunas = mascara.preencher(modelo.conteudo.get("html", ""), valores, condicoes)[1] if modelo else []
        resumo.append(LeituraMinutaResumo(variante=variante, titulo=mascara.VARIANTES[variante], modelo_ativo=modelo is not None, lacunas=lacunas))
    return resumo


def gerar(sessao: Session, contrato: Contrato, processo: ProcessoProrrogacao | None, variante: str) -> LeituraMinuta:
    """Texto preenchido de uma variante, pronto para copiar para o SEI.

    Lança `RegistroNaoEncontrado` (404) se a variante não existir ou não houver modelo ativo.
    """
    if variante not in mascara.VARIANTES:
        raise RegistroNaoEncontrado("Minuta")
    modelo = _modelo_ativo(sessao, variante)
    if modelo is None:
        raise RegistroNaoEncontrado("Modelo ativo desta minuta")
    valores, condicoes = valores_e_condicoes(sessao, contrato, processo)
    html, lacunas = mascara.preencher(modelo.conteudo.get("html", ""), valores, condicoes)
    return LeituraMinuta(variante=variante, titulo=mascara.VARIANTES[variante], html=html, lacunas=lacunas)


def campos(sessao: Session, contrato: Contrato, processo: ProcessoProrrogacao | None) -> list[CampoMinuta]:
    """Dados das minutas: primeiro os que a equipe digita, depois os que o SGI calcula (corrigíveis).

    Cada campo traz o `valor` digitado (se houver) e o `calculado` pelo SGI, para
    a tela mostrar a sugestão ao lado do que foi corrigido.
    """
    calculados, _ = valores_e_condicoes(sessao, contrato, processo, ignorar_digitados=True)
    digitados = (processo.dados_minuta if processo else None) or {}
    lista = [CampoMinuta(nome=n, rotulo=r[0], descricao=r[1], digitado=True, multilinha=r[2], valor=digitados.get(n, ""), calculado=calculados.get(n, ""))
             for n, r in mascara.DIGITADOS.items()]
    lista += [CampoMinuta(nome=n, rotulo=d.split(" (")[0].rstrip("."), descricao=d, digitado=False, valor=digitados.get(n, ""), calculado=calculados.get(n, ""))
              for n, d in mascara.DO_SGI.items()]
    return lista


def panorama(sessao: Session, contrato: Contrato, processo: ProcessoProrrogacao | None) -> LeituraMinutas:
    """Tudo o que o passo "Minutas" da tela precisa: os documentos, o que falta e os campos."""
    return LeituraMinutas(documentos=listar(sessao, contrato, processo), campos=campos(sessao, contrato, processo))
