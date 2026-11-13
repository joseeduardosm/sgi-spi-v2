/**
 * =============================================================================
 * ARQUIVO: recorrencias.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Listar e gerenciar as séries de tarefas recorrentes de uma equipe (ou as
 * pessoais): pausar, retomar, editar e excluir.
 *
 * RESUMO TÉCNICO:
 * Componente standalone com template inline. Lê o equipeId da rota (ausente =
 * recorrências pessoais), carrega as séries pela API e mostra um cartão por
 * série com estado, próximas datas e responsáveis. A edição abre um modal com
 * título, prioridade, horário, responsáveis e o SeletorRecorrenciaComponent.
 *
 * FINALIDADE DE NEGÓCIO:
 * Rotinas fixas da SPI (backups, conferências, relatórios mensais) viram
 * tarefa sozinhas pelo calendário. Esta tela permite acompanhar essas rotinas,
 * suspender temporariamente, ajustar a regra ou encerrar a série sem perder as
 * tarefas já criadas.
 *
 * CONTEXTO NO SISTEMA:
 * Rotas /tarefas/recorrencias e /tarefas/equipes/:equipeId/recorrencias
 * (tarefas.routes.ts). Usa TarefasApiService (/api/tarefas/recorrencias),
 * SeletorUsuariosComponent, AvataresComponent e DialogosService.
 *
 * =============================================================================
 */

import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { AvataresComponent } from './avatares.component';
import { CabecalhoTarefasComponent } from './cabecalho-tarefas.component';
import { SeletorRecorrenciaComponent } from './seletor-recorrencia.component';
import { TarefasApiService } from './tarefas-api.service';
import { PrioridadeTarefa, Recorrencia, RegraRecorrencia, ROTULOS_PRIORIDADE } from './tarefas.models';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
/** Séries da equipe (`/tarefas/equipes/:equipeId/recorrencias`) ou as pessoais (`/tarefas/recorrencias`). */
@Component({
  selector: 'app-recorrencias',
  imports: [EsqueletoComponent, FormsModule, DatePipe, RouterLink, AvataresComponent, CabecalhoTarefasComponent, SeletorUsuariosComponent, SeletorRecorrenciaComponent],
  template: `
    <app-cabecalho-tarefas titulo="Tarefas recorrentes" [trilha]="equipeId ? [{ rotulo: 'Equipes', rota: '/tarefas/equipes' }, { rotulo: 'Recorrências' }] : [{ rotulo: 'Recorrências' }]"
                           descricao="Rotinas que viram tarefa sozinhas, pelo calendário. Para criar uma, marque “Repetir esta tarefa” em Nova tarefa." />
    <div class="barra-acoes-tarefa"><div class="principais"><a class="acao-primaria" routerLink="/tarefas/nova" [queryParams]="equipeId ? { equipe: equipeId } : {}">+ Nova tarefa recorrente</a></div></div>

    <div class="grade-equipes">
      @for (r of series(); track r.id) {
        <article class="cartao-dados cartao-recorrencia">
          <header>
            <div><h2>{{ r.titulo }}</h2><small>{{ r.resumo }}</small></div>
            <span class="selo-recorrencia" [attr.data-estado]="estado(r)">{{ rotuloEstado(r) }}</span>
          </header>
          <div class="corpo">
            <p class="linha-dados"><strong>Prioridade:</strong> {{ prioridades[r.prioridade] }} · <strong>Prazo às</strong> {{ r.hora_prazo.slice(0, 5) }} · <strong>Criadas:</strong> {{ r.geradas }}</p>
            @if (r.proxima_data) {
              <p class="linha-dados"><strong>Próximas:</strong> @for (d of r.proximas; track d; let ultimo = $last) { {{ d + 'T12:00:00' | date: 'dd/MM/yyyy' }}{{ ultimo ? '' : ' · ' }} }</p>
            } @else { <p class="linha-dados">A série terminou: não há próximas ocorrências.</p> }
            @if (r.ultimo_erro) { <p class="aviso-formulario">Pausada pelo sistema: {{ r.ultimo_erro }}</p> }
            <app-avatares [pessoas]="r.responsaveis" tamanho="pequeno" />
            @if (r.pode_gerir) {
              <div class="acoes-formulario">
                @if (r.ativa) { <button type="button" class="acao-secundaria" (click)="pausar(r)">Pausar</button> }
                @else { <button type="button" class="acao-primaria" (click)="retomar(r)">Retomar</button> }
                <button type="button" class="acao-secundaria" (click)="editar(r)">Editar</button>
                <button type="button" class="acao-recusar" (click)="excluir(r)">Excluir</button>
              </div>
            }
          </div>
        </article>
      } @empty { <div class="estado-vazio">@if (carregando()) { <app-esqueleto tipo="lista" [linhas]="3" /> } @else { {{ 'Nenhuma tarefa recorrente por aqui.' }} }</div> }
    </div>

    @if (editando(); as e) {
      <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation" (click)="editando.set(null)"></div>
      <section animate.leave="mov-modal-sai" class="modal-portal modal-largo" role="dialog" aria-modal="true" aria-labelledby="titulo-editar-rec">
        <header><div><h2 id="titulo-editar-rec">Editar tarefa recorrente</h2><small>As mudanças valem para as próximas ocorrências; as já criadas não mudam.</small></div>
          <button type="button" aria-label="Fechar" (click)="editando.set(null)">×</button></header>
        <form class="grade-formulario" (submit)="$event.preventDefault(); salvar()">
          <div class="ocupa-duas"><label for="er-titulo">Título</label><input id="er-titulo" name="titulo" maxlength="200" required [(ngModel)]="form.titulo" /></div>
          <div><label for="er-prio">Prioridade</label>
            <select id="er-prio" name="prio" [(ngModel)]="form.prioridade">@for (p of listaPrioridades; track p) { <option [value]="p">{{ prioridades[p] }}</option> }</select></div>
          <div><label for="er-hora">Horário do prazo</label><input id="er-hora" name="hora" type="time" [(ngModel)]="form.hora" /></div>
          <div class="ocupa-duas"><label for="er-resp">Responsáveis</label>
            <app-seletor-usuarios idCampo="er-resp" [selecionados]="form.responsaveis" (selecionadosChange)="form.responsaveis = $event" [fonte]="api.opcoesPessoas" /></div>
          <div class="ocupa-duas"><app-seletor-recorrencia [prazo]="prazoReferencia(e)" [regra]="form.regra" (regraChange)="form.regra = $event ?? form.regra" /></div>
          <div class="ocupa-duas acoes-formulario">
            <button type="submit" class="acao-primaria" [disabled]="!form.titulo.trim() || !form.responsaveis.length">Salvar</button>
            <button type="button" class="acao-secundaria" (click)="editando.set(null)">Cancelar</button>
          </div>
        </form>
      </section>
    }
  `,
})
/**
 * Lista de séries recorrentes. Recursos usados: `inject()` obtém serviços
 * (API, diálogos, rota) e `signal()` guarda estado reativo da tela (lista,
 * carregando, série em edição); mudar um signal redesenha o template.
 */
export class RecorrenciasComponent implements OnInit {
  protected readonly api = inject(TarefasApiService);
  private readonly dialogos = inject(DialogosService);
  // Sem equipeId na URL, a tela mostra as recorrências pessoais do usuário.
  protected readonly equipeId = inject(ActivatedRoute).snapshot.paramMap.get('equipeId');
  protected readonly series = signal<Recorrencia[]>([]);
  protected readonly carregando = signal(true);
  protected readonly editando = signal<Recorrencia | null>(null);
  protected readonly prioridades = ROTULOS_PRIORIDADE;
  protected readonly listaPrioridades: PrioridadeTarefa[] = ['baixa', 'normal', 'alta', 'critica'];
  /** Cópia editável da série aberta no modal (preenchida em `editar`). */
  protected form: { titulo: string; prioridade: PrioridadeTarefa; hora: string; responsaveis: OpcaoUsuario[]; regra: RegraRecorrencia } = {
    titulo: '', prioridade: 'normal', hora: '18:00', responsaveis: [], regra: { frequencia: 'semanal', intervalo: 1, dias_semana: [0], somente_dias_uteis: false, antecedencia_dias: 0, fim: null, max_ocorrencias: null },
  };

  ngOnInit(): void {
    this.carregar();
  }

  /** Busca as séries na API e atualiza a lista (com esqueleto enquanto carrega). */
  private carregar(): void {
    this.carregando.set(true);
    this.api.recorrencias(this.equipeId).subscribe({
      next: (l) => { this.series.set(l); this.carregando.set(false); },
      error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível carregar as recorrências'); },
    });
  }

  /**
   * Estado visual da série, por ordem de prioridade: erro (pausada pelo
   * sistema) > pausada (pelo usuário) > ativa (há próxima data) > encerrada
   * (a regra não gera mais datas).
   */
  protected estado(r: Recorrencia): string {
    return r.ultimo_erro ? 'erro' : !r.ativa ? 'pausada' : r.proxima_data ? 'ativa' : 'encerrada';
  }

  /** Texto do selo correspondente ao `estado` da série. */
  protected rotuloEstado(r: Recorrencia): string {
    return { erro: 'Pausada por erro', pausada: 'Pausada', ativa: 'Ativa', encerrada: 'Encerrada' }[this.estado(r)] ?? '';
  }

  /** Data e hora da primeira ocorrência (referência da regra); o dia vale para "nos dias" e para o mensal. */
  protected prazoReferencia(r: Recorrencia): string {
    return `${r.inicio}T${this.form.hora || r.hora_prazo.slice(0, 5)}`;
  }

  /** Cria o tratador de erro padrão (diálogo com `titulo`) para os `subscribe`. */
  private falha(titulo: string) {
    return (e: unknown) => this.dialogos.mostrarErro(e, titulo);
  }

  /** Pausa a série: ela para de gerar tarefas até ser retomada. */
  protected pausar(r: Recorrencia): void {
    this.api.pausarRecorrencia(r.id).subscribe({ next: () => this.carregar(), error: this.falha('Não foi possível pausar') });
  }

  /** Retoma uma série pausada (pelo usuário ou pelo sistema). */
  protected retomar(r: Recorrencia): void {
    this.api.retomarRecorrencia(r.id).subscribe({ next: () => this.carregar(), error: this.falha('Não foi possível retomar') });
  }

  /**
   * Abre o modal de edição. Converte os responsáveis da série para o formato
   * de opção do seletor de usuários e copia a regra (spread) para não alterar
   * a série original antes de salvar.
   */
  protected editar(r: Recorrencia): void {
    this.form = {
      titulo: r.titulo, prioridade: r.prioridade, hora: r.hora_prazo.slice(0, 5), regra: { ...r.regra },
      responsaveis: r.responsaveis.map((p) => ({ id: p.id, login: p.login, nome_completo: p.nome, cargo: '', ativo: true })),
    };
    this.editando.set(r);
  }

  /**
   * Envia a série alterada. Campos que o modal não edita (descrição,
   * checklist, marcadores) são reenviados como estavam, porque a API recebe a
   * série inteira. O horário ganha ":00" (segundos) no formato que a API espera.
   */
  protected salvar(): void {
    const r = this.editando();
    if (!r) return;
    this.api.alterarRecorrencia(r.id, {
      titulo: this.form.titulo.trim(), descricao: r.descricao, prioridade: this.form.prioridade, checklist: r.checklist, marcadores_ids: r.marcadores.map((m) => m.id),
      responsaveis_ids: this.form.responsaveis.map((p) => p.id), regra: this.form.regra, hora_prazo: this.form.hora ? `${this.form.hora}:00` : null,
    }).subscribe({ next: () => { this.editando.set(null); this.carregar(); }, error: this.falha('Não foi possível salvar a recorrência') });
  }

  /** Pede confirmação (com espera de 3 s) e exclui a série; as tarefas já criadas continuam. */
  protected async excluir(r: Recorrencia): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Excluir esta recorrência?', mensagem: `"${r.titulo}" deixa de gerar tarefas. As tarefas já criadas continuam, sem vínculo com a série.`,
      rotuloConfirmar: 'Excluir', segundos: 3, perigo: true,
    });
    if (ok) this.api.excluirRecorrencia(r.id).subscribe({ next: () => this.carregar(), error: this.falha('Não foi possível excluir') });
  }
}
