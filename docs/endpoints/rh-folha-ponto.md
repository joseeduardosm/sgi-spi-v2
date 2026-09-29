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
| `422` | `validacao` | `competencia` ausente ou fora do formato `AAAA-MM` |

A geração é auditada como `rh.folha_ponto` (competência).

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
