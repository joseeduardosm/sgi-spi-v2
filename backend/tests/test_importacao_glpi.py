# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a conversão dos ativos do GLPI em bens do Patrimônio (chapa, número de série e descrição).
from app.services.patrimonio.importacao_glpi import montar_bem


def _ativo(**campos):
    return {"tipo": "computers", "id": 1, "serie": "SN1", "patrimonio": "00061", "tipo_nome": "Notebook", "fabricante": "Lenovo", "modelo": "ThinkPad T14", **campos}


def test_sem_patrimonio_fica_sem_chapa_e_so_com_serie():
    usadas: set[str] = set()
    bem = montar_bem(_ativo(patrimonio="N/C"), usadas)
    assert bem["chapa"] is None and bem["numero_serie"] == "SN1" and not usadas
    assert montar_bem(_ativo(patrimonio="00061"), usadas)["chapa"] == "00061"


def test_chapa_repetida_so_vale_para_o_primeiro_e_nada_vai_para_observacoes():
    usadas: set[str] = set()
    montar_bem(_ativo(), usadas)
    segundo = montar_bem(_ativo(id=2), usadas)
    assert segundo["chapa"] is None and "observacoes" not in segundo


def test_descricao_tem_tipo_marca_e_modelo():
    assert montar_bem(_ativo(), set())["descricao"] == "Notebook Lenovo ThinkPad T14"
    # Modelo que já começa pela marca não repete a marca
    assert montar_bem(_ativo(modelo="Lenovo T14"), set())["descricao"] == "Notebook Lenovo T14"
    # Tipo do GLPI que na verdade é fabricante (monitor "Infoway") é ignorado: vale o rótulo do ativo
    assert montar_bem(_ativo(tipo="monitors", tipo_nome="Infoway", fabricante="Dell", modelo=None), set())["descricao"] == "Monitor Dell"
    assert montar_bem(_ativo(tipo="networkequipments", tipo_nome="Switch", fabricante=None, modelo=None), set())["descricao"] == "Switch"


def test_inservivel_entra_como_ativo_com_conservacao_1():
    bem = montar_bem(_ativo(local="INSERVÍVEL - SPI"), set())
    assert bem["situacao"] == "ativo" and bem["conservacao"] == 1
    assert montar_bem(_ativo(estado="DESCARTE"), set())["conservacao"] == 1
    assert montar_bem(_ativo(local="05º Andar", estado="PRODUÇÃO"), set())["conservacao"] == 4
