// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela Notificações do sistema da conta root: preparar, revisar e enviar o e-mail de changelog.

import { DatePipe } from '@angular/common';
import { Component, computed, DestroyRef, inject, OnInit, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AdministracaoNotificacoesComponent } from './administracao-notificacoes.component';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { catchError, debounceTime, EMPTY, Subject, switchMap } from 'rxjs';

import { OpcaoUsuario } from '../../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { TrilhaComponent } from '../../../shared/componentes/trilha/trilha.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { NotificacoesSistemaApiService } from './notificacoes-sistema-api.service';
import { UsuariosApiService } from '../../usuarios/usuarios-api.service';
import { DestinoChangelog, EnvioChangelog, RascunhoChangelog } from './notificacoes-sistema.models';

function dataBr(texto: string): string {
  return texto.split('-').reverse().join('/');
}

/**
 * Notificações do sistema (só a conta root): o botão "Preparar e-mail de changelog" abre uma janela com o rascunho montado das
 * entradas do CHANGELOG ainda não enviadas. Assunto e texto são editáveis, com a prévia no layout oficial ao lado;
 * o envio vai a todos os usuários ativos com e-mail ou só a um endereço de teste. Abaixo, o histórico dos envios.
 */
@Component({
  selector: 'app-notificacoes-sistema',
  imports: [FormsModule, DatePipe, TrilhaComponent, SeletorUsuariosComponent, AdministracaoNotificacoesComponent],
  templateUrl: './notificacoes-sistema.component.html',
  host: { '(document:keydown.escape)': 'fechar()' },
  // Ações de cada envio: botões do catálogo lado a lado, alinhados à direita (nunca texto solto)
  styles: `
    .acoes-envio { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: 6px; }
    .acoes-envio button { white-space: nowrap; }
  `,
})
export class NotificacoesSistemaComponent implements OnInit {
  private readonly api = inject(NotificacoesSistemaApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly sanitizador = inject(DomSanitizer);
  private readonly destruir = inject(DestroyRef);

  protected readonly historico = signal<EnvioChangelog[]>([]);
  protected readonly rascunho = signal<RascunhoChangelog | null>(null);
  protected readonly previa = signal<SafeHtml | null>(null);
  protected readonly erroPrevia = signal(false);
  protected assunto = '';
  protected corpo = '';
  protected destino: DestinoChangelog = 'teste';
  /** Quando enviar: na hora ou agendado para `agendarPara` (valor de um `datetime-local`, no horário do navegador). */
  protected quando: 'agora' | 'agendar' = 'agora';
  protected agendarPara = '';
  protected emailTeste = '';
  // Destino "selecionados": 1 ou n usuários e/ou setores (sistêmicos ou institucionais)
  protected readonly usuariosApi = inject(UsuariosApiService);
  protected usuarios: OpcaoUsuario[] = [];
  protected readonly setoresEscolhidos = signal<number[]>([]);
  protected readonly filtroSetores = signal('');
  private readonly setoresFiltrados = computed(() => {
    const termo = this.filtroSetores().trim().toLowerCase();
    const setores = this.rascunho()?.setores ?? [];
    return termo ? setores.filter((s) => s.nome.toLowerCase().includes(termo)) : setores;
  });
  protected readonly institucionaisFiltrados = computed(() => this.setoresFiltrados().filter((s) => !s.sistemico));
  protected readonly sistemicosFiltrados = computed(() => this.setoresFiltrados().filter((s) => s.sistemico));

  /** O setor e seus descendentes: na lista hierárquica, os seguintes com nível maior, até voltar ao mesmo nível. */
  private comDescendentes(id: number): number[] {
    const setores = this.rascunho()?.setores ?? [];
    const i = setores.findIndex((s) => s.id === id);
    if (i < 0 || setores[i].sistemico) return [id];
    const ids = [id];
    for (let j = i + 1; j < setores.length && !setores[j].sistemico && setores[j].nivel > setores[i].nivel; j++) ids.push(setores[j].id);
    return ids;
  }
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
        this.quando = 'agora';
        this.agendarPara = '';
        this.usuarios = [];
        this.setoresEscolhidos.set([]);
        this.filtroSetores.set('');
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

  /** Marcar ou desmarcar um setor pai vale também para todos os setores filhos. */
  protected alternarSetor(id: number, marcado: boolean): void {
    const grupo = this.comDescendentes(id);
    this.setoresEscolhidos.update((ids) => (marcado ? [...new Set([...ids, ...grupo])] : ids.filter((x) => !grupo.includes(x))));
    this.atualizarContagem();
  }

  /** Quantos da seleção receberão (todo escolhido ativo e com e-mail, tenha ou não ligado "Novidades do SGI SPI"); mostrado na janela do envio a escolhidos. */
  protected readonly contagem = signal<{ total: number; selecionados: number } | null>(null);

  protected atualizarContagem(): void {
    if (this.destino !== 'selecionados' || (!this.usuarios.length && !this.setoresEscolhidos().length)) { this.contagem.set(null); return; }
    this.api.contagem(this.usuarios.map((u) => u.id), this.setoresEscolhidos()).subscribe({ next: (c) => this.contagem.set(c), error: () => this.contagem.set(null) });
  }

  /** Menor horário aceito no agendamento (daqui a 2 minutos), no formato do `datetime-local`. */
  protected minimoAgendamento(): string {
    const d = new Date(Date.now() + 2 * 60000 - new Date().getTimezoneOffset() * 60000);
    return d.toISOString().slice(0, 16);
  }

  private agendado(): boolean {
    return this.destino !== 'teste' && this.quando === 'agendar';
  }

  protected podeEnviar(): boolean {
    if (!this.assunto.trim() || !this.corpo.trim()) return false;
    if (this.agendado() && (!this.agendarPara || new Date(this.agendarPara).getTime() < Date.now() + 60000)) return false;
    if (this.destino === 'selecionados') return this.usuarios.length > 0 || this.setoresEscolhidos().length > 0;
    return this.destino === 'todos' || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.emailTeste.trim());
  }

  /** Texto do botão de envio conforme o destino. */
  protected rotuloEnviar(): string {
    if (this.agendado()) return 'Agendar envio';
    return { todos: 'Enviar a todos', selecionados: 'Enviar aos escolhidos', teste: 'Enviar teste' }[this.destino];
  }

  protected async enviar(): Promise<void> {
    const r = this.rascunho();
    if (!r || !this.podeEnviar()) return;
    if (this.destino === 'selecionados') {
      const nomes = this.setoresEscolhidos().map((id) => r.setores.find((s) => s.id === id)?.nome ?? '');
      const ok = await this.dialogos.confirmar({
        titulo: this.agendado() ? 'Agendar o envio aos escolhidos?' : 'Enviar aos escolhidos?',
        mensagem: `"${this.assunto.trim()}" vai para ${this.usuarios.length} usuário(s)` +
          (nomes.length ? ` e para as pessoas dos setores: ${nomes.join(', ')} (inclui os setores filhos)` : '') + `. Um e-mail para cada${this.textoQuando()}.`,
        rotuloConfirmar: this.agendado() ? 'Agendar' : 'Enviar',
      });
      if (!ok) return;
    }
    if (this.destino === 'todos') {
      const ok = await this.dialogos.confirmar({
        titulo: this.agendado() ? 'Agendar o envio a todos os usuários?' : 'Enviar a todos os usuários?',
        mensagem: `"${this.assunto.trim()}" vai para ${r.total_destinatarios} usuário(s) ativo(s) com e-mail (a lista final é a do momento do envio), um e-mail para cada${this.textoQuando()}. ` +
          (this.agendado() ? 'Você pode cancelar o agendamento até a hora marcada.' : 'Não há como desfazer.'),
        rotuloConfirmar: this.agendado() ? 'Agendar' : 'Enviar a todos',
        segundos: 3,
      });
      if (!ok) return;
    }
    const pedido = {
      assunto: this.assunto.trim(), corpo: this.corpo.trim(), destino: this.destino,
      email_teste: this.destino === 'teste' ? this.emailTeste.trim() : null, ate_data: r.ate,
      usuarios_ids: this.destino === 'selecionados' ? this.usuarios.map((u) => u.id) : [],
      setores_ids: this.destino === 'selecionados' ? this.setoresEscolhidos() : [],
      agendar_para: this.agendado() ? new Date(this.agendarPara).toISOString() : null,
    };
    this.dialogos.executar(this.api.enviar(pedido), 'Registrando o envio…').subscribe({
      next: (envio) => {
        this.carregarHistorico();
        if (envio.situacao === 'agendado') {
          this.fechar();
          this.dialogos.avisar('Envio agendado', `Sai em ${new Date(envio.agendado_para!).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })} para ${envio.total} destinatário(s) (a lista final é a do momento do envio). Dá para cancelar no histórico.`);
        } else if (envio.destino !== 'teste') {
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

  private textoQuando(): string {
    return this.agendado() ? `, em ${new Date(this.agendarPara).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}` : '';
  }

  protected async cancelarAgendamento(e: EnvioChangelog): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Cancelar o agendamento?', mensagem: `"${e.assunto}" não será enviado em ${new Date(e.agendado_para!).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}.`,
      rotuloConfirmar: 'Cancelar agendamento', perigo: true,
    });
    if (!ok) return;
    this.api.cancelarEnvio(e.id).subscribe({ next: () => this.carregarHistorico(), error: (erro) => this.dialogos.mostrarErro(erro, 'Não foi possível cancelar') });
  }

  /** Reaproveita um envio anterior (ex.: reenviar a todos um texto já testado). */
  protected reaproveitar(e: EnvioChangelog): void {
    this.api.rascunho().subscribe({
      next: (r) => {
        this.rascunho.set({ ...r, ate: e.ate_data ?? r.ate });
        this.assunto = e.assunto;
        this.corpo = e.corpo;
        this.destino = 'teste';
        this.usuarios = [];
        this.setoresEscolhidos.set([]);
        this.filtroSetores.set('');
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
