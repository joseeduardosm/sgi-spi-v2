// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela de geração da assinatura de e-mail: formulário, prévia ao vivo, download e cópia.

import { TrilhaComponent } from '../../shared/componentes/trilha/trilha.component';
import { Component, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { AssinaturaApiService, DadosAssinatura } from './assinatura-api.service';

const VAZIO: DadosAssinatura = {
  nome_completo: '', cargo: '', departamento: '', email: '', ramal: '', celular: '', andar: '', lado: '',
  incluir_celular: false, incluir_andar_lado: false,
};

/** Quem ainda não tem o mínimo (nome, cargo e e-mail) não gera a prévia. */
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/**
 * Assinatura de e-mail institucional. Os dados vêm do perfil em vigor e podem ser ajustados só para gerar a imagem (nada
 * é gravado no perfil). A prévia (PNG e HTML) é atualizada 400 ms depois da última tecla.
 */
@Component({
  selector: 'app-assinatura-email',
  imports: [FormsModule, RouterLink, TrilhaComponent],
  template: `
    <section class="painel-gestao assinatura-email">
      <app-trilha [itens]="[{ rotulo: 'Assinatura de e-mail', rota: '/assinatura-email' }]" />
      <div class="barra-ferramentas">
        <div>
          <h2>Assinatura de e-mail</h2>
          <p>Gere a assinatura institucional com os dados do seu perfil. Ajustes feitos aqui valem só para a imagem e não alteram o seu cadastro.</p>
        </div>
      </div>

      @if (!carregado()) {
        <p class="estado-vazio">Carregando…</p>
      } @else {
        @if (faltando().length) {
          <p class="aviso-bloco">Faltam no seu perfil: <b>{{ faltando().join(', ') }}</b>. Preencha abaixo para gerar a assinatura e, depois,
            atualize o <a routerLink="/perfil">perfil</a> para a CGP validar.</p>
        }
        <div class="grade-assinatura">
          <form class="cartao-dados" aria-label="Dados da assinatura" (ngSubmit)="atualizar(0)">
            <header><div><h2>Dados</h2><small>Pré-preenchidos com o seu perfil validado.</small></div></header>
            <div class="corpo campos-assinatura">
              <div class="campo"><label for="as-nome">Nome completo *</label><input id="as-nome" name="nome" maxlength="220" [(ngModel)]="dados.nome_completo" (ngModelChange)="atualizar()" /></div>
              <div class="campo"><label for="as-cargo">Cargo/função *</label><input id="as-cargo" name="cargo" maxlength="180" [(ngModel)]="dados.cargo" (ngModelChange)="atualizar()" /></div>
              <div class="campo"><label for="as-depto">Departamento</label><input id="as-depto" name="departamento" maxlength="180" [(ngModel)]="dados.departamento" (ngModelChange)="atualizar()" /></div>
              <div class="campo"><label for="as-email">E-mail *</label><input id="as-email" name="email" type="email" maxlength="254" [(ngModel)]="dados.email" (ngModelChange)="atualizar()" /></div>
              <div class="campo curto"><label for="as-ramal">Ramal</label><input id="as-ramal" name="ramal" inputmode="numeric" maxlength="20" [(ngModel)]="dados.ramal" (ngModelChange)="atualizar()" />
                <small class="ajuda">Sai como {{ prefixo() }}{{ dados.ramal || 'XXXX' }}.</small></div>
              <div class="campo curto"><label for="as-celular">Celular</label><input id="as-celular" name="celular" inputmode="tel" maxlength="30" [(ngModel)]="dados.celular" (ngModelChange)="atualizar()" /></div>
              <div class="opcoes-assinatura">
                <label class="opcao"><input type="checkbox" name="incluir_celular" [(ngModel)]="dados.incluir_celular" (ngModelChange)="atualizar(0)" />
                  <span><strong>Incluir o celular</strong><small>Aparece ao lado do telefone.</small></span></label>
                <label class="opcao"><input type="checkbox" name="incluir_andar_lado" [(ngModel)]="dados.incluir_andar_lado" (ngModelChange)="atualizar(0)" />
                  <span><strong>Incluir andar e lado</strong><small>Ex.: {{ dados.andar ? dados.andar + 'º andar' : '5º andar' }} · Lado {{ dados.lado || 'B' }} (do seu perfil).</small></span></label>
              </div>
            </div>
          </form>

          <section class="cartao-dados" aria-label="Prévia da assinatura">
            <header><div><h2>Prévia</h2><small>Imagem em alta resolução, exibida no tamanho de e-mail (564 px).</small></div></header>
            <div class="corpo">
              @if (pngSrc(); as src) {
                <div class="moldura-previa"><img [src]="src" alt="Prévia da assinatura de e-mail" width="564" /></div>
              } @else {
                <div class="moldura-previa vazia">{{ motivoSemPrevia() }}</div>
              }
              @for (a of avisos(); track a) { <p class="aviso-bloco">{{ a }}</p> }

              <div class="acoes-assinatura">
                <button type="button" class="acao-primaria" [disabled]="!pngSrc() || ocupado()" (click)="baixarPng()">Baixar PNG</button>
                <button type="button" class="acao-secundaria" [disabled]="!htmlBruto() || ocupado()" (click)="copiar()">Copiar assinatura</button>
                <button type="button" class="acao-secundaria" [disabled]="!htmlBruto() || ocupado()" (click)="baixarHtml()">Baixar HTML</button>
              </div>

              @if (htmlSeguro(); as html) {
                <details class="versao-html">
                  <summary>Ver a versão em HTML (texto selecionável, e-mail e telefone clicáveis)</summary>
                  <iframe title="Assinatura em HTML" [srcdoc]="html"></iframe>
                </details>
              }
            </div>
          </section>
        </div>

        <section class="cartao-dados" aria-labelledby="titulo-instalar">
          <header><div><h2 id="titulo-instalar">Como instalar</h2><small>Use <b>Copiar assinatura</b> e cole no editor de assinaturas. Se preferir a imagem, insira o PNG e deixe-o com 564 px de largura.</small></div></header>
          <div class="corpo instalar-assinatura">
            <details open><summary>Outlook (novo) e Outlook na web</summary>
              <ol><li>Clique na engrenagem (<b>Configurações</b>) &gt; <b>Conta</b> &gt; <b>Assinaturas</b> &gt; <b>Nova assinatura</b>.</li>
                <li>Cole (<kbd>Ctrl</kbd>+<kbd>V</kbd>) no editor e dê um nome à assinatura.</li>
                <li>Escolha a assinatura para novas mensagens e respostas e clique em <b>Salvar</b>.</li></ol></details>
            <details><summary>Outlook clássico (Windows)</summary>
              <ol><li><b>Arquivo</b> &gt; <b>Opções</b> &gt; <b>Email</b> &gt; <b>Assinaturas</b> &gt; <b>Novo</b>.</li>
                <li>Cole a assinatura no editor, defina o padrão para novas mensagens e respostas e confirme com <b>OK</b>.</li></ol></details>
            <details><summary>Gmail e outros webmails</summary>
              <ol><li>Abra as configurações e procure <b>Assinatura</b>.</li><li>Crie uma assinatura, cole o conteúdo copiado e salve.</li></ol></details>
          </div>
        </section>
      }
    </section>
  `,
})
export class AssinaturaEmailComponent implements OnInit, OnDestroy {
  private readonly api = inject(AssinaturaApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly sanitizador = inject(DomSanitizer);
  private temporizador: ReturnType<typeof setTimeout> | undefined;
  /** Chamada mais recente: respostas antigas (digitação rápida) são descartadas. */
  private sequencia = 0;

  protected readonly prefixo = signal('');
  protected dados: DadosAssinatura = { ...VAZIO };
  protected readonly carregado = signal(false);
  protected readonly faltando = signal<string[]>([]);
  protected readonly pngSrc = signal<string | null>(null);
  protected readonly htmlBruto = signal<string | null>(null);
  protected readonly htmlSeguro = signal<SafeHtml | null>(null);
  protected readonly avisos = signal<string[]>([]);
  protected readonly motivoSemPrevia = signal('Preencha nome, cargo e e-mail para ver a prévia.');
  protected readonly ocupado = signal(false);

  ngOnInit(): void {
    this.api.dados().subscribe({
      next: (d) => {
        const { faltando, telefone_prefixo, ...resto } = d;
        this.prefixo.set(telefone_prefixo);
        this.dados = { ...VAZIO, ...resto };
        this.faltando.set(faltando);
        this.carregado.set(true);
        this.atualizar(0);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar os dados do perfil'),
    });
  }

  ngOnDestroy(): void {
    clearTimeout(this.temporizador);
  }

  /** O mínimo para gerar: nome, cargo e e-mail válido. */
  private completo(): boolean {
    return !!this.dados.nome_completo.trim() && !!this.dados.cargo.trim() && EMAIL.test(this.dados.email.trim());
  }

  /** Atualiza a prévia depois de `atraso` ms (a cada tecla o tempo recomeça). */
  protected atualizar(atraso = 400): void {
    clearTimeout(this.temporizador);
    if (!this.completo()) {
      this.pngSrc.set(null);
      this.htmlBruto.set(null);
      this.htmlSeguro.set(null);
      this.avisos.set([]);
      this.motivoSemPrevia.set('Preencha nome, cargo e um e-mail válido para ver a prévia.');
      return;
    }
    this.temporizador = setTimeout(() => {
      const numero = ++this.sequencia;
      this.api.previa(this.dados).subscribe({
        next: (p) => {
          if (numero !== this.sequencia) return;
          this.pngSrc.set(`data:image/png;base64,${p.png_base64}`);
          this.htmlBruto.set(p.html);
          // O HTML vem do servidor, com todo texto digitado escapado
          this.htmlSeguro.set(this.sanitizador.bypassSecurityTrustHtml(`<body style="margin:12px;font-family:Arial,sans-serif">${p.html}</body>`));
          this.avisos.set(p.avisos);
        },
        error: (e) => {
          if (numero !== this.sequencia) return;
          this.pngSrc.set(null);
          this.motivoSemPrevia.set(e?.error?.detalhe ?? 'Não foi possível gerar a prévia.');
        },
      });
    }, atraso);
  }

  protected baixarPng(): void {
    this.executar(this.api.baixarPng(this.dados), 'Gerando o PNG…');
  }

  protected baixarHtml(): void {
    this.executar(this.api.baixarHtml(this.dados), 'Gerando o HTML…');
  }

  private executar(chamada: ReturnType<AssinaturaApiService['baixarPng']>, mensagem: string): void {
    this.ocupado.set(true);
    this.dialogos.executar(chamada, mensagem).subscribe({
      next: () => this.ocupado.set(false),
      error: (e) => {
        this.ocupado.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível gerar a assinatura');
      },
    });
  }

  /** Copia a assinatura como HTML (e texto simples): ao colar no Outlook ou no webmail ela mantém o layout e os links. */
  protected async copiar(): Promise<void> {
    const html = this.htmlBruto();
    if (!html) return;
    const texto = new DOMParser().parseFromString(html, 'text/html').body.innerText || '';
    try {
      await navigator.clipboard.write([new ClipboardItem({
        'text/html': new Blob([html], { type: 'text/html' }),
        'text/plain': new Blob([texto], { type: 'text/plain' }),
      })]);
      this.dialogos.avisar('Assinatura copiada', 'Cole (Ctrl+V) no editor de assinaturas do seu e-mail. Veja os passos em "Como instalar".');
    } catch {
      this.dialogos.avisar('Não foi possível copiar', 'O navegador bloqueou a cópia. Use "Baixar HTML" ou "Baixar PNG" e siga os passos em "Como instalar".');
    }
  }
}
