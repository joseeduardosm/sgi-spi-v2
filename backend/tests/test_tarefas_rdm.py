"""
===============================================================================
ARQUIVO: test_tarefas_rdm.py
AUTOR: José Eduardo Santana Martins

FINALIDADE:
Testar a RDM (Requisição de Mudança) digital das tarefas: preenchimento,
envio com número do Protocolo, aprovação com PDF e e-mail, reprovação com
motivo e reenvio com o mesmo número.

RESUMO TÉCNICO:
A fixture `cenario` cria usuários, uma equipe e uma tarefa em andamento e
troca `servico_smtp.enviar_email` por uma função que guarda as mensagens.
Os testes chamam `/api/tarefas/{numero}/rdm` (ler, salvar rascunho, enviar,
aprovar, reprovar, PDF) e conferem a numeração `RDM SGI 00001/AAAA` em
`NumeroProtocolo`, o texto do PDF (lido com pypdf), destinatários e anexo
do e-mail e o histórico da tarefa.

FINALIDADE DE NEGÓCIO:
Garante o controle de mudanças da infraestrutura: só a liderança aprova, a
aprovação gera o formulário oficial assinado com cargo e setor, todos os
envolvidos recebem o PDF, a reprovação exige motivo e o número reservado no
Protocolo não pode ser liberado à mão.

CONTEXTO NO SISTEMA:
Liga o módulo Tarefas (`app/models/tarefas.py`, serviço de RDM) ao módulo
Protocolo (`app/models/protocolo.py`, rotas `/api/protocolo/...`) e ao
envio de e-mail (`app/services/servico_smtp.py`). Usa `criar_usuario` e
`cabecalho` de `tests/conftest.py`.

===============================================================================
"""

from datetime import date, datetime, timedelta, timezone
from io import BytesIO

import pytest
from pypdf import PdfReader
from sqlalchemy import select

from app.core.banco import FabricaSessao, hoje_sao_paulo
from app.models.protocolo import NumeroProtocolo
from app.models.tarefas import EventoTarefa, Tarefa
from app.services import servico_smtp
from tests.conftest import cabecalho, criar_usuario

URL = "/api/tarefas"


@pytest.fixture
def cenario(cliente, admin, monkeypatch):
    """Lia lidera a equipe Infra; Ana executa a tarefa; Beto segue; Caio é de fora. E-mails capturados.

    Devolve um dicionário com os ids, os cabeçalhos de autenticação, o número da
    tarefa (já em andamento) e a lista `enviados`, onde cada e-mail "enviado" é guardado.
    """
    extra = {"lia": {"cargo": "Diretor", "departamento": "CGI"}}
    ids = {login: criar_usuario(login, nome_completo=nome, email=f"{login}@sp.gov.br", **extra.get(login, {}))
           for login, nome in (("lia", "Lia Líder"), ("ana", "Ana Executora"), ("beto", "Beto Seguidor"), ("caio", "Caio Externo"))}
    h = {k: cabecalho(cliente, k) for k in ids}
    equipe = cliente.post(f"{URL}/equipes", json={"nome": "Infra", "lideres_ids": [ids["lia"]], "membros_ids": [ids["ana"], ids["beto"]]}, headers=h["lia"])
    assert equipe.status_code == 201, equipe.text
    prazo = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    t = cliente.post(URL, json={"titulo": "Trocar placa de rede da VM 105", "prazo": prazo, "equipe_id": equipe.json()["id"], "responsaveis_ids": [ids["ana"]]}, headers=h["lia"]).json()
    assert cliente.post(f"{URL}/{t['numero']}/mover", json={"acao": "iniciar"}, headers=h["ana"]).status_code == 200
    # Seguidor é gravado direto no banco: quem segue a tarefa também deve receber o PDF da RDM
    with FabricaSessao() as s:
        from app.models.tarefas import SeguidorTarefa
        s.add(SeguidorTarefa(tarefa_id=s.scalar(select(Tarefa.id).where(Tarefa.numero == t["numero"])), usuario_id=ids["beto"]))
        s.commit()
    enviados: list = []

    class Resultado:
        sucesso, mensagem = True, ""

    # Troca o envio real por uma função que só guarda a mensagem e devolve "sucesso".
    # O `append(...) or Resultado()` funciona porque `append` devolve None.
    monkeypatch.setattr(servico_smtp, "enviar_email", lambda sessao, mensagem: enviados.append(mensagem) or Resultado())
    return {"ids": ids, "h": h, "numero": t["numero"], "enviados": enviados}


def _formulario(**mudancas) -> dict:
    """Formulário de RDM completo e válido; os argumentos nomeados substituem seções inteiras."""
    hoje = hoje_sao_paulo()
    corpo = {
        "titulo": "Instalar drivers VirtIO na VM 105",
        "identificacao": {"tipo": "PROGRAMADA", "solicitante": "Ana Executora", "area": "CAS1", "data_solicitacao": hoje.isoformat()},
        "objetivo": "Instalar drivers da placa de rede e guest-agent.", "justificativa": "Placa fora do padrão VirtIO.",
        "categorizacao": {"acao": "INSTALAÇÃO", "finalidade": "CORREÇÃO", "prioridade": "MÉDIA", "risco": "BAIXO", "impacto": "MÉDIO"},
        "janela": {"inicio_data": (hoje + timedelta(days=2)).isoformat(), "inicio_hora": "07:00", "fim_data": (hoje + timedelta(days=2)).isoformat(), "fim_hora": "10:00", "tempo": "03 horas"},
        "plano_execucao": [{"atividade": "Atachar a ISO virtio-win à VM 105", "executor": "CAS1", "etapa": "EXECUÇÃO"}],
        "rollback": [{"atividade": "Voltar a placa para e1000", "tempo": "00:30", "executor": "CAS1"}],
        "complementares": {"categoria": "Servidores", "riscos": "Perda de rede durante a troca", "pre_requisitos": ["Backup realizado e validado, quando aplicável"]},
    }
    corpo.update(mudancas)
    return corpo


def _rdm(cliente, cen, quem="ana"):
    """Lê a RDM da tarefa do cenário como o usuário `quem`."""
    return cliente.get(f"{URL}/{cen['numero']}/rdm", headers=cen["h"][quem]).json()


def test_formulario_inicial_e_obrigatorios(cliente, cenario):
    """RDM nova vem pré-preenchida; rascunho salva incompleto, mas o envio exige os campos obrigatórios."""
    cen = cenario
    rdm = _rdm(cliente, cen)
    assert not rdm["existe"] and rdm["situacao"] == "rascunho" and rdm["pode_editar"] and not rdm["pode_decidir"]
    assert rdm["formulario"]["titulo"] == "Trocar placa de rede da VM 105" and rdm["formulario"]["identificacao"]["solicitante"] == "Ana Executora"
    assert [l["etapa"] for l in rdm["formulario"]["cronograma"]] == ["HOMOLOGAÇÃO", "EXECUÇÃO", "VALIDAÇÃO"] and len(rdm["formulario"]["conhecimento"]) == 5
    # Rascunho salva sem conferir obrigatórios; enviar confere
    assert cliente.put(f"{URL}/{cen['numero']}/rdm", json={"titulo": "Só o título"}, headers=cen["h"]["ana"]).json()["existe"] is True
    r = cliente.post(f"{URL}/{cen['numero']}/rdm/enviar", json={"titulo": "Só o título"}, headers=cen["h"]["ana"])
    assert r.status_code == 400 and "objetivo" in r.json()["detalhe"] and "rollback" in r.json()["detalhe"]
    # Quem é de fora não vê; quem não executa não edita
    assert cliente.get(f"{URL}/{cen['numero']}/rdm", headers=cen["h"]["caio"]).status_code == 404
    assert cliente.put(f"{URL}/{cen['numero']}/rdm", json=_formulario(), headers=cen["h"]["beto"]).status_code == 403
    # A tarefa oferece "Gerar RDM" a quem executa
    assert "gerar_rdm" in cliente.get(f"{URL}/{cen['numero']}", headers=cen["h"]["ana"]).json()["acoes"]


def test_enviar_numera_pelo_protocolo_e_aprovar_gera_pdf_e_email(cliente, cenario):
    """Caminho feliz: enviar reserva o número no Protocolo; aprovar gera PDF, e-mail e histórico; concluir a tarefa conclui a RDM."""
    cen, ano = cenario, hoje_sao_paulo().year
    r = cliente.post(f"{URL}/{cen['numero']}/rdm/enviar", json=_formulario(), headers=cen["h"]["ana"])
    assert r.status_code == 200, r.text
    rdm = r.json()
    assert (rdm["numero"], rdm["situacao"]) == (f"00001/{ano}", "pendente")
    assert rdm["rotulo"] == f"RDM SGI 00001/{ano} - Instalar drivers VirtIO na VM 105"
    tarefa = cliente.get(f"{URL}/{cen['numero']}", headers=cen["h"]["lia"]).json()
    assert tarefa["status"] == "em_validacao" and tarefa["rdm"] == {"rotulo": rdm["rotulo"], "situacao": "pendente"}
    # Com a RDM pendente, a validação vira aprovar/reprovar RDM (só a liderança)
    assert {"aprovar_rdm", "reprovar_rdm"} <= set(tarefa["acoes"]) and "validar" not in tarefa["acoes"]
    assert cliente.post(f"{URL}/{cen['numero']}/mover", json={"acao": "validar"}, headers=cen["h"]["lia"]).status_code == 403
    assert cliente.post(f"{URL}/{cen['numero']}/rdm/aprovar", headers=cen["h"]["ana"]).status_code == 403
    # No Protocolo, o número é do tipo RDM SGI, reservado e sem ações manuais
    with FabricaSessao() as s:
        n = s.scalar(select(NumeroProtocolo).where(NumeroProtocolo.reservado_em.is_not(None)))
        assert n.sequencia.tipo.nome == "RDM SGI" and n.numero == 1 and n.sequencia.exercicio == ano
    r = cliente.post(f"{URL}/{cen['numero']}/rdm/aprovar", headers=cen["h"]["lia"])
    assert r.status_code == 200, r.text
    assert r.json()["situacao"] == "aprovada" and r.json()["tem_pdf"]
    assert cliente.get(f"{URL}/{cen['numero']}", headers=cen["h"]["lia"]).json()["status"] == "em_andamento"
    # PDF: as seções da matriz, o anexo complementar e o rodapé com cargo e setor de quem aprovou
    pdf = cliente.get(f"{URL}/{cen['numero']}/rdm/pdf", headers=cen["h"]["ana"])
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    texto = " ".join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
    for trecho in ("FORMULÁRIO DE REQUISIÇÃO DE MUDANÇA", "1. IDENTIFICAÇÃO", "10. PLANO DE REMEDIAÇÃO", "13. RESULTADO PÓS IMPLEMENTAÇÃO",
                   "INFORMAÇÕES COMPLEMENTARES", "Perda de rede", "Preenchido via SGI SPI - Aprovado por Lia Líder - Diretor - CGI"):
        assert trecho in texto, trecho
    # E-mail com o PDF para responsáveis, seguidores e quem aprovou
    assert len(cen["enviados"]) == 1
    mensagem = cen["enviados"][0]
    assert mensagem.assunto == f"RDM Tarefa #{cen['numero']} - aprovada"
    assert sorted(mensagem.para) == ["ana@sp.gov.br", "beto@sp.gov.br", "lia@sp.gov.br"]
    assert mensagem.anexos[0].nome == f"RDM-SGI-00001-{ano}.pdf" and mensagem.anexos[0].conteudo[:4] == b"%PDF"
    # PDF anexado no histórico da tarefa e no número do Protocolo (que passa a utilizado)
    with FabricaSessao() as s:
        evento = s.scalar(select(EventoTarefa).where(EventoTarefa.titulo.like("%aprovada")))
        assert evento is not None and len(evento.anexos) == 1
        assert s.scalar(select(NumeroProtocolo).where(NumeroProtocolo.numero == 1)).estado == "utilizado"
    # Executada a mudança: entregar e validar normalmente → RDM concluída (verde)
    assert cliente.post(f"{URL}/{cen['numero']}/mover", json={"acao": "entregar"}, headers=cen["h"]["ana"]).status_code == 200
    assert cliente.post(f"{URL}/{cen['numero']}/mover", json={"acao": "validar"}, headers=cen["h"]["lia"]).status_code == 200
    assert _rdm(cliente, cen)["situacao"] == "concluida"
    lista = cliente.get(f"{URL}/rdms", headers=cen["h"]["ana"]).json()
    assert [(x["numero"], x["situacao"], x["tarefa_numero"]) for x in lista] == [(f"00001/{ano}", "concluida", cen["numero"])]
    assert cliente.get(f"{URL}/rdms", headers=cen["h"]["caio"]).json() == []
    assert cliente.get(f"{URL}/rdms?situacao=pendente", headers=cen["h"]["ana"]).json() == []


def test_reprovar_exige_motivo_e_reenvio_mantem_o_numero(cliente, cenario):
    """Reprovar sem motivo é recusado; reprovada, a RDM volta para edição e o reenvio usa o mesmo número."""
    cen, ano = cenario, hoje_sao_paulo().year
    assert cliente.post(f"{URL}/{cen['numero']}/rdm/enviar", json=_formulario(), headers=cen["h"]["ana"]).status_code == 200
    assert cliente.post(f"{URL}/{cen['numero']}/rdm/reprovar", json={"motivo": ""}, headers=cen["h"]["lia"]).status_code == 422
    r = cliente.post(f"{URL}/{cen['numero']}/rdm/reprovar", json={"motivo": "Falta o plano de comunicação."}, headers=cen["h"]["lia"])
    assert r.status_code == 200, r.text
    assert (r.json()["situacao"], r.json()["motivo_reprovacao"], r.json()["tem_pdf"]) == ("reprovada", "Falta o plano de comunicação.", False)
    assert cliente.get(f"{URL}/{cen['numero']}", headers=cen["h"]["ana"]).json()["status"] == "em_andamento"
    assert cen["enviados"] == []
    # Corrige e reenvia: mesmo número, volta a pendente
    rdm = _rdm(cliente, cen)
    assert rdm["pode_editar"]
    corpo = _formulario(comunicacao=[{"quem": "SPI / CAS1", "momento": "Início da atividade", "meio": "Email", "responsavel": "CAS1"}])
    r = cliente.post(f"{URL}/{cen['numero']}/rdm/enviar", json=corpo, headers=cen["h"]["ana"])
    assert (r.json()["numero"], r.json()["situacao"]) == (f"00001/{ano}", "pendente")
    with FabricaSessao() as s:
        assert len(list(s.scalars(select(NumeroProtocolo).where(NumeroProtocolo.reservado_em.is_not(None))))) == 1


def test_numero_da_rdm_nao_e_reservado_a_mao_no_protocolo(cliente, cenario, admin):
    """A sequência "RDM SGI" é controlada pelas Tarefas: nem o SuperRoot reserva ou libera número à mão no Protocolo."""
    cen = cenario
    assert cliente.post(f"{URL}/{cen['numero']}/rdm/enviar", json=_formulario(), headers=cen["h"]["ana"]).status_code == 200
    with FabricaSessao() as s:
        n = s.scalar(select(NumeroProtocolo).where(NumeroProtocolo.numero == 2))
        sequencia_id, numero_id, reservado_id = n.sequencia_id, n.id, s.scalar(select(NumeroProtocolo.id).where(NumeroProtocolo.numero == 1))
    r = cliente.post(f"/api/protocolo/sequencias/{sequencia_id}/proximo", json={"finalidade": "Teste"}, headers=admin)
    assert r.status_code == 403 and "Tarefas" in r.json()["detalhe"]
    grade = cliente.get(f"/api/protocolo/sequencias/{sequencia_id}/numeros", headers=admin).json()
    primeiro = next(x for x in grade["itens"] if x["id"] == str(reservado_id))
    assert (primeiro["numero_formatado"][:5], primeiro["rdm_situacao"], primeiro["tarefa_numero"]) == ("00001", "pendente", cen["numero"])
    assert not (primeiro["pode_liberar"] or primeiro["pode_anexar"] or primeiro["pode_concluir_sem_documento"])
    assert cliente.post(f"/api/protocolo/numeros/{reservado_id}/liberar", json={"motivo": "x"}, headers=admin).status_code == 403
