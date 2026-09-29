# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a folha de ponto em PDF (Módulo RH).
"""Folha de ponto: competências, conteúdo do PDF (identificação, fins de semana, feriados e férias aprovadas) e permissões."""

from io import BytesIO

from pypdf import PdfReader

from app.core.banco import FabricaSessao
from app.models.rh import Afastamento, Feriado
from tests.apoio_rh import funcionais
from tests.test_rh_afastamentos import _ambiente, equipe  # noqa: F401  (fixtures reaproveitadas; hoje = 01/10/2026)

URL = "/api/rh/folha-ponto"


def _texto(conteudo: bytes) -> list[str]:
    return [pagina.extract_text() for pagina in PdfReader(BytesIO(conteudo)).pages]


def test_competencias_disponiveis(cliente, equipe):  # noqa: F811
    _, h, _ = equipe
    lista = cliente.get(f"{URL}/competencias", headers=h["ana"]).json()
    assert len(lista) == 15
    assert lista[0] == {"valor": "2026-12", "rotulo": "Dezembro/2026", "atual": False}
    assert [c["valor"] for c in lista if c["atual"]] == ["2026-10"] and lista[-1]["valor"] == "2025-10"
    assert cliente.get(URL, params={"competencia": "2025-09"}, headers=h["ana"]).status_code == 400
    assert cliente.get(URL, params={"competencia": "2027-01"}, headers=h["ana"]).status_code == 400
    assert cliente.get(URL, params={"competencia": "2026-13"}, headers=h["ana"]).status_code == 422


def test_folha_com_identificacao_feriados_e_ferias_aprovadas(cliente, equipe):  # noqa: F811
    ids, h, _ = equipe
    from datetime import date, time

    funcionais(ids["ana"], autorizador_id=ids["chefe"], inicio_aquisitivo_dia=1, inicio_aquisitivo_mes=1, exercicio=2026,
               jornada_semanal_horas=40, regime_plantao=False, horario_trabalho_inicio=time(9), horario_trabalho_fim=time(18),
               horario_estudante=False, intervalo_inicio=time(12), intervalo_fim=time(13), rg_cin="12.345.678-9", rs_pv="1.234.567/8")
    with FabricaSessao() as sessao:
        sessao.add_all([
            Feriado(data=date(2026, 10, 12), descricao="Nossa Senhora Aparecida", tipo="feriado", abrangencia="nacional"),
            Feriado(data=date(2026, 10, 28), descricao="Dia do Servidor Público", tipo="ponto_facultativo", abrangencia="estadual"),
            # Férias aprovadas (19 a 23/10) aparecem; a pendente (26 e 27/10) não
            Afastamento(usuario_id=ids["ana"], tipo="ferias", inicio=date(2026, 10, 19), fim=date(2026, 10, 23), dias=5, exercicio=2026,
                        status="aprovado"),
            Afastamento(usuario_id=ids["ana"], tipo="licenca_premio", inicio=date(2026, 10, 26), fim=date(2026, 10, 27), dias=2,
                        exercicio=2026, status="pendente"),
        ])
        sessao.commit()
    r = cliente.get(URL, params={"competencia": "2026-10"}, headers=h["ana"])
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"] == 'attachment; filename="folha-ponto-2026-10-ana.pdf"'
    paginas = _texto(r.content)
    assert len(paginas) == 2
    primeira = paginas[0]
    for trecho in ("GOVERNO DO ESTADO DE SÃO PAULO", "Diretoria A", "REGISTRO DE PONTO – OUTUBRO/2026", "ANA SOUZA", "12.345.678-9",
                   "1.234.567/8", "40 horas/semanais", "das 9:00 às 18:00", "das 12:00 às 13:00", "Nossa Senhora Aparecida",
                   "PONTO FACULTATIVO", "Dia do Servidor Público", "19/10/2026 a 23/10/2026"):
        assert trecho in primeira, trecho
    assert primeira.count("SÁBADO") == 2 * 5 and primeira.count("DOMINGO") == 2 * 4  # outubro/2026: 5 sábados, 4 domingos
    assert primeira.count("FÉRIAS") == 2 * 5 and "LICENÇA-PRÊMIO" not in primeira
    assert "INFORMAÇÕES FINANCEIRAS" in paginas[1] and "CONSOLIDAÇÃO" in paginas[1]
    # Sem dados funcionais: sai com os campos em branco
    r = cliente.get(URL, params={"competencia": "2026-10"}, headers=h["rh"])
    assert r.status_code == 200 and "RITA RH" in _texto(r.content)[0]
