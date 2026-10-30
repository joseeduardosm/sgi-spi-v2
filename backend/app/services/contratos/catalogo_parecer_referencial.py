# Criado por José Eduardo Santana Martins
# Este arquivo serve para listar os 37 itens do checklist do Parecer Referencial NLC nº 1/2026 (Modelo 6 da SPI) e a linha de cada um na planilha.
"""Catálogo do checklist "Lista de verificação da aplicabilidade do Parecer Referencial NLC nº 1/2026".

Cada item traz o texto da pergunta, a referência ao parecer e a **linha** da planilha-modelo (`recursos/prorrogacao/checklist-parecer-referencial.xlsx`)
onde a resposta (coluna C) e o documento/página (coluna D) são escritos na exportação. A ordem e os grupos seguem o Modelo 6.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ItemParecer:
    numero: int
    grupo: str
    texto: str
    referencia: str
    linha: int


_G1 = "Validação do enquadramento"
_G2 = "Previsão, limites e continuidade"
_G3 = "Vantajosidade econômica e técnica"
_G4 = "Regularidade da execução e do contratado"
_G5 = "Aspectos orçamentários e financeiros"
_G6 = "Garantia contratual"
_G7 = "Contratos celebrados por dispensa em razão do valor"
_G8 = "Pedido de repactuação (se houver)"
_G9 = "Formalização e publicidade"

_LINHAS = [
    (_G1, "O contrato é regido pela Lei federal nº 14.133/2021?", "Parecer, item 13, ‘a’.", 8),
    (_G1, "O objeto do contrato é a prestação de serviços contínuos?", "Parecer, item 13, ‘b’, e Capítulo V.", 10),
    (_G1, "O termo aditivo será celebrado antes do término da vigência do contrato e sem solução de continuidade?", "Parecer, item 13, ‘c’.", 13),
    (_G1, "O aditivo visa apenas à prorrogação do prazo de vigência?", "Parecer, item 13, ‘d’.", 16),
    (_G1, "O prazo de prorrogação pretendido é igual ou inferior ao prazo inicialmente previsto?", "Parecer, item 13, ‘e’, e nota de rodapé nº 4.", 19),
    (_G1, "Não se trata de contratação emergencial, convênio ou parceria com o terceiro setor?", "Parecer, item 13, ‘f’ e ‘g’.", 22),
    (_G1, "Não há alterações na minuta padronizada do termo aditivo (Anexo I)?", "Parecer, item 12.", 25),
    (_G1, "O Parecer Referencial está dentro do prazo de validade (1 ano da emissão)?", "Parecer, item 103.", 28),
    (_G1, "O processo foi instruído com: (i) cópia integral do Parecer Referencial incluindo o despacho de aprovação; (ii) Declaração de Atendimento da autoridade "
          "competente; e (iii) documentação/certidões atualizadas que comprovem o atendimento dos pressupostos do Parecer?", "Parecer, item 102; Anexo III.", 31),
    (_G2, "Existe previsão de prorrogação no Edital/Aviso ou no Contrato (no caso de contratação direta sem disputa)?", "Parecer, itens 21, ‘ii’, e 33.", 34),
    (_G2, "Há justificativa técnica caracterizando o serviço como contínuo?", "Parecer, itens 21, ‘iv’ e 28.", 36),
    (_G2, "A Administração declarou, por escrito, o interesse motivado na manutenção do contrato?", "Parecer, itens 21, ‘iv’ e 47.", 39),
    (_G2, "O Contratado manifestou interesse expresso e por escrito na prorrogação dentro do prazo?", "Parecer, item 44, ‘v’, e Capítulo XIII.", 42),
    (_G2, "A vigência total do contrato (somadas prorrogações anteriores + a pretendida) não ultrapassa 10 anos?", "Parecer, item 20 e 21, ‘iii’.", 45),
    (_G3, "Foi realizada pesquisa de preços atual e metodologicamente adequada demonstrando que os preços permanecem vantajosos?", "Parecer, itens 38 e 44, ‘vi’.", 50),
    (_G3, "Foram excluídos custos não renováveis já pagos ou amortizados (ex.: mobilização, treinamento inicial, custos de transição), se houver?",
     "Parecer, itens 21, ‘vii’, e 39.", 54),
    (_G3, "Foi verificada a adequação aos valores referenciais do Estado (CADTERC, PRODESP), se houver?", "Parecer, item 43.", 58),
    (_G3, "Foi considerada a possibilidade de negociação com o Contratado para se obter condições mais vantajosas?", "Parecer, item 23.", 61),
    (_G3, "Há manifestação conclusiva da autoridade sobre a vantajosidade em comparação a alternativas?", "Parecer, item 44, ‘ix’, e 64.", 64),
    (_G4, "Consta nos autos relatório do gestor e do fiscal com manifestações expressas sobre a regularidade da execução, demonstrando o cumprimento das "
          "obrigações contratuais e dos níveis de desempenho previstos no edital/aviso/contrato (quantidade, qualidade, tempestividade e modo de execução)?",
     "Parecer, itens 21, ‘iv’, e 45.", 68),
    (_G4, "O contratado mantém as condições iniciais de habilitação? (Verificar certidões fiscais, trabalhistas, previdenciárias e FGTS)",
     "Parecer, itens 21, ‘viii’, e Capítulo IX.", 74),
    (_G4, "Foram consultados os cadastros de sanções e impedimentos (SICAF, CADIN Estadual, e-Sanções, CEIS, CNEP, CNCIAI e TCESP)?", "Parecer, item 24.", 78),
    (_G4, "Foi consultada junto aos cadastros administrados pela Receita Federal a situação do devedor para verificar a sua contumácia, na forma da Lei "
          "Complementar federal nº 225/2026?", "Parecer, item 25.", 82),
    (_G5, "Há prévio empenho para as parcelas do exercício corrente (indicação de classificação funcional e categoria econômica)?",
     "Parecer, item 21, ‘x’, e Capítulo X.", 87),
    (_G5, "Caso a contratação ultrapasse o exercício financeiro, há previsão no Plano Plurianual (PPA)?", "Parecer, itens 21, ‘xi’, e 63, ‘XI’.", 91),
    (_G5, "Para prorrogações em 2026, foi observado o art. 42 da LRF (disponibilidade de caixa)?", "Parecer, item 55.", 94),
    (_G6, "A garantia de execução (se exigida originalmente) foi renovada ou ajustada para cobrir o novo período e valor?",
     "Parecer, itens 21, ‘ix’, e Capítulo XI.", 98),
    (_G6, "Juntou-se aos autos comprovação da renovação da garantia antes da assinatura do aditivo?", "Parecer, item 61.", 101),
    (_G7, "Foi verificado se o valor total (vigência inicial) respeitou o limite legal da dispensa?", "Parecer, Capítulo XV.", 105),
    (_G7, "Foi demonstrado o cumprimento do limite de despesa da unidade gestora para objetos de mesma natureza no exercício (§ 1º do art. 75)?",
     "Parecer, item 79.", 108),
    (_G7, "Juntou-se aos autos declaração de que a situação fática que justificou a dispensa se mantém?", "Parecer, itens 21, ‘v’, e 44, ‘iv’.", 112),
    (_G8, "O pedido de repactuação foi feito antes da assinatura da prorrogação?", "Parecer, itens 92-96.", 116),
    (_G8, "Se o cálculo da repactuação não estiver pronto na data da prorrogação, foi incluída cláusula de “resguardo” no Termo Aditivo para garantir o direito futuro?",
     "Parecer, item 95.", 119),
    (_G8, "O pedido de repactuação veio acompanhado de demonstração analítica da variação de custos (planilha comparativa)?", "Parecer, itens 83 e 96-98.", 124),
    (_G9, "Foi utilizada a Minuta Padrão de Termo Aditivo (Anexo I do Parecer)?", "Parecer, item 21, ‘xii’.", 129),
    (_G9, "A Declaração de Atendimento (Anexo II ou III) foi preenchida e assinada pela autoridade competente, atestando o cumprimento de todos os itens deste "
          "Parecer Referencial?", "Parecer, item 11, ‘ii’.", 132),
    (_G9, "O Termo Aditivo contém as cláusulas essenciais (período, valor, exclusão de custos não renováveis, garantia, ratificação)?", "Parecer, item 72.", 137),
]

ITENS: list[ItemParecer] = [ItemParecer(i, g, t, r, linha) for i, (g, t, r, linha) in enumerate(_LINHAS, start=1)]
POR_NUMERO: dict[int, ItemParecer] = {i.numero: i for i in ITENS}
assert len(ITENS) == 37
