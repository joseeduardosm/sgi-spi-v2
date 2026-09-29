// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela de feriados e pontos facultativos do Módulo RH (todos veem; só a CGP cadastra).

import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRhComponent } from './cabecalho-rh.component';
import { RhApiService } from './rh-api.service';
import { AbrangenciaFeriado, Feriado, ROTULOS_ABRANGENCIA, ROTULOS_TIPO_FERIADO, TipoFeriado } from './rh.models';

const DIAS = ['domingo', 'segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado'];

/** Formulário da janela (novo ou edição). */
interface Edicao {
  id?: string;
  data: string;
  descricao: string;
  tipo: TipoFeriado;
  abrangencia: AbrangenciaFeriado;
}

/**
 * Feriados e pontos facultativos do ano. Aparecem no calendário de férias, no painel e na folha de ponto; com o
 * parâmetro ligado, férias e licença-prêmio não podem começar nessas datas. Só a CGP cadastra, altera e exclui.
 */
@Component({
  selector: 'app-feriados',
  imports: [FormsModule, CabecalhoRhComponent],
  host: { '(document:keydown.escape)': 'edicao.set(null)' },
  template: `
    <app-cabecalho-rh titulo="Feriados e pontos facultativos" [trilha]="['Feriados']"
                      descricao="Aparecem no calendário de férias, no painel e na folha de ponto. Cadastro feito pela CGP." />
    <section class="painel-gestao" aria-labelledby="titulo-feriados">
      <div class="barra-ferramentas">
        <div>
          <h2 id="titulo-feriados">Feriados de {{ ano() }}</h2>
          <p>{{ lista().length }} data(s) cadastrada(s).</p>
        </div>
        <div class="acoes-formulario">
          <button type="button" class="acao-secundaria acao-pequena" (click)="mudarAno(-1)">‹ {{ ano() - 1 }}</button>
          <button type="button" class="acao-secundaria acao-pequena" (click)="mudarAno(1)">{{ ano() + 1 }} ›</button>
          @if (cgp()) { <button type="button" class="acao-primaria" (click)="novo()"><span>+</span> Novo feriado</button> }
        </div>
      </div>
      <div class="tabela-gestao-envoltorio">
        <table class="tabela-gestao">
          <thead><tr><th>Data</th><th>Dia da semana</th><th>Descrição</th><th>Tipo</th><th>Abrangência</th>@if (cgp()) { <th class="coluna-acoes">Ações</th> }</tr></thead>
          <tbody>
            @for (f of lista(); track f.id) {
              <tr>
                <td><strong>{{ dataBr(f.data) }}</strong></td>
                <td>{{ diaSemana(f.data) }}</td>
                <td>{{ f.descricao }}</td>
                <td><span class="selo-situacao" [class.alerta]="f.tipo === 'ponto_facultativo'">{{ tipos[f.tipo] }}</span></td>
                <td>{{ abrangencias[f.abrangencia] }}</td>
                @if (cgp()) {
                  <td class="coluna-acoes acoes-linha">
                    <button type="button" class="link-arquivo" (click)="editar(f)">Editar</button>
                    <button type="button" class="link-arquivo" (click)="excluir(f)">Excluir</button>
                  </td>
                }
              </tr>
            } @empty {
              <tr><td class="estado-vazio" [attr.colspan]="cgp() ? 6 : 5">Nenhum feriado ou ponto facultativo cadastrado em {{ ano() }}.</td></tr>
            }
          </tbody>
        </table>
      </div>
    </section>

    @if (edicao(); as e) {
      <div class="fundo-modal" role="presentation" (click)="edicao.set(null)"></div>
      <section class="modal-portal" role="dialog" aria-modal="true" aria-labelledby="titulo-janela-feriado">
        <header>
          <div><span class="modal-sobretitulo">Feriados</span><h2 id="titulo-janela-feriado">{{ e.id ? 'Editar' : 'Novo' }} feriado ou ponto facultativo</h2></div>
          <button type="button" aria-label="Fechar" (click)="edicao.set(null)">×</button>
        </header>
        <form (ngSubmit)="salvar(e)">
          <div class="grade-formulario">
            <div><label for="feriado-data">Data</label><input id="feriado-data" name="data" type="date" required [(ngModel)]="e.data" /></div>
            <div><label for="feriado-tipo">Tipo</label>
              <select id="feriado-tipo" name="tipo" [(ngModel)]="e.tipo">
                <option value="feriado">Feriado</option><option value="ponto_facultativo">Ponto facultativo</option>
              </select></div>
            <div class="ocupa-duas"><label for="feriado-descricao">Descrição</label>
              <input id="feriado-descricao" name="descricao" maxlength="200" required placeholder="Ex.: Nossa Senhora Aparecida" [(ngModel)]="e.descricao" /></div>
            <div><label for="feriado-abrangencia">Abrangência</label>
              <select id="feriado-abrangencia" name="abrangencia" [(ngModel)]="e.abrangencia">
                <option value="nacional">Nacional</option><option value="estadual">Estadual</option><option value="municipal">Municipal</option>
              </select></div>
          </div>
          <footer>
            <button type="button" class="acao-secundaria" (click)="edicao.set(null)">Cancelar</button>
            <button type="submit" class="acao-primaria" [disabled]="!e.data || !e.descricao.trim()">Salvar</button>
          </footer>
        </form>
      </section>
    }
  `,
})
export class FeriadosComponent implements OnInit {
  private readonly api = inject(RhApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly tipos = ROTULOS_TIPO_FERIADO;
  protected readonly abrangencias = ROTULOS_ABRANGENCIA;
  protected readonly ano = signal(new Date().getFullYear());
  protected readonly lista = signal<Feriado[]>([]);
  protected readonly cgp = signal(false);
  protected readonly edicao = signal<Edicao | null>(null);

  ngOnInit(): void {
    this.api.papeis().subscribe({ next: (p) => this.cgp.set(p.cgp), error: () => undefined });
    this.carregar();
  }

  protected carregar(): void {
    this.api.feriados(this.ano()).subscribe({
      next: (l) => this.lista.set(l),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar os feriados'),
    });
  }

  protected mudarAno(delta: number): void {
    this.ano.update((a) => a + delta);
    this.carregar();
  }

  protected novo(): void {
    this.edicao.set({ data: '', descricao: '', tipo: 'feriado', abrangencia: 'nacional' });
  }

  protected editar(f: Feriado): void {
    this.edicao.set({ id: f.id, data: f.data, descricao: f.descricao, tipo: f.tipo, abrangencia: f.abrangencia });
  }

  protected salvar(e: Edicao): void {
    const dados = { data: e.data, descricao: e.descricao.trim(), tipo: e.tipo, abrangencia: e.abrangencia };
    this.dialogos.executar(this.api.salvarFeriado(dados, e.id), 'Salvando…').subscribe({
      next: (f) => {
        this.edicao.set(null);
        // Ao salvar em outro ano, a lista passa a mostrar esse ano
        this.ano.set(Number(f.data.slice(0, 4)));
        this.carregar();
      },
      error: (erro) => this.dialogos.mostrarErro(erro, 'Não foi possível salvar'),
    });
  }

  protected async excluir(f: Feriado): Promise<void> {
    const ok = await this.dialogos.confirmar({
      titulo: 'Excluir esta data?',
      mensagem: `${ROTULOS_TIPO_FERIADO[f.tipo]} de ${this.dataBr(f.data)} (${f.descricao}) deixa de aparecer no calendário e na folha de ponto.`,
      rotuloConfirmar: 'Excluir',
    });
    if (!ok) return;
    this.dialogos.executar(this.api.excluirFeriado(f.id), 'Excluindo…').subscribe({
      next: () => this.carregar(),
      error: (erro) => this.dialogos.mostrarErro(erro, 'Não foi possível excluir'),
    });
  }

  protected dataBr(texto: string): string {
    return texto.split('-').reverse().join('/');
  }

  protected diaSemana(texto: string): string {
    return DIAS[new Date(`${texto}T00:00:00Z`).getUTCDay()];
  }
}
