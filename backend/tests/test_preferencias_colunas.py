# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar as colunas que cada usuário escolhe mostrar nas listagens.
"""Preferências de colunas: por usuário e por tela, na ordem escolhida, com restauração do padrão."""

from tests.conftest import cabecalho, criar_usuario

URL = "/api/preferencias/colunas/patrimonio.bens"


def test_colunas_por_usuario_e_por_tela_com_restauracao(cliente, admin):
    criar_usuario("outra")
    h = cabecalho(cliente, "outra")
    # Nunca escolheu: nulo (vale o padrão da tela)
    assert cliente.get(URL, headers=h).json() == {"tela": "patrimonio.bens", "colunas": None, "padrao_global": None}
    r = cliente.put(URL, json={"colunas": ["chapa", "numero_serie", "descricao", "chapa"]}, headers=h)
    assert r.status_code == 200 and r.json()["colunas"] == ["chapa", "numero_serie", "descricao"]
    # Troca a lista inteira; cada usuário e cada tela têm a sua
    assert cliente.put(URL, json={"colunas": ["descricao", "chapa"]}, headers=h).json()["colunas"] == ["descricao", "chapa"]
    assert cliente.get(URL, headers=admin).json()["colunas"] is None
    assert cliente.get("/api/preferencias/colunas/outra.tela", headers=h).json()["colunas"] is None
    # Ids inválidos e lista vazia são recusados
    assert cliente.put(URL, json={"colunas": ["Chapa Maiúscula"]}, headers=h).status_code == 422
    assert cliente.put(URL, json={"colunas": []}, headers=h).status_code == 422
    # Restaurar o padrão (idempotente) e exigir login
    assert cliente.delete(URL, headers=h).status_code == 204 and cliente.delete(URL, headers=h).status_code == 204
    assert cliente.get(URL, headers=h).json()["colunas"] is None
    assert cliente.get(URL).status_code == 401


def test_visao_global_so_o_superroot_grava_e_vale_para_quem_nao_tem_pessoal(cliente, admin):
    criar_usuario("outra")
    h = cabecalho(cliente, "outra")
    # Usuário comum não grava nem apaga a visão global
    assert cliente.put(URL, params={"visao": "global"}, json={"colunas": ["chapa"]}, headers=h).status_code == 403
    assert cliente.delete(URL, params={"visao": "global"}, headers=h).status_code == 403
    # O SuperRoot define a global; ela aparece para todos em `padrao_global`, sem mexer na visão pessoal de ninguém
    r = cliente.put(URL, params={"visao": "global"}, json={"colunas": ["chapa", "numero_serie"]}, headers=admin)
    assert r.status_code == 200 and r.json()["padrao_global"] == ["chapa", "numero_serie"] and r.json()["colunas"] is None
    assert cliente.get(URL, headers=h).json() == {"tela": "patrimonio.bens", "colunas": None, "padrao_global": ["chapa", "numero_serie"]}
    # Trocar a global não cria uma segunda; apagar volta ao padrão da tela
    assert cliente.put(URL, params={"visao": "global"}, json={"colunas": ["descricao"]}, headers=admin).json()["padrao_global"] == ["descricao"]
    assert cliente.delete(URL, params={"visao": "global"}, headers=admin).status_code == 204
    assert cliente.get(URL, headers=h).json()["padrao_global"] is None
