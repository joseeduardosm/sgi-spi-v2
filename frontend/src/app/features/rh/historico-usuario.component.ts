/**
 * =============================================================================
 * ARQUIVO: historico-usuario.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Aba "Histórico" da pessoa: a linha do tempo funcional (cadastro, cargos e
 * setores, férias, licença-prêmio, exoneração), com filtros e exportação em
 * PDF.
 *
 * RESUMO TÉCNICO:
 * Componente standalone com template inline. Lê o id da pessoa na URL, busca
 * o histórico na RhCargosApiService com filtros de período (de/até) e de tipo
 * de fato (chips), mostra a tabela de cargos ocupados e a de eventos, e baixa o
 * mesmo conteúdo em PDF.
 *
 * FINALIDADE DE NEGÓCIO:
 * Dá ao RH e ao próprio servidor uma visão única e auditável da vida
 * funcional: cada fato com data, hora e quem registrou. O RH vê qualquer
 * pessoa; cada servidor vê o seu.
 *
 * CONTEXTO NO SISTEMA:
 * Rota do Módulo RH (rh.routes.ts) com o id do usuário. Usa os tipos de
 * rh-cargos.models.ts (HistoricoUsuario), o cabeçalho app-cabecalho-rh e
 * app-esqueleto. Os fatos são gravados pelo backend do RH (cargos, férias,
 * validação de ficha, admissão).
 *
 * =============================================================================
 */

import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRhComponent } from './cabecalho-rh.component';
import { RhCargosApiService } from './rh-cargos-api.service';
import { HistoricoUsuario } from './rh-cargos.models';

/** Histórico funcional: o que aconteceu com a pessoa, por quem foi registrado e quando (dd/mm/aaaa hh:mm). O RH vê qualquer pessoa; cada um vê o seu. */
@Component({
  selector: 'app-historico-usuario',
  imports: [FormsModule, CabecalhoRhComponent, EsqueletoComponent],
  template: `
    <app-cabecalho-rh titulo="Histórico funcional" [trilha]="['Histórico']" descricao="Cadastro, cargos e setores, férias e licença-prêmio, até a exoneração, com quem registrou cada fato." />

    @if (carregando()) {
      <app-esqueleto tipo="tabela" [linhas]="6" [colunas]="3" />
    } @else if (historico(); as h) {
      <section class="painel-gestao" aria-labelledby="titulo-historico">
        <div class="barra-ferramentas">
          <div>
            <h2 id="titulo-historico">{{ h.nome }} <small class="texto-codigo">&#64;{{ h.login }}</small></h2>
            <p>{{ h.cargo_atual || 'Sem cargo' }} · {{ h.setor_atual || 'Sem setor' }}</p>
          </div>
          <div class="acoes-formulario"><button type="button" class="acao-secundaria" [class.carregando]="baixando()" (click)="exportar(h)">Exportar PDF</button></div>
        </div>

        <div class="filtros-gestao">
          <div class="campo"><label for="hist-de">De</label><input id="hist-de" type="date" [(ngModel)]="de" (ngModelChange)="carregar()" /></div>
          <div class="campo"><label for="hist-ate">Até</label><input id="hist-ate" type="date" [(ngModel)]="ate" (ngModelChange)="carregar()" /></div>
        </div>
        <div class="chips-filtro" role="group" aria-label="Tipo de fato">
          <button type="button" [class.ativo]="!tiposMarcados().length" (click)="tiposMarcados.set([]); carregar()">Todos</button>
          @for (t of tiposDisponiveis(h); track t[0]) {
            <button type="button" [class.ativo]="tiposMarcados().includes(t[0])" (click)="alternarTipo(t[0])">{{ t[1] }}</button>
          }
        </div>

        <h3>Cargos e setores por onde passou</h3>
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao">
            <thead><tr><th>Cargo</th><th>Setor</th><th>Início</th><th>Fim</th><th>Ato</th></tr></thead>
            <tbody>
              @for (o of h.ocupacoes; track o.id) {
                <tr>
                  <td><strong>{{ o.cargo_rotulo }}</strong></td><td>{{ o.setor_nome }}</td><td>{{ dataBr(o.inicio) }}</td>
                  <td>@if (o.fim) { {{ dataBr(o.fim) }} <small>{{ o.motivo_fim }}</small> } @else { <span class="selo-situacao">Vigente</span> }</td>
                  <td>{{ o.ato || '—' }}</td>
                </tr>
              } @empty { <tr><td class="estado-vazio" colspan="5">Nenhum cargo registrado.</td></tr> }
            </tbody>
          </table>
        </div>

        <h3>Linha do tempo</h3>
        <div class="tabela-gestao-envoltorio">
          <table class="tabela-gestao">
            <thead><tr><th>Quando</th><th>Fato</th><th>Registrado por</th></tr></thead>
            <tbody>
              @for (e of h.eventos; track e.id) {
                <tr>
                  <td class="texto-codigo">{{ dataHoraBr(e.ocorrido_em) }}</td>
                  <td><strong>{{ e.titulo }}</strong> <span class="selo-nivel">{{ h.tipos[e.tipo] || e.tipo }}</span>@if (e.detalhe) { <small>{{ e.detalhe }}</small> }</td>
                  <td>{{ e.autor_nome || 'Sistema' }}</td>
                </tr>
              } @empty { <tr><td class="estado-vazio" colspan="3">Nenhum fato no período.</td></tr> }
            </tbody>
          </table>
        </div>
      </section>
    }
  `,
})
export class HistoricoUsuarioComponent implements OnInit {
  // inject() obtém os serviços pela injeção de dependência do Angular.
  private readonly rota = inject(ActivatedRoute);
  private readonly api = inject(RhCargosApiService);
  private readonly dialogos = inject(DialogosService);

  // signal(): estado reativo da tela; quando muda, o template é redesenhado.
  protected readonly historico = signal<HistoricoUsuario | null>(null);
  protected readonly carregando = signal(true);
  protected readonly baixando = signal(false);
  protected readonly tiposMarcados = signal<string[]>([]);
  /** Filtro de período (AAAA-MM-DD), ligado aos campos De e Até por ngModel. */
  protected de = '';
  protected ate = '';
  private usuarioId = 0;
  /** Tipos já vistos: os chips não somem quando o filtro esvazia a lista. */
  private tiposConhecidos: [string, string][] = [];

  /** Lê o id da pessoa na URL e carrega o histórico. */
  ngOnInit(): void {
    this.usuarioId = Number(this.rota.snapshot.paramMap.get('id'));
    this.carregar();
  }

  /** Busca o histórico com os filtros atuais; na primeira resposta guarda a lista de tipos para os chips. */
  protected carregar(): void {
    this.api.historico(this.usuarioId, { tipos: this.tiposMarcados(), de: this.de, ate: this.ate }).subscribe({
      next: (h) => {
        if (!this.tiposConhecidos.length) this.tiposConhecidos = Object.entries(h.tipos);
        this.historico.set(h);
        this.carregando.set(false);
      },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível carregar o histórico'); },
    });
  }

  /** Pares [código, rótulo] dos tipos de fato para os chips de filtro. */
  protected tiposDisponiveis(h: HistoricoUsuario): [string, string][] {
    return this.tiposConhecidos.length ? this.tiposConhecidos : Object.entries(h.tipos);
  }

  /** Marca ou desmarca um tipo de fato no filtro e recarrega. */
  protected alternarTipo(tipo: string): void {
    const atual = this.tiposMarcados();
    this.tiposMarcados.set(atual.includes(tipo) ? atual.filter((t) => t !== tipo) : [...atual, tipo]);
    this.carregar();
  }

  /** Baixa o PDF do histórico com os mesmos filtros da tela (o login entra no nome do arquivo). */
  protected exportar(h: HistoricoUsuario): void {
    this.baixando.set(true);
    this.api.baixarHistoricoPdf(this.usuarioId, h.login, { tipos: this.tiposMarcados(), de: this.de, ate: this.ate }).subscribe({
      next: () => this.baixando.set(false),
      error: (e) => { this.baixando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível gerar o PDF'); },
    });
  }

  /** "AAAA-MM-DD" para "DD/MM/AAAA" (vazio quando nulo). */
  protected dataBr(iso: string | null): string {
    return iso ? iso.split('-').reverse().join('/') : '';
  }

  /** Data e hora ISO para "DD/MM/AAAA HH:MM" no fuso do navegador. */
  protected dataHoraBr(iso: string): string {
    const d = new Date(iso);
    const p = (n: number) => String(n).padStart(2, '0');
    return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`;
  }
}
