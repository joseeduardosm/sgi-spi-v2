// Criado por José Eduardo Santana Martins
// Este arquivo serve para configurar a Reserva de Espaços: horário de funcionamento, antecedência, duração máxima e fiscais (SuperRoot grava).

import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoReservasComponent } from './cabecalho-reservas.component';
import { ReservasApiService } from './reservas-api.service';
import { Configuracao, UsuarioBusca } from './reservas.models';

@Component({
  selector: 'app-configuracao-reservas',
  imports: [FormsModule, CabecalhoReservasComponent],
  template: `
    <app-cabecalho-reservas titulo="Configuração" descricao="Regras gerais e quem atua como fiscal da reserva de espaços." />
    <section class="painel-gestao protocolo reservas">
      @if (cfg(); as c) {
        @if (!superRoot) { <p class="aviso-formulario">Somente o SuperRoot altera a configuração.</p> }
        <form class="grade-formulario" (ngSubmit)="salvar()">
          <div><label for="cf-ab">Abertura</label><input id="cf-ab" name="ab" type="time" required [disabled]="!superRoot" [(ngModel)]="c.hora_abertura" /></div>
          <div><label for="cf-fe">Fechamento</label><input id="cf-fe" name="fe" type="time" required [disabled]="!superRoot" [(ngModel)]="c.hora_fechamento" /></div>
          <div><label for="cf-ant">Antecedência mínima (horas; 0 = sem limite)</label><input id="cf-ant" name="ant" type="number" min="0" max="720" [disabled]="!superRoot" [(ngModel)]="c.antecedencia_minima_horas" /></div>
          <div><label for="cf-dur">Duração máxima (horas; 0 = sem limite)</label><input id="cf-dur" name="dur" type="number" min="0" max="24" [disabled]="!superRoot" [(ngModel)]="c.duracao_maxima_horas" /></div>
          <div class="ocupa-duas"><label>Fiscais</label>
            <ul class="lista-fiscais">
              @for (f of c.fiscais; track f.id) {
                <li>{{ f.nome }} <small>{{ f.login }}</small>@if (superRoot) { <button type="button" class="acao-recusar acao-pequena" (click)="remover(f)">Remover</button> }</li>
              } @empty { <li class="estado-vazio">Nenhum fiscal: as solicitações são avisadas aos SuperRoots.</li> }
            </ul>
            @if (superRoot) {
              <input name="busca" placeholder="Adicionar fiscal: digite o nome ou login" [ngModel]="busca" (ngModelChange)="buscar($event)" autocomplete="off" />
              @if (encontrados().length) { <ul class="lista-busca">@for (u of encontrados(); track u.id) { <li><button type="button" (click)="adicionar(u)">{{ u.nome }} <small>{{ u.login }}</small></button></li> }</ul> }
            }
          </div>
          @if (superRoot) { <div class="ocupa-duas acoes-formulario"><button type="submit" class="acao-primaria">Salvar configuração</button></div> }
        </form>
      }
    </section>
  `,
})
export class ConfiguracaoReservasComponent implements OnInit {
  private readonly api = inject(ReservasApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly superRoot = inject(AutenticacaoService).possuiPapel('SuperRoot');
  protected readonly cfg = signal<Configuracao | null>(null);
  protected readonly encontrados = signal<UsuarioBusca[]>([]);
  protected busca = '';

  ngOnInit(): void {
    this.api.configuracao().subscribe({ next: (c) => this.cfg.set({ ...c, hora_abertura: c.hora_abertura.slice(0, 5), hora_fechamento: c.hora_fechamento.slice(0, 5) }), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar a configuração') });
  }

  protected buscar(texto: string): void {
    this.busca = texto;
    if (texto.trim().length < 2) return this.encontrados.set([]);
    this.api.usuarios(texto.trim()).subscribe((u) => this.encontrados.set(u));
  }

  protected adicionar(u: UsuarioBusca): void {
    const c = this.cfg()!;
    if (!c.fiscais.some((f) => f.id === u.id)) this.cfg.set({ ...c, fiscais: [...c.fiscais, u] });
    this.busca = '';
    this.encontrados.set([]);
  }

  protected remover(f: UsuarioBusca): void {
    const c = this.cfg()!;
    this.cfg.set({ ...c, fiscais: c.fiscais.filter((x) => x.id !== f.id) });
  }

  protected salvar(): void {
    const { fiscais, ...resto } = this.cfg()!;
    this.api.gravarConfiguracao({ ...resto, fiscais_ids: fiscais.map((f) => f.id) }).subscribe({
      next: (c) => { this.cfg.set({ ...c, hora_abertura: c.hora_abertura.slice(0, 5), hora_fechamento: c.hora_fechamento.slice(0, 5) }); this.dialogos.avisar('Configuração salva', 'As regras e a lista de fiscais foram atualizadas.'); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar a configuração'),
    });
  }
}
