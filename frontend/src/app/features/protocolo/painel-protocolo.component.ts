// Criado por José Eduardo Santana Martins
// Este arquivo serve para o painel do Protocolo: reservas e utilizações por mês, top 10 pessoas e reservados sem documento.

import { DatePipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoProtocoloComponent } from './cabecalho-protocolo.component';
import { ProtocoloApiService } from './protocolo-api.service';
import { PainelProtocolo, PessoaPainel, TipoProtocolo } from './protocolo.models';

const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

/** Painel por tipo e exercício. As barras são CSS puro (reservados sem documento + utilizados no mês). */
@Component({
  selector: 'app-painel-protocolo',
  imports: [FormsModule, DatePipe, CabecalhoProtocoloComponent],
  template: `
    <app-cabecalho-protocolo titulo="Painel do Protocolo" descricao="Reservas e utilizações por mês, quem mais usa e o que está sem documento." />
    <section class="painel-gestao protocolo">
      <div class="barra-protocolo">
        <div class="campo"><label for="pp-tipo">Tipo de documento</label>
          <select id="pp-tipo" [ngModel]="tipoId()" (ngModelChange)="escolher($event, ano())">
            @for (t of tipos(); track t.id) { <option [value]="t.id">{{ t.nome }}</option> }
          </select></div>
        <div class="campo curto"><label for="pp-ano">Exercício</label>
          <select id="pp-ano" [ngModel]="ano()" (ngModelChange)="escolher(tipoId(), +$event)">
            @for (a of anos; track a) { <option [ngValue]="a">{{ a }}</option> }
          </select></div>
        <span class="espacador"></span>
        <button type="button" class="acao-secundaria acao-pequena" (click)="exportar('xlsx')">Exportar planilha</button>
        <button type="button" class="acao-secundaria acao-pequena" (click)="exportar('pdf')">Exportar PDF</button>
      </div>

      @if (painel(); as p) {
        <div class="cartao-dados">
          <header><div><h2>{{ p.tipo_nome }} — {{ p.ano }}</h2><small>Reservados ainda sem documento e documentos anexados em cada mês.</small></div>
            <div class="legenda-protocolo"><span class="reservado">Reservados</span><span class="utilizado">Utilizados</span></div></header>
          <div class="corpo">
            <div class="grafico-meses" role="img" aria-label="Reservas e utilizações por mês">
              @for (m of p.meses; track m.mes) {
                <div class="coluna-mes" [title]="m.reservados + ' reservado(s), ' + m.utilizados + ' utilizado(s)'">
                  <div class="barras"><i class="utilizado" [style.height.%]="altura(m.utilizados)"></i><i class="reservado" [style.height.%]="altura(m.reservados)"></i></div>
                  <b>{{ meses[m.mes - 1] }}</b><small>{{ m.reservados + m.utilizados }}</small>
                </div>
              }
            </div>
          </div>
        </div>

        <div class="grade-painel-protocolo">
          <div class="cartao-dados">
            <header><div><h2>Top 10 pessoas</h2><small>Total de reservas e de documentos utilizados no exercício.</small></div></header>
            <div class="corpo">
              @for (pessoa of pessoas(); track pessoa.nome) {
                <div class="linha-pessoa">
                  <span class="nome-pessoa"><i>{{ iniciais(pessoa.nome) }}</i>{{ pessoa.nome }}</span>
                  <span class="metrica reservado"><i><b [style.width.%]="largura(pessoa.reservadas)"></b></i>{{ pessoa.reservadas }}</span>
                  <span class="metrica utilizado"><i><b [style.width.%]="largura(pessoa.utilizadas)"></b></i>{{ pessoa.utilizadas }}</span>
                </div>
              } @empty { <p class="estado-vazio">Sem reservas no exercício.</p> }
            </div>
          </div>
          <div class="cartao-dados">
            <header><div><h2>Reservados sem documento ({{ p.sem_documento.length }})</h2><small>Números reservados que ainda esperam o documento.</small></div></header>
            <div class="tabela-gestao-envoltorio">
              <table class="tabela-gestao">
                <thead><tr><th>Número</th><th>Finalidade</th><th>Responsável</th><th>Reserva</th></tr></thead>
                <tbody>
                  @for (n of p.sem_documento; track n.id) {
                    <tr><td><strong>{{ n.numero_formatado }}</strong></td><td>{{ n.finalidade }}</td><td>{{ n.reservado_por_nome }}</td><td>{{ n.reservado_em | date: 'dd/MM/yyyy' }}</td></tr>
                  } @empty { <tr><td class="estado-vazio" colspan="4">Nenhuma reserva pendente.</td></tr> }
                </tbody>
              </table>
            </div>
          </div>
        </div>
      } @else {
        <p class="estado-vazio">{{ tipoId() ? 'Carregando…' : 'Nenhum tipo de documento cadastrado.' }}</p>
      }
    </section>
  `,
})
export class PainelProtocoloComponent implements OnInit {
  private readonly api = inject(ProtocoloApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly meses = MESES;
  protected readonly anos = Array.from({ length: 6 }, (_, i) => new Date().getFullYear() + 1 - i);
  protected readonly tipos = signal<TipoProtocolo[]>([]);
  protected readonly tipoId = signal('');
  protected readonly ano = signal(new Date().getFullYear());
  protected readonly painel = signal<PainelProtocolo | null>(null);

  protected readonly maximoMes = computed(() => Math.max(1, ...(this.painel()?.meses.map((m) => m.reservados + m.utilizados) ?? [1])));
  /** Une as duas listas para cada pessoa ocupar uma linha só. */
  protected readonly pessoas = computed(() => {
    const p = this.painel();
    if (!p) return [];
    const linhas = new Map<string, { nome: string; reservadas: number; utilizadas: number }>();
    const somar = (lista: PessoaPainel[], campo: 'reservadas' | 'utilizadas') => {
      for (const x of lista) {
        const linha = linhas.get(x.nome) ?? { nome: x.nome, reservadas: 0, utilizadas: 0 };
        linha[campo] = x.quantidade;
        linhas.set(x.nome, linha);
      }
    };
    somar(p.mais_reservaram, 'reservadas');
    somar(p.mais_utilizaram, 'utilizadas');
    return [...linhas.values()].sort((a, b) => b.reservadas - a.reservadas || b.utilizadas - a.utilizadas || a.nome.localeCompare(b.nome)).slice(0, 10);
  });
  private readonly maximoPessoa = computed(() => Math.max(1, ...this.pessoas().flatMap((x) => [x.reservadas, x.utilizadas])));

  ngOnInit(): void {
    this.api.tipos().subscribe({
      next: (r) => {
        this.tipos.set(r.itens);
        if (r.itens.length) this.escolher(r.itens[0].id, this.ano());
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar o painel'),
    });
  }

  protected escolher(tipoId: string, ano: number): void {
    this.tipoId.set(tipoId);
    this.ano.set(ano);
    this.painel.set(null);
    this.api.painel(tipoId, ano).subscribe({ next: (p) => this.painel.set(p), error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected altura(valor: number): number {
    return (valor * 100) / this.maximoMes();
  }

  protected largura(valor: number): number {
    return (valor * 100) / this.maximoPessoa();
  }

  protected iniciais(nome: string): string {
    const partes = nome.trim().split(/\s+/);
    return `${partes[0]?.[0] ?? ''}${partes.length > 1 ? partes[partes.length - 1][0] : ''}`.toUpperCase();
  }

  protected exportar(formato: 'xlsx' | 'pdf'): void {
    this.dialogos.executar(this.api.exportar(formato, this.tipoId() || null, this.ano()), 'Gerando o arquivo…').subscribe({
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível exportar'),
    });
  }
}
