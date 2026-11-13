/**
 * =============================================================================
 * ARQUIVO: changelog.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Mostrar a tela Changelog: as novidades do sistema para o usuário final,
 * navegáveis por dia.
 *
 * RESUMO TÉCNICO:
 * Componente standalone com template embutido. A entrada data (input ligado ao
 * parâmetro da rota) escolhe o dia; o computed atual() acha esse dia em
 * NOVIDADES ou cai no mais recente. Lista lateral de dias (no celular, um
 * select), corpo com as novidades do dia e links para o dia vizinho. No
 * ngOnInit chama NovidadesVistasService.marcarVistas().
 *
 * FINALIDADE DE NEGÓCIO:
 * Conta às pessoas, em linguagem simples, o que mudou no trabalho delas no SGI
 * SPI (tela, regra, fluxo, documento gerado), sem precisar perguntar à TI.
 * Abrir a tela apaga a bolinha que avisa que há novidade.
 *
 * CONTEXTO NO SISTEMA:
 * Rota /changelog e /changelog/:data em app.routes.ts. Dados em novidades.ts;
 * a data da bolinha fica em core/changelog/ultima-novidade.ts. Reaproveita o
 * layout (classes manuais-*) da tela de Manuais.
 *
 * =============================================================================
 */

import { Component, computed, inject, input, OnInit } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { Router, RouterLink } from '@angular/router';

import { AcessoService } from '../../core/acesso/acesso.service';
import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { NovidadesVistasService } from '../../core/changelog/novidades-vistas.service';
import { moduloVisivel } from '../../core/changelog/visibilidade-novidades';
import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';
import { DiaNovidades, NOVIDADES } from './novidades';

/**
 * Converte a data ISO da novidade para o formato curto brasileiro.
 * Ex.: "10/11/2026" a partir de "2026-11-10".
 */
function dataCurta(data: string): string {
  const [ano, mes, dia] = data.split('-');
  return `${dia}/${mes}/${ano}`;
}

/**
 * Data por extenso para o título do dia: "terça-feira, 10 de novembro de 2026".
 * Usa meio-dia local, para o fuso não trocar o dia (meia-noite UTC viraria o dia anterior no Brasil).
 */
function dataPorExtenso(data: string): string {
  return new Date(`${data}T12:00:00`).toLocaleDateString('pt-BR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
}

/**
 * Changelog: novidades do SGI SPI em linguagem de usuário final, só nos dias com mudança de negócio.
 *
 * Mesmo layout dos Manuais: a lista de dias à esquerda (no celular, um seletor no topo), as novidades do dia no centro
 * e "← mais recente / mais antigo →" no rodapé. Todos veem todas as novidades. Abrir a tela apaga a bolinha do menu.
 *
 * No template, `@for` repete um trecho para cada item da lista (o `track` diz ao Angular como identificar
 * cada item), `@if` mostra um trecho só quando a condição é verdadeira e `@let` guarda um valor para reuso.
 */
@Component({
  selector: 'app-changelog',
  imports: [NgTemplateOutlet, RouterLink, TrilhaComponent],
  template: `
    <div class="changelog">
      <div class="cabecalho-pagina">
        <div>
          <app-trilha [itens]="[{ rotulo: 'Changelog' }]" />
          <h1>Novidades do SGI SPI</h1>
          <small>O que mudou no sistema, dia a dia, em linguagem simples.</small>
        </div>
      </div>

      <!-- Navegação entre os dias (decisão do usuário): setas para o dia anterior e o próximo e, no meio, a lista para pular direto a uma data.
           A lista lateral de dias saiu: com o histórico crescendo, ela virava uma barra sem fim. -->
      <ng-template #navegacao let-posicao>
        <nav class="changelog-navegacao" [attr.aria-label]="'Navegar entre os dias (' + posicao + ')'">
          @if (vizinho(1); as anterior) {
            <a class="acao-secundaria" [routerLink]="['/changelog', anterior.data]" [attr.aria-label]="'Dia anterior: ' + curta(anterior.data)">← {{ curta(anterior.data) }}</a>
          } @else { <span></span> }
          @if (posicao === 'topo') {
            <div class="changelog-escolha"><label for="changelog-dia">Ir para o dia</label>
              <select id="changelog-dia" (change)="irPara($any($event.target).value)">
                @for (d of dias(); track d.data) { <option [value]="d.data" [selected]="d.data === atual()?.data">{{ curta(d.data) }} · {{ d.resumo }}</option> }
              </select></div>
          } @else { <span></span> }
          @if (vizinho(-1); as proximo) {
            <a class="acao-secundaria" [routerLink]="['/changelog', proximo.data]" [attr.aria-label]="'Próximo dia: ' + curta(proximo.data)">{{ curta(proximo.data) }} →</a>
          } @else { <span></span> }
        </nav>
      </ng-template>

      <div class="changelog-leitura">
        <ng-container *ngTemplateOutlet="navegacao; context: { $implicit: 'topo' }" />
        @let dia = atual();
        @if (dia) {
        <article class="painel-gestao manuais-artigo">
          <div class="conteudo-manual">
            <h2 style="margin-top: 0">{{ extenso(dia.data) }}</h2>
            @for (n of dia.novidades; track n.titulo) {
              <section class="changelog-novidade">
                <span class="selo-nivel">{{ n.modulo }}</span>
                <h3>{{ n.titulo }}</h3>
                @for (paragrafo of paragrafos(n.texto); track $index) { <p>{{ paragrafo }}</p> }
                @if (n.itens?.length) {
                  <ul>@for (item of n.itens; track $index) { <li>{{ item }}</li> }</ul>
                }
              </section>
            }
          </div>
          <!-- As mesmas setas no fim do dia, para quem leu até embaixo -->
          <ng-container *ngTemplateOutlet="navegacao; context: { $implicit: 'rodapé' }" />
        </article>
        } @else {
          <!-- Nenhuma novidade dos módulos que a pessoa usa -->
          <article class="painel-gestao manuais-artigo"><p class="estado-vazio">Ainda não há novidades dos módulos que você usa.</p></article>
        }
      </div>
    </div>
  `,
})
export class ChangelogComponent implements OnInit {
  // inject() pede ao Angular uma instância de um serviço (roteador e controle de novidades vistas).
  private readonly roteador = inject(Router);
  private readonly vistas = inject(NovidadesVistasService);

  /**
   * Dia aberto (parâmetro da rota, AAAA-MM-DD); sem ele, o mais recente.
   * input() é uma entrada do componente lida como sinal (this.data()); aqui o roteador preenche
   * com o parâmetro :data da URL.
   */
  readonly data = input<string | undefined>(undefined);

  private readonly acesso = inject(AcessoService);
  private readonly autenticacao = inject(AutenticacaoService);

  /**
   * Dias com novidade, do mais recente para o mais antigo, só com as novidades dos módulos a que a pessoa tem acesso
   * (decisão do usuário). Dia que fica sem nenhuma novidade visível some da lista.
   */
  protected readonly dias = computed<DiaNovidades[]>(() => NOVIDADES
    .map((d) => ({ ...d, novidades: d.novidades.filter((n) => moduloVisivel(n.modulo, this.acesso, this.autenticacao)) }))
    .filter((d) => d.novidades.length > 0));
  /**
   * Dia aberto: o da rota, ou o mais recente se a data não existir.
   * computed() é um valor derivado que se recalcula sozinho quando o sinal lido (data) muda.
   */
  protected readonly atual = computed<DiaNovidades | undefined>(() => this.dias().find((d) => d.data === this.data()) ?? this.dias()[0]);

  // Expõe as funções de formatação ao template (o template só enxerga membros da classe).
  protected readonly curta = dataCurta;
  protected readonly extenso = dataPorExtenso;

  /** Abrir a tela conta como "visto": apaga a bolinha do menu. */
  ngOnInit(): void {
    this.vistas.marcarVistas();
  }

  /** Quebra o texto da novidade em parágrafos (separados por linha em branco) para virar vários <p>. */
  protected paragrafos(texto: string): string[] {
    return texto.split('\n\n');
  }

  /** Dia mais recente (−1, "próximo", seta →) ou mais antigo (+1, "anterior", seta ←) que o aberto, se houver. */
  protected vizinho(passo: -1 | 1): DiaNovidades | null {
    const lista = this.dias();
    const atual = this.atual();
    const indice = atual ? lista.findIndex((d) => d.data === atual.data) : -1;
    return indice < 0 ? null : lista[indice + passo] ?? null;
  }

  /** Navega para o dia escolhido no seletor do celular (a rota muda e o input "data" acompanha). */
  protected irPara(data: string): void {
    void this.roteador.navigate(['/changelog', data]);
  }
}
