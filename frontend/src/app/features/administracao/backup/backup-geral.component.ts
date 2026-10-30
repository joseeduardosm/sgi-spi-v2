// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela Administração › Backup: gerar, baixar e importar o backup geral do sistema (banco + anexos). Só SuperRoot.

import { DatePipe, DecimalPipe } from '@angular/common';
import { HttpClient, HttpEventType } from '@angular/common/http';
import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ambiente } from '../../../../environments/ambiente';
import { EsqueletoComponent } from '../../../shared/componentes/esqueleto/esqueleto.component';
import { TrilhaComponent } from '../../../shared/componentes/trilha/trilha.component';
import { EtapaTrilha, TrilhaEtapasComponent } from '../../../shared/componentes/trilha-etapas/trilha-etapas.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';

interface BackupGuardado { nome: string; tamanho: number; criado_em: string; antes_da_importacao: boolean }
interface Andamento {
  operacao: 'gerar' | 'importar' | null;
  situacao: 'em_andamento' | 'concluido' | 'erro' | 'reiniciando' | null;
  mensagem: string;
  arquivo: string | null;
  /** Etapa atual (ou, no erro, a etapa em que parou): ver ETAPAS. */
  etapa: string | null;
  /** 0 a 100, para a barra do modal. */
  percentual: number | null;
  atualizado_em: string | null;
}

/** Etapas mostradas no modal de andamento, na ordem em que o servidor passa por elas. A importação começa pelo envio do arquivo (só no navegador). */
const ETAPAS: Record<'gerar' | 'importar', { id: string; rotulo: string }[]> = {
  gerar: [
    { id: 'banco', rotulo: 'Copiar o banco' },
    { id: 'anexos', rotulo: 'Juntar os anexos' },
    { id: 'finalizar', rotulo: 'Finalizar o .zip' },
  ],
  importar: [
    { id: 'enviar', rotulo: 'Enviar o arquivo' },
    { id: 'guardar', rotulo: 'Guardar o estado atual' },
    { id: 'banco', rotulo: 'Restaurar o banco' },
    { id: 'anexos', rotulo: 'Copiar os anexos' },
    { id: 'migracoes', rotulo: 'Atualizar o banco' },
    { id: 'reiniciar', rotulo: 'Reiniciar o sistema' },
  ],
};
interface PainelBackup { backups: BackupGuardado[]; andamento: Andamento }

/**
 * Backup geral (só SuperRoot): um .zip com o banco inteiro (configurações, ACLs, SMTP, LDAP, tudo) e os anexos.
 * Gerar e importar rodam em segundo plano no servidor; a tela consulta o andamento a cada poucos segundos.
 */
@Component({
  selector: 'app-backup-geral',
  imports: [EsqueletoComponent, FormsModule, DatePipe, DecimalPipe, TrilhaComponent, TrilhaEtapasComponent],
  template: `
    <div class="cabecalho-pagina">
      <div>
        <app-trilha [itens]="[{ rotulo: 'Administração' }, { rotulo: 'Backup' }]" />
        <h1>Backup geral</h1>
        <small>Um arquivo .zip com o banco inteiro (configurações, controle de acesso, servidores SMTP e LDAP, contratos, RH, tudo) e todos os anexos.</small>
      </div>
    </div>

    @if (painel(); as p) {
      @if (p.andamento.situacao; as s) {
        <p class="aviso-bloco" [class.erro]="s === 'erro'" [class.informativo]="s !== 'erro'" role="status">
          {{ p.andamento.mensagem }}@if (s === 'em_andamento') { <span> (atualizando sozinho…)</span> }
        </p>
      }

      <section class="painel-gestao" aria-labelledby="titulo-gerar-backup">
        <div class="barra-ferramentas"><div><h2 id="titulo-gerar-backup">Gerar e baixar</h2>
          <p>O backup é gerado no servidor (pode levar alguns minutos) e fica guardado na lista abaixo para baixar.</p></div>
          <button type="button" class="acao-primaria" [class.carregando]="emAndamento()" [disabled]="emAndamento()" (click)="gerar()">Gerar backup agora</button></div>
        @if (p.backups.length) {
          <div class="tabela-gestao-envoltorio">
            <table class="tabela-gestao">
              <thead><tr><th>Arquivo</th><th>Gerado em</th><th class="num">Tamanho</th><th>Origem</th><th></th></tr></thead>
              <tbody>
                @for (b of p.backups; track b.nome) {
                  <tr>
                    <td><span class="texto-codigo">{{ b.nome }}</span></td>
                    <td>{{ b.criado_em | date: 'dd/MM/yyyy HH:mm' }}</td>
                    <td class="num">{{ tamanho(b.tamanho) }}</td>
                    <td>@if (b.antes_da_importacao) { <span class="selo-situacao alerta">Estado antes de uma importação</span> } @else { <span class="selo-situacao inativo">Gerado na tela</span> }</td>
                    <td><button type="button" class="acao-secundaria acao-pequena" [class.carregando]="baixando() === b.nome" [disabled]="!!baixando()" (click)="baixar(b.nome)">Baixar</button></td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        } @else { <p class="estado-vazio" style="margin: 14px 24px">Nenhum backup guardado ainda.</p> }
      </section>

      <section class="painel-gestao" aria-labelledby="titulo-importar-backup" style="margin-top: 18px">
        <div class="barra-ferramentas"><div><h2 id="titulo-importar-backup">Importar backup</h2>
          <p>Use um .zip gerado nesta tela, deste ou de outro servidor (ex.: produção para homologação).</p></div></div>
        <div class="corpo" style="padding: 0 24px 20px">
          <p class="aviso-bloco erro"><strong>Substitui tudo.</strong> O banco inteiro e todos os anexos deste servidor são trocados pelos do arquivo. Antes, o sistema guarda
            automaticamente um backup do estado atual (aparece na lista acima). As senhas de LDAP e SMTP só funcionam se este servidor usar a mesma
            <span class="texto-codigo">CHAVE_CIFRA_LDAP</span> do servidor de origem. No fim, o sistema reinicia e será preciso entrar de novo.</p>
          <div class="grade-formulario">
            <div><label for="backup-arquivo">Arquivo .zip *</label>
              <input id="backup-arquivo" type="file" accept=".zip,application/zip" (change)="arquivo = $any($event.target).files?.[0] ?? null" /></div>
            <div><label for="backup-confirmacao">Digite SUBSTITUIR para confirmar *</label>
              <input id="backup-confirmacao" autocomplete="off" [(ngModel)]="confirmacao" /></div>
          </div>
          <div class="acoes-formulario">
            <button type="button" class="acao-perigo" [class.carregando]="progressoEnvio() !== null" [disabled]="!arquivo || confirmacao !== 'SUBSTITUIR' || emAndamento() || progressoEnvio() !== null" (click)="importar()">
              {{ progressoEnvio() !== null ? 'Enviando ' + progressoEnvio() + '%' : 'Importar e substituir tudo' }}</button>
          </div>
        </div>
      </section>
    } @else {
      <app-esqueleto tipo="formulario" [linhas]="4" />
    }

    <!-- Modal de andamento: abre ao gerar ou importar e mostra a etapa, a barra e o que o servidor está fazendo agora -->
    @if (modalAberto() && operacaoModal(); as op) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal modal-largo" role="dialog" aria-modal="true" aria-labelledby="titulo-andamento-backup">
        <header>
          <div>
            <span class="modal-sobretitulo">Backup geral</span>
            <h2 id="titulo-andamento-backup">{{ tituloModal() }}</h2>
          </div>
          <button type="button" aria-label="Fechar" (click)="fecharModal()">×</button>
        </header>
        <div class="corpo-andamento">
          <app-trilha-etapas [etapas]="etapasModal()" [mostrarProgresso]="false" ariaLabel="Etapas do backup" />
          <div class="cabeca-andamento">
            <span>{{ mensagemModal() }}</span>
            <b>{{ percentualModal() | number: '1.0-0' }}%</b>
          </div>
          <div class="trilho-andamento" [class.erro]="situacaoModal() === 'erro'" [class.concluido]="situacaoModal() === 'concluido' || situacaoModal() === 'reiniciando'"
               role="progressbar" aria-label="Andamento do backup" aria-valuemin="0" aria-valuemax="100" [attr.aria-valuenow]="percentualModal()" aria-live="polite">
            <i [style.width.%]="percentualModal()"></i>
          </div>
          @if (situacaoModal() === 'erro') {
            <p class="aviso-bloco erro">Parou na etapa destacada. Nada foi trocado se a falha foi antes da restauração do banco; confira a mensagem acima.</p>
          } @else if (situacaoModal() === 'reiniciando') {
            <p class="aviso-bloco informativo">O sistema está reiniciando. Esta página recarrega sozinha quando ele voltar (será preciso entrar de novo).</p>
          } @else if (situacaoModal() !== 'concluido') {
            <p class="dica-andamento">Pode fechar esta janela: o servidor continua e o andamento aparece de novo ao voltar a esta tela.</p>
          }
          <footer>
            @if (situacaoModal() === 'concluido' && painel()?.andamento?.arquivo; as nome) {
              <button type="button" class="acao-secundaria" (click)="fecharModal()">Fechar</button>
              <button type="button" class="acao-primaria" [class.carregando]="baixando() === nome" [disabled]="!!baixando()" (click)="baixar(nome)">Baixar agora</button>
            } @else {
              <button type="button" class="acao-secundaria" (click)="fecharModal()">{{ emAndamento() || progressoEnvio() !== null ? 'Continuar em segundo plano' : 'Fechar' }}</button>
            }
          </footer>
        </div>
      </section>
    }
  `,
  styles: `
    .corpo-andamento { padding: 22px 25px; display: flex; flex-direction: column; gap: 14px; }
    .cabeca-andamento { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; color: var(--spi-texto); font-size: var(--spi-texto-compacto);
      b { font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; } }
    /* Mesmo desenho da barra de prazo / trilha de etapas */
    .trilho-andamento { height: 10px; overflow: hidden; border-radius: var(--spi-raio-pilula); background: var(--spi-borda);
      i { display: block; height: 100%; border-radius: var(--spi-raio-pilula); background: var(--spi-vermelho); transition: width 300ms ease-out; }
      &.concluido i { background: var(--spi-sucesso); }
      &.erro i { background: var(--spi-perigo); } }
    .dica-andamento { margin: 0; color: var(--spi-apagado); font-size: var(--spi-texto-compacto); }
    .aviso-bloco { margin: 0; }
    footer { margin-top: 4px; }
    @media (prefers-reduced-motion: reduce) { .trilho-andamento i { transition: none; } }
  `,
})
export class BackupGeralComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly dialogos = inject(DialogosService);
  private readonly base = `${ambiente.urlApi}/admin/backups`;

  protected readonly painel = signal<PainelBackup | null>(null);
  protected readonly baixando = signal<string | null>(null);
  protected readonly progressoEnvio = signal<number | null>(null);
  /** Modal de andamento: abre ao clicar em gerar/importar (ou ao entrar na tela com algo rodando) e fecha só quando a pessoa quiser. */
  protected readonly modalAberto = signal(false);
  /** Operação mostrada no modal: a do servidor ou, durante o envio do .zip, a importação que ainda nem chegou lá. */
  protected readonly operacaoModal = computed(() => (this.progressoEnvio() !== null ? 'importar' : this.painel()?.andamento.operacao) ?? null);
  protected readonly situacaoModal = computed(() => (this.progressoEnvio() !== null ? 'em_andamento' : this.painel()?.andamento.situacao) ?? null);

  protected readonly tituloModal = computed(() => {
    const op = this.operacaoModal(), sit = this.situacaoModal();
    if (sit === 'erro') return op === 'gerar' ? 'O backup não foi gerado' : 'A importação não terminou';
    if (sit === 'concluido') return 'Backup gerado';
    if (sit === 'reiniciando') return 'Backup importado';
    return op === 'gerar' ? 'Gerando o backup' : 'Importando o backup';
  });

  protected readonly mensagemModal = computed(() => {
    const envio = this.progressoEnvio();
    if (envio !== null) return envio < 100 ? `Enviando o arquivo para o servidor: ${envio}%…` : 'Conferindo o arquivo no servidor…';
    return this.painel()?.andamento.mensagem ?? '';
  });

  /** Percentual da barra. Na importação, o envio do arquivo é o primeiro trecho (0 a 10%) e o servidor ocupa o resto. */
  protected readonly percentualModal = computed(() => {
    const envio = this.progressoEnvio();
    const andamento = this.painel()?.andamento;
    if (envio !== null) return envio / 10;
    const servidor = andamento?.percentual ?? 0;
    return andamento?.operacao === 'importar' ? 10 + servidor * 0.9 : servidor;
  });

  /** Etapas do modal com a situação de cada uma, a partir da etapa atual informada pelo servidor. */
  protected readonly etapasModal = computed<EtapaTrilha[]>(() => {
    const op = this.operacaoModal();
    if (!op) return [];
    const lista = ETAPAS[op];
    const sit = this.situacaoModal();
    const atual = this.progressoEnvio() !== null ? 'enviar' : this.painel()?.andamento.etapa;
    const indice = Math.max(0, lista.findIndex((e) => e.id === atual));
    return lista.map((e, i) => {
      if (sit === 'concluido' || sit === 'reiniciando') return { ...e, estado: i < lista.length - 1 || sit === 'concluido' ? 'concluida' : 'atual' };
      if (i < indice) return { ...e, estado: 'concluida' };
      if (i === indice) return { ...e, estado: sit === 'erro' ? 'recusada' : 'atual', subtitulo: sit === 'erro' ? 'falhou' : undefined };
      return { ...e, estado: 'aguardando' };
    });
  });
  protected arquivo: File | null = null;
  protected confirmacao = '';
  private consulta: ReturnType<typeof setTimeout> | undefined;

  constructor() {
    inject(DestroyRef).onDestroy(() => clearTimeout(this.consulta));
  }

  ngOnInit(): void {
    this.carregar(true);
  }

  protected emAndamento(): boolean {
    return this.painel()?.andamento.situacao === 'em_andamento';
  }

  /** Carrega a lista e o andamento; enquanto algo roda no servidor, consulta de novo a cada 3 segundos. */
  private carregar(abrindoTela = false): void {
    this.http.get<PainelBackup>(this.base).subscribe({
      next: (p) => {
        // Entrou na tela com um backup ou importação rodando: já mostra o andamento
        if (abrindoTela && (p.andamento.situacao === 'em_andamento' || p.andamento.situacao === 'reiniciando')) this.modalAberto.set(true);
        this.aplicar(p);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar os backups'),
    });
  }

  private aplicar(p: PainelBackup): void {
    this.painel.set(p);
    clearTimeout(this.consulta);
    if (p.andamento.situacao === 'em_andamento') this.consulta = setTimeout(() => this.carregar(), 3000);
    if (p.andamento.situacao === 'reiniciando' && p.andamento.operacao === 'importar') this.esperarReinicio();
  }

  protected gerar(): void {
    this.modalAberto.set(true);
    this.http.post<PainelBackup>(this.base, {}).subscribe({
      next: (p) => this.aplicar(p),
      error: (e) => {
        this.modalAberto.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível gerar o backup');
      },
    });
  }

  protected fecharModal(): void {
    this.modalAberto.set(false);
  }

  /**
   * Baixa o .zip pelo próprio navegador: pede um link assinado (vale 5 minutos, só para este arquivo) e abre o endereço.
   * Assim o download aparece na barra de downloads do Chrome com o progresso dele, e o arquivo (mais de 1 GB) não passa pela memória da página.
   */
  protected baixar(nome: string): void {
    this.baixando.set(nome);
    this.http.post<{ url: string }>(`${this.base}/arquivo/${encodeURIComponent(nome)}/link`, {}).subscribe({
      next: ({ url }) => {
        const link = document.createElement('a');
        link.href = url;
        link.download = nome;
        document.body.appendChild(link);
        link.click();
        link.remove();
        this.baixando.set(null);
      },
      error: (e) => {
        this.baixando.set(null);
        this.dialogos.mostrarErro(e, 'Não foi possível baixar o backup');
      },
    });
  }

  /** Confirma de novo, envia o .zip (com progresso) e acompanha a importação até o sistema reiniciar. */
  protected async importar(): Promise<void> {
    if (!this.arquivo || this.confirmacao !== 'SUBSTITUIR') return;
    const ok = await this.dialogos.confirmar({
      titulo: 'Substituir todo o sistema por este backup?',
      mensagem: `O banco inteiro e todos os anexos serão trocados pelos de "${this.arquivo.name}". O estado atual fica guardado num backup automático. O sistema reinicia no fim.`,
      rotuloConfirmar: 'Importar e substituir tudo',
      segundos: 5,
      perigo: true,
    });
    if (!ok) return;
    this.modalAberto.set(true);
    const dados = new FormData();
    dados.append('arquivo', this.arquivo);
    dados.append('confirmacao', this.confirmacao);
    this.progressoEnvio.set(0);
    this.http.post(`${this.base}/importar`, dados, { observe: 'events', reportProgress: true }).subscribe({
      next: (evento) => {
        if (evento.type === HttpEventType.UploadProgress) this.progressoEnvio.set(Math.round((100 * evento.loaded) / (evento.total || this.arquivo!.size)));
        if (evento.type === HttpEventType.Response) {
          this.progressoEnvio.set(null);
          this.confirmacao = '';
          this.carregar();
        }
      },
      error: (e) => {
        this.progressoEnvio.set(null);
        this.modalAberto.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível importar o backup');
      },
    });
  }

  /** Depois da importação a API reinicia: espera ela voltar e recarrega a página (será preciso entrar de novo). */
  private esperarReinicio(): void {
    clearTimeout(this.consulta);
    this.consulta = setTimeout(() => {
      this.http.get(`${ambiente.urlApi}/saude`).subscribe({
        next: () => window.location.assign('/'),
        error: () => this.esperarReinicio(),
      });
    }, 6000);
  }

  protected tamanho(bytes: number): string {
    if (bytes >= 1024 ** 3) return (bytes / 1024 ** 3).toLocaleString('pt-BR', { maximumFractionDigits: 2 }) + ' GB';
    return (bytes / 1024 ** 2).toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + ' MB';
  }
}
