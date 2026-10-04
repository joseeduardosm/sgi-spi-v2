// Criado por José Eduardo Santana Martins
// Este arquivo serve para o usuário enviar ou remover a própria foto e escolher se aparece nos aniversariantes (usado no Perfil e nos Ramais).

import { Component, inject, OnInit, output, signal } from '@angular/core';

import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { AvatarComponent } from './avatar.component';
import { Preferencias } from './diretorio.models';
import { DiretorioApiService } from './diretorio-api.service';

@Component({
  selector: 'app-foto-perfil',
  imports: [AvatarComponent],
  template: `
    @if (prefs(); as p) {
      <div class="corpo-preferencias">
        <app-avatar [nome]="nome()" [foto]="p.foto_url" />
        <div>
          <p class="apagado">PNG ou JPG de até 5 MB, recortada em quadrado. Aparece no seu cartão de Ramais e nos aniversariantes.
            {{ p.foto_origem === 'ldap' ? 'Esta foto veio do diretório corporativo; se você enviar outra, ela passa a valer.' : '' }}</p>
          <label class="acao-secundaria escolher-foto" [class.desabilitado]="enviando()">
            {{ enviando() ? 'Enviando…' : (p.foto_url ? 'Trocar foto' : 'Escolher foto') }}
            <input type="file" accept="image/png,image/jpeg" hidden [disabled]="enviando()" (change)="escolher($event)" />
          </label>
          @if (p.foto_url) { <button type="button" class="acao-secundaria" (click)="remover()">Remover foto</button> }
        </div>
      </div>
      <label class="opcao-privacidade">
        <input type="checkbox" [checked]="p.ocultar_aniversario" (change)="ocultar($event)" />
        <span>Não mostrar meu aniversário<small>Você sai das listas de aniversariantes, não recebe recados no mural nem o parabéns automático.</small></span>
      </label>
    } @else { <p class="estado-vazio">Carregando…</p> }
  `,
})
export class FotoPerfilComponent implements OnInit {
  /** Avisa a tela que a foto mudou, para recarregar os cartões. */
  readonly alterou = output<void>();
  private readonly api = inject(DiretorioApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly nome = signal(inject(AutenticacaoService).usuario()?.nome_completo ?? '');
  protected readonly prefs = signal<Preferencias | null>(null);
  protected readonly enviando = signal(false);

  ngOnInit(): void {
    this.api.preferencias().subscribe({ next: (p) => this.prefs.set(p), error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected escolher(evento: Event): void {
    const entrada = evento.target as HTMLInputElement;
    const arquivo = entrada.files?.[0];
    entrada.value = '';
    if (!arquivo) return;
    this.enviando.set(true);
    this.api.enviarFoto(arquivo).subscribe({
      next: (p) => { this.prefs.set(p); this.enviando.set(false); this.alterou.emit(); },
      error: (e) => { this.enviando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível enviar a foto'); },
    });
  }

  protected remover(): void {
    this.api.removerFoto().subscribe({ next: (p) => { this.prefs.set(p); this.alterou.emit(); }, error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected ocultar(evento: Event): void {
    const marcado = (evento.target as HTMLInputElement).checked;
    this.api.ocultarAniversario(marcado).subscribe({ next: (p) => this.prefs.set(p), error: (e) => this.dialogos.mostrarErro(e) });
  }
}
