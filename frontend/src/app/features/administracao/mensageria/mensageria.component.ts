// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela Mensageria da conta root: preparar, revisar e enviar o e-mail de changelog.

import { DatePipe } from '@angular/common';
import { Component, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { catchError, debounceTime, EMPTY, Subject, switchMap } from 'rxjs';

import { TrilhaComponent } from '../../../shared/componentes/trilha/trilha.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { MensageriaApiService } from './mensageria-api.service';
import { EnvioChangelog, RascunhoChangelog } from './mensageria.models';

function dataBr(texto: string): string {
  return texto.split('-').reverse().join('/');
}

/**
 * Mensageria (só a conta root): o botão "Preparar e-mail de changelog" abre uma janela com o rascunho montado das
 * entradas do CHANGELOG ainda não enviadas. Assunto e texto são editáveis, com a prévia no layout oficial ao lado;
 * o envio vai a todos os usuários ativos com e-mail ou só a um endereço de teste. Abaixo, o histórico dos envios.
 */
@Component({
  selector: 'app-mensageria',
  imports: [FormsModule, DatePipe, TrilhaComponent],
  templateUrl: './mensageria.component.html',
  host: { '(document:keydown.escape)': 'fechar()' },
})
export class MensageriaComponent implements OnInit {
  private readonly api = inject(MensageriaApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly sanitizador = inject(DomSanitizer);
  private readonly destruir = inject(DestroyRef);

  protected readonly historico = signal<EnvioChangelog[]>([]);
  protected readonly rascunho = signal<RascunhoChangelog | null>(null);
  protected readonly previa = signal<SafeHtml | null>(null);
  protected readonly erroPrevia = signal(false);
  protected assunto = '';
  protected corpo = '';
  protected destino: 'todos' | 'teste' = 'teste';
  protected emailTeste = '';
  // Prévia atualizada 600 ms depois da última digitação
  private readonly edicao = new Subject<void>();
  private acompanhamento?: ReturnType<typeof setTimeout>;

  constructor() {
    this.edicao
      .pipe(
        debounceTime(600),
        // Uma falha na prévia não interrompe as próximas
        switchMap(() =>
          this.api.previa(this.assunto.trim() || '(sem assunto)', this.corpo.trim() || ' ').pipe(
            catchError(() => {
              this.erroPrevia.set(true);
              return EMPTY;
            }),
          ),
        ),
        takeUntilDestroyed(this.destruir),
      )
      .subscribe((html) => {
        this.previa.set(this.sanitizador.bypassSecurityTrustHtml(html));
        this.erroPrevia.set(false);
      });
    this.destruir.onDestroy(() => clearTimeout(this.acompanhamento));
  }

  ngOnInit(): void {
    this.carregarHistorico();
  }

  protected carregarHistorico(): void {
    this.api.historico().subscribe({
      next: (h) => {
        this.historico.set(h);
        // Envio em andamento: consulta de novo em 3 s até concluir
        clearTimeout(this.acompanhamento);
        if (h.some((e) => !e.concluido_em)) this.acompanhamento = setTimeout(() => this.carregarHistorico(), 3000);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar o histórico'),
    });
  }

  /** Abre a janela com o rascunho do CHANGELOG. */
  protected preparar(): void {
    this.dialogos.executar(this.api.rascunho(), 'Lendo o CHANGELOG…').subscribe({
      next: (r) => {
        this.rascunho.set(r);
        this.assunto = r.assunto;
        this.corpo = r.corpo;
        this.destino = 'teste';
        this.previa.set(null);
        this.editou();
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível montar o rascunho'),
    });
  }

  protected editou(): void {
    this.edicao.next();
  }

  protected fechar(): void {
    this.rascunho.set(null);
  }

  protected podeEnviar(): boolean {
    return !!this.assunto.trim() && !!this.corpo.trim() && (this.destino === 'todos' || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.emailTeste.trim()));
  }

  protected async enviar(): Promise<void> {
    const r = this.rascunho();
    if (!r || !this.podeEnviar()) return;
    if (this.destino === 'todos') {
      const ok = await this.dialogos.confirmar({
        titulo: 'Enviar a todos os usuários?',
        mensagem: `"${this.assunto.trim()}" vai para ${r.total_destinatarios} usuário(s) ativo(s) com e-mail, um e-mail para cada. Não há como desfazer.`,
        rotuloConfirmar: 'Enviar a todos',
        segundos: 3,
      });
      if (!ok) return;
    }
    const pedido = {
      assunto: this.assunto.trim(), corpo: this.corpo.trim(), destino: this.destino,
      email_teste: this.destino === 'teste' ? this.emailTeste.trim() : null, ate_data: r.ate,
    };
    this.dialogos.executar(this.api.enviar(pedido), 'Registrando o envio…').subscribe({
      next: (envio) => {
        this.carregarHistorico();
        if (envio.destino === 'todos') {
          this.fechar();
          this.dialogos.avisar('Envio iniciado', `Os e-mails saem em segundo plano para ${envio.total} destinatário(s); acompanhe o resultado no histórico.`);
        } else {
          // O teste não fecha a janela: dá para ajustar o texto e mandar de novo
          this.dialogos.avisar('Teste enviado', `Confira a caixa de ${this.emailTeste.trim()}. A janela continua aberta para ajustes.`);
        }
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível enviar'),
    });
  }

  /** Reaproveita um envio anterior (ex.: reenviar a todos um texto já testado). */
  protected reaproveitar(e: EnvioChangelog): void {
    this.api.rascunho().subscribe({
      next: (r) => {
        this.rascunho.set({ ...r, ate: e.ate_data ?? r.ate });
        this.assunto = e.assunto;
        this.corpo = e.corpo;
        this.destino = 'teste';
        this.previa.set(null);
        this.editou();
      },
      error: (erro) => this.dialogos.mostrarErro(erro),
    });
  }

  protected data(texto: string): string {
    return dataBr(texto);
  }
}
