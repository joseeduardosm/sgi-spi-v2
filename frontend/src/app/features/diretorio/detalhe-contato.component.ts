// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o cartão completo de um contato (chefia, equipe, QR Code, vCard e ações) numa janela.

import { Component, DestroyRef, effect, inject, input, output, signal, untracked } from '@angular/core';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { AvatarComponent } from './avatar.component';
import { ContatoDetalhe, ContatoResumo, dataBr } from './diretorio.models';
import { DiretorioApiService } from './diretorio-api.service';

@Component({
  selector: 'app-detalhe-contato',
  imports: [AvatarComponent],
  template: `
    <div class="fundo-modal" (click)="fechar.emit()"></div>
    <section class="modal-portal modal-largo detalhe-contato" role="dialog" aria-modal="true" aria-label="Cartão do contato">
      <header>
        <h2>Cartão de contato</h2>
        <button type="button" class="fechar" aria-label="Fechar" (click)="fechar.emit()">×</button>
      </header>
      @if (contato(); as c) {
        <div class="corpo-detalhe-contato">
          <div class="identidade-detalhe">
            <app-avatar [nome]="c.nome" [foto]="c.foto_url" />
            <div>
              <h3>{{ c.nome }}</h3>
              @if (c.cargo) { <p>{{ c.cargo }}</p> }
              @if (c.setor) { <p class="apagado">{{ c.setor }}</p> }
              @if (c.ferias_fim) { <span class="selo-ferias" role="status">🌴 De férias até {{ dataBr(c.ferias_fim) }}</span> }
            </div>
          </div>
          <dl class="campos-detalhe">
            <div><dt>Ramal</dt><dd class="destaque">{{ c.ramal }}</dd></div>
            @if (c.email) { <div><dt>E-mail</dt><dd><a [href]="'mailto:' + c.email">{{ c.email }}</a></dd></div> }
            @if (c.celular) { <div><dt>Celular</dt><dd>@if (c.whatsapp_url) { <a [href]="c.whatsapp_url" target="_blank" rel="noopener">{{ c.celular }}</a> } @else { {{ c.celular }} }</dd></div> }
            @if (c.linkedin) { <div><dt>LinkedIn</dt><dd><a [href]="c.linkedin" target="_blank" rel="noopener noreferrer">Ver perfil</a></dd></div> }
            @if (c.local) { <div><dt>Localização</dt><dd>{{ c.local }}</dd></div> }
          </dl>
          @if (c.chefia) {
            <h4>Chefia imediata</h4>
            <div class="pessoas-detalhe"><button type="button" (click)="abrirOutro.emit(c.chefia.id)">
              <app-avatar [nome]="c.chefia.nome" [foto]="c.chefia.foto_url" /><span>{{ c.chefia.nome }}<small>{{ c.chefia.cargo }}</small></span></button></div>
          }
          @if (c.equipe.length) {
            <h4>Equipe ({{ c.equipe.length }})</h4>
            <div class="pessoas-detalhe">
              @for (p of c.equipe; track p.id) {
                <button type="button" (click)="abrirOutro.emit(p.id)"><app-avatar [nome]="p.nome" [foto]="p.foto_url" /><span>{{ p.nome }}<small>{{ p.cargo }}</small></span></button>
              }
            </div>
          }
          <div class="qr-detalhe">
            @if (qr()) { <img [src]="qr()" alt="QR Code com o contato (vCard)" width="132" height="132" /> }
            <p>Aponte a câmera do celular para salvar o contato.</p>
          </div>
        </div>
        <footer>
          <button type="button" class="acao-secundaria" (click)="baixar(c)">Baixar vCard (.vcf)</button>
          <button type="button" class="acao-primaria" (click)="fechar.emit()">Fechar</button>
        </footer>
      } @else {
        <p class="estado-vazio">Carregando…</p>
      }
    </section>
  `,
})
export class DetalheContatoComponent {
  readonly contatoId = input.required<number>();
  readonly fechar = output<void>();
  /** Pedido para abrir a chefia ou um integrante da equipe. */
  readonly abrirOutro = output<number>();
  private readonly api = inject(DiretorioApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly contato = signal<ContatoDetalhe | null>(null);
  protected readonly qr = signal<string | null>(null);
  protected readonly dataBr = dataBr;

  constructor() {
    effect(() => {
      const id = this.contatoId();
      // `untracked`: o efeito só deve reagir à troca de contato; ler/gravar `qr` aqui o faria rodar em ciclo (a tela "piscava")
      untracked(() => {
        this.contato.set(null);
        this.liberarQr();
        this.api.detalhe(id).subscribe({
          next: (c) => this.contato.set(c),
          error: (e) => { this.dialogos.mostrarErro(e, 'Não foi possível abrir o contato'); this.fechar.emit(); },
        });
        this.api.qrcode(id).subscribe({ next: (u) => this.qr.set(u), error: () => undefined });
      });
    });
    inject(DestroyRef).onDestroy(() => this.liberarQr());
  }

  protected baixar(c: ContatoDetalhe): void {
    this.api.baixarVcard(c.id, c.nome).subscribe({ error: (e) => this.dialogos.mostrarErro(e) });
  }

  private liberarQr(): void {
    const atual = this.qr();
    if (atual) URL.revokeObjectURL(atual);
    this.qr.set(null);
  }
}
export type { ContatoResumo };
