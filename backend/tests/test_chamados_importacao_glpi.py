# Criado por José Eduardo Santana Martins
# Este arquivo serve para testar a importação do histórico do GLPI (leitura do dump, de-para, carga idempotente e ensaio).
"""Importação do GLPI a partir de um dump pequeno, escrito aqui no formato do mysqldump."""

import csv

from sqlalchemy import func, select

from app.core.banco import FabricaSessao
from app.models.chamados import AcompanhamentoChamado, AnexoChamado, AtorChamado, CategoriaChamados, CategoriaItilChamados, Chamado, SolucaoChamado, TarefaChamado, ValidacaoChamado
from app.services.chamados import importacao_glpi, parametros
from tests.conftest import criar_usuario
from tests.test_chamados import BASE, _preparar

DUMP = r"""-- MariaDB dump 10.19
DROP TABLE IF EXISTS `glpi_configs`;
CREATE TABLE `glpi_configs` (
  `id` int unsigned NOT NULL AUTO_INCREMENT,
  `context` varchar(150) DEFAULT NULL,
  `name` varchar(150) DEFAULT NULL,
  `value` text DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB;
INSERT INTO `glpi_configs` VALUES (1,'core','version','11.0.8'),(2,'core','url_base','http://x');
CREATE TABLE `glpi_users` (
  `id` int unsigned NOT NULL,
  `name` varchar(255) DEFAULT NULL,
  `realname` varchar(255) DEFAULT NULL,
  `firstname` varchar(255) DEFAULT NULL
) ENGINE=InnoDB;
INSERT INTO `glpi_users` VALUES (7,'maria','Souza','Maria'),(8,'joao','Lima','João'),(9,'fulano.saiu','Antigo','Fulano');
CREATE TABLE `glpi_useremails` (
  `id` int unsigned NOT NULL,
  `users_id` int unsigned NOT NULL,
  `email` varchar(255) DEFAULT NULL
) ENGINE=InnoDB;
INSERT INTO `glpi_useremails` VALUES (1,9,'fulano@exemplo.com');
CREATE TABLE `glpi_groups` (
  `id` int unsigned NOT NULL,
  `name` varchar(255) DEFAULT NULL,
  `completename` text DEFAULT NULL
) ENGINE=InnoDB;
INSERT INTO `glpi_groups` VALUES (3,'Suporte TI','TI > Suporte TI');
CREATE TABLE `glpi_itilcategories` (
  `id` int unsigned NOT NULL,
  `itilcategories_id` int unsigned NOT NULL DEFAULT 0,
  `name` varchar(255) DEFAULT NULL,
  `level` int NOT NULL DEFAULT 0,
  `groups_id` int unsigned NOT NULL DEFAULT 0,
  `is_helpdeskvisible` tinyint NOT NULL DEFAULT 1,
  `is_incident` tinyint NOT NULL DEFAULT 1,
  `is_request` tinyint NOT NULL DEFAULT 1
) ENGINE=InnoDB;
INSERT INTO `glpi_itilcategories` VALUES (20,0,'Hardware',1,3,1,1,1),(21,20,'Impressora',2,0,1,1,1),(22,20,'Impressora',2,0,1,1,1);
CREATE TABLE `glpi_tickets` (
  `id` int unsigned NOT NULL,
  `name` varchar(255) DEFAULT NULL,
  `date` timestamp NULL DEFAULT NULL,
  `closedate` timestamp NULL DEFAULT NULL,
  `solvedate` timestamp NULL DEFAULT NULL,
  `takeintoaccountdate` timestamp NULL DEFAULT NULL,
  `date_mod` timestamp NULL DEFAULT NULL,
  `status` int NOT NULL DEFAULT 1,
  `content` longtext DEFAULT NULL,
  `priority` int NOT NULL DEFAULT 1,
  `itilcategories_id` int unsigned NOT NULL DEFAULT 0,
  `type` int NOT NULL DEFAULT 1,
  `time_to_resolve` timestamp NULL DEFAULT NULL,
  `time_to_own` timestamp NULL DEFAULT NULL,
  `is_deleted` tinyint NOT NULL DEFAULT 0
) ENGINE=InnoDB;
INSERT INTO `glpi_tickets` VALUES (1500,'Impressora não imprime','2026-03-02 09:00:00','2026-03-02 15:00:00','2026-03-02 14:00:00','2026-03-02 09:05:00','2026-03-02 15:00:00',6,'&lt;p&gt;A impressora d\'água parou.\r\nSem papel.&lt;/p&gt;',4,21,1,'2026-03-02 13:00:00','2026-03-02 09:15:00',0),(1501,'Pedido do \"ex-servidor\"','2026-03-03 10:00:00',NULL,NULL,NULL,'2026-03-03 10:00:00',2,'<p>Texto já em HTML</p>',3,0,2,NULL,NULL,0),(1502,'Apagado','2026-03-04 10:00:00',NULL,NULL,NULL,'2026-03-05 10:00:00',1,NULL,3,22,1,NULL,NULL,1);
CREATE TABLE `glpi_tickets_users` (
  `id` int unsigned NOT NULL,
  `tickets_id` int unsigned NOT NULL,
  `users_id` int unsigned NOT NULL,
  `type` int NOT NULL,
  `alternative_email` varchar(255) DEFAULT NULL
) ENGINE=InnoDB;
INSERT INTO `glpi_tickets_users` VALUES (1,1500,7,1,NULL),(2,1501,9,1,NULL),(3,1500,7,3,NULL);
CREATE TABLE `glpi_groups_tickets` (
  `id` int unsigned NOT NULL,
  `tickets_id` int unsigned NOT NULL,
  `groups_id` int unsigned NOT NULL,
  `type` int NOT NULL
) ENGINE=InnoDB;
INSERT INTO `glpi_groups_tickets` VALUES (1,1500,3,2);
CREATE TABLE `glpi_itilfollowups` (
  `id` int unsigned NOT NULL,
  `itemtype` varchar(100) NOT NULL,
  `items_id` int unsigned NOT NULL,
  `date` timestamp NULL DEFAULT NULL,
  `users_id` int unsigned NOT NULL DEFAULT 0,
  `content` longtext DEFAULT NULL,
  `is_private` tinyint NOT NULL DEFAULT 0
) ENGINE=InnoDB;
INSERT INTO `glpi_itilfollowups` VALUES (40,'Ticket',1500,'2026-03-02 10:00:00',8,'<p>Vou olhar</p>',0),(41,'Ticket',1500,'2026-03-02 11:00:00',8,'<p>Interno</p>',1),(42,'Change',9,'2026-03-02 11:00:00',8,'x',0);
CREATE TABLE `glpi_itilsolutions` (
  `id` int unsigned NOT NULL,
  `itemtype` varchar(100) NOT NULL,
  `items_id` int unsigned NOT NULL,
  `content` longtext DEFAULT NULL,
  `date_creation` timestamp NULL DEFAULT NULL,
  `users_id` int unsigned NOT NULL DEFAULT 0,
  `status` int NOT NULL DEFAULT 1
) ENGINE=InnoDB;
INSERT INTO `glpi_itilsolutions` VALUES (60,'Ticket',1500,'<p>Primeira</p>','2026-03-02 12:00:00',8,4),(61,'Ticket',1500,'<p>Trocado o toner</p>','2026-03-02 14:00:00',8,3);
CREATE TABLE `glpi_tickettasks` (
  `id` int unsigned NOT NULL,
  `tickets_id` int unsigned NOT NULL,
  `date` timestamp NULL DEFAULT NULL,
  `users_id` int unsigned NOT NULL DEFAULT 0,
  `content` longtext DEFAULT NULL,
  `is_private` tinyint NOT NULL DEFAULT 0,
  `end` timestamp NULL DEFAULT NULL,
  `state` int NOT NULL DEFAULT 1,
  `users_id_tech` int unsigned NOT NULL DEFAULT 0,
  `date_mod` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB;
INSERT INTO `glpi_tickettasks` VALUES (70,1500,'2026-03-02 10:30:00',8,'<p>Pedir toner</p>',1,'2026-03-02 11:30:00',2,8,NULL);
CREATE TABLE `glpi_ticketvalidations` (
  `id` int unsigned NOT NULL,
  `users_id` int unsigned NOT NULL DEFAULT 0,
  `tickets_id` int unsigned NOT NULL,
  `users_id_validate` int unsigned NOT NULL DEFAULT 0,
  `itemtype_target` varchar(255) DEFAULT NULL,
  `items_id_target` int unsigned NOT NULL DEFAULT 0,
  `comment_submission` text DEFAULT NULL,
  `comment_validation` text DEFAULT NULL,
  `status` int NOT NULL DEFAULT 2,
  `submission_date` timestamp NULL DEFAULT NULL,
  `validation_date` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB;
INSERT INTO `glpi_ticketvalidations` VALUES (80,8,1500,0,'User',7,'Pode trocar?','Pode',3,'2026-03-02 10:00:00','2026-03-02 10:10:00');
CREATE TABLE `glpi_documents` (
  `id` int unsigned NOT NULL,
  `filename` varchar(255) DEFAULT NULL,
  `filepath` varchar(255) DEFAULT NULL,
  `mime` varchar(255) DEFAULT NULL,
  `is_deleted` tinyint NOT NULL DEFAULT 0,
  `users_id` int unsigned NOT NULL DEFAULT 0
) ENGINE=InnoDB;
INSERT INTO `glpi_documents` VALUES (90,'foto.txt','TXT/ab/foto.txt','text/plain',0,7),(91,'sumiu.pdf','PDF/cd/sumiu.pdf','application/pdf',0,7);
CREATE TABLE `glpi_documents_items` (
  `id` int unsigned NOT NULL,
  `documents_id` int unsigned NOT NULL,
  `items_id` int unsigned NOT NULL,
  `itemtype` varchar(100) NOT NULL,
  `date_creation` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB;
INSERT INTO `glpi_documents_items` VALUES (95,90,40,'ITILFollowup','2026-03-02 10:00:00'),(96,91,1500,'Ticket','2026-03-02 10:00:00');
CREATE TABLE `glpi_plugin_tag_tags` (
  `id` int unsigned NOT NULL,
  `name` varchar(255) DEFAULT NULL
) ENGINE=InnoDB;
INSERT INTO `glpi_plugin_tag_tags` VALUES (5,'Pessoa Teste'),(6,'LINUX');
CREATE TABLE `glpi_plugin_tag_tagitems` (
  `id` int unsigned NOT NULL,
  `plugin_tag_tags_id` int unsigned NOT NULL,
  `items_id` int unsigned NOT NULL,
  `itemtype` varchar(100) NOT NULL
) ENGINE=InnoDB;
INSERT INTO `glpi_plugin_tag_tagitems` VALUES (1,6,1501,'Ticket');
CREATE TABLE `glpi_ticketsatisfactions` (
  `id` int unsigned NOT NULL,
  `tickets_id` int unsigned NOT NULL,
  `satisfaction` int DEFAULT NULL
) ENGINE=InnoDB;
INSERT INTO `glpi_ticketsatisfactions` VALUES (1,1500,5);
"""


def _escrever_de_para(pasta, arquivo, ajuste):
    caminho = pasta / arquivo
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    for linha in linhas:
        ajuste(linha)
    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=list(linhas[0].keys()), delimiter=";")
        escritor.writeheader()
        escritor.writerows(linhas)


def test_leitor_do_dump_entende_escapes_nulos_e_colunas():
    linhas = list(importacao_glpi._tuplas(r"(1,'a\'b','c''d',NULL,-2.5,'x\\y\nz'),(2,'(),',0,'',3,'')"))
    assert linhas == [[1, "a'b", "c'd", None, -2.5, "x\\y\nz"], [2, "(),", 0, "", 3, ""]]


def test_preparar_e_carregar_o_historico(cliente, admin, tmp_path):
    c = _preparar(cliente, admin)
    dump = tmp_path / "glpi.sql"
    dump.write_text(DUMP, encoding="utf-8")
    arquivos = tmp_path / "files"
    (arquivos / "TXT" / "ab").mkdir(parents=True)
    (arquivos / "TXT" / "ab" / "foto.txt").write_text("conteúdo do anexo", encoding="utf-8")
    pasta = tmp_path / "de-para"
    dados = importacao_glpi.ler_dump(dump)
    assert importacao_glpi.versao(dados) == "11.0.8" and len(dados["glpi_tickets"]) == 3
    assert dados["glpi_tickets"][0]["content"].startswith("&lt;p&gt;A impressora d'água parou.\r\n")

    with FabricaSessao() as sessao:
        rel = importacao_glpi.preparar(sessao, dados, pasta)
    # Sugestões: login igual casa; grupo pelo nome do setor; etiqueta com o nome de uma pessoa vira responsável (há 4 "Pessoa Teste": não sugere)
    usuarios = {l["login_glpi"]: l["login_sgi"] for l in csv.DictReader(open(pasta / "usuarios.csv", encoding="utf-8-sig"), delimiter=";")}
    assert usuarios == {"maria": "maria", "joao": "joao", "fulano.saiu": ""}
    grupos = list(csv.DictReader(open(pasta / "grupos.csv", encoding="utf-8-sig"), delimiter=";"))
    assert grupos[0]["setor_sgi"] == "Suporte TI"
    etiquetas = {l["etiqueta"]: l["acao"] for l in csv.DictReader(open(pasta / "etiquetas.csv", encoding="utf-8-sig"), delimiter=";")}
    assert etiquetas == {"Pessoa Teste": "nota", "LINUX": "nota"} and any("fulano.saiu" in a for a in rel.avisos)
    # A pessoa revisa: LINUX vira atribuição ao técnico joao
    _escrever_de_para(pasta, "etiquetas.csv", lambda l: l.update(acao="responsavel:joao") if l["etiqueta"] == "LINUX" else None)

    # Ensaio: nada fica
    with FabricaSessao() as sessao:
        rel = importacao_glpi.carregar(sessao, dados, pasta, c["ids"]["setor_ti"], arquivos)
        assert rel.destino["chamados"] == 3
        sessao.rollback()
    with FabricaSessao() as sessao:
        assert sessao.scalar(select(func.count()).select_from(Chamado)) == 0

    # Carga de verdade
    with FabricaSessao() as sessao:
        rel = importacao_glpi.carregar(sessao, dados, pasta, c["ids"]["setor_ti"], arquivos)
        sessao.commit()
    assert rel.destino["chamados"] == 3 and rel.destino["acompanhamentos"] == 2 and rel.destino["soluções"] == 2 and rel.destino["anexos"] == 1
    assert rel.destino["pesquisas de satisfação"] == 1 and any("sumiu.pdf" in a for a in rel.avisos)
    assert any("Categoria repetida" in a for a in rel.avisos)
    with FabricaSessao() as sessao:
        ch = sessao.scalar(select(Chamado).where(Chamado.numero == 1500))
        assert ch.importado and ch.status_base == "solucionado" and ch.prioridade == "alta" and ch.prioridade_origem == "importado"
        assert ch.setor_nome == "Suporte TI" and ch.solicitante_id is not None and "d'água" in ch.descricao and "<p>" in ch.descricao
        # 14h em São Paulo = 17h UTC
        assert (ch.solucionado_em.hour, ch.solucionado_em.minute) == (17, 0)
        # A categoria do GLPI vira categoria ITIL (classificação técnica); o assunto é o "Importados do GLPI" (inativo)
        assert sessao.get(CategoriaItilChamados, ch.categoria_itil_id).caminho == "Hardware > Impressora"
        assert sessao.get(CategoriaChamados, ch.categoria_id).nome == "Importados do GLPI" and not sessao.get(CategoriaChamados, ch.categoria_id).ativa
        solucoes = {s.texto: s.status for s in sessao.scalars(select(SolucaoChamado).where(SolucaoChamado.chamado_id == ch.id))}
        assert solucoes == {"<p>Primeira</p>": "substituida", "<p>Trocado o toner</p>": "vigente"}
        assert sessao.scalar(select(TarefaChamado)).estado == "feita"
        assert sessao.scalar(select(ValidacaoChamado)).status == "aprovada"
        assert sessao.scalar(select(func.count()).select_from(AtorChamado)) == 0  # o observador é a própria solicitante
        anexo = sessao.scalar(select(AnexoChamado))
        assert anexo.alvo_tipo == "acompanhamento"
        assert sessao.scalar(select(AcompanhamentoChamado).where(AcompanhamentoChamado.origem_glpi_id == 41)).privado
        # Sem par no SGI: solicitante externo pelo e-mail; etiqueta LINUX → responsável joao; sem categoria → categoria inativa
        ex = sessao.scalar(select(Chamado).where(Chamado.numero == 1501))
        assert ex.solicitante_externo == "fulano@exemplo.com" and ex.responsavel_id == c["ids"]["tecnico"] and ex.tipo == "requisicao"
        assert ex.categoria_itil_id is None and ex.categoria_id == ch.categoria_id
        assert sessao.scalar(select(Chamado).where(Chamado.numero == 1502)).excluido_em is not None
        assert parametros.obter_inteiro(sessao, "proximo_numero") == 1503

    # De novo: nada duplicado
    with FabricaSessao() as sessao:
        rel = importacao_glpi.carregar(sessao, dados, pasta, c["ids"]["setor_ti"], arquivos)
        sessao.commit()
    assert rel.destino["chamados"] == 0 and rel.pulados["chamados"] == 3 and rel.pulados["categorias ITIL"] == 3
    # O importado é só leitura; o próximo chamado aberto continua depois do maior
    r = cliente.post(f"{BASE}/1500/acompanhamentos", data={"dados": '{"texto": "<p>oi</p>"}'}, headers=admin)
    assert r.status_code == 409
    novo = cliente.post(BASE, data={"dados": f'{{"titulo": "Novo depois da carga", "descricao": "<p>x</p>", "categoria_id": "{c["ids"]["categoria"]}"}}'},
                        headers=c["cab"]["solicitante"])
    assert novo.json()["numero"] == 1503


def test_de_para_com_login_inexistente_para_a_carga(cliente, admin, tmp_path):
    c = _preparar(cliente, admin)
    criar_usuario("sobra")
    dump = tmp_path / "glpi.sql"
    dump.write_text(DUMP, encoding="utf-8")
    dados = importacao_glpi.ler_dump(dump)
    pasta = tmp_path / "dp"
    with FabricaSessao() as sessao:
        importacao_glpi.preparar(sessao, dados, pasta)
    _escrever_de_para(pasta, "usuarios.csv", lambda l: l.update(login_sgi="ninguem") if l["login_glpi"] == "fulano.saiu" else None)
    with FabricaSessao() as sessao:
        try:
            importacao_glpi.carregar(sessao, dados, pasta, c["ids"]["setor_ti"])
            raise AssertionError("devia recusar")
        except importacao_glpi.ErroImportacao as erro:
            assert "ninguem" in str(erro)
