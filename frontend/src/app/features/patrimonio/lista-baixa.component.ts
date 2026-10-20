// Criado por José Eduardo Santana Martins
// Este arquivo serve para montar, enviar e aprovar uma baixa de bens (motivo e processo por grupo, termo em PDF na aprovação).
import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { classeMarcador } from '../tarefas/marcadores.paleta';
import { CabecalhoPatrimonioComponent } from './cabecalho-patrimonio.component';
import { PatrimonioApiService } from './patrimonio-api.service';
import { PatrimonioEstadoService } from './patrimonio-estado.service';
import { TrilhaEtapasComponent } from '../../shared/componentes/trilha-etapas/trilha-etapas.component';
import { trilhaBaixa } from './trilhas-patrimonio';
import { Baixa, COR_STATUS, MotivoBaixa, ROTULOS_MOTIVO_BAIXA, ROTULOS_STATUS } from './patrimonio.models';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
/** `/patrimonio/baixas/:baixaId`. */
@Component({
  selector: 'app-lista-baixa',
  imports: [TrilhaEtapasComponent, EsqueletoComponent, FormsModule, RouterLink, CabecalhoPatrimonioComponent, SeletorUsuariosComponent],
  template: `
    <app-cabecalho-patrimonio titulo="Baixa de bens" descricao="A baixa herda os bens de uma lista aprovada: informe motivo e processo, envie o termo à autoridade e conclua com o PDF do de acordo (D.O.E.)." />
    @if (baixa(); as b) {
      <section class="painel-gestao patrimonio">
        <app-trilha-etapas [etapas]="trilha(b)" ariaLabel="Etapas da baixa" />
        <div class="pat-topo-bem">
          <span class="pat-marcadores"><b class="texto-codigo">#{{ b.numero }}</b><span [class]="marcador(cores[b.status])">{{ rotulos[b.status] }}</span><span [class]="marcador(0)">{{ b.solicitante_nome }}</span></span>
          <div class="pat-acoes">
            <button type="button" class="acao-secundaria" (click)="relatorio(b, 'pdf')" title="PDF consolidado: índice, relatório, fotos e anexos">Relatório PDF</button>
            <button type="button" class="acao-secundaria" (click)="relatorio(b, 'xlsx')">Relatório Excel</button>
            @if (b.tem_termo) { <button type="button" class="acao-secundaria" (click)="termo(b)">Baixar o termo (PDF)</button> }
            @if (souDono()) { <button type="button" class="acao-secundaria" (click)="abrirCompartilhar(b)">Compartilhar{{ b.colaboradores?.length ? ' (' + b.colaboradores!.length + ')' : '' }}</button> }
            @if (rascunho()) { <button type="button" class="acao-recusar" (click)="descartar()">Descartar rascunho</button> }
          </div>
        </div>

        @if (b.colaboradores?.length) {
          <p class="pat-aviso pat-colaboradores">Compartilhada com: <strong>{{ nomesColaboradores(b) }}</strong>@if (!souDono() && rascunho()) { · montada por {{ b.solicitante_nome }} }. Quem recebe faz tudo na baixa, mas só o controle total conclui.</p>
        }

        @if (compartilhando()) {
          <div animate.leave="mov-fundo-sai" class="fundo-modal" role="presentation" (click)="compartilhando.set(false)"></div>
          <section animate.leave="mov-modal-sai" class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="titulo-compartilhar-baixa">
            <header>
              <div><span class="modal-sobretitulo">Baixa #{{ b.numero }}</span><h2 id="titulo-compartilhar-baixa">Compartilhar a baixa</h2></div>
              <button type="button" aria-label="Fechar" (click)="compartilhando.set(false)">×</button>
            </header>
            <form (submit)="$event.preventDefault(); salvarCompartilhamento(b)">
              <p class="dica-formulario" style="margin-top: 0">Quem receber a baixa faz <strong>tudo o que você faz nela</strong>: incluir e tirar bens, definir motivo e processo, enviar para aprovação e descartar. Só não pode aprová-la, nem você.</p>
              <div class="grade-formulario">
                <div class="ocupa-duas">
                  <label for="compartilhar-usuarios-baixa">Pessoas ({{ colaboradoresEscolhidos().length }})</label>
                  <app-seletor-usuarios idCampo="compartilhar-usuarios-baixa" [(selecionados)]="colaboradoresEscolhidos" [fonte]="fonteUsuarios" textoAjuda="Pesquisar por nome ou login" />
                </div>
              </div>
              <footer>
                <button type="button" class="acao-secundaria" (click)="compartilhando.set(false)">Cancelar</button>
                <button type="submit" class="acao-primaria">Salvar</button>
              </footer>
            </form>
          </section>
        }

        @if (b.classificacao_origem_id) { <p class="pat-aviso">Os bens vieram da lista aprovada <a [routerLink]="['/patrimonio/inserviveis', b.classificacao_origem_id]">ver a lista</a>. Para incluir outro bem, aprove-o em uma lista e dê a baixa dela.</p> }

        <ul class="pat-lista-itens">
          @for (i of b.itens; track i.id) {
            <li>
              @if (rascunho()) { <input type="checkbox" class="pat-selecao" [name]="'m' + i.id" [checked]="marcados().has(i.id)" (change)="alternar(i.id)" [attr.aria-label]="'Marcar ' + i.rotulo" /> }
              <div><strong class="texto-codigo">{{ i.rotulo }}</strong> <span>{{ i.descricao }}</span>@if (i.chapa && i.numero_serie) { <small>Série {{ i.numero_serie }}</small> }<small>{{ i.situacao_anterior === 'extraviado' ? 'Extraviado' : 'Inservível' }}{{ i.valor_aquisicao ? ' · R$ ' + i.valor_aquisicao : '' }}</small>
                @if (i.motivo) { <small class="pat-justificativa">{{ motivos[i.motivo] }} · processo {{ i.processo }}</small> }</div>
              <span class="pat-acoes">
                @if (i.resultado) { <span [class]="marcador(i.resultado === 'aprovado' ? 10 : 1)">{{ i.resultado === 'aprovado' ? 'Baixado' : 'Recusado' }}</span> }
                @if (rascunho() && b.itens.length > 1) { <button type="button" class="acao-recusar acao-pequena" (click)="tirar(b.id, i.id)">Tirar</button> }
              </span>
            </li>
          } @empty { <li class="estado-vazio">Nenhum bem na baixa.</li> }
        </ul>

        @if (rascunho() && b.itens.length) {
          <div class="pat-painel-acao">
            <strong>Motivo e processo</strong>
            <small>Marque todos ou um grupo de bens e informe o motivo e o número do processo.</small>
            <select name="motivo" [(ngModel)]="motivo"><option value="">Motivo da baixa</option>@for (m of listaMotivos; track m[0]) { <option [value]="m[0]">{{ m[1] }}</option> }</select>
            <input name="processo" placeholder="Número do processo" [(ngModel)]="processo" />
            <div class="pat-acoes">
              <button type="button" class="acao-secundaria" (click)="marcarTodos(b)">Marcar todos</button>
              <button type="button" class="acao-primaria" [disabled]="!marcados().size || !motivo || !processo.trim()" (click)="definirMotivo(b)">Aplicar a {{ marcados().size }} marcado(s)</button>
            </div>
          </div>
          <div class="pat-barra-inferior"><button type="button" class="acao-primaria" [disabled]="semMotivo(b) > 0" (click)="enviar(b)">Enviar e gerar o termo</button></div>
        }

        @if (b.status === 'aguardando_aceite') {
          <div class="pat-painel-acao">
            <strong>Aguardando o aceite da autoridade</strong>
            <small>Leve o termo em PDF à autoridade (SEI). Com o de acordo, na maioria das vezes a publicação no D.O.E., anexe o PDF para concluir: os bens passam a Baixado.</small>
            @if (estado.podeAdministrar()) {
              <div class="pat-acoes">
                <label class="acao-secundaria">Escolher o PDF do de acordo / D.O.E.<input type="file" hidden accept="application/pdf" (change)="escolherConclusao($event)" /></label>
                @if (pdfConclusao()) { <span class="pat-aviso">{{ pdfConclusao()!.name }}</span> }
                <button type="button" class="acao-positiva" [class.carregando]="enviandoConclusao()" [disabled]="!pdfConclusao() || enviandoConclusao()" (click)="concluir(b)">Concluir a baixa</button>
              </div>
              <textarea name="motivo-recusa" rows="2" placeholder="Se a autoridade não deu o aceite, escreva o motivo para registrar a recusa" [(ngModel)]="motivoRecusa"></textarea>
              <div class="pat-acoes"><button type="button" class="acao-recusar" [disabled]="!motivoRecusa.trim()" (click)="recusar(b)">Registrar recusa</button></div>
            } @else { <small>Só quem tem controle total em Patrimônio conclui a baixa.</small> }
          </div>
        }
        @if (b.tem_conclusao) { <p class="pat-aviso">Concluída com o PDF do de acordo da autoridade. <button type="button" class="acao-secundaria acao-pequena" (click)="baixarConclusao(b)">Baixar o PDF</button></p> }
        @if (b.motivo_recusa) { <p class="pat-aviso">Motivo da recusa: {{ b.motivo_recusa }}</p> }
        <p class="pat-aviso">A baixa registrada aqui não baixa o bem no SAM: o termo serve para fazer isso lá.</p>
        <div class="pat-barra-inferior"><a class="acao-secundaria" routerLink="/patrimonio/baixas">Voltar</a></div>
      </section>
          } @else { <app-esqueleto tipo="lista" [linhas]="4" /> }
  `,
})
export class ListaBaixaComponent implements OnInit {
  private readonly api = inject(PatrimonioApiService);
  private readonly roteador = inject(Router);
  private readonly dialogos = inject(DialogosService);
  protected readonly estado = inject(PatrimonioEstadoService);

  readonly baixaId = input.required<string>();
  protected readonly baixa = signal<Baixa | null>(null);
  protected readonly marcados = signal<Set<string>>(new Set());
  protected readonly pdfConclusao = signal<File | null>(null);
  protected readonly enviandoConclusao = signal(false);
  protected readonly trilha = trilhaBaixa;
  // Edita a baixa (rascunho) quem a montou e quem recebeu a baixa compartilhada: os poderes são os mesmos
  protected readonly rascunho = computed(() => {
    const b = this.baixa();
    const eu = this.estado.acesso()?.usuario_id;
    return b?.status === 'rascunho' && (b.solicitante_id === eu || !!b.colaboradores?.some((x) => x.id === eu));
  });
  /** Só quem montou a baixa escolhe com quem compartilhá-la. */
  protected readonly souDono = computed(() => this.baixa()?.status === 'rascunho' && this.baixa()?.solicitante_id === this.estado.acesso()?.usuario_id);
  protected readonly compartilhando = signal(false);
  protected readonly colaboradoresEscolhidos = signal<OpcaoUsuario[]>([]);
  protected readonly fonteUsuarios = (busca: string) => this.api.opcoesUsuarios(busca);
  protected motivo: MotivoBaixa | '' = '';
  protected processo = '';
  protected motivoRecusa = '';
  protected readonly marcador = classeMarcador;
  protected readonly cores = COR_STATUS;
  protected readonly rotulos = ROTULOS_STATUS;
  protected readonly motivos = ROTULOS_MOTIVO_BAIXA;
  protected readonly listaMotivos = Object.entries(ROTULOS_MOTIVO_BAIXA);

  ngOnInit(): void {
    void this.estado.carregar();
    this.api.baixa(this.baixaId()).subscribe({
      next: (b) => this.definir(b),
      error: (e) => { this.dialogos.mostrarErro(e, 'Não foi possível carregar a baixa'); void this.roteador.navigate(['/patrimonio/baixas']); },
    });
  }

  private definir(b: Baixa): void {
    this.baixa.set(b);
  }

  protected nomesColaboradores(b: Baixa): string {
    return (b.colaboradores ?? []).map((x) => x.nome).join(', ');
  }

  protected abrirCompartilhar(b: Baixa): void {
    this.colaboradoresEscolhidos.set((b.colaboradores ?? []).map((x) => ({ id: x.id, login: '', nome_completo: x.nome, cargo: '', ativo: true })));
    this.compartilhando.set(true);
  }

  protected salvarCompartilhamento(b: Baixa): void {
    this.api.compartilharBaixa(b.id, this.colaboradoresEscolhidos().map((u) => u.id)).subscribe({
      next: (x) => { this.definir(x); this.compartilhando.set(false); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível compartilhar a baixa'),
    });
  }

  protected souSolicitante(b: Baixa): boolean {
    return b.solicitante_id === this.estado.acesso()?.usuario_id;
  }

  protected semMotivo(b: Baixa): number {
    return b.itens.filter((i) => !i.motivo || !i.processo).length;
  }

  /** Bem escolhido na lista de sugestões: entra pelo id (vale também para bem sem chapa ou com número de série repetido). */
  /** Inclui os bens de uma sala, um a um; os que a API recusar (já em outra baixa etc.) viram um aviso único. */
  protected tirar(id: string, itemId: string): void {
    this.api.tirarDaBaixa(id, itemId).subscribe({ next: (x) => this.definir(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível tirar o bem') });
  }

  protected alternar(id: string): void {
    this.marcados.update((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }

  protected marcarTodos(b: Baixa): void {
    this.marcados.set(new Set(b.itens.map((i) => i.id)));
  }

  protected definirMotivo(b: Baixa): void {
    this.api.motivoBaixa(b.id, [...this.marcados()], this.motivo as MotivoBaixa, this.processo.trim()).subscribe({
      next: (x) => { this.definir(x); this.marcados.set(new Set()); }, error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível aplicar o motivo'),
    });
  }

  protected enviar(b: Baixa): void {
    this.api.enviarBaixa(b.id).subscribe({ next: (x) => this.definir(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível enviar') });
  }

  protected async descartar(): Promise<void> {
    if (!(await this.dialogos.confirmar({ titulo: 'Descartar o rascunho?', mensagem: 'A lista da baixa será apagada.', rotuloConfirmar: 'Descartar', segundos: 2 }))) return;
    this.api.descartarBaixa(this.baixaId()).subscribe({ next: () => void this.roteador.navigate(['/patrimonio/baixas']), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível descartar') });
  }

  /** Recusa a lista inteira (nenhum item aprovado), com o motivo informado. */
  protected escolherConclusao(evento: Event): void {
    this.pdfConclusao.set((evento.target as HTMLInputElement).files?.[0] ?? null);
  }

  /** Conclui com o PDF do de acordo da autoridade (D.O.E.): os bens passam a Baixado. */
  protected async concluir(b: Baixa): Promise<void> {
    const arquivo = this.pdfConclusao();
    if (!arquivo) return;
    if (!(await this.dialogos.confirmar({ titulo: 'Concluir a baixa?', mensagem: `Os ${b.itens.length} bem(ns) passam a Baixado e saem dos painéis.`, rotuloConfirmar: 'Concluir', segundos: 2 }))) return;
    this.enviandoConclusao.set(true);
    this.api.concluirBaixa(b.id, arquivo).subscribe({
      next: (x) => { this.enviandoConclusao.set(false); this.pdfConclusao.set(null); this.definir(x); },
      error: (e) => { this.enviandoConclusao.set(false); this.dialogos.mostrarErro(e, 'Não foi possível concluir a baixa'); },
    });
  }

  protected recusar(b: Baixa): void {
    this.api.recusarBaixa(b.id, this.motivoRecusa.trim()).subscribe({ next: (x) => this.definir(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível registrar a recusa') });
  }

  protected baixarConclusao(b: Baixa): void {
    this.api.baixarConclusaoBaixa(b.id).subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível baixar o PDF') });
  }

  protected relatorio(b: Baixa, formato: 'pdf' | 'xlsx'): void {
    this.dialogos.executar(this.api.relatorioBaixa(b.id, formato), 'Gerando o relatório…').subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível gerar o relatório') });
  }

  protected termo(b: Baixa): void {
    this.api.baixarTermo(b.id).subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível baixar o termo') });
  }
}
