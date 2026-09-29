# Módulo RH: folha de ponto em PDF (`/api/rh/folha-ponto`)

Tag no OpenAPI: **Módulo RH**. Implementação:
- rotas: `backend/app/api/routes/rh.py`;
- PDF: `backend/app/services/rh/folha_ponto.py` (reportlab, A4 retrato), no modelo de frequência da SPI (`apoio/10-2026 - FOLHA DE FREQUENCIA.doc`).

## Finalidade

Cada usuário gera a **própria** folha de ponto do mês, pronta para imprimir, assinar e entregar ao superior imediato.

## Endpoints

Autenticação: `Authorization: Bearer <token>` (perfil em dia; ver [autenticacao.md](autenticacao.md)).

| Método e caminho | Resposta |
|---|---|
| `GET /api/rh/folha-ponto/competencias` | `CompetenciaFolha[]`: do mês atual (fuso de São Paulo) 12 meses para trás e 2 para frente, do mais recente ao mais antigo |
| `GET /api/rh/folha-ponto?competencia=AAAA-MM` | `200 application/pdf`, anexo `folha-ponto-AAAA-MM-<login>.pdf` |

**`CompetenciaFolha`:** `valor` (`"2026-10"`), `rotulo` (`"Outubro/2026"`), `atual` (mês corrente, pré-selecionado).

```json
[{ "valor": "2026-12", "rotulo": "Dezembro/2026", "atual": false }, { "valor": "2026-11", "rotulo": "Novembro/2026", "atual": false },
 { "valor": "2026-10", "rotulo": "Outubro/2026", "atual": true }]
```

### Erros

| HTTP | `codigo` | Causa |
|---|---|---|
| `400` | `invalido` | Competência fora da janela ("Competência fora do período disponível (últimos 12 meses e próximos 2).") |
| `401` | `nao_autenticado` | Sem token ou token inválido |
| `403` | `revisao_perfil_obrigatoria` | Perfil pendente |
| `409` | `folha_cadastro_pendente` | O usuário tem alteração de cadastro aguardando validação da CGP (os campos vêm no `detalhe`) |
| `409` | `folha_dados_incompletos` | Faltam dados funcionais: jornada de trabalho, horário de trabalho, intervalo de almoço e descanso, RG/CIN nº ou RS/PV nº (os que faltam vêm no `detalhe`) |
| `422` | `validacao` | `competencia` ausente ou fora do formato `AAAA-MM` |

A geração é auditada como `rh.folha_ponto` (competência).

### Pré-requisitos e aviso à CGP

A folha só é gerada quando **não há alteração de cadastro aguardando validação** e os **dados funcionais obrigatórios** estão preenchidos. Regime de plantão e horário de estudante já valem "Não" por padrão e não bloqueiam. A pendência de cadastro é conferida primeiro.

Quando a folha é recusada (`409`):
- **todos da CGP** recebem na caixa de mensagens, com e-mail oficial:
  - "[Nome] quer baixar a folha de ponto, mas ainda não tem os dados preenchidos", com a lista dos campos; ou
  - "[Nome] quer baixar a folha de ponto, mas tem alterações de cadastro aguardando validação".
  - O link leva a RH › Validações do usuário.
  - No máximo um aviso por motivo, por usuário e por dia (chaves `folha-ponto:dados:{usuario}:{AAAAMMDD}` e `folha-ponto:validacao:{usuario}:{AAAAMMDD}`).
- Os avisos são **encerrados** sozinhos quando a CGP completa os dados funcionais ou quando não resta alteração pendente (validada ou recusada).

## Conteúdo do PDF

A4 retrato, **frente e verso**, conservando a estrutura do modelo `apoio/10-2026 - FOLHA DE FREQUENCIA.doc`: a mesma ordem de blocos, os mesmos textos e rótulos e a mesma disposição das colunas. O sistema preenche só o setor, a competência, a identificação e as marcações dos dias.

**Frente: a tabela do mês inteira**
- **Cabeçalho em caixa** (igual na frente e no verso):
  - à esquerda, o brasão com "GOVERNO DO ESTADO DE SÃO PAULO / Secretaria de Parcerias em Investimentos";
  - à direita, "GOVERNO DO ESTADO DE SÃO PAULO", "SECRETARIA DE PARCERIAS EM INVESTIMENTOS", o **setor** do usuário (Departamento do perfil, no lugar de "Unidade") e "REGISTRO DE PONTO OUTUBRO/2026".
- **Identificação** em duas colunas, com o rótulo em negrito:
  - esquerda: Servidor (nome em maiúsculas), Função (cargo do perfil), Jornada de Trabalho ("40 horas/semanais"), Horário de Trabalho ("das 9:00 às 18:00"), Intervalo de Almoço e Descanso ("das 12:00 às 13:00");
  - direita: RG/CIN nº, RS/PV nº, Regime de Plantão (Sim/Não), Horário de Estudante (Sim/Não).
  - Os campos além de nome e cargo vêm dos dados funcionais da CGP ([rh-cadastro.md](rh-cadastro.md)); o que não foi informado sai em branco.
- **Tabela diária** (todos os dias do mês): Dia | Entrada (Hora, Assinatura) | Saída (Hora, Assinatura) | Observações | Visto do Superior Imediato. Nas linhas marcadas, "---------" na Hora e a marca em **vermelho** na Assinatura, de Entrada e de Saída, nesta prioridade:
  1. sábado e domingo: SÁBADO/DOMINGO;
  2. feriado ou ponto facultativo cadastrado: FERIADO/PONTO FACULTATIVO, com a descrição em Observações;
  3. férias ou licença-prêmio **aprovadas ou gozadas**: FÉRIAS/LICENÇA-PRÊMIO, com o período em Observações no primeiro dia do mês em que aparecem. Pedidos pendentes, recusados e cancelados não entram.
- **Informações financeiras** logo abaixo da tabela, em branco para preencher à mão:
  - FÉRIAS, MÉDIA de GTN, ACA (entre 8 e 12 / superior a 12 horas diárias), GTN e percentual;
  - SERVIÇO EXTRAORDINÁRIO (20% / 10%), SUBSTITUIÇÃO EVENTUAL (cargo/função substituído), VALE TRANSPORTE - CLT (Sim/Não).
- **Assinaturas:** do servidor e do superior imediato, com a data.

**Verso: só as anotações.** O mesmo cabeçalho, "CONSOLIDAÇÃO" com 42 linhas pautadas, "Data ______/______/_______" e a assinatura do superior imediato ou do responsável.

## Consumo no Angular

- **Menu do usuário** (canto superior direito, `layout-autenticado`): item "Folha de ponto" abaixo de "Meu perfil" (oculto com o perfil pendente).
- **Janela** `features/rh/folha-ponto-dialogo.component.ts`: lista de competências (atual pré-selecionada) e "Gerar PDF", que baixa o arquivo (`RhApiService.folhaPonto`, com `baixarArquivo`).
- **Bloqueio:** com `409 folha_dados_incompletos` ou `folha_cadastro_pendente`, a janela fecha e abre o aviso modal "Folha de ponto indisponível" com o `detalhe` da API (que já informa que a CGP foi avisada). `baixarArquivo` converte o corpo de erro que chega como `Blob` de volta para JSON, então o `detalhe` aparece também nos demais downloads.
