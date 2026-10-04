// Criado por José Eduardo Santana Martins
// Este arquivo serve para desenhar o cartão de visita de um contato do diretório de ramais, com as ações rápidas.

import { ChangeDetectionStrategy, Component, computed, input, output, signal } from '@angular/core';

import { AvatarComponent } from './avatar.component';
import { Contato, seloFerias } from './diretorio.models';

/** Cartão no formato de cartão de visita (proporção 85 × 55): foto, nome, cargo, setor e ramal em destaque. */
@Component({
  selector: 'app-cartao-contato',
  imports: [AvatarComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <article class="cartao-visita" [class.em-ferias]="!!selo()">
      <button type="button" class="favorito" [class.ativo]="contato().favorito" [attr.aria-pressed]="contato().favorito"
              [attr.aria-label]="(contato().favorito ? 'Remover dos favoritos: ' : 'Fixar nos favoritos: ') + contato().nome"
              (click)="favoritar.emit(contato())">{{ contato().favorito ? '★' : '☆' }}</button>
      <button type="button" class="corpo-cartao" (click)="abrir.emit(contato())" [attr.aria-label]="'Abrir o cartão de ' + contato().nome">
        <app-avatar [nome]="contato().nome" [foto]="contato().foto_url" />
        <span class="dados-cartao">
          <strong class="nome-cartao" [title]="contato().nome">{{ contato().nome }}</strong>
          @if (contato().cargo) { <span class="cargo-cartao" [title]="contato().cargo">{{ contato().cargo }}</span> }
          @if (contato().setor) { <span class="setor-cartao" [title]="contato().setor">{{ contato().setor }}</span> }
          <span class="ramal-cartao"><small>Ramal</small> {{ contato().ramal }}</span>
          @if (contato().local) { <span class="local-cartao">{{ contato().local }}</span> }
        </span>
      </button>
      @if (selo()) { <span class="selo-ferias" role="status">🌴 {{ selo() }}</span> }
      <footer class="acoes-cartao-visita">
        <button type="button" (click)="copiar()" [title]="copiado() ? 'Copiado!' : 'Copiar ramal'">{{ copiado() ? '✓' : '⧉' }}<span>Ramal</span></button>
        <a [href]="'tel:' + contato().ramal" title="Ligar para o ramal">☎<span>Ligar</span></a>
        @if (contato().email) { <a [href]="'mailto:' + contato().email" title="Enviar e-mail">✉<span>E-mail</span></a> }
        @if (contato().email) {
          <a [href]="teams()" target="_blank" rel="noopener" title="Conversar no Teams">💬<span>Teams</span></a>
        }
        @if (contato().linkedin) { <a [href]="contato().linkedin" target="_blank" rel="noopener noreferrer" title="Perfil no LinkedIn">in<span>LinkedIn</span></a> }
        @if (contato().whatsapp_url) { <a [href]="contato().whatsapp_url" target="_blank" rel="noopener" title="WhatsApp">✆<span>WhatsApp</span></a> }
      </footer>
    </article>
  `,
})
export class CartaoContatoComponent {
  readonly contato = input.required<Contato>();
  readonly abrir = output<Contato>();
  readonly favoritar = output<Contato>();
  protected readonly copiado = signal(false);
  protected readonly selo = computed(() => seloFerias(this.contato()));
  protected readonly teams = computed(() => `https://teams.microsoft.com/l/chat/0/0?users=${encodeURIComponent(this.contato().email)}`);

  protected copiar(): void {
    navigator.clipboard?.writeText(this.contato().ramal).then(() => {
      this.copiado.set(true);
      setTimeout(() => this.copiado.set(false), 1500);
    }, () => undefined);
  }
}
