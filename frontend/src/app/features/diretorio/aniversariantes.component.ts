// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir na página inicial os aniversariantes de hoje, da semana e do mês, com acesso ao mural de parabéns.

import { Component, inject, OnInit, signal } from '@angular/core';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { AvatarComponent } from './avatar.component';
import { Aniversariante, diaMes, PeriodoAniversario, quando, ROTULOS_PERIODO } from './diretorio.models';
import { DiretorioApiService } from './diretorio-api.service';
import { MuralParabensComponent } from './mural-parabens.component';

const CHAVE_FECHADO = 'diretorio.aniversariantes.fechado_ate';
const SETE_DIAS_MS = 7 * 24 * 60 * 60 * 1000;

/** Instante (ms) até o qual o usuário pediu para esconder o quadro, ou 0 se não pediu ou já venceu. */
function fechadoAte(): number {
  try {
    const ate = Number(localStorage.getItem(CHAVE_FECHADO));
    return ate > Date.now() ? ate : 0;
  } catch { return 0; }
}

@Component({
  selector: 'app-aniversariantes',
  imports: [AvatarComponent, MuralParabensComponent],
  template: `
    @if (visivel()) {
    <section class="cartao-dados aniversariantes" aria-label="Aniversariantes">
      <header>
        <h2>🎂 Aniversariantes</h2>
        <div class="abas-periodo" role="tablist">
          @for (p of periodos; track p) {
            <button type="button" role="tab" [attr.aria-selected]="p === periodo()" [class.ativa]="p === periodo()" (click)="trocar(p)">{{ rotulos[p] }}</button>
          }
        </div>
        <button type="button" class="fechar-aniversariantes" (click)="fechar()" title="Fechar por 7 dias" aria-label="Fechar aniversariantes por 7 dias">×</button>
      </header>
      <ul>
        @for (a of lista(); track a.id) {
          <li [class.hoje]="a.e_hoje">
            <app-avatar [nome]="a.nome" [foto]="a.foto_url" />
            <div class="quem"><strong>{{ a.nome }}</strong><small>{{ a.setor || a.cargo }}</small></div>
            <div class="quando"><b>{{ a.e_hoje ? '🎉 Hoje' : diaMes(a.dia, a.mes) }}</b><small>{{ a.e_hoje ? diaMes(a.dia, a.mes) : quando(a.dias_restantes) }}</small></div>
            @if (a.pode_parabenizar || a.total_parabens) {
              <button type="button" class="acao-secundaria" (click)="mural.set(a)">
                {{ a.ja_parabenizei ? 'Ver mural' : (a.pode_parabenizar ? 'Parabenizar' : 'Mural') }}@if (a.total_parabens) { ({{ a.total_parabens }}) }</button>
            }
          </li>
        } @empty { <li class="estado-vazio">{{ carregando() ? 'Carregando…' : semAniversario() }}</li> }
      </ul>
    </section>
    }
    @if (mural(); as m) { <app-mural-parabens [pessoa]="m" (fechar)="mural.set(null)" (alterou)="carregar()" /> }
  `,
})
export class AniversariantesComponent implements OnInit {
  private readonly api = inject(DiretorioApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly periodos: PeriodoAniversario[] = ['dia', 'semana', 'mes'];
  protected readonly rotulos = ROTULOS_PERIODO;
  protected readonly periodo = signal<PeriodoAniversario>('semana');
  protected readonly lista = signal<Aniversariante[]>([]);
  protected readonly carregando = signal(true);
  protected readonly mural = signal<Aniversariante | null>(null);
  protected readonly diaMes = diaMes;
  protected readonly quando = quando;

  protected readonly visivel = signal(!fechadoAte());

  ngOnInit(): void { if (this.visivel()) this.carregar(); }

  /** Esconde o quadro por 7 dias (guardado neste navegador); depois disso ele volta sozinho. */
  protected fechar(): void {
    try { localStorage.setItem(CHAVE_FECHADO, String(Date.now() + SETE_DIAS_MS)); } catch { /* sem armazenamento: fecha só até recarregar */ }
    this.visivel.set(false);
  }

  protected trocar(p: PeriodoAniversario): void {
    this.periodo.set(p);
    this.carregar();
  }

  protected semAniversario(): string {
    return { dia: 'Ninguém faz aniversário hoje.', semana: 'Nenhum aniversário nos próximos 7 dias.', mes: 'Nenhum aniversário neste mês.' }[this.periodo()];
  }

  protected carregar(): void {
    this.carregando.set(true);
    this.api.aniversariantes(this.periodo()).subscribe({
      next: (l) => { this.lista.set(l); this.carregando.set(false); },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível carregar os aniversariantes'); },
    });
  }
}
