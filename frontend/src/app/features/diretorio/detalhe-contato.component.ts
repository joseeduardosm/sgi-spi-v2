// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o cartão completo de um contato (chefia, equipe, QR Code, vCard e ações) numa janela.

import { Component, DestroyRef, effect, inject, input, output, signal, untracked } from '@angular/core';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { AvatarComponent } from './avatar.component';
import { ContatoDetalhe, ContatoResumo, dataBr } from './diretorio.models';
import { DiretorioApiService } from './diretorio-api.service';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
@Component({
  selector: 'app-detalhe-contato',
  imports: [EsqueletoComponent, AvatarComponent],
  template: `
    <div animate.leave="mov-fundo-sai" class="fundo-modal" (click)="fechar.emit()"></div>
    <section animate.leave="mov-modal-sai" class="modal-portal modal-largo detalhe-contato" role="dialog" aria-modal="true" aria-label="Cartão do contato">
      <header>
        <h2>Cartão de contato</h2>
        <button type="button" class="fechar" aria-label="Fechar" (click)="fechar.emit()">×</button>
      </header>
      @if (contato(); as c) {
        <div class="corpo-detalhe-contato">
          <!-- Coluna da pessoa: identidade, contatos, curtir e QR Code -->
          <aside class="coluna-pessoa">
            <div class="identidade-detalhe">
              <app-avatar [nome]="c.nome" [foto]="c.foto_url" />
              <div>
                <h3>{{ c.nome }}</h3>
                @if (c.cargo) { <p>{{ c.cargo }}</p> }
                @if (c.setor) { <p class="apagado">{{ c.setor }}</p> }
              </div>
            </div>
            @if (c.ferias_fim) { <span class="selo-ferias" role="status">🌴 De férias até {{ dataBr(c.ferias_fim) }}</span> }

            <dl class="campos-detalhe">
              <div><dt>Ramal</dt><dd class="destaque">{{ c.ramal }}</dd></div>
              @if (c.email) { <div><dt>E-mail</dt><dd><a [href]="'mailto:' + c.email">{{ c.email }}</a></dd></div> }
              @if (c.celular) {
                <div class="largo"><dt>Celular</dt>
                  <dd class="com-acao">{{ c.celular }}
                    @if (c.whatsapp_url) {
                      <a class="acao-secundaria acao-pequena botao-icone" [href]="c.whatsapp_url" target="_blank" rel="noopener noreferrer" aria-label="Abrir conversa no WhatsApp" title="Abrir conversa no WhatsApp">
                        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="12" cy="12" r="11" fill="#25D366" /><path d="M12 5.4a6.6 6.6 0 0 0-5.7 9.9l-.9 3.3 3.4-.9A6.6 6.6 0 1 0 12 5.4Z" fill="none" stroke="#fff" stroke-width="1.5" /><path d="M9.6 9.2c.2-.4.5-.4.7-.4l.5 1.2c-.1.3-.4.6-.5.7.5 1 1.3 1.7 2.3 2.2.2-.2.5-.6.7-.7l1.2.6c0 .3-.1.7-.4 1-.7.6-1.6.4-2.6-.1-1.5-.7-2.6-1.9-3.2-3.2-.3-.7-.1-1.2.3-1.6Z" fill="#fff" /></svg>
                      </a>
                    }
                  </dd></div>
              }
              @if (c.local) { <div><dt>Localização</dt><dd>{{ c.local }}</dd></div> }
              <div><dt>LinkedIn</dt>
                <dd>
                  <!-- Preenchido: botão que abre o perfil. Vazio: o botão aparece apagado e sem clique -->
                  @if (c.linkedin) {
                    <a class="acao-secundaria acao-pequena botao-icone" [href]="c.linkedin" target="_blank" rel="noopener noreferrer" aria-label="Abrir o perfil no LinkedIn" title="Abrir o perfil no LinkedIn">
                      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><rect x="1" y="1" width="22" height="22" rx="4" fill="#0A66C2" /><rect x="5.6" y="9.5" width="2.6" height="8.4" fill="#fff" /><circle cx="6.9" cy="6.6" r="1.5" fill="#fff" /><path d="M10.4 9.5h2.4v1.1c.4-.7 1.3-1.3 2.6-1.3 2.5 0 3.1 1.6 3.1 3.8v4.8h-2.5v-4.2c0-1-.1-2.1-1.4-2.1s-1.7 1-1.7 2.1v4.2h-2.5V9.5Z" fill="#fff" /></svg>
                    </a>
                  } @else {
                    <button type="button" class="acao-secundaria acao-pequena botao-icone" disabled aria-label="LinkedIn não informado" title="LinkedIn não informado">
                      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><rect x="1" y="1" width="22" height="22" rx="4" fill="currentColor" /><rect x="5.6" y="9.5" width="2.6" height="8.4" fill="#fff" /><circle cx="6.9" cy="6.6" r="1.5" fill="#fff" /><path d="M10.4 9.5h2.4v1.1c.4-.7 1.3-1.3 2.6-1.3 2.5 0 3.1 1.6 3.1 3.8v4.8h-2.5v-4.2c0-1-.1-2.1-1.4-2.1s-1.7 1-1.7 2.1v4.2h-2.5V9.5Z" fill="#fff" /></svg>
                    </button>
                  }
                </dd></div>
            </dl>

            <!-- Curtir: todos veem o total; só o dono vê quem curtiu (lista na coluna ao lado) -->
            <div class="curtir-detalhe">
              @if (c.pode_curtir) {
                <button type="button" class="acao-secundaria acao-pequena botao-curtir" [class.curtido]="c.curtido" [attr.aria-pressed]="c.curtido" [disabled]="curtindo()" (click)="curtir(c)">
                  <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M7 11v9H4v-9h3Zm0 0 4-7c1.5 0 2.5 1.2 2.2 2.7L12.7 10H19a2 2 0 0 1 1.9 2.6l-1.8 6A2 2 0 0 1 17.2 20H7" [attr.fill]="c.curtido ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" /></svg>
                  {{ c.curtido ? 'Curtido' : 'Curtir' }}
                </button>
              }
              @if (c.curtidas) { <span class="total-curtidas">{{ c.curtidas }} {{ c.curtidas === 1 ? 'curtida' : 'curtidas' }}</span> }
            </div>

            <div class="qr-detalhe">
              @if (qr()) { <img loading="lazy" decoding="async" [src]="qr()" alt="QR Code com o contato (vCard)" width="104" height="104" /> }
              <p>Aponte a câmera do celular para salvar o contato.</p>
            </div>
          </aside>

          <!-- Coluna do conteúdo: sobre, curtidas (só do dono), chefia e equipe em grade -->
          <div class="coluna-conteudo">
            @if (c.bio) {
              <h4>Sobre</h4>
              <p class="bio-detalhe">{{ c.bio }}</p>
            }
            @if (c.curtido_por?.length) {
              <h4>Curtido por ({{ c.curtido_por!.length }})</h4>
              <div class="pessoas-detalhe">
                @for (p of c.curtido_por; track p.id) {
                  <button type="button" (click)="abrirOutro.emit(p.id)"><app-avatar [nome]="p.nome" [foto]="p.foto_url" /><span>{{ p.nome }}<small>{{ p.cargo }}</small></span></button>
                }
              </div>
            }
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
            @if (!c.bio && !c.chefia && !c.equipe.length && !c.curtido_por?.length) {
              <p class="apagado">Esta pessoa ainda não preencheu a bio, e não há chefia nem equipe cadastradas.</p>
            }
          </div>
        </div>
        <footer>
          <button type="button" class="acao-secundaria" (click)="baixar(c)">Baixar vCard (.vcf)</button>
          <button type="button" class="acao-primaria" (click)="fechar.emit()">Fechar</button>
        </footer>
      } @else {
        <app-esqueleto tipo="formulario" [linhas]="5" />
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
  protected readonly curtindo = signal(false);
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

  /** Curte ou descurte; recarrega o cartão para o total e o estado virem do servidor. */
  protected curtir(c: ContatoDetalhe): void {
    this.curtindo.set(true);
    this.api.curtir(c.id, !c.curtido).subscribe({
      next: () => this.api.detalhe(c.id).subscribe({ next: (novo) => { this.contato.set(novo); this.curtindo.set(false); }, error: () => this.curtindo.set(false) }),
      error: (e) => { this.curtindo.set(false); this.dialogos.mostrarErro(e, 'Não foi possível curtir'); },
    });
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
