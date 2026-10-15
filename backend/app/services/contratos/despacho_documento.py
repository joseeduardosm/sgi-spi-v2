# Criado por José Eduardo Santana Martins
# Este arquivo serve para preencher o texto do despacho de pagamento (a partir da máscara) mostrado na tela da competência.
"""Despacho de pagamento: texto da máscara ativa, preenchido com os dados da competência (não vai no consolidado: aparece na tela com botão Copiar)."""



from app.services.contratos import despacho_mascara

MESES = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro")


def _data(d) -> str:
    return f"{d:%d/%m/%Y}" if d else ""


def valores(contrato, competencia, vencimento, equipe: dict[str, object]) -> dict[str, str]:
    """Valor de cada placeholder do despacho. `equipe` traz o usuário de cada papel designado (papel → `Usuario`)."""
    v = {
        "nrocontrato": contrato.numero, "razaosocialempresa": contrato.empresa.razao_social, "cnpjempresa": contrato.empresa.cnpj or "",
        "objetodocontrato": (contrato.objeto or "").strip().rstrip("."), "processogestao": contrato.sei_gestao_numero or "",
        "iniciocompetencia": _data(competencia.periodo_inicio), "fimcompetencia": _data(competencia.periodo_fim),
        "mescompetencia": f"{MESES[competencia.competencia.month - 1]}/{competencia.competencia.year}",
        "vencimentodanotafiscal": _data(vencimento),
    }
    for sufixo, (papel, rotulo) in despacho_mascara.FUNCOES.items():
        pessoa = equipe.get(papel)
        v[f"nome{sufixo}"] = (pessoa.nome_completo or pessoa.login) if pessoa else ""
        v[f"cargo{sufixo}"] = (pessoa.cargo or "") if pessoa else ""
        v[f"funcao{sufixo}"] = rotulo if pessoa else ""
        v[f"setor{sufixo}"] = (pessoa.departamento or "") if pessoa else ""
    autoridade = contrato.autoridade_despacho
    v["nomeautoridade"] = (autoridade.nome_completo or autoridade.login) if autoridade else ""
    v["cargoautoridade"] = (autoridade.cargo or "") if autoridade else ""
    v["setorautoridade"] = (autoridade.departamento or "") if autoridade else ""
    return v


def texto_html(mascara: str, dados: dict[str, str]) -> str:
    return despacho_mascara.preencher(mascara, dados)
