# SGI SPI — Referência de Estilo
> papel de trabalho limpo, uma caneta vermelha

**Tema:** claro, com tema escuro (`data-tema="escuro"` no `<html>`)
**Base técnica:** Angular + Bootstrap 5.3 + SCSS (`frontend/src/styles.scss` e `frontend/src/styles/`)

**Estado (13/10/2026): implementado** — tokens, selos, chips, menu ativo, sombras→borda, raios, pesos e fontes (Inter + Geist Mono, hospedadas em `node_modules/@fontsource` e empacotadas no build). Este documento consolida a identidade visual que já existe no SGI SPI e incorpora princípios de duas referências externas (Perplexity e Dub, catalogadas no Refero Styles). **A identidade continua sendo a da SPI**: o vermelho institucional, o fundo cinza-claro, a barra lateral escura e as variáveis `--spi-*`. Das referências vêm apenas *regras de disciplina*: um único acento de cor, bordas em vez de sombras, vocabulário fechado de raios e pesos, pílulas de status e densidade compacta.

O SGI é um sistema de trabalho, não um site de marketing: telas densas de dados (contratos, patrimônio, tarefas, RH), muitos formulários e uso também no celular (levantamento de bens em campo). Tudo aqui foi pensado para isso.

---

## 1. Princípios

1. **Um acento só: o vermelho SPI.** Ele marca a ação principal, o item ativo, o foco e os destaques de marca. Nenhuma outra cor "de marca" entra no sistema. *(Perplexity: um único acento cromático.)*
2. **Borda antes de sombra.** Containers são definidos por borda de 1px em `--spi-borda`. Sombra é exceção: menus flutuantes, modais e o anel de foco. *(Dub: elevação por bordas.)*
3. **Cor com significado só no status.** Verde, âmbar, azul e vermelho aparecem em pílulas de status e alertas, sempre em par "fundo suave + texto forte". Nunca como decoração. *(Dub: pílulas de status tingidas.)*
4. **Hierarquia por tamanho e espaço, não por negrito.** Menos pesos tipográficos, usados com intenção. *(Perplexity: faixa estreita de pesos.)*
5. **Vocabulário fechado.** Cinco raios, uma escala de espaçamento, uma escala tipográfica. Valor fora da escala é erro. *(Dub: disciplina de raios.)*
6. **Compacto, mas tocável.** Densidade alta na mesa; alvos de toque de no mínimo 44px no celular.
7. **Funciona nos dois temas.** Nenhum hex fixo em componente: só `var(--spi-*)` ou `var(--cor-*)`.

---

## 2. Cores

### 2.1 Identidade (já existentes — não alterar)

| Token | Claro | Escuro | Função |
|-------|-------|--------|--------|
| `--spi-fundo` | `#f6f7f8` | `#12171c` | Canvas da aplicação |
| `--spi-texto` | `#18222e` | `#e8ecef` | Texto de corpo |
| `--spi-titulo` | `#17202a` | `#f2f4f6` | Títulos |
| `--spi-rotulo` | `#27313d` | `#d5dbe1` | Rótulos de campo |
| `--spi-apagado` | `#586372` | `#a3adb8` | Texto secundário, ícones inativos |
| `--spi-apagado-2` | `#667180` | `#9aa5b1` | Texto auxiliar, introduções |
| `--spi-rodape` | `#7b8490` | `#8a95a1` | Rodapé, placeholders |
| `--spi-borda` | `#e2e5e8` | `#333e49` | Borda estrutural de cards, tabelas, divisórias |
| `--spi-borda-campo` | `#ced5dc` | `#44505c` | Borda de campos e botões contornados |
| `--spi-link` | `#1a56a0` | `#7fb0ee` | Links em texto |

### 2.2 Acento de marca (já existentes — iguais nos dois temas)

| Token | Valor | Função |
|-------|-------|--------|
| `--spi-vermelho` | `#c82331` | **O acento.** Botão principal, item ativo, foco |
| `--spi-vermelho-escuro` | `#a91c28` | Hover/pressionado do botão principal |
| `--spi-vermelho-destaque` | `#bd222d` | Sobretítulos e marcadores de seção |
| `--spi-vermelho-suave` | `#fcecee` / `#3a2226` | Fundo de item ativo, seleção, linha destacada |

### 2.3 Superfícies (implementadas em `styles/_tema.scss`)

Hoje as superfícies usam `--cor-ffffff` e `--cor-fcfcfc` espalhados. A proposta é nomear os níveis:

| Nível | Token | Claro | Escuro | Uso |
|-------|-------|-------|--------|-----|
| 0 | `--spi-fundo` | `#f6f7f8` | `#12171c` | Canvas |
| 1 | `--spi-superficie` | `#ffffff` | `#1b2330` | Cards, tabelas, formulários, modais |
| 2 | `--spi-superficie-alt` | `#fafbfc` | `#171c23` | Painel dentro de card, filtros, cabeçalho de tabela, linha em hover |
| — | `--spi-superficie-ativa` | = `--spi-vermelho-suave` | = `--spi-vermelho-suave` | Item selecionado, resultado de busca ativo |

### 2.4 Status (implementados em `styles/_tema.scss`; os `.selo-*` de `styles.scss` já os usam)

Sempre usadas em par. Texto forte sobre fundo suave, com bolinha à esquerda.

| Status | Token texto | Claro | Escuro | Token fundo | Claro | Escuro | Exemplos de uso |
|--------|-------------|-------|--------|-------------|-------|--------|-----------------|
| Sucesso | `--spi-sucesso` | `#1d6b43` | `#6fd3a0` | `--spi-sucesso-suave` | `#d4f0de` | `#173327` | Vigente, concluído, localizado |
| Alerta | `--spi-alerta` | `#9a6400` | `#f0c062` | `--spi-alerta-suave` | `#fdf1d8` | `#3a2e14` | A vencer, pendente, sem chapa |
| Perigo | `--spi-perigo` | `#a91c28` | `#f1959c` | `--spi-perigo-suave` | `#fcecee` | `#3a2226` | Vencido, inservível, erro |
| Informação | `--spi-info` | `#1a56a0` | `#7fb0ee` | `--spi-info-suave` | `#dbeafe` | `#1a2a40` | Em análise, rascunho, novo |
| Neutro | `--spi-apagado` | — | — | `--spi-superficie-alt` | — | — | Arquivado, baixado, sem status |

> Status nunca depende só da cor: a pílula sempre tem texto ("Vencido"), e a bolinha é reforço.

### 2.5 Barra lateral (já existente — escura nos dois temas)

Fundo escuro, texto `#c7ced6`, hover `#ffffff`. Item ativo: fundo vermelho suave translúcido com filete vermelho à esquerda, ou fundo `--spi-vermelho` com texto branco — escolher **um** padrão e usar em todo o menu.

---

## 3. Tipografia

### 3.1 Famílias

| Token | Valor | Uso |
|-------|-------|-----|
| `--spi-fonte` | `Arial, Helvetica, sans-serif` | Toda a interface (atual) |
| `--spi-fonte-mono` | `ui-monospace, "Cascadia Mono", Consolas, "Liberation Mono", monospace` | **Novo.** Números de patrimônio, nº de processo SEI, nº de contrato, CNPJ, códigos de barras, valores alinhados em tabela |

> **Feito:** Arial trocada por **Inter** em `--spi-fonte` e usar **Geist Mono** em `--spi-fonte-mono`. As duas são gratuitas (licença OFL) e devem ser **hospedadas no próprio servidor** (pacotes `@fontsource/inter` e `@fontsource/geist-mono`), sem CDN externo, porque o SGI roda na intranet e o Módulo Protocolo precisa funcionar offline. Como a troca fica só nas variáveis, nenhum componente muda.
>
> ```scss
> --spi-fonte: 'Inter', Arial, Helvetica, sans-serif;
> --spi-fonte-mono: 'Geist Mono', ui-monospace, Consolas, monospace;
> ```
>
> Opcional: **Satoshi** só no título de página e na tela de login (nunca no corpo). Gratuita pelo Fontshare; confirme a licença ao baixar.

A fonte mono vem do Dub (Geist Mono para dados técnicos): no SGI ela resolve um problema real, que é ler e comparar códigos de patrimônio e números de processo sem confundir `0`/`O` e `1`/`l`.

### 3.2 Escala

| Função | Token | Tamanho | Entrelinha | Peso |
|--------|-------|---------|------------|------|
| Microrrótulo (sobretítulo, `dt`, cabeçalho de grupo) | `--spi-texto-micro` | 11px | 1.4 | 700, caixa alta, espaçamento 0.06–0.16em |
| Legenda / auxiliar | `--spi-texto-legenda` | 12px | 1.4 | 400 |
| Corpo compacto (tabelas, listas, busca) | `--spi-texto-compacto` | 13px | 1.45 | 400 |
| Corpo | `--spi-texto-corpo` | 14px | 1.5 | 400 |
| Corpo destaque / introdução | `--spi-texto-destaque` | 16px | 1.5 | 400 |
| Título de card / seção | `--spi-titulo-secao` | 20px | 1.3 | 700 |
| Título de página (área autenticada) | `--spi-titulo-pagina` | 28px | 1.15 | 800, espaçamento -0.02em |
| Título de página pública (login, portal) | — | `clamp(2.3rem, 5vw, 3.4rem)` | 1.05 | 800, espaçamento -0.035em (atual) |

### 3.3 Pesos

Hoje o código usa 700 em 145 lugares e 800 em 50 — quase tudo é negrito, e por isso nada se destaca. Vocabulário proposto:

| Peso | Uso |
|------|-----|
| 400 | Texto de corpo, células de tabela, descrições |
| 600 | Rótulos de campo, texto de botão, cabeçalho de tabela, valor em destaque |
| 700 | Títulos de seção e de card, microrrótulos em caixa alta |
| 800 | **Só** título de página e sobretítulo |

---

## 4. Espaçamento, raios e sombras

### 4.1 Espaçamento (base 4px)

`4 · 8 · 12 · 16 · 20 · 24 · 32 · 48 · 64` → tokens `--spi-espaco-4` … `--spi-espaco-64`

| Contexto | Valor |
|----------|-------|
| Entre elementos (ícone + texto, botões em grupo) | 8px |
| Padding de card | 16px (celular) / 20–24px (mesa) |
| Entre campos de formulário | 16px |
| Entre seções da página | 32px |
| Largura máxima do conteúdo | 1300px (atual `.largura-portal`); formulários de leitura longa: 900px |

### 4.2 Raios — vocabulário fechado

O código atual usa 10 valores (3, 4, 6, 7, 8, 9, 10, 12, 14, 999px). Proposta: **cinco**.

| Token | Valor | Elementos |
|-------|-------|-----------|
| `--spi-raio-p` | 6px | Campos, checkboxes, botões pequenos, células destacadas |
| `--spi-raio-m` | 8px | Botões, itens de menu, resultados de busca, abas |
| `--spi-raio-g` | 12px | Cards, tabelas, dropdowns, painéis |
| `--spi-raio-gg` | 16px | Modais, card de destaque do painel |
| `--spi-raio-pilula` | 999px | Pílulas de status, chips de filtro, contadores, avatares |

Migração: 3/4 → 6 · 7 → 6 · 9/10 → 8 ou 12 conforme o elemento · 14 → 12 ou 16.

### 4.3 Sombras — só quatro

| Token | Valor | Uso |
|-------|-------|-----|
| `--spi-sombra-sutil` | `0 1px 2px #18222d0d` | Card clicável em repouso (opcional) |
| `--spi-sombra-flutuante` | `0 12px 30px #18222d1f` | Dropdowns, resultados de busca, popovers |
| `--spi-sombra-modal` | `0 18px 45px #18222d26` | Modais e card do login |
| `--spi-anel-foco` | `0 0 0 3px #c8233126` | Foco de campo e de botão (acessibilidade) |

Cards comuns, tabelas e formulários **não têm sombra**: borda de 1px resolve.

---

## 5. Componentes

### Botão principal
Fundo `--spi-vermelho`, texto branco, peso 600, 14px, raio 8px, padding 10px × 16px, altura mínima 40px (44px no celular). Hover `--spi-vermelho-escuro`. **Um por tela ou por formulário** — a ação que conclui a tarefa ("Salvar", "Registrar movimentação").

### Botão secundário (contornado)
Fundo `--spi-superficie`, texto `--spi-texto`, borda 1px `--spi-borda-campo`, raio 8px, mesmo tamanho do principal. Hover: borda e texto `--spi-vermelho`. É o botão padrão de quase tudo ("Filtrar", "Exportar", "Voltar").

### Botão fantasma
Fundo transparente, texto `--spi-apagado`, sem borda, raio 8px. Hover: fundo `--spi-superficie-alt`, texto `--spi-texto`. Para ações de ícone, "Cancelar", ações de linha em tabela.

### Botão destrutivo
Contornado com texto e borda `--spi-perigo`; só vira preenchido dentro do modal de confirmação.

### Campo de formulário
Já existe estilo base global — manter. Borda 1px `--spi-borda-campo`, raio 6px, altura mínima 46px, fundo `--spi-superficie`. Foco: borda `--spi-vermelho` + `--spi-anel-foco`. Rótulo acima em 13–14px peso 600 `--spi-rotulo`. Erro: borda `--spi-perigo` + mensagem 12px `--spi-perigo` abaixo.

### Card
Fundo `--spi-superficie`, borda 1px `--spi-borda`, raio 12px, padding 16–24px, **sem sombra**. Cabeçalho opcional: título 20px/700 + ações à direita, separado do corpo por borda inferior.

### Card de indicador (painéis)
Variação do card para KPIs (painel executivo, painel do patrimônio): microrrótulo em caixa alta 11px `--spi-apagado`, valor em 28px peso 700, linha de contexto 12px. Clicável quando leva a uma lista filtrada: hover com borda `--spi-borda-campo` e `--spi-sombra-sutil`. *(Adaptado do card de sugestão do Perplexity.)*

### Painel interno
Fundo `--spi-superficie-alt`, sem borda, raio 12px, padding 12–16px. Para agrupar blocos dentro de um card (dados do bem, resumo do contrato, filtros). *(Dub: "muted alt card".)*

### Tabela
Dentro de card. Cabeçalho: fundo `--spi-superficie-alt`, texto 11–12px peso 600 caixa alta `--spi-apagado`. Linhas: 13–14px, borda inferior 1px `--spi-borda`, padding vertical 10–12px, hover `--spi-superficie-alt`, selecionada `--spi-superficie-ativa`. Números, datas e códigos alinhados à direita (códigos em `--spi-fonte-mono`). No celular, a tabela vira lista de cards.

### Selo de status (classes `.selo-*`, já existem)
Hoje há vários selos com estilos próprios (`.selo-situacao`, `.selo-status`, `.selo-origem`, `.selo-nivel`, `.selo-risco`, `.selo-prioridade-tarefa`…), todos com raio 10px e texto de 10px. **Não criar classe nova**: unificar o visual desses selos no padrão abaixo, mantendo os nomes e os modificadores que já existem (`.a_vencer`, `.inativo` etc.).
Raio 999px, padding 3px × 10px, 12px peso 600, fundo `--spi-*-suave`, texto `--spi-*`, bolinha de 6px da mesma cor antes do texto (opcional). Sem borda. Um status por selo.

### Chips de filtro (`.chips-filtro`, já existe em Tarefas)
Reaproveitar o contêiner `.chips-filtro` nos outros módulos em vez de criar outro. Cada chip: raio 999px, padding 6px × 12px, 13px, borda 1px `--spi-borda-campo`, fundo transparente. Ativo: fundo `--spi-vermelho-suave`, borda e texto `--spi-vermelho`. Para filtros rápidos ("Vigentes", "A vencer", "Meus"). *(Perplexity: chips de modo.)*

### Etiqueta "Novo"
Fundo `--spi-vermelho`, texto branco, 10–11px peso 700, raio 999px, padding 2px × 8px. Só para funcionalidade nova no menu ou no manual.

### Sobretítulo + título de página (já existentes)
`── GESTÃO DE CONTRATOS` em `--spi-vermelho-destaque`, 11px, 800, espaçamento 0.16em, com filete de 27×2px. É a assinatura visual do SGI — manter.

### Busca global (já existente)
Campo de 40px no topo; resultados em dropdown com raio 12px e `--spi-sombra-flutuante`; resultado ativo com `--spi-superficie-ativa`.

### Item da barra lateral
Texto 13–14px, padding 8px × 12px, raio 8px, ícone + rótulo. Ativo: um único padrão para todo o menu (ver 2.5). Rótulos de grupo: 11px, 700, caixa alta, cor apagada.

### Modal
Fundo `--spi-superficie`, raio 16px, `--spi-sombra-modal`, largura padrão 480px (formulários maiores: até 860px). Rodapé com secundário à esquerda do principal.

### Estado vazio
Ícone simples em `--spi-apagado`, frase curta do que falta, e uma ação ("Cadastrar primeiro bem"). Sem ilustração.

### Carregamento
Sempre `<app-esqueleto>` com o formato aproximado do conteúdo (linhas de tabela, cards de indicador). Nunca o texto "Carregando…". Botão de salvar em andamento leva `[class.carregando]`.

### Estruturas que já existem (copiar, não recriar)

| Necessidade | Use |
|-------------|-----|
| Tela de gestão (lista + filtros + ações) | `.painel-gestao` |
| Barra de filtros e busca | `.barra-protocolo` + `.campo`, com o `label` **acima** do campo |
| Ações no rodapé de cartão/formulário | `footer.acoes-formulario` |
| Filtros rápidos | `.chips-filtro` |
| Status | `.selo-*` existente do módulo, ou `.selo-status` |
| Sobretítulo + título | `.sobretitulo` + `.titulo-pagina` |

---

## 5A. Como construir uma tela nova

1. **Procure a tela existente mais parecida** e copie a estrutura e as classes dela antes de escrever HTML/CSS.
2. **Antes de criar qualquer classe, cheque se o nome já existe:** `grep -rn "nome-da-classe" frontend/src`. Classes globais de outros módulos vazam e quebram o layout.
3. Nunca crie classe própria de campo ou de barra quando já existe uma global. Campos (`select`, `textarea`, `input`) já têm estilo base global.
4. Todo botão, campo e cartão tem espaçamento interno e distância dos vizinhos — nada colado na borda ou em outro elemento.
5. Estilo novo de módulo vai em `frontend/src/styles/_<modulo>.scss`, usando só tokens.
6. Depois do `ng build`, diga o que conferiu na tela; se não a abriu, diga.

---

## 5B. Movimento (detalhes em `docs/movimento.md`)

- Carga de dados: `<app-esqueleto>`.
- Modais e menus: classes e `animate.leave` de `_movimento.scss`.
- Botão de salvar: `[class.carregando]`.
- Imagens: `loading="lazy"`. Gráficos e editor rico: dentro de `@defer`.
- Nada anima ação frequente ou de teclado; `prefers-reduced-motion` é respeitado.
- Conferência: `npm run verificar:movimento` em `frontend/`.

---

## 5C. Referências para elementos novos

Vale quando for pedido um seletor, componente ou tela que **não existe em nenhum módulo do SGI**. Se existir algo equivalente, copie (seção 5A) e não consulte nada.

### Onde procurar
- https://styles.refero.design/
- https://www.inspora.design/
- http://spell.sh/
- https://magicui.design/
- https://icon.museum/
- https://www.rareui.com/

### Como usar
- As referências servem para **ideia de padrão e de interação**, não para copiar código. O SGI é Angular + Bootstrap + SCSS: componentes em React/Tailwind (como os da Magic UI) são reescritos em Angular com os tokens deste documento.
- A identidade continua a do SGI: vermelho como único acento, tokens `--spi-*`, raios, pesos e regras de movimento deste arquivo. Animação vistosa de referência só entra se respeitar a seção 5B.

### Formato da proposta (antes de implementar)
Para cada opção (2 ou 3):
1. **Nome e referência:** o que é e o link de onde veio.
2. **Como ficaria no SGI:** descrição curta ou esboço, já com as cores e componentes daqui.
3. **Prós e contras:** uso no celular, acessibilidade, esforço de implementação.
4. **Recomendação:** qual eu escolheria e por quê.

Só implementar depois da escolha.

---

## 6. Celular (levantamento de patrimônio em campo)

- Alvos de toque ≥ 44px; botão principal com largura total no rodapé fixo da tela.
- Campo de código de patrimônio em `--spi-fonte-mono`, 18px, com botão de câmera ao lado.
- Tabelas viram cards empilhados: código e status na primeira linha, descrição e local abaixo.
- Feedback de leitura de código: selo de status grande ("Localizado", "Não encontrado", "Sem chapa") logo abaixo do campo.
- Indicador de conexão discreto no topo quando estiver offline (pílula âmbar "Offline — 12 pendentes").

---

## 7. O que fazer e o que evitar

### Faça
- Use só variáveis (`var(--spi-*)` ou `var(--cor-*)`) — nunca hex fixo em componente.
- Use o vermelho para **uma** ação principal por tela, para o item ativo e para o foco.
- Defina containers com borda de 1px `--spi-borda`.
- Use os selos `.selo-*` existentes para todo status, sempre com texto.
- Copie a estrutura de uma tela equivalente e cheque com `grep` se a classe já existe antes de criar uma.
- Use a fonte mono para códigos e números de identificação.
- Siga os cinco raios e os quatro pesos.
- Teste toda tela nova nos dois temas e em 375px de largura.

### Evite
- Não crie outra cor de marca (azul, verde ou roxo "de destaque"). Cor fora do vermelho só com significado de status.
- Não use vermelho para decorar: ele perde força como sinal de ação e de erro.
- Não use sombra em card comum, tabela ou formulário.
- Não use negrito em texto de corpo para criar hierarquia — use tamanho, cor apagada ou espaço.
- Não use gradientes, fotos ou ilustrações decorativas.
- Não deixe campo com visual nativo do navegador.
- Não invente raio, espaçamento ou tamanho de fonte fora das escalas.

---

## 8. Guia de prompts para agentes de IA

Referência rápida:
- fundo: `var(--spi-fundo)` · superfície: `var(--spi-superficie)` · superfície interna: `var(--spi-superficie-alt)`
- texto: `var(--spi-texto)` · secundário: `var(--spi-apagado)` · borda: `var(--spi-borda)`
- acento / ação principal / ativo / foco: `var(--spi-vermelho)`
- status: `--spi-sucesso`, `--spi-alerta`, `--spi-perigo`, `--spi-info` (+ `-suave`)

Exemplos:

1. **Lista de bens:** tela em `.painel-gestao` (copiar a estrutura da lista do Protocolo); card com raio 12px e borda `--spi-borda`; cabeçalho "Bens permanentes" 20px/700 com botão principal "Cadastrar bem" à direita; `.chips-filtro` com "Todos · Localizados · Sem chapa · Inservíveis"; tabela com colunas Patrimônio (`.texto-codigo`, direita), Descrição, Local, Status (`.selo-*` do módulo); carga com `<app-esqueleto>`. No celular, cada linha vira um card.
2. **Card de indicador:** microrrótulo "CONTRATOS A VENCER (90 DIAS)" 11px/700 `--spi-apagado`; valor "14" 28px/700; linha "3 vencem este mês" 12px `--spi-alerta`. Clicável, leva à lista filtrada.
3. **Formulário de movimentação:** grade de 2 colunas na mesa e 1 no celular; rótulos 13px/600; campos com estilo base global; rodapé em `footer.acoes-formulario` com "Cancelar" (fantasma) e "Registrar movimentação" (principal, com `[class.carregando]`).
4. **Selo de situação de contrato (`.selo-situacao`):** "Vigente" (`--spi-sucesso` sobre `--spi-sucesso-suave`), "A vencer" (alerta), "Vencido" (perigo), "Em elaboração" (info), raio 999px, 12px/600, bolinha de 6px.

---

## 9. Implementação (SCSS)

Novos tokens para `frontend/src/styles.scss` (`:root`) e os pares escuros em `frontend/src/styles/_tema.scss` (`:root[data-tema='escuro']`). As variáveis `--spi-*` existentes continuam como estão.

```scss
:root {
  /* Superfícies */
  --spi-superficie: #ffffff;
  --spi-superficie-alt: #fafbfc;
  --spi-superficie-ativa: var(--spi-vermelho-suave);

  /* Status */
  --spi-sucesso: #1d6b43;   --spi-sucesso-suave: #d4f0de;
  --spi-alerta: #9a6400;    --spi-alerta-suave: #fdf1d8;
  --spi-perigo: #a91c28;    --spi-perigo-suave: #fcecee;
  --spi-info: #1a56a0;      --spi-info-suave: #dbeafe;

  /* Tipografia */
  --spi-fonte: Arial, Helvetica, sans-serif;
  --spi-fonte-mono: ui-monospace, "Cascadia Mono", Consolas, "Liberation Mono", monospace;
  --spi-texto-micro: 11px;
  --spi-texto-legenda: 12px;
  --spi-texto-compacto: 13px;
  --spi-texto-corpo: 14px;
  --spi-texto-destaque: 16px;
  --spi-titulo-secao: 20px;
  --spi-titulo-pagina: 28px;

  /* Espaçamento */
  --spi-espaco-4: 4px;   --spi-espaco-8: 8px;   --spi-espaco-12: 12px;
  --spi-espaco-16: 16px; --spi-espaco-20: 20px; --spi-espaco-24: 24px;
  --spi-espaco-32: 32px; --spi-espaco-48: 48px; --spi-espaco-64: 64px;

  /* Raios */
  --spi-raio-p: 6px;
  --spi-raio-m: 8px;
  --spi-raio-g: 12px;
  --spi-raio-gg: 16px;
  --spi-raio-pilula: 999px;

  /* Sombras */
  --spi-sombra-sutil: 0 1px 2px #18222d0d;
  --spi-sombra-flutuante: 0 12px 30px #18222d1f;
  --spi-sombra-modal: 0 18px 45px #18222d26;
  --spi-anel-foco: 0 0 0 3px #c8233126;
}

:root[data-tema='escuro'] {
  --spi-superficie: #1b2330;
  --spi-superficie-alt: #171c23;

  --spi-sucesso: #6fd3a0;   --spi-sucesso-suave: #173327;
  --spi-alerta: #f0c062;    --spi-alerta-suave: #3a2e14;
  --spi-perigo: #f1959c;    --spi-perigo-suave: #3a2226;
  --spi-info: #7fb0ee;      --spi-info-suave: #1a2a40;

  --spi-sombra-flutuante: 0 12px 30px #0000004d;
  --spi-sombra-modal: 0 18px 45px #00000066;
}

/* Selos: unifica o visual dos .selo-* que já existem, sem renomear nada.
   As cores de cada selo continuam no seu módulo, mas passam a usar os tokens de status. */
.selo-situacao, .selo-status, .selo-origem, .selo-nivel, .selo-tipo, .selo-risco, .selo-ferias, .selo-prioridade-tarefa {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 3px 10px; border-radius: var(--spi-raio-pilula);
  font-size: var(--spi-texto-legenda); font-weight: 600; line-height: 1.4; white-space: nowrap;
}
/* exemplo no módulo de contratos */
.selo-situacao {
  &.vigente  { color: var(--spi-sucesso); background: var(--spi-sucesso-suave); }
  &.a_vencer { color: var(--spi-alerta);  background: var(--spi-alerta-suave); }
  &.vencido  { color: var(--spi-perigo);  background: var(--spi-perigo-suave); }
  &.inativo  { color: var(--spi-apagado); background: var(--spi-superficie-alt); }
}

/* Única classe nova proposta (conferir antes: grep -rn "texto-codigo" frontend/src) */
.texto-codigo { font-family: var(--spi-fonte-mono); font-variant-numeric: tabular-nums; }
```

> Os nomes de modificador acima (`.vigente`, `.vencido`) são ilustrativos: use os que cada módulo já tem.

### O que foi aplicado (decisões)
- Menu lateral: item ativo = fundo vermelho translúcido + filete de 3px à esquerda (`barra-lateral.component.scss`).
- Sombras: removidas de cards, tabelas e formulários; ficam só em menus/dropdowns (`--spi-sombra-flutuante`), modais/login (`--spi-sombra-modal`), barras fixas (`--spi-sombra-sutil`) e foco (`--spi-anel-foco`).
- Raios: 3–7 → `--spi-raio-p`; 8–9 (e 10 em botões/campos) → `-m`; 10–14 em cards/painéis → `-g`; 16 → `-gg`; 99/999 → `-pilula`. Alguns valores fora da escala (2px, 17–22px, círculos) ficaram de propósito.
- Pesos: 800 só em título de página e sobretítulo; rótulos/botões/selos/chips em 600; títulos de seção e microrrótulos em 700.
- Chips: o visual de `.chips-filtro` vale também para `.chips-tipo`, `.chips-tipos` e `.chips-categorias` (ativo em vermelho suave).
- Componentes Spell (botão copiar, seletor de cor, tilt dos ramais, gráficos): seguem as mesmas regras de tema; o gráfico lê as cores do tema ativo.

### Ordem sugerida de adoção (histórico)
1. Adicionar os tokens (sem mudar nada visível).
2. Unificar o visual dos `.selo-*` e levar `.chips-filtro` aos módulos que filtram; começar pelo Módulo Protocolo.
3. Adotar `.texto-codigo` nos números de patrimônio, processo e contrato.
4. Trocar sombras de cards comuns por borda, tela a tela.
5. Consolidar raios e pesos (busca por `border-radius` e `font-weight` nos `.scss`).
6. Decidir Arial × Inter.

---

## 10. De onde veio cada ideia

| Ideia | Origem | Como foi adaptada |
|-------|--------|-------------------|
| Um único acento cromático | Perplexity (teal) | O acento é o vermelho SPI |
| Faixa estreita de pesos | Perplexity (400–500) | Quatro pesos com função definida; 800 só em título |
| Chips em pílula, etiqueta "Novo" | Perplexity | Chips de filtro e etiqueta vermelha |
| Card de sugestão | Perplexity | Card de indicador dos painéis |
| Elevação por bordas | Dub | Cards e tabelas sem sombra |
| Pílulas de status tingidas | Dub | Visual unificado dos `.selo-*` existentes, com tokens de status para os dois temas |
| Vocabulário fechado de raios | Dub | Cinco raios, mapeados a partir dos dez atuais |
| Fonte mono para dados técnicos | Dub (Geist Mono) | Códigos de patrimônio, processos, contratos |
| Painel interno cinza | Dub (muted alt card) | `--spi-superficie-alt` |
| Escala tipográfica com títulos | Dub | Escala própria até 28px na área autenticada |

**Descartado de propósito:** canvas cor de pergaminho e teal (Perplexity), azul de marca e acentos laranja/roxo/verde decorativos (Dub), gradiente cônico, fontes proprietárias (pplxSans, Satoshi), largura máxima de 900px para tudo e padrões de página de marketing (hero, nuvem de logos).
