# Criado por José Eduardo Santana Martins
# Este arquivo serve para guardar os sete modelos padrão da prorrogação contratual (texto-base semeado em Contratos › Modelos).
"""Modelos padrão da prorrogação, a partir dos documentos de `apoio/Prorrogações` (Parecer Referencial NLC nº 1/2026).

São a **semente** da migração: depois de semeados, quem manda é a tela de Modelos (SuperRoot ou controle total em Contratos). Já saem com as
correções dos originais: nome da empresa, ano e autoridades viram placeholders (nada de nome de outra empresa nem de ano fixo), "sediada
sediado" e "prestação de contínuos" corrigidos, parágrafo repetido removido e as notas de orientação (OBS) trocadas por parágrafos condicionais
(`#se…`), que o sistema liga ou desliga sozinho.
"""


def _p(texto: str, alinhamento: str = "justify") -> str:
    return f'<p style="text-align: {alinhamento}">{texto}</p>'


def _b(texto: str) -> str:
    return f"<strong>{texto}</strong>"


def _centro(texto: str) -> str:
    return _p(_b(texto), "center")


def _direita(texto: str) -> str:
    return _p(texto, "right")


_ASSINATURA_SSGC = _centro("#ssgcnome") + _p("Subsecretário de Gestão Corporativa", "center")

MINUTA_ADITIVO = "".join([
    _centro("MINUTA DE TERMO DE ADITAMENTO"),
    _p(_b("Processo Administrativo nº #numeroprocesso")),
    _p(_b("Contrato nº #nrocontrato")),
    _p(f"{_b('#nrotermo TERMO DE ADITAMENTO AO CONTRATO Nº #nrocontrato')} FIRMADO ENTRE {_b('O ESTADO DE SÃO PAULO')}, POR MEIO DA "
       f"{_b('SECRETARIA DE PARCERIAS EM INVESTIMENTOS')}, E O FORNECEDOR #razaosocialempresa, TENDO POR OBJETO #objetodocontrato."),
    _p(f"No mês de #mesanoatual, na cidade de São Paulo, compareceram, de um lado, como {_b('CONTRATANTE')}, o Estado de São Paulo, por intermédio da "
       f"{_b('SECRETARIA DE PARCERIAS EM INVESTIMENTOS')}, inscrita no CNPJ sob nº 96.480.850/0001-03, com sede na Rua Iaiá, 126 – Itaim Bibi – CEP 04542-060, "
       f"neste ato representada pelo Sr. {_b('#ssgcnome')}, Subsecretário de Gestão Corporativa, inscrito no CPF sob o nº #ssgccpf, no uso da competência "
       f"conferida pela legislação aplicável, e, de outro lado, como {_b('CONTRATADO')}, o fornecedor {_b('#razaosocialempresa')}, inscrito no CNPJ sob nº "
       f"#cnpjempresa, com sede na #enderecoempresa, neste ato representado pelo(a) Sr.(ª) #representantenome, #representantefuncao, inscrito(a) no CPF sob "
       f"o nº #representantecpf, #baserepresentacao."),
    _p(f"As referidas partes, {_b('CONSIDERANDO')}:"),
    _p(f"{_b('a)')} que foi celebrado o {_b('Contrato SPI nº #nrocontrato')}, tendo por objeto #objetodocontrato;"),
    _p(f"{_b('b)')} que na Cláusula #clausulavigencia do referido instrumento ficou estabelecida a vigência do ajuste por #vigenciainicialmeses, contados a partir de "
       "#vigenciainicialinicio, prorrogável até o limite de 10 (dez) anos, na forma do artigo 107 da Lei nº 14.133, de 1º de abril de 2021;"),
    _p(f"{_b('c)')} que o CONTRATADO comprovou, perante o CONTRATANTE, que mantém as condições de habilitação e qualificação exigidas à época do procedimento de "
       "contratação (#modalidade) e/ou previamente à celebração do ajuste, nos termos do artigo 92, inciso XVI, da Lei nº 14.133, de 2021;"),
    _p(f"{_b('d)')} que a prorrogação do contrato foi expressamente justificada por escrito e autorizada pela autoridade competente, conforme documento nº "
       "#docjustificativa do Processo nº #numeroprocesso;"),
    _p(f"{_b('e)')} que este caso concreto se enquadra, integralmente, nos parâmetros e pressupostos do Parecer Referencial #parecerreferencial, com o "
       "cumprimento de todas as orientações jurídicas nele contidas;"),
    _p(f"{_b('RESOLVEM')}, de comum acordo, aditar o Contrato {_b('SPI nº #nrocontrato')}, nos termos do artigo 107 da Lei nº 14.133, de 2021, o que ora fazem "
       "nos termos a seguir expostos:"),
    _p(_b("CLÁUSULA PRIMEIRA – DA PRORROGAÇÃO")),
    _p(f"{_b('1.1.')} O prazo de vigência do contrato fica prorrogado por mais #mesesprorrogacao, de #inicioprorrogacao a #fimprorrogacao."),
    _p(f"#secustosnaorenovaveis {_b('1.2.')} Fica alterado o contrato, para eliminação dos custos não renováveis já pagos ou amortizados no âmbito da "
       "contratação, conforme discriminado na planilha que integra este termo de aditamento como anexo, com efeitos a partir de #efeitoscustos."),
    _p(_b("CLÁUSULA SEGUNDA – DO VALOR E RECURSOS ORÇAMENTÁRIOS")),
    _p(f"{_b('2.1.')} O valor total estimado do presente contrato passa a ser de #valorprorrogacao (#valorprorrogacaoextenso) para o período de "
       "#mesesprorrogacao, sendo #valoresporexercicio, onerando o orçamento em sua classificação funcional programática e categoria econômica #dotacao, "
       "conforme Nota de Empenho #nrone. Quando a execução do contrato ultrapassar o presente exercício, a dotação relativa ao(s) exercício(s) financeiro(s) "
       "subsequente(s) será indicada após aprovação da Lei Orçamentária respectiva e liberação dos créditos correspondentes, mediante apostilamento."),
    _p(f"#sedemandavariavel {_b('2.2.')} O valor indicado nesta cláusula é meramente estimativo, de forma que os pagamentos devidos ao CONTRATADO dependerão "
       "dos quantitativos efetivamente demandados, medidos e fornecidos."),
    _p(f"#serepactuacao {_b('2.3.')} Desde que atendidos os requisitos legais e a disciplina do contrato, fica resguardado ao CONTRATADO o direito à "
       "repactuação de preços referente a #periodosrepactuacao, concernente ao lapso temporal de vigência imediatamente anterior à presente prorrogação, por "
       "justificadamente não ter sido possível realizá-la até a presente data."),
    _p(_b("CLÁUSULA TERCEIRA – DA GARANTIA DA EXECUÇÃO")),
    _p(f"{_b('3.')} O CONTRATADO apresenta, nesta ocasião, a comprovação da renovação da garantia contratual anteriormente prestada, em conformidade com a "
       "disciplina do contrato especificado no preâmbulo."),
    _p(_b("CLÁUSULA QUARTA – DA DIVULGAÇÃO E PUBLICAÇÃO")),
    _p(f"{_b('4.')} Cabe ao CONTRATANTE divulgar a presente prorrogação no Portal Nacional de Contratações Públicas – PNCP, no prazo de #prazopncp dias úteis "
       "contados da data de sua assinatura, em conformidade com o artigo 94 da Lei nº 14.133, de 2021, bem como divulgar e manter o aditamento à disposição do "
       "público no respectivo sítio eletrônico oficial na Internet, em atenção ao artigo 91, “caput”, da Lei nº 14.133, de 2021, além de publicar seu extrato "
       "no Diário Oficial do Estado, nos termos do Decreto estadual nº 67.717, de 25 de maio de 2023."),
    _p(_b("CLÁUSULA QUINTA – DA RATIFICAÇÃO")),
    _p(f"{_b('5.')} Permanecem em vigor as demais cláusulas e condições contratuais não alteradas pelo presente instrumento."),
    _p("E por estarem assim, justas e acertadas, firmam as partes o presente instrumento em 01 (uma) via, sendo assinado também por duas testemunhas abaixo "
       "identificadas, para todos os fins e efeitos de direito."),
    _direita("São Paulo, data da última assinatura eletrônica das partes."),
    _centro("#ssgcnome") + _p("Representante legal do Contratante", "center"),
    _centro("#representantenome") + _p("Representante legal do Contratado", "center"),
    _p(_b("TESTEMUNHAS:")),
    _p(f"Nome: {_b('#testemunhaanome')}<br/>CPF: #testemunhaacpf"),
    _p(f"Nome: {_b('#testemunhabnome')}<br/>CPF: #testemunhabcpf"),
])

TERMO_CIENCIA = "".join([
    _centro("ANEXO I"),
    _centro("ANEXO LC-01 - TERMO DE CIÊNCIA E DE NOTIFICAÇÃO"),
    _centro("(CONTRATOS)"),
    _p(f"CONTRATANTE: {_b('SECRETARIA DE PARCERIAS EM INVESTIMENTOS')}<br/>CONTRATADO: {_b('#razaosocialempresa')}<br/>CONTRATO SPI Nº: {_b('#nrocontrato')}"
       "<br/>OBJETO: #objetodocontrato"),
    _p("Pelo presente TERMO, nós, abaixo identificados:"),
    _p(_b("1. Estamos CIENTES de que:"), "left"),
    _p(f"{_b('a)')} o ajuste acima referido, seus aditamentos, bem como o acompanhamento de sua execução contratual, estarão sujeitos a análise e julgamento pelo "
       "Tribunal de Contas do Estado de São Paulo, cujo trâmite processual ocorrerá pelo sistema eletrônico;"),
    _p(f"{_b('b)')} poderemos ter acesso ao processo, tendo vista e extraindo cópias das manifestações de interesse, Despachos e Decisões, mediante regular "
       "cadastramento no Sistema de Processo Eletrônico, em consonância com o estabelecido na Resolução nº 01/2011 do TCESP;"),
    _p(f"{_b('c)')} além de disponíveis no processo eletrônico, todos os Despachos e Decisões que vierem a ser tomados, relativamente ao aludido processo, serão "
       "publicados no Diário Oficial Eletrônico do Tribunal de Contas do Estado de São Paulo, em conformidade com o artigo 90 da Lei Complementar nº 709, de "
       "14 de janeiro de 1993, iniciando-se, a partir de então, a contagem dos prazos processuais, conforme regras do Código de Processo Civil;"),
    _p(f"{_b('d)')} as informações pessoais dos responsáveis pela contratante e interessados estão cadastradas no módulo eletrônico do “Cadastro Corporativo "
       "TCESP – CadTCESP”, nos termos previstos no Artigo 2º das Instruções nº 01/2024, conforme “Declaração(ões) de Atualização Cadastral” anexa(s);"),
    _p(f"{_b('e)')} é de exclusiva responsabilidade do contratado manter seus dados sempre atualizados."),
    _p(_b("2. Damo-nos por NOTIFICADOS para:"), "left"),
    _p("a) o acompanhamento dos atos do processo até seu julgamento final e consequente publicação;"),
    _p("b) se for o caso e de nosso interesse, nos prazos e nas formas legais e regimentais, exercer o direito de defesa, interpor recursos e o que mais couber."),
    _direita("São Paulo, na data da última assinatura digital."),
    _p(f"{_b('AUTORIDADE MÁXIMA DO ÓRGÃO/ENTIDADE:')}<br/>Nome: {_b('#secretarionome')}<br/>Cargo: Secretário<br/>CPF: #secretariocpf", "left"),
    _p(f"{_b('RESPONSÁVEIS PELA HOMOLOGAÇÃO DO CERTAME OU RATIFICAÇÃO DA DISPENSA/INEXIGIBILIDADE DE LICITAÇÃO:')}<br/>Nome: {_b('#ssgcnome')}"
       "<br/>Cargo: Subsecretário de Gestão Corporativa<br/>CPF: #ssgccpf", "left"),
    _p(f"{_b('RESPONSÁVEIS QUE ASSINARAM O AJUSTE:')}<br/>{_b('PELO CONTRATANTE:')}<br/>Nome: {_b('#ssgcnome')}<br/>Cargo: Subsecretário de Gestão Corporativa"
       f"<br/>CPF: #ssgccpf<br/>{_b('PELA CONTRATADA:')}<br/>Nome: {_b('#representantenome')}<br/>Cargo: #representantefuncao<br/>CPF: #representantecpf", "left"),
    _p(f"{_b('ORDENADOR DE DESPESAS DA CONTRATANTE:')}<br/>Nome: {_b('#ssgcnome')}<br/>Cargo: Subsecretário de Gestão Corporativa<br/>CPF: #ssgccpf", "left"),
    _p(f"{_b('GESTOR(ES) DO CONTRATO:')}<br/>Nome: {_b('#gestor')}", "left"),
    _p(f"{_b('TESTEMUNHAS')}<br/>1) Nome: {_b('#testemunhaanome')}<br/>CPF: #testemunhaacpf<br/>2) Nome: {_b('#testemunhabnome')}<br/>CPF: #testemunhabcpf", "left"),
    _p("(*) O Termo de Ciência e de Notificação deve identificar as pessoas físicas que tenham concorrido para a prática do ato jurídico, na condição de "
       "ordenador da despesa; de partes contratantes; de responsáveis por ações de acompanhamento, monitoramento e avaliação; de responsáveis por processos "
       "licitatórios; de responsáveis por prestações de contas; de responsáveis com atribuições previstas em atos legais ou administrativos e de interessados "
       "relacionados a processos de competência deste Tribunal."),
])


def _declaracao(titulo: str, itens: list[str]) -> str:
    letras = "abcdefghijklmnopqrstuvwxyz"
    return "".join([
        _centro(titulo),
        _p("Eu, #ssgcnome, dirigente da Subsecretaria de Gestão Corporativa, em conformidade com o Parecer Referencial #parecerreferencial, declaro para todos "
           "os fins de direito que:"),
        *[_p(f"{letras[i]}) {texto}{';' if i < len(itens) - 1 else '.'}") for i, texto in enumerate(itens)],
        _direita("São Paulo, na data da assinatura digital."),
        _ASSINATURA_SSGC,
    ])


_COMUNS_FINAIS = [
    "foi providenciada a reserva orçamentária dos valores referentes ao exercício corrente",
    "se ultrapassar 1 (um) exercício financeiro, há previsão no plano plurianual, e será observado o disposto no inciso II do “caput” do artigo 106 da Lei "
    "federal nº 14.133/2021",
    "será utilizada a minuta padrão que constitui Anexo I do Parecer Referencial especificado no preâmbulo",
    "o caso concreto se enquadra, integralmente, nos parâmetros e pressupostos do Parecer Referencial especificado no preâmbulo, e serão cumpridas todas as "
    "orientações jurídicas nele contidas",
]

DECLARACAO_LICITACAO = _declaracao("ANEXO II - DECLARAÇÃO DE ATENDIMENTO PARA CONTRATO DECORRENTE DE LICITAÇÃO", [
    "o contrato SPI nº #nrocontrato está em vigor",
    "a prorrogação está prevista no edital, e está formalmente demonstrado no processo que a forma de prestação dos serviços tem natureza continuada",
    "a vigência contratual total, com a prorrogação, não ultrapassará o limite decenal previsto no artigo 107 da Lei federal nº 14.133/2021",
    "as condições e os preços permanecem vantajosos para a Administração e em harmonia com os preços do mercado, na forma do artigo 107 da Lei federal nº 14.133/2021",
    "foi juntado relatório que discorre sobre a execução do contrato, com informações de que os serviços estão sendo prestados regularmente",
    "foi juntada justificativa, por escrito, de que a Administração mantém interesse na realização do serviço",
    "há manifestação expressa do Contratado informando o interesse na prorrogação",
    "foi comprovado que o Contratado mantém todas as condições iniciais de habilitação e qualificação exigidas na licitação e/ou previamente à celebração do ajuste",
    *_COMUNS_FINAIS,
])

DECLARACAO_DIRETA = _declaracao("ANEXO III - DECLARAÇÃO DE ATENDIMENTO PARA CONTRATO FORMALIZADO MEDIANTE DISPENSA OU INEXIGIBILIDADE DE LICITAÇÃO", [
    "o contrato SPI nº #nrocontrato está em vigor",
    "a prorrogação está prevista no aviso de contratação direta ou contrato, e está formalmente demonstrado no processo que a forma de prestação dos serviços "
    "tem natureza continuada",
    "a vigência contratual total, com a prorrogação, não ultrapassará o limite decenal previsto no artigo 107 da Lei federal nº 14.133/2021",
    "subsiste, no momento da prorrogação, a situação fática que deu lastro à contratação direta nos termos da Lei federal nº 14.133/2021",
    "as condições e os preços permanecem vantajosos para a Administração e em harmonia com os preços do mercado, na forma do artigo 107 da Lei federal nº 14.133/2021",
    "foi juntado relatório que discorre sobre a execução do contrato, com informações de que os serviços estão sendo prestados regularmente",
    "foi juntada justificativa, por escrito, de que a Administração mantém interesse na realização do serviço",
    "há manifestação expressa do Contratado informando o interesse na prorrogação",
    "foi comprovado que o Contratado mantém todas as condições iniciais de habilitação e qualificação exigidas no procedimento e/ou previamente à celebração do ajuste",
    *_COMUNS_FINAIS,
])

DECLARACAO_TCE = "".join([
    _centro("DECLARAÇÃO DE DOCUMENTOS À DISPOSIÇÃO DO TCE-SP"),
    _p(f"{_b('CONTRATANTE:')} SECRETARIA DE PARCERIAS EM INVESTIMENTOS<br/>{_b('CNPJ Nº:')} 96.480.850/0001-03<br/>{_b('CONTRATADA:')} #razaosocialempresa"
       f"<br/>{_b('CNPJ Nº:')} #cnpjempresa<br/>{_b('OBJETO:')} #objetodocontrato<br/>{_b('CONTRATO Nº (DE ORIGEM):')} #nrocontrato"
       f"<br/>{_b('DATA DA ASSINATURA:')} #assinaturadocontrato<br/>{_b('VIGÊNCIA INICIAL:')} #vigenciainicialmeses, contados do dia #vigenciainicialinicio "
       "a #vigenciainicialfim", "left"),
    _p(_b("DADOS DA PRORROGAÇÃO CONTRATUAL"), "left"),
    _p(f"{_b('VIGÊNCIA DA PRORROGAÇÃO:')} #mesesprorrogacao, contados do dia #inicioprorrogacao a #fimprorrogacao<br/>{_b('DATA DA ASSINATURA DO TERMO ADITIVO:')} "
       f"__/__/____<br/>{_b('VALOR DA PRORROGAÇÃO (R$):')} #valorprorrogacao (#valorprorrogacaoextenso).", "left"),
    _p("Declaro(amos), na qualidade de responsável(is) pela entidade supra epigrafada, sob as penas da Lei, que os demais documentos originais, atinentes à "
       "correspondente contratação (#modalidade), encontram-se no respectivo processo administrativo arquivado na origem à disposição do Tribunal de Contas do "
       "Estado de São Paulo, e serão remetidos quando requisitados."),
    _direita("São Paulo, na data da assinatura digital."),
    _centro("#ssgcnome") + _p("Subsecretário de Gestão Corporativa", "center"),
])


def _lista(*itens: str) -> str:
    return "".join(_p(i) for i in itens)


DESPACHO_INSTRUCAO = "".join([
    _p(f"{_b('PROCESSO nº:')} #numeroprocesso<br/>{_b('INTERESSADO:')} Secretaria de Parcerias em Investimentos<br/>{_b('ASSUNTO:')} #objetodocontrato "
       "(Contrato #nrocontrato)", "left"),
    _p(_b("À Diretoria de Gestão Administrativa,")),
    _p("Trata-se de procedimento destinado à formalização do #nrotermo Termo Aditivo ao Contrato nº #nrocontrato, firmado com a empresa #razaosocialempresa, "
       "tendo por objeto #objetodocontrato."),
    _p(_b("1. Da Instrução Processual")),
    _p("Os autos foram encaminhados a esta Coordenadoria para complementação da instrução. Verifica-se que o procedimento se encontra devidamente instruído, "
       "contando com as manifestações das áreas técnicas competentes e com a documentação necessária à formalização do aditivo. Assim, relacionam-se a seguir "
       "os principais documentos que subsidiam a presente instrução:"),
    _p(_b("Etapa 1: Instrução Inicial pelo Gestor e Fiscal / Área Requisitante")),
    _lista("Relatório e Justificativa do Gestor (doc. nº #docjustificativa);", "Deliberação do Comitê Gestor / COETIC, se aplicável."),
    _p(_b("Etapa 2: Consultas Prévias de Sanções e Impedimentos de Contratar")),
    _p("Consultas prévias de sanções e impedimentos (SICAF, CADIN Estadual, e-Sanções SP, CEIS, CNEP, Apenados TCESP, CNCIAI/CNJ) (doc. nº #dochabilitacao)."),
    _p(_b("Etapa 3: Consulta à Empresa Contratada sobre o Interesse na Prorrogação")),
    _lista("Consulta e aceite da Contratada (doc. nº #docaceite);", "Proposta atualizada da Contratada (doc. nº #docproposta)."),
    _p(_b("Etapa 4: Pesquisa de Preços e Vantajosidade")),
    _lista("Pesquisa de preços, quadro comparativo e aferição de preços: #aferiprecos (doc. nº #docpesquisa);",
           "Memória de cálculo – depuração de custos e relatório de negociação de preços;",
           "Declaração de vantajosidade (doc. nº #docvantajosidade);", "Planilha orçamentária (doc. nº #docplanilha)."),
    _p(_b("Etapa 5: Planejamento Orçamentário e Financeiro (DOF)")),
    _lista("Nota de Reserva #notareserva (doc. nº #docreserva);", "Declaração PPA – exercícios futuros e LRF art. 42, se aplicável."),
    _p(_b("Etapa 6: Elaboração de Minutas, Declarações e Instrução (CCC)")),
    _lista("Cópia do Parecer Referencial #parecerreferencial (doc. nº #docparecerreferencial);", "Minuta do Termo de Aditamento (doc. nº #docminuta);",
           "Anexo I – Planilha de serviços não renováveis, se aplicável;", "Anexo II – Termo de Ciência e Notificação;",
           "Minuta da Declaração de Documentos à Disposição do TCE;",
           "Checklist prévio de verificação do atendimento ao Parecer Referencial (doc. nº #docchecklist);",
           "Documentos de habilitação enviados pela empresa e emitidos pela SPI (doc. nº #dochabilitacao);",
           "Despacho de encaminhamento CCC/DGA à SSGC para autorização da prorrogação contratual."),
    _p(_b("2. Da análise jurídica")),
    _p("O presente caso encontra amparo no Parecer Referencial #parecerreferencial (doc. nº #docparecerreferencial), cujas orientações foram observadas na "
       "instrução dos autos."),
    _p(_b("3. Do atendimento ao parecer jurídico e checklist processual")),
    _p("Informa-se que as exigências e recomendações constantes do Parecer Referencial e do respectivo checklist processual foram integralmente analisadas e "
       "atendidas, conforme o detalhamento a seguir:"),
    _p(f"{_b('Relatório de Execução do Contrato e Justificativa do Gestor:')} instruído com a justificativa técnica e a motivação para a prorrogação da vigência "
       "contratual, o atestado de prestação regular dos serviços a contento e a demonstração motivada do interesse público (doc. nº #docjustificativa)."),
    _p(f"{_b('Consulta e verificação junto à empresa contratada:')} realizado o envio de comunicação formal de consulta e obtida a manifestação expressa de "
       "aceite da Contratada, com o respectivo resguardo de direito futuro à repactuação, quando aplicável (docs. nº #docaceite e #docproposta)."),
    _p(f"{_b('Certidões de regularidade fiscal, trabalhista e previdenciária:')} juntadas as certidões conjuntas federal/INSS, CNDT, CRF do FGTS, CND Estadual e "
       "CND Municipal válidas (doc. nº #dochabilitacao)."),
    _p(f"{_b('Consultas de sanções e impedimentos de contratar:')} realizadas as consultas prévias e verificados os cadastros no SICAF, CADIN Estadual, "
       "e-Sanções SP, CEIS, CNEP, Relação de Apenados do TCESP e CNCIAI/CNJ (em nome da empresa e do sócio majoritário), bem como o extrato do CADIN Federal e a "
       "contumácia do devedor nos termos da LC nº 225/2026."),
    _p(f"{_b('Pesquisa de preços de mercado, quadro comparativo e aferição referencial:')} realizada pesquisa de mercado atualizada, com elaboração do quadro "
       "comparativo de preços e aferição aos valores referenciais (doc. nº #docpesquisa)."),
    _p(f"{_b('Memória de cálculo, depuração de custos e relatório de negociação:')} efetuada a exclusão/depuração de custos fixos e variáveis não renováveis já "
       "amortizados, o registro das negociações com a contratada e a declaração motivada de vantajosidade econômica e técnica (doc. nº #docvantajosidade)."),
    _p(f"{_b('Reserva orçamentária e adequação financeira:')} efetivada a reserva de recursos por meio da Nota de Reserva nº #notareserva, com a devida indicação "
       "de adequação orçamentária e financeira (doc. nº #docreserva)."),
    _p(f"{_b('Minutas, declarações e instrução formal:')} instruído o feito com a cópia do Parecer Referencial aplicável, minuta do Termo Aditivo, anexos "
       "aplicáveis, Termo de Ciência e Notificação, Declaração de Documentos à Disposição do TCE e a lista prévia de verificação de aplicabilidade."),
    _p(f"Registra-se que o atendimento integral a todas as etapas e exigências acima descritas encontra-se consolidado no {_b('Checklist Prévio de Verificação do '
       'Atendimento ao Parecer Referencial')}, juntado aos autos sob o {_b('doc. nº #docchecklist')}."),
    _p(_b("4. Do prazo e justificativa da prorrogação")),
    _p("O Contrato nº #nrocontrato, celebrado em #assinaturadocontrato, possui vigência de #vigenciainicialmeses, com término atual previsto para "
       "#vigenciaatualfim. O Gestor do Contrato solicitou a prorrogação da avença por mais #mesesprorrogacao (doc. nº #docjustificativa)."),
    _p("A solicitação encontra-se devidamente justificada, considerando a essencialidade dos serviços para a continuidade das atividades institucionais da "
       "Pasta, a regular execução contratual, a anuência da contratada e o amparo legal previsto nos arts. 106 e 107 da Lei nº 14.133/2021."),
    _p(_b("5. Fundamentação legal")),
    _p("A prorrogação contratual encontra respaldo nos arts. 106 e 107 da Lei Federal nº 14.133/2021, bem como na Cláusula de Vigência e Prorrogação do "
       "Contrato original."),
    _p(_b("6. Do reajustamento e da repactuação")),
    _p("#tratamentoreajuste"),
    _p(_b("7. Da pesquisa de preços")),
    _p("A pesquisa de preços foi realizada mediante consulta direta a fornecedores / fontes idôneas, em estrita conformidade com a Lei Federal nº 14.133/2021 e "
       "com o Decreto Estadual nº 67.888/2023, restando consubstanciada em #aferiprecos (doc. nº #docpesquisa), com a finalidade de subsidiar a análise da "
       "proposta, demonstrar a compatibilidade dos valores com o mercado e aferir a vantajosidade da prorrogação contratual."),
    _p(_b("8. Da planilha orçamentária, dos valores e do recurso orçamentário")),
    _p("Conforme proposta atualizada (doc. nº #docproposta), o valor total estimado para o período de prorrogação é de #valorprorrogacaoextenso "
       "(#valorprorrogacao)."),
    _p("A reserva de recursos foi efetivada por meio da Nota de Reserva nº #notareserva (doc. nº #docreserva)."),
    _p(_b("9. Do encaminhamento")),
    _p(f"{_b('I.')} Submetem-se os autos à apreciação da Diretoria de Gestão Administrativa, para ciência e, se de acordo, encaminhamento ao Sr. Subsecretário "
       "de Gestão Corporativa, no uso da competência conferida pela legislação vigente, para, se de acordo:"),
    _p(f"{_b('a. Inicialmente:')} {_b('ASSINAR')} a Declaração de Atendimento ao Parecer Referencial (doc. nº #docdeclaracao), atestando o cumprimento dos "
       "pressupostos estabelecidos no referido opinativo jurídico."),
    _p(f"{_b('b. Após:')} {_b('ACOLHER E APROVAR')} as justificativas da prorrogação e demais documentos da instrução processual; {_b('APROVAR')} a minuta "
       "definitiva do Termo Aditivo (doc. nº #docminuta)."),
    _p(f"{_b('II. AUTORIZAR')}, nos termos dos arts. 106 e 107 da Lei Federal nº 14.133/2021, a prorrogação do Contrato nº #nrocontrato, celebrado entre a "
       "Secretaria de Parcerias em Investimentos e a empresa #razaosocialempresa, inscrita no CNPJ/MF sob o nº #cnpjempresa, por mais #mesesprorrogacao, a partir "
       "de #inicioprorrogacao, com término em #fimprorrogacao."),
    _p(f"{_b('III. AUTORIZAR')} a emissão de nota de empenho no valor total de #valorempenho, destinado ao exercício de #anoempenho, conforme demonstrado na "
       "planilha acostada aos autos (doc. nº #docplanilha)."),
    _p(f"{_b('IV.')} Na sequência, {_b('ENCAMINHAR')} os autos à Diretoria de Orçamento e Finanças, para emissão da Nota de Empenho, procedendo-se, se "
       "necessário, à verificação da atualidade das certidões e consultas cadastrais da contratada (CADIN estadual, e-Sanções, CEIS/CNEP, TCE-SP, entre outras)."),
    _p(f"{_b('V.')} Após a emissão da respectiva Nota de Empenho, {_b('ENCAMINHEM-SE')} os autos à Coordenadoria de Contratações e Convênios, para formalização "
       "do Termo Aditivo, coleta de assinaturas e adoção dos demais atos administrativos pertinentes."),
    _direita("São Paulo, na data da assinatura digital."),
    _centro("#responsavelnome") + _p("#responsavelcargo", "center"),
    _p(_b("De acordo. Acolho e aprovo a presente instrução.")),
    _centro("#coordenadornome") + _p("Coordenador da Coordenadoria de Contratação e Convênios", "center"),
    _p(_b("À Subsecretaria de Gestão Corporativa")),
    _p("De acordo. Acolho as manifestações constantes dos autos e as providências adotadas pela Coordenadoria de Contratações e Convênios, e submeto os autos "
       "ao Sr. Subsecretário de Gestão Corporativa para:"),
    _lista("providenciar as deliberações constantes do item 9, inciso I, alíneas “a” e “b”, bem como a adoção das providências previstas no item 9, incisos II e III;",
           "na sequência, à Diretoria de Orçamento e Finanças, para emissão do empenho, conforme indicado no item 9, III, observadas as verificações cadastrais pertinentes;",
           "após, retornar os autos à Coordenadoria de Contratações e Convênios para adoção das providências subsequentes, nos termos do item 9, inciso V."),
    _centro("#diretornome") + _p("Diretoria de Gestão Administrativa", "center"),
])

DESPACHO_AUTORIZACAO = "".join([
    _p(f"{_b('PROCESSO nº:')} #numeroprocesso<br/>{_b('INTERESSADO:')} Secretaria de Parcerias em Investimentos<br/>{_b('ASSUNTO:')} #objetodocontrato "
       "(Contrato #nrocontrato)", "left"),
    _centro("DESPACHO DE AUTORIZAÇÃO DA PRORROGAÇÃO"),
    _p("Trata-se de procedimento destinado à formalização do #nrotermo Termo Aditivo ao Termo de Contrato nº #nrocontrato, firmado com a empresa "
       "#razaosocialempresa, tendo por objeto #objetodocontrato."),
    _p("Quanto à análise jurídica, o presente caso encontra-se abrangido pelo Parecer Referencial #parecerreferencial (doc. nº #docparecerreferencial), tendo "
       "sido verificado o atendimento dos requisitos e condicionantes nele estabelecidos. Dessa forma, por se tratar de hipótese já previamente analisada pela "
       "Consultoria Jurídica, dispensa-se a elaboração de nova manifestação jurídica individualizada, não havendo óbice ao prosseguimento da prorrogação contratual."),
    _p("Nesse contexto, verifica-se, à luz das manifestações técnicas constantes dos autos, em especial da área técnica (doc. nº #docjustificativa), da unidade de "
       "contratações e da unidade de gestão administrativa (doc. nº #docdespacho), que a instrução processual observou regularmente os requisitos legais e "
       "contratuais aplicáveis à presente prorrogação, encontrando-se o expediente devidamente instruído com a manifestação de interesse da contratada, a "
       "justificativa da área gestora quanto à necessidade e vantajosidade da continuidade da contratação, a pesquisa de preços realizada, a minuta do termo "
       "aditivo e a correspondente disponibilidade orçamentária."),
    _p("Verifica-se, ainda, que foram observados os requisitos legais e contratuais para a prorrogação da vigência do ajuste, em especial a manifestação "
       "favorável da área gestora quanto à necessidade e à vantajosidade da continuidade da contratação, a concordância da contratada e a disponibilidade de "
       "recursos orçamentários. A prorrogação contratual encontra respaldo nos arts. 106 e 107 da Lei Federal nº 14.133/2021, bem como na Cláusula de Vigência e "
       "Prorrogação do Contrato #nrocontrato, que autorizam a renovação sucessiva de contratos de serviços contínuos, desde que mantidas as condições pactuadas "
       "e demonstrada a vantajosidade para a Administração, encontrando-se o procedimento devidamente instruído e apto à formalização do Termo Aditivo."),
    _p("Diante do exposto, e considerando as manifestações das áreas técnicas competentes, e no uso da competência que me é conferida pela "
       f"{_b('Resolução SPI nº 17/2025')}:"),
    _p(f"{_b('CONSIGNO')} que foi devidamente assinada a Declaração de Atendimento ao Parecer Referencial aplicável (doc. nº #docdeclaracao), em conformidade com "
       "o modelo constante dos Anexos do referido parecer, restando atendida a providência prevista no opinativo jurídico."),
    _p(f"{_b('ACOLHO E APROVO')} as justificativas da prorrogação (doc. nº #docjustificativa) e demais documentos da instrução processual, estando demonstrada a "
       "necessidade do aditivo;"),
    _p(f"{_b('APROVO')} a minuta do Termo Aditivo Definitivo ao Contrato #nrocontrato (doc. nº #docminuta)."),
    _p(f"{_b('AUTORIZO')}, nos termos dos arts. 106 e 107 da Lei Federal nº 14.133/2021, bem como na Cláusula de Vigência do contrato, a prorrogação do "
       "Contrato #nrocontrato, celebrado entre a Secretaria de Parcerias em Investimentos e a empresa #razaosocialempresa, inscrita no CNPJ/MF sob o nº "
       "#cnpjempresa, por mais #mesesprorrogacao, a partir de #inicioprorrogacao, com término em #fimprorrogacao."),
    _p(f"{_b('AUTORIZO')} a emissão de nota de empenho no valor total de #valorempenho, destinado ao exercício de #anoempenho, conforme demonstrado na planilha "
       "acostada aos autos (doc. nº #docplanilha), sendo a despesa suportada pela reserva orçamentária constante (doc. nº #docreserva)."),
    _p("Registra-se a necessidade de verificar a atualidade das certidões e consultas cadastrais da contratada, promovendo-se, se necessário, a sua "
       "atualização, inclusive mediante consultas ao CADIN estadual, E-SANÇÕES, CEIS/CNEP, relação de apenados do TCE-SP e demais certidões e consultas "
       "pertinentes, especialmente aquelas necessárias à emissão da nota de empenho."),
    _p(f"Na sequência, {_b('ENCAMINHEM-SE')} os autos à Diretoria de Orçamento e Finanças para emissão da respectiva Nota de Empenho Complementar, observados "
       "os termos e valores acima consignados."),
    _p("Restituam-se os autos ao setor competente para adoção das providências subsequentes cabíveis, com estrita observância das disposições legais aplicáveis."),
    _direita("São Paulo, na data da assinatura digital."),
    _centro("#autoridadenome") + _p("#autoridadecargo", "center"),
])

# variante → (nome do modelo, HTML)
MODELOS: dict[str, tuple[str, str]] = {
    "despacho_instrucao": ("Despacho de instrução da prorrogação (CCC/DGA → SSGC)", DESPACHO_INSTRUCAO),
    "declaracao_atendimento_licitacao": ("Declaração de Atendimento — contrato de licitação (Anexo II)", DECLARACAO_LICITACAO),
    "declaracao_atendimento_direta": ("Declaração de Atendimento — dispensa ou inexigibilidade (Anexo III)", DECLARACAO_DIRETA),
    "minuta_aditivo": ("Minuta do Termo de Aditamento (Anexo I)", MINUTA_ADITIVO),
    "termo_ciencia": ("Termo de Ciência e de Notificação (TCE-SP)", TERMO_CIENCIA),
    "declaracao_tce": ("Declaração de documentos à disposição do TCE-SP", DECLARACAO_TCE),
    "despacho_autorizacao": ("Despacho de autorização da prorrogação", DESPACHO_AUTORIZACAO),
}
