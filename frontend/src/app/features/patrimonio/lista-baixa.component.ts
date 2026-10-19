// Criado por José Eduardo Santana Martins
// Este arquivo serve para montar, enviar e aprovar uma baixa de bens (motivo e processo por grupo, termo em PDF na aprovação).
import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { Router, RouterLink } from '@angular/router';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { classeMarcador } from '../tarefas/marcadores.paleta';
import { CabecalhoPatrimonioComponent } from './cabecalho-patrimonio.component';
import { FilaOfflineService } from './fila-offline.service';
import { LeitorCodigoComponent } from './leitor-codigo.component';
import { PatrimonioApiService } from './patrimonio-api.service';
import { PatrimonioEstadoService } from './patrimonio-estado.service';
import { BuscaBemComponent } from './busca-bem.component';
import { RelacionarSalaComponent } from './relacionar-sala.component';
import { Baixa, Bem, COR_STATUS, MotivoBaixa, ROTULOS_MOTIVO_BAIXA, ROTULOS_STATUS } from './patrimonio.models';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
/** `/patrimonio/baixas/:baixaId`. */
@Component({
  selector: 'app-lista-baixa',
  imports: [EsqueletoComponent, FormsModule, RouterLink, CabecalhoPatrimonioComponent, LeitorCodigoComponent, BuscaBemComponent, RelacionarSalaComponent, SeletorUsuariosComponent],
  template: `
    <app-cabecalho-patrimonio titulo="Baixa de bens" descricao="Leia os códigos (ou digite a chapa ou o número de série), informe motivo e processo e envie para aprovação." />
    @if (baixa(); as b) {
      <section class="painel-gestao patrimonio">
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
          <p class="pat-aviso pat-colaboradores">Compartilhada com: <strong>{{ nomesColaboradores(b) }}</strong>@if (!souDono() && rascunho()) { · montada por {{ b.solicitante_nome }} }. Quem recebe faz tudo na baixa, mas não pode aprová-la.</p>
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

        @if (rascunho()) {
          <div class="pat-linha-campo">
            <app-busca-bem [(texto)]="chapa" nome="chapa" placeholder="Digite parte da chapa ou do nº de série" (escolhido)="incluirBem($event)" (enviar)="incluir($event)" />
            <button type="button" class="acao-secundaria" (click)="incluir(chapa)">Adicionar</button>
            <button type="button" class="acao-primaria" (click)="lendo.set(true)">Ler códigos</button>
          </div>
          <app-relacionar-sala modo="baixa" (confirmado)="incluirVarios($event)" />
          @for (l of locais(); track l) { <p class="pat-aviso">Chapa {{ l }}: aguardando envio (sem conexão).</p> }
          @if (aviso()) { <p class="pat-aviso" role="alert">{{ aviso() }}</p> }
        }

        <ul class="pat-lista-itens">
          @for (i of b.itens; track i.id) {
            <li>
              @if (rascunho()) { <input type="checkbox" class="pat-selecao" [name]="'m' + i.id" [checked]="marcados().has(i.id)" (change)="alternar(i.id)" [attr.aria-label]="'Marcar ' + i.rotulo" /> }
              @else if (decidindo()) { <input type="checkbox" class="pat-selecao" [name]="'a' + i.id" [checked]="aprovados().has(i.id)" (change)="alternarAprovado(i.id)" [attr.aria-label]="'Aprovar ' + i.rotulo" /> }
              <div><strong class="texto-codigo">{{ i.rotulo }}</strong> <span>{{ i.descricao }}</span>@if (i.chapa && i.numero_serie) { <small>Série {{ i.numero_serie }}</small> }<small>{{ i.situacao_anterior === 'extraviado' ? 'Extraviado' : 'Inservível' }}{{ i.valor_aquisicao ? ' · R$ ' + i.valor_aquisicao : '' }}</small>
                @if (i.motivo) { <small class="pat-justificativa">{{ motivos[i.motivo] }} · processo {{ i.processo }}</small> }</div>
              <span class="pat-acoes">
                @if (i.resultado) { <span [class]="marcador(i.resultado === 'aprovado' ? 10 : 1)">{{ i.resultado === 'aprovado' ? 'Baixado' : 'Recusado' }}</span> }
                @if (rascunho()) { <button type="button" class="acao-recusar acao-pequena" (click)="tirar(b.id, i.id)">Tirar</button> }
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
          <div class="pat-barra-inferior"><button type="button" class="acao-primaria" [disabled]="semMotivo(b) > 0" (click)="enviar(b)">Enviar para aprovação</button></div>
        }

        @if (decidindo()) {
          <div class="pat-painel-acao">
            <strong>Decisão</strong>
            <small>Os itens marcados serão baixados; os demais, recusados. A recusa exige motivo.</small>
            <textarea name="motivo-recusa" rows="2" placeholder="Motivo da recusa (obrigatório ao recusar)" [(ngModel)]="motivoRecusa"></textarea>
            <div class="pat-acoes">
              <button type="button" class="acao-recusar" [disabled]="!motivoRecusa.trim()" (click)="recusarTudo(b)">Recusar tudo</button>
              <button type="button" class="acao-positiva" [disabled]="!aprovados().size || (aprovados().size < b.itens.length && !motivoRecusa.trim())" (click)="decidir(b)">
                {{ aprovados().size < b.itens.length ? 'Aprovar os ' + aprovados().size + ' marcado(s) e recusar os demais' : 'Aprovar tudo' }}</button>
            </div>
          </div>
        }
        @if (b.status === 'pendente' && estado.podeAdministrar() && souSolicitante(b)) { <p class="pat-aviso">Quem montou a baixa não pode aprová-la: outra pessoa com controle total precisa decidir.</p> }
        @if (b.motivo_recusa) { <p class="pat-aviso">Motivo da recusa: {{ b.motivo_recusa }}</p> }
        <p class="pat-aviso">A baixa registrada aqui não baixa o bem no SAM: o termo serve para fazer isso lá.</p>
        <div class="pat-barra-inferior"><a class="acao-secundaria" routerLink="/patrimonio/baixas">Voltar</a></div>
      </section>
      @if (lendo()) { <app-leitor-codigo [continuo]="true" (lido)="incluir($event)" (fechar)="lendo.set(false)" /> }
    } @else { <app-esqueleto tipo="lista" [linhas]="4" /> }
  `,
})
export class ListaBaixaComponent implements OnInit {
  private readonly api = inject(PatrimonioApiService);
  private readonly fila = inject(FilaOfflineService);
  private readonly roteador = inject(Router);
  private readonly dialogos = inject(DialogosService);
  protected readonly estado = inject(PatrimonioEstadoService);

  readonly baixaId = input.required<string>();
  protected readonly baixa = signal<Baixa | null>(null);
  protected readonly lendo = signal(false);
  protected readonly aviso = signal('');
  protected readonly marcados = signal<Set<string>>(new Set());
  protected readonly aprovados = signal<Set<string>>(new Set());
  protected readonly locais = signal<string[]>([]);
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
  protected readonly decidindo = computed(() => this.baixa()?.status === 'pendente' && this.estado.podeAdministrar() && !this.souSolicitante(this.baixa()!));
  protected chapa = '';
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
      next: (b) => { this.definir(b); this.aprovados.set(new Set(b.itens.map((i) => i.id))); },
      error: (e) => { this.dialogos.mostrarErro(e, 'Não foi possível carregar a baixa'); void this.roteador.navigate(['/patrimonio/baixas']); },
    });
  }

  private definir(b: Baixa): void {
    this.baixa.set(b);
    this.aviso.set('');
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

  protected incluir(chapa: string): void {
    const c = chapa.trim();
    this.chapa = '';
    if (!c) return;
    const guardar = () => { void this.fila.enfileirar({ tipo: 'incluir_baixa', corpo: { lista: { id: this.baixaId() }, chapa: c } }, `Chapa ${c} na baixa`); this.locais.update((l) => [...l, c]); };
    if (!this.fila.online()) { guardar(); return; }
    this.api.incluirNaBaixa(this.baixaId(), { chapa: c }).subscribe({
      next: (x) => this.definir(x), error: (e) => (e?.status === 0 ? guardar() : this.aviso.set(e?.error?.detalhe ?? `Não foi possível incluir ${c}.`)),
    });
  }

  /** Bem escolhido na lista de sugestões: entra pelo id (vale também para bem sem chapa ou com número de série repetido). */
  protected incluirBem(b: Bem): void {
    this.api.incluirNaBaixa(this.baixaId(), { bem_id: b.id }).subscribe({ next: (x) => this.definir(x), error: (e) => this.aviso.set(e?.error?.detalhe ?? `Não foi possível incluir ${b.rotulo}.`) });
  }

  /** Inclui os bens de uma sala, um a um; os que a API recusar (já em outra baixa etc.) viram um aviso único. */
  protected async incluirVarios(bens: Bem[]): Promise<void> {
    let recusados = 0;
    for (const b of bens) {
      try { this.definir(await firstValueFrom(this.api.incluirNaBaixa(this.baixaId(), { bem_id: b.id }))); } catch { recusados++; }
    }
    this.aviso.set(recusados ? `${bens.length - recusados} de ${bens.length} bem(ns) incluídos; ${recusados} não puderam entrar (já em outra baixa ou situação inválida).` : '');
  }

  protected tirar(id: string, itemId: string): void {
    this.api.tirarDaBaixa(id, itemId).subscribe({ next: (x) => this.definir(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível tirar o bem') });
  }

  protected alternar(id: string): void {
    this.marcados.update((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }

  protected alternarAprovado(id: string): void {
    this.aprovados.update((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
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
  protected recusarTudo(b: Baixa): void {
    this.api.decidirBaixa(b.id, [], this.motivoRecusa.trim()).subscribe({ next: (x) => this.definir(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível recusar') });
  }

  protected decidir(b: Baixa): void {
    this.api.decidirBaixa(b.id, [...this.aprovados()], this.motivoRecusa.trim() || undefined).subscribe({ next: (x) => this.definir(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível decidir') });
  }

  protected relatorio(b: Baixa, formato: 'pdf' | 'xlsx'): void {
    this.dialogos.executar(this.api.relatorioBaixa(b.id, formato), 'Gerando o relatório…').subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível gerar o relatório') });
  }

  protected termo(b: Baixa): void {
    this.api.baixarTermo(b.id).subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível baixar o termo') });
  }
}
