// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o mural de parabéns de um aniversariante e permitir deixar ou apagar um recado.

import { DatePipe } from '@angular/common';
import { Component, inject, input, OnInit, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { Aniversariante, diaMes, MAXIMO_RECADO, Parabens } from './diretorio.models';
import { DiretorioApiService } from './diretorio-api.service';
import { AvatarComponent } from './avatar.component';
import { LinkificarPipe } from '../../shared/utilitarios/linkificar.pipe';

@Component({
  selector: 'app-mural-parabens',
  imports: [LinkificarPipe, FormsModule, DatePipe, AvatarComponent],
  template: `
    <div class="fundo-modal" (click)="fechar.emit()"></div>
    <section class="modal-portal" role="dialog" aria-modal="true" aria-label="Mural de parabéns">
      <header><h2>🎉 Mural de parabéns</h2><button type="button" class="fechar" aria-label="Fechar" (click)="fechar.emit()">×</button></header>
      <div class="corpo-mural">
        <div class="homenageado">
          <app-avatar [nome]="pessoa().nome" [foto]="pessoa().foto_url" />
          <div><strong>{{ pessoa().nome }}</strong><small>{{ pessoa().cargo }} · {{ data() }}</small></div>
        </div>
        <ul class="recados">
          @for (r of recados(); track r.id) {
            <li><p [innerHTML]="r.texto | linkificar"></p>
              <small>{{ r.autor_nome }} · {{ r.criado_em | date: 'dd/MM HH:mm' }}
                @if (r.meu) { · <button type="button" class="link-apagar" (click)="apagar()">apagar</button> }</small></li>
          } @empty { <li class="estado-vazio">{{ carregando() ? 'Carregando…' : 'Ainda não há recados. Seja o primeiro!' }}</li> }
        </ul>
        @if (pessoa().pode_parabenizar && !jaEscrevi()) {
          <form (submit)="$event.preventDefault(); enviar()">
            <textarea class="form-control" rows="3" name="texto" [(ngModel)]="texto" [maxlength]="maximo" placeholder="Escreva um recado carinhoso…"
                      aria-label="Seu recado"></textarea>
            <div class="rodape-recado"><small>{{ texto.length }}/{{ maximo }}</small>
              <button type="submit" class="acao-primaria" [disabled]="!texto.trim() || enviando()">Enviar parabéns</button></div>
          </form>
        } @else if (!pessoa().pode_parabenizar) {
          <p class="dica-formulario">Só é possível deixar parabéns no dia do aniversário.</p>
        }
      </div>
    </section>
  `,
})
export class MuralParabensComponent implements OnInit {
  readonly pessoa = input.required<Aniversariante>();
  readonly fechar = output<void>();
  /** Avisa a lista que os recados mudaram (contador e botão). */
  readonly alterou = output<void>();
  private readonly api = inject(DiretorioApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly recados = signal<Parabens[]>([]);
  protected readonly carregando = signal(true);
  protected readonly enviando = signal(false);
  protected readonly maximo = MAXIMO_RECADO;
  protected texto = '';

  protected data(): string { return diaMes(this.pessoa().dia, this.pessoa().mes); }
  protected jaEscrevi(): boolean { return this.recados().some((r) => r.meu); }

  ngOnInit(): void {
    this.api.mural(this.pessoa().id).subscribe({
      next: (r) => { this.recados.set(r); this.carregando.set(false); },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível abrir o mural'); },
    });
  }

  protected enviar(): void {
    this.enviando.set(true);
    this.api.parabenizar(this.pessoa().id, this.texto.trim()).subscribe({
      next: (r) => { this.recados.update((l) => [...l, r]); this.texto = ''; this.enviando.set(false); this.alterou.emit(); },
      error: (e) => { this.enviando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível enviar o recado'); },
    });
  }

  protected apagar(): void {
    this.api.apagarRecado(this.pessoa().id).subscribe({
      next: () => { this.recados.update((l) => l.filter((r) => !r.meu)); this.alterou.emit(); },
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }
}
