# Criado por José Eduardo Santana Martins
# Este arquivo serve para as regras de conversão das planilhas "Visão Geral" do SAM em bens do Patrimônio (funções puras, sem banco).
"""Conversão das linhas da "Visão Geral" do SAM (ativos e baixados) nos campos do bem.

- Chapa: prefixo da sigla (SPI) + número com 6 dígitos (2835 → SPI002835), como `servico_bens.montar_chapa`.
- Valores no formato brasileiro ("1.870,00"), datas "dd/mm/aaaa" (com espaços nas pontas) e vida útil "8/120" (meses depreciados / vida útil).
- Conservação do SAM → escala 1 a 5 do sistema; o texto original do SAM fica em `estado_sam`.
- Bens da planilha de baixados entram com situação "baixado"; os demais, "ativo". Todos na sala "NECESSÁRIO ATUALIZAR".
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

# Estado de conservação do SAM -> escala do sistema (1 Péssimo, 2 Ruim, 3 Regular, 4 Bom, 5 Ótimo); "Antieconômico" = conserto não compensa
CONSERVACAO_SAM = {"novo": 5, "ótimo": 5, "otimo": 5, "bom": 4, "regular": 3, "ruim": 2, "antieconômico": 2, "antieconomico": 2, "péssimo": 1, "pessimo": 1}
CONSERVACAO_PADRAO = 4
CONSERVACAO_BAIXADO = 1
# Dados que o SAM traz com dois espaços no lugar do hífen ("INTEGRACAO SAMESTOQUE  SAMPATRIMONIO"): só normaliza espaços repetidos
ORIGEM_IMPORTACAO = "importação SAM"


def texto(valor: Any, limite: int | None = None) -> str | None:
    """Texto sem espaços repetidos nem nas pontas; vazio vira `None`."""
    if valor is None:
        return None
    t = re.sub(r"\s+", " ", str(valor)).strip()
    if not t:
        return None
    return t[:limite] if limite else t


def valor_br(valor: Any) -> Decimal | None:
    """"1.870,00" → Decimal('1870.00'); números do Excel passam direto; vazio vira `None`."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor)).quantize(Decimal("0.01"))
    try:
        return Decimal(str(valor).strip().replace(".", "").replace(",", ".")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def data_br(valor: Any) -> date | None:
    """"18/12/2025" (com ou sem espaços) → date; datas do Excel passam direto; inválida vira `None`."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    t = texto(valor)
    if not t:
        return None
    try:
        return datetime.strptime(t, "%d/%m/%Y").date()
    except ValueError:
        return None


def vida_util(valor: Any) -> tuple[int | None, int | None]:
    """"8/120" → (8 meses depreciados, 120 de vida útil); um número só vale como vida útil."""
    t = texto(valor)
    if not t:
        return None, None
    partes = t.split("/")
    try:
        if len(partes) == 2:
            return int(partes[0]), int(partes[1])
        return None, int(partes[0])
    except ValueError:
        return None, None


def chapa_sam(sigla: Any, numero: Any) -> str | None:
    """Sigla + número com 6 dígitos (zeros à esquerda). Número que não é só dígitos fica como veio."""
    n = texto(numero)
    if not n:
        return None
    if n.endswith(".0"):  # número lido como decimal pelo Excel
        n = n[:-2]
    prefixo = (texto(sigla) or "").upper()
    return (prefixo + (n.zfill(6) if n.isdigit() else n))[:60]


def conservacao(estado: Any, baixado: bool) -> int:
    """Baixados (inservíveis) entram com 1; os demais seguem a tabela do SAM."""
    if baixado:
        return CONSERVACAO_BAIXADO
    return CONSERVACAO_SAM.get((texto(estado) or "").lower(), CONSERVACAO_PADRAO)


def referencia_depreciacao(valor: Any) -> str | None:
    """Mês de referência AAAAMM da última depreciação."""
    t = texto(valor)
    return t[:6] if t and t.isdigit() else None


def montar_bem(linha: dict[str, Any], baixado: bool) -> dict[str, Any]:
    """Converte uma linha da planilha (chaves = cabeçalhos) nos campos do bem. A localização e o evento ficam a cargo do script."""
    chapa = chapa_sam(linha.get("Sigla"), linha.get("Chapa"))
    meses_dep, vida = vida_util(linha.get("Vida Útil(Meses)"))
    return {
        "id_cliente": f"sam:{chapa}",
        "chapa": chapa,
        "chapa_chave": chapa.lower() if chapa else None,
        "descricao": (texto(linha.get("Descrição do Item")) or "Bem importado do SAM")[:300],
        "numero_serie": texto(linha.get("Numero de Serie"), 80),
        "conservacao": conservacao(linha.get("Estado de Conservacao"), baixado),
        "situacao": "baixado" if baixado else "ativo",
        "origem": "proprio",
        "uge": texto(linha.get("UGE"), 40),
        "ua": texto(linha.get("UA"), 40),
        "divisao": texto(linha.get("Descrição da Divisão"), 80),
        "valor_aquisicao": valor_br(linha.get("Valor de Aquisição")),
        "valor_atual": valor_br(linha.get("Valor Atual")),
        "data_aquisicao": data_br(linha.get("Data de Aquisição")),
        # --- Dados do SAM ---
        "item_codigo": texto(linha.get("Item"), 20),
        "uo": texto(linha.get("UO"), 20),
        "tipo_sam": texto(linha.get("Tipo"), 40),
        "conta_contabil": texto(linha.get("Conta Contábil"), 20),
        "conta_depreciacao": texto(linha.get("ContaDepreciacao"), 20),
        "depreciacao_acumulada": valor_br(linha.get("Depreciação Acumulada")),
        "depreciacao_mensal": valor_br(linha.get("Depreciação Mensal")),
        "vida_util_meses": vida,
        "meses_depreciados": meses_dep,
        "ultima_depreciacao_ref": referencia_depreciacao(linha.get("Última Depreciação (Mes/Ref)")),
        "data_incorporacao": data_br(linha.get("Data de Incorporação")),
        "empenho": texto(linha.get("Empenho"), 40),
        "numero_documento": texto(linha.get("Número de Documento"), 40),
        "ultimo_historico": texto(linha.get("Último Histórico"), 120),
        "data_ultimo_historico": data_br(linha.get("Data do Último Histórico")),
        "estado_sam": texto(linha.get("Estado de Conservacao"), 30),
        "destino_uge": texto(linha.get("Destino UGE"), 20),
        "responsavel_sam": texto(linha.get("Responsável"), 120),
    }
