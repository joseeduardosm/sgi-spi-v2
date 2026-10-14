# Movimento da interface (skeleton, entrada, saída e progresso)

Regras da skill [design-motion-principles](https://github.com/kylezantos/design-motion-principles) aplicadas ao SGI SPI. Código: `frontend/src/styles/_movimento.scss`, `shared/componentes/esqueleto`, `shared/componentes/barra-progresso`, `core/progresso`, `core/navegacao/precarregamento.ts`.

## Regras
- **Duração:** `--mov-rapido` 120 ms (saídas), `--mov-padrao` 180 ms (entradas), `--mov-lento` 280 ms. Sempre abaixo de 300 ms.
- **Easing:** `--ease-entra` (ease-out) para chegar, `--ease-sai` (ease-in) para sair, `linear` para progresso. Nunca `ease` puro.
- **Só `transform` e `opacity`.** Entrada: sobe 8 px com fade; saída mais curta e sutil. Nunca partir de `scale(0)`.
- **Frequência:** não animam ações frequentes ou por teclado (digitar em busca/filtro, setas em combobox, paleta de comandos, atalhos, hover, checkbox, mudar filtro/aba na mesma tela).
- **`prefers-reduced-motion`:** a regra global em `src/styles.scss` zera durações e iterações; o esqueleto fica estático e o anel do botão vira um ponto.

## O que cada peça faz
| Peça | Onde | Como usar |
|---|---|---|
| **Esqueleto** | `<app-esqueleto tipo="lista\|tabela\|painel\|formulario\|cartao\|texto\|linha" [linhas]="n" [colunas]="n" />` | Em todo carregamento de dados: `@if (carregando()) { <app-esqueleto … /> } @else { … }`. Em tabelas, dentro do `<td colspan>`. **Nunca** escrever "Carregando…" em texto. |
| **Barra de progresso do topo** | `app-barra-progresso` no layout autenticado | Automática: acende em navegação e requisições acima de 150 ms (fica ao menos 300 ms). Consultas de fundo (`/resumo`) não acendem. Envio de arquivo (FormData) e download de arquivo (blob, quando o servidor informa o tamanho) mostram o percentual; sem tamanho, a barra desliza. |
| **Troca de tela** | `withViewTransitions` em `app.config.ts` | Fade + 8 px entre telas; não anima quando só muda a query string. |
| **Modais** | classes `.fundo-modal` e `.modal-portal` | Entrada automática pela classe; saída com `animate.leave="mov-fundo-sai"` / `"mov-modal-sai"` (já aplicado em todos os modais). |
| **Menus e avisos** | `.menu-usuario-lista`, `.painel-filtros`, `.pat-sucesso`, `.pat-aviso` | Entrada automática; saída com `animate.leave="mov-sai"`. |
| **Botão em andamento** | `[class.carregando]="salvando()"` | Anel girando e botão desabilitado. |
| **Imagens** | `loading="lazy" decoding="async"`; imagens autenticadas pela diretiva `appImagemAutenticada` | A diretiva só baixa quando a imagem chega a 200 px da tela e aparece com fade. Imagens do topo da página (logos, destaque) carregam na hora. |
| **Blocos pesados** | `@defer (on idle) { … } @placeholder { <app-esqueleto … /> }` | Gráficos (`app-grafico`) e editor rico (`app-editor-rico`) são baixados sob demanda. |
| **Módulos** | `PrecarregamentoOcioso` | As rotas dos módulos são baixadas em segundo plano, com o navegador ocioso (não em "economizar dados" nem em 2G). |

## Listas de busca (combobox, paleta, busca global)
Durante a busca mostram um esqueleto curto (`tipo="texto"`), sem animar a abertura da lista (abre ao digitar: frequência alta).

## Verificação
- `npm run verificar:movimento` (em `frontend/`): falha se achar o texto "Carregando…" em alguma tela ou `<img>` sem `loading="lazy"` (fora das exceções de imagens do topo).
- Conferência visual: DevTools com rede "Slow 3G" (esqueletos e barra), emulação de `prefers-reduced-motion: reduce`, e a aba Performance para 60 fps.
- **Verificação visual automatizada** (`frontend/scripts/verificar-visual.mjs`): abre o build (`dist/sgi-spi/browser`) num Chromium sem tela, com **API simulada** (nada real é tocado) e sessão de teste; tira capturas durante o carregamento (esqueletos e barra), confere a animação de entrada e saída de modal e menu, o modo `prefers-reduced-motion` (`REDUZIDO=1`) e lista erros de console por rota. Uso: `CHROME=<caminho do chrome> node scripts/verificar-visual.mjs <pasta de saída>` (variáveis `ROTAS`, `CENARIO=modal`, `REDUZIDO`, `ATRASO_API`). Erros de console nessa verificação costumam vir da API simulada devolver formatos vazios; avalie cada um.
