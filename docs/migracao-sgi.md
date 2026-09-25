# Migração do Módulo de Contratos do SGI SPI

Traz os dados do Módulo de Contratos do SGI SPI (10.23.1.220, PostgreSQL `sgi_spi`, schema `sgi`) para o
contratos-spi. São dois scripts:

| Script | O que faz |
|---|---|
| `scripts/extrair-contratos-sgi.py` | Gera o **pacote** a partir do SGI, **somente leitura** |
| `scripts/migrar-contratos-sgi.py` | Carrega o pacote no banco do contratos-spi, confere os dados e copia os anexos |

## 1. Extração (somente leitura no SGI)

```bash
cd /home/administrador/projeto
SGI_SENHA='...' backend/.venv/bin/python scripts/extrair-contratos-sgi.py /caminho/do/pacote
```

- Conecta por SSH (`SGI_HOST`, padrão `10.23.1.220`; `SGI_USUARIO`, padrão `administrador`). A mesma senha é
  usada no `sudo` para ler o banco como `postgres`. Sem `SGI_SENHA`, o script pede a senha.
- Nada é gravado no SGI:
  - as tabelas saem numa única transação `repeatable read read only`, com `\copy ... to stdout`, para que todas
    reflitam o mesmo instante;
  - os anexos vêm por SFTP, e o SHA-256 de cada um é conferido;
  - o mapa de usuários (`usuarios.csv`) é montado lá a partir do `portal-data.json`, **sem senhas nem hashes**.
- O formato é o do `deploy/sql/backup-modulo-contratos.sh` do SGI (`dados/NN_tabela.csv`, `usuarios.csv`,
  `anexos/`, `MANIFESTO.txt`), mais a tabela `contract_execution_commitment_note_selections`, criada no SGI em
  24/09/2026, que liga as várias NEs a cada competência.
- O pacote contém dados pessoais (CPF de prepostos, nomes, e-mails) e documentos contratuais. A pasta é criada
  com permissão 700. Apague-a depois da virada.

## 2. Carga

```bash
cd /home/administrador/projeto/backend
.venv/bin/python ../scripts/migrar-contratos-sgi.py /caminho/do/pacote                         # ensaio
.venv/bin/python ../scripts/migrar-contratos-sgi.py /caminho/do/pacote --gravar                # carga
.venv/bin/python ../scripts/migrar-contratos-sgi.py /caminho/do/pacote --gravar --substituir   # recarga (virada)
```

- **Ensaio** (padrão): carrega tudo numa transação, confere e **desfaz**. Não copia arquivos.
- `--gravar`: grava, desde que a conferência não aponte divergência. Os anexos são copiados para
  `ANEXOS_DIRETORIO` com a mesma chave do SGI (`AAAA/MM/<uuid>.pdf`) e o SHA-256 conferido. Qualquer falha
  desfaz tudo.
- `--substituir`: apaga antes contratos, empresas, anexos do módulo e a auditoria migrada (`sgi.*`), na mesma
  transação. Sem essa opção, a carga só roda com o módulo vazio.

### De-para

| SGI | contratos-spi |
|---|---|
| UUIDs de todas as tabelas | preservados |
| `*UserId` (id do `portal-data.json`) | usuário local com o mesmo login ou o mesmo id externo (AD). A conta administrativa local do SGI (`admin`) vira o `root`. Quem não existir é criado **inativo e sem senha** |
| Papéis `Manager`, `ManagerSubstitute`, `AdministrativeInspector`… | `gestor`, `gestor_suplente`, `fiscal_administrativo`… |
| Assinatura do ateste por suplente "em exercício" | posto do titular (`gestor`, `fiscal_administrativo` ou `fiscal_tecnico`) |
| Etapas `Measurement` … `Download`, `BankOrder`, `Completed` | `medicao` … `consolidado`, `ordem_bancaria`, `concluida` |
| `ExecutionPeriodicity` (`Monthly`, `Bimonthly`…) | `periodicidade_meses` (1, 2, 3, 6, 12) |
| `contract_documents` sem arquivo (as 23 posições do catálogo) | não migradas (aqui só existe o documento que tem PDF) |
| `contract_term_extensions` | prorrogação + termo aditivo nos documentos importantes (código 024 em diante) |
| `contracts.AdjustedGlobalValue` | `valor_global_reajustado`, só se a vigência reajustada ainda for a atual (a prorrogação descarta a fotografia) |
| `DefinitionJson` do formulário (`Scale`, `Ranges`, `Groups`) | `definicao` (`escala`, `faixas`, `grupos`), com os mesmos ids de grupos e itens |
| `stored_attachments.Category` (`contract-…`) | `categoria` (`contrato-…`) |
| `audit_events` | `auditoria` com `acao = sgi.<ação>`, `alvo_tipo` `contrato`/`empresa` e o payload em `dados.legado` |

As fotografias não são recalculadas: itens e preços da medição, itens do reajuste, nomes nas ciências e o
formulário copiado na avaliação entram como estão.

**Competências:** entram como estão, com os períodos do SGI, que seguem o aniversário do contrato (ex.: 06/08 a
05/09). A geração daqui não cria período que se sobreponha a elas. Competências novas, por exemplo depois de
uma prorrogação, seguem o mês civil.

### Conferência

A gravação é bloqueada se a carga divergir do pacote em qualquer destes pontos:
- soma dos débitos de cada NE;
- etapa de cada competência;
- quantidade de contratos, itens, competências, itens de medição, itens de reajuste e anexos.

O valor global calculado aqui (mês a mês, 30/360, pró-rata por item) é comparado com a fotografia do SGI só
como **aviso**, porque os dois sistemas contam os meses de formas diferentes.

## Pela tela (botão "Importar do SGI")

O SuperRoot pode fazer a extração e a carga com substituição (seções 1 e 2) pela carteira de contratos, informando
a senha da origem (SGI) e a deste servidor. Ver [endpoints/contratos-migracao-sgi.md](endpoints/contratos-migracao-sgi.md).
O pacote é apagado ao final.

Para só apagar os dados do módulo (e os arquivos deles), sem carregar nada:

```bash
cd /home/administrador/projeto/backend
.venv/bin/python ../scripts/migrar-contratos-sgi.py /dev/null --apenas-limpar
```

## 3. Virada para produção

1. Avise os usuários e congele o uso do módulo no SGI.
2. Gere um pacote novo (seção 1).
3. Rode a carga com `--gravar --substituir` (seção 2). Tudo o que foi feito no contratos-spi desde a carga
   anterior é **apagado** e substituído pelo SGI.
4. Confira alguns contratos na tela e apague o pacote.

## Histórico

| Data | Pacote | Resultado |
|---|---|---|
| 24/09/2026 | extração somente leitura do 10.23.1.220 | 38 empresas, 40 contratos, 78 competências, 8 NEs, 14 reajustes, 5 prorrogações, 565 anexos (SHA-256 conferido), 1.128 eventos de auditoria. Conferência sem divergências. |
