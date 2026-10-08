// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o detalhe da reserva: dados, série, linha do tempo, análise do fiscal e cancelamento com escopo.

import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoReservasComponent } from './cabecalho-reservas.component';
import { ReservasApiService } from './reservas-api.service';
import { dataBr, EscopoCancelamento, horaCurta, ReservaDetalhe, ROTULOS_EVENTO, ROTULOS_STATUS } from './reservas.models';

@Component({
  selector: 'app-detalhe-reserva',
  imports: [FormsModule, DatePipe, RouterLink, CabecalhoReservasComponent],
  template: `
    <app-cabecalho-reservas titulo="Reserva" />
    @if (r(); as r) {
      <section class="painel-gestao protocolo reservas">
        <div class="cartao-dados">
          <header>
            <div><h2><i class="ponto-cor" [style.background]="r.espaco_cor"></i>{{ r.titulo }}</h2>
              <small>{{ r.espaco_nome }} · {{ data(r.data) }}, {{ hora(r.hora_inicio) }}–{{ hora(r.hora_fim) }}</small></div>
            <span [class]="'selo-reserva ' + r.status">{{ rotulos[r.status] }}</span>
          </header>
          <div class="corpo">
            <dl class="dados-reserva">
              <div><dt>Responsável</dt><dd>{{ r.responsavel_nome || '—' }}</dd></div>
              <div><dt>Solicitante</dt><dd>{{ r.solicitante_nome || '—' }}</dd></div>
              @if (r.participantes) { <div><dt>Participantes</dt><dd>{{ r.participantes }}</dd></div> }
              @if (r.fiscal_nome) { <div><dt>Fiscal</dt><dd>{{ r.fiscal_nome }}</dd></div> }
              @if (r.justificativa) { <div class="larga"><dt>{{ r.status === 'CANCELADA' ? 'Motivo do cancelamento' : 'Justificativa' }}</dt><dd>{{ r.justificativa }}</dd></div> }
              @if (r.observacoes) { <div class="larga"><dt>Observações</dt><dd>{{ r.observacoes }}</dd></div> }
            </dl>
            <div class="acoes-formulario">
              @if (r.pode_analisar) {
                <button type="button" class="acao-aprovar-janela" [disabled]="ocupado()" (click)="deferir()">Deferir</button>
                <button type="button" class="acao-recusar" [disabled]="ocupado()" (click)="painel.set('recusa')">Indeferir</button>
              }
              @if (r.pode_editar) { <a class="acao-secundaria" [routerLink]="['/reserva-espacos/reservas', r.id, 'editar']">Alterar</a> }
              @if (r.pode_cancelar) { <button type="button" class="acao-recusar" (click)="painel.set('cancelar')">Cancelar reserva</button> }
            </div>

            @if (painel() === 'recusa') {
              <div class="recusa">
                <label for="dr-just">Justificativa do indeferimento</label>
                <textarea id="dr-just" rows="2" maxlength="4000" [(ngModel)]="texto"></textarea>
                <div class="acoes-formulario">
                  <button type="button" class="acao-recusar" [disabled]="!texto.trim() || ocupado()" (click)="indeferir()">Confirmar indeferimento</button>
                  <button type="button" class="acao-secundaria" (click)="painel.set('')">Voltar</button>
                </div>
              </div>
            }
            @if (painel() === 'cancelar') {
              <div class="recusa">
                @if (r.ocorrencias_serie > 1) {
                  <label for="dr-escopo">O que cancelar</label>
                  <select id="dr-escopo" [(ngModel)]="escopo">
                    <option value="ocorrencia">Só esta ocorrência ({{ data(r.data) }})</option>
                    <option value="serie">Toda a série ({{ r.ocorrencias_serie }} ocorrências)</option>
                    <option value="periodo">Um período da série</option>
                  </select>
                  @if (escopo === 'periodo') {
                    <div class="par-horas"><div><label for="dr-de">De</label><input id="dr-de" type="date" [(ngModel)]="de" /></div>
                      <div><label for="dr-ate">Até</label><input id="dr-ate" type="date" [(ngModel)]="ate" /></div></div>
                  }
                }
                <label for="dr-motivo">Motivo do cancelamento</label>
                <textarea id="dr-motivo" rows="2" maxlength="4000" [(ngModel)]="texto"></textarea>
                <div class="acoes-formulario">
                  <button type="button" class="acao-recusar" [disabled]="!texto.trim() || ocupado()" (click)="cancelar()">Confirmar cancelamento</button>
                  <button type="button" class="acao-secundaria" (click)="painel.set('')">Voltar</button>
                </div>
              </div>
            }
          </div>
        </div>

        @if (r.serie.length) {
          <div class="cartao-dados">
            <header><div><h2>Demais ocorrências da série</h2><small>{{ r.serie.length }} outra(s)</small></div></header>
            <div class="corpo serie">
              @for (o of r.serie; track o.id) {
                <a [routerLink]="['/reserva-espacos/reservas', o.id]" [class.cancelada]="o.status === 'CANCELADA'">{{ data(o.data) }} <small>{{ rotulos[o.status] }}</small></a>
              }
            </div>
          </div>
        }

        <div class="cartao-dados">
          <header><div><h2>Histórico</h2></div></header>
          <div class="corpo">
            <ol class="linha-do-tempo">
              @for (e of r.eventos; track e.id) {
                <li><strong>{{ rotuloEvento(e.tipo) }}</strong> <small>{{ e.usuario_nome }} · {{ e.criado_em | date: 'dd/MM/yyyy HH:mm' }}</small>
                  @if (motivo(e.detalhes); as m) { <p>{{ m }}</p> }</li>
              }
            </ol>
          </div>
        </div>
      </section>
    }
  `,
})
export class DetalheReservaComponent implements OnInit {
  private readonly api = inject(ReservasApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);

  protected readonly r = signal<ReservaDetalhe | null>(null);
  protected readonly painel = signal<'' | 'recusa' | 'cancelar'>('');
  protected readonly ocupado = signal(false);
  protected texto = '';
  protected escopo: EscopoCancelamento = 'ocorrencia';
  protected de = '';
  protected ate = '';
  protected rotulos = ROTULOS_STATUS;
  protected data = dataBr;
  protected hora = horaCurta;

  ngOnInit(): void {
    this.rota.paramMap.subscribe(() => { this.painel.set(''); this.texto = ''; this.carregar(); });
  }

  protected rotuloEvento = (tipo: string) => ROTULOS_EVENTO[tipo] ?? tipo;

  protected motivo(d: Record<string, unknown> | null): string {
    const m = d?.['motivo'] ?? d?.['justificativa'];
    return typeof m === 'string' ? m : '';
  }

  private carregar(): void {
    const id = Number(this.rota.snapshot.paramMap.get('id'));
    this.api.detalhe(id).subscribe({ next: (r) => this.r.set(r), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar a reserva') });
  }

  private concluir<T>(proxima: () => void) {
    return {
      next: () => { this.ocupado.set(false); this.painel.set(''); this.texto = ''; proxima(); },
      error: (e: unknown) => { this.ocupado.set(false); this.dialogos.mostrarErro(e, 'Não foi possível concluir a operação'); },
    } as { next: (v: T) => void; error: (e: unknown) => void };
  }

  protected async deferir(): Promise<void> {
    const r = this.r();
    if (!r) return;
    const serie = r.ocorrencias_serie > 1 ? ` As ${r.ocorrencias_serie} ocorrências da série serão deferidas juntas.` : '';
    if (!(await this.dialogos.confirmar({ titulo: 'Deferir reserva?', mensagem: `"${r.titulo}" em ${r.espaco_nome}.${serie}`, rotuloConfirmar: 'Deferir' }))) return;
    this.ocupado.set(true);
    this.api.analisar(r.id, 'deferir').subscribe(this.concluir(() => this.carregar()));
  }

  protected indeferir(): void {
    this.ocupado.set(true);
    this.api.analisar(this.r()!.id, 'indeferir', this.texto.trim()).subscribe(this.concluir(() => this.carregar()));
  }

  protected cancelar(): void {
    const r = this.r()!;
    this.ocupado.set(true);
    this.api.cancelar(r.id, r.ocorrencias_serie > 1 ? this.escopo : 'ocorrencia', this.texto.trim(), this.de, this.ate).subscribe(this.concluir(() => this.carregar()));
  }
}
