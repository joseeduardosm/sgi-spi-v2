# Diário de bordo do contrato (`/api/contratos/{contrato_id}/diario`)

Tag no OpenAPI: **Contratos: diário de bordo**. Implementação: `backend/app/api/routes/contratos/diario.py`.
Regras em `backend/app/services/contratos/servico_diario.py`; e-mails em `servico_notificacoes.py`.

## Finalidade

A equipe do contrato relata as ocorrências da execução. Quando a ocorrência implicar **glosa**, indica os
itens do contrato e as quantidades a glosar. As glosas limitam o que pode ser medido na competência (ver
[contratos-execucao.md](contratos-execucao.md#medição-saldo-glosas-e-saldo-líquido)). Cada ocorrência é
enviada por e-mail à equipe e aos prepostos da contratada, com até **5 anexos** (fotos, PDFs, planilhas…).
A ocorrência pode também **impactar a avaliação da qualidade**: fica vinculada a itens do formulário de
avaliação ativo e pesa na avaliação da competência da data (ver
[contratos-execucao.md](contratos-execucao.md)).

## Regras

- **Leitura:** ACL `contratos` ≥ LEITURA.
- **Registro e reenvio de e-mail:** quem pode editar o contrato: criador, integrante **vigente** da equipe ou
  SuperRoot, sempre com ACL ≥ MODIFICACAO. Os demais recebem `403 acesso_negado`.
- **Imutável:** a ocorrência não é editada nem excluída (registro histórico). Correções entram como nova ocorrência.
- **Data da ocorrência:** o dia em que aconteceu. Não pode ser futura nem anterior ao início do contrato. O
  registro guarda também a data e a hora em que foi feito (`criado_em`), quem registrou e o papel dele.
- **Glosa:** com `possui_glosa = true`, ao menos um item **deste contrato**, quantidade > 0 (até 4 casas) e sem
  repetir item. Sem glosa, nenhum item.
- **Anexos:** até **5 arquivos** por ocorrência, enviados no mesmo registro (multipart). Formatos gerais do
  sistema, **conferidos pelo conteúdo** (extensão trocada ou formato não aceito → `400 invalido` com o nome do
  arquivo); soma dos tamanhos até o limite `ANEXOS_TAMANHO_MAXIMO_MB`. Os anexos seguem a ocorrência: não são
  trocados nem removidos depois.
- **Impacto na avaliação da qualidade:** com `impacta_avaliacao = true`, ao menos um item de `itens_avaliacao`,
  todos do **formulário de avaliação ativo** do contrato (`400` com item de outro formulário; sem formulário
  ativo → `400` "O contrato não tem formulário de avaliação ativo"). Sem impacto, nenhum item (`422`). O registro
  guarda o id, o nome e o grupo do item (retrato do momento).
  - Na avaliação da competência cujo período contém a data da ocorrência, os itens vinculados mostram a
    ocorrência, e **nota máxima nesses itens exige justificativa** (inicial e gestor). O vínculo é pelo id do item
    e, se o formulário da competência for de outra versão, pelo nome do item.
  - O PDF da avaliação traz a seção "Ocorrências do diário de bordo consideradas".
  - Ocorrência registrada **depois** de salva a avaliação gera aviso em `avisos[]` da competência (revisar as
    notas), enquanto a avaliação não estiver concluída.
- **Competência da glosa:** a glosa vale na competência regular cujo período contém a data da ocorrência. Se a
  medição dela já foi concluída quando a glosa é registrada, a glosa só é aplicada se a medição for reaberta
  (a leitura traz `medicao_ja_concluida = true` e o e-mail avisa).
- **E-mail** (em segundo plano, pelo [servidor SMTP](smtp.md) ativo):
  - destinatários: e-mails dos integrantes vigentes da equipe (perfil do usuário) e dos prepostos **ativos**
    da empresa contratada, sem repetição;
  - "Responder para": a equipe vigente, para que as respostas não voltem à caixa de envio;
  - assunto `[Diário de bordo] Contrato NNN/AAAA — ocorrência de dd/mm/aaaa`; corpo com contrato, contratada,
    data, quem registrou, relato, "Haverá glosa: Sim/Não" com os itens e quantidades, "Impacta a avaliação da
    qualidade: Sim/Não" com os itens e a lista de anexos;
  - **os anexos vão no e-mail**. Se a soma passar de 15 MB, não são anexados e o texto avisa que estão
    disponíveis no sistema;
  - o resultado (destinatários, sucesso ou erro) fica em `email`. Sem servidor SMTP ativo ou sem destinatário
    com e-mail, a ocorrência é salva e o erro fica registrado; use o reenvio.
- **Auditoria:** `contrato.diario.registrar`.

## Schemas

### `GravacaoOcorrencia` (requisição)

Enviada no campo `dados` (texto JSON) do `multipart/form-data`; os arquivos vão em `arquivos` (repetido, 0 a 5).
JSON inválido ou fora das regras → `422 validacao`.

| Campo | Tipo | Regras |
|---|---|---|
| `data_ocorrencia` | date | Obrigatória; não futura; não anterior ao início do contrato |
| `descricao` | string | 1 a 4000 caracteres |
| `possui_glosa` | boolean | A ocorrência implicará glosa? |
| `glosas` | `[{item_id, quantidade}]` | Só com `possui_glosa`; item do contrato; quantidade > 0; sem repetir item |
| `impacta_avaliacao` | boolean | A ocorrência impacta a avaliação da qualidade? (padrão `false`) |
| `itens_avaliacao` | `string[]` | Ids de itens do formulário ativo (`DiarioContrato.itens_avaliacao`). Obrigatório com impacto; vazio sem impacto; até 50 |

### `LeituraOcorrencia` (resposta)

`id`, `data_ocorrencia`, `descricao`, `possui_glosa`, `glosas[]` (`item_id`, `descricao_item`, `quantidade`),
`registrada_por_id`, `registrada_por_nome`, `registrada_por_papel` (`gestor`, `fiscal_tecnico`… ou vazio),
`criado_em` (data e hora do registro), `competencia_rotulo` (competência da data, se houver),
`medicao_ja_concluida` (glosa registrada depois de concluída a medição da competência), `anexos[]` (`id`,
`nome`, `tamanho` em bytes, `tipo`), `impacta_avaliacao`, `itens_avaliacao[]` (`item_id`, `item_nome`,
`grupo_nome`) e `email` (`enviado_em`, `ok`, `destinatarios[]`, `erro`; `enviado_em` nulo enquanto o
envio em segundo plano não terminou).

### `DiarioContrato` (resposta do `GET`)

`ocorrencias[]` (em ordem de registro, a mais antiga primeiro), `pode_registrar` e `itens[]` (`id`, `ordem`,
`descricao`, `tipo`) para o combobox da glosa e `itens_avaliacao[]` (`id`, `nome`, `grupo`): itens do formulário
de avaliação ativo, para marcar o impacto (vazio sem formulário ativo).

## Endpoints

| Método e caminho | Descrição | Respostas |
|---|---|---|
| `GET /api/contratos/{contrato_id}/diario` | Diário completo | `200` `DiarioContrato`, `404` |
| `POST /api/contratos/{contrato_id}/diario` | `multipart/form-data` (`dados` + `arquivos`). Registra a ocorrência e agenda o e-mail | `201` `LeituraOcorrencia`, `400 invalido`, `403`, `404`, `422` |
| `GET /api/contratos/{contrato_id}/diario/{ocorrencia_id}/anexos/{anexo_id}` | Baixa um anexo da ocorrência (ACL LEITURA) | `200` arquivo, `404` |
| `POST /api/contratos/{contrato_id}/diario/{ocorrencia_id}/reenviar` | Reenvia o e-mail (síncrono) e devolve a ocorrência com o novo resultado | `200`, `403`, `404` |
| `GET /api/contratos/{contrato_id}/diario/pdf?inicio=&fim=` | Diário em PDF (A4 paisagem): ocorrências com data no período (limites inclusivos; sem período = todo o contrato) e glosas por item. Nome `DIARIO_DE_BORDO_SPI_NNN_AAAA.pdf` | `200` `application/pdf`, `404` |

Exemplo de registro com glosa, impacto e uma foto:

```bash
curl -X POST .../api/contratos/{contrato_id}/diario \
  -H "Authorization: Bearer <token>" \
  -F 'dados={"data_ocorrencia":"2026-01-10","descricao":"Posto de limpeza descoberto das 8h às 12h.","possui_glosa":true,"glosas":[{"item_id":"8f1c…","quantidade":"0.5"}],"impacta_avaliacao":true,"itens_avaliacao":["pontualidade"]}' \
  -F 'arquivos=@posto.jpg'
```

## Consumo no Angular

- Aba **Diário de bordo** do detalhe do contrato (à esquerda de **Execução**).
- Formulário (se `pode_registrar`): data, ocorrência e "Esta ocorrência implicará glosa?". Com "Sim", linhas com
  combobox dos itens e quantidade.
- "Esta ocorrência impacta a avaliação da qualidade?" (Não/Sim; desabilitado sem formulário ativo). Com "Sim",
  caixas de marcar dos `itens_avaliacao`, agrupadas por `grupo`.
- "+ Anexar arquivos": até 5, listados com tamanho e "remover" antes de registrar. O envio usa `FormData`
  (`ContratosApiService.registrarOcorrencia(id, dados, arquivos)`).
- Lista em forma de chat: quem registrou (nome e papel), data da ocorrência, data e hora do registro, relato,
  glosas, o selo "Impacta a avaliação" com os itens, os anexos (links de download,
  `ContratosApiService.baixarAnexoOcorrencia`) e o resultado do e-mail, com **Reenviar** em caso de falha. Botão **Baixar PDF**.


**E-mail da ocorrência:** o envio por e-mail à equipe e aos prepostos só acontece com `enviar_email = true` em `dados` (padrão `false`); o reenvio manual continua disponível.
