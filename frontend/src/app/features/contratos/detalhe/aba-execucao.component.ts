import { Component, inject, input, OnInit, output, signal } from '@angular/core';
import { Router } from '@angular/router';

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { PainelExecucao, ResumoCompetencia } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { ROTULOS_ETAPA, ROTULOS_SITUACAO_COMPETENCIA } from '../compartilhado/rotulos';

/** Aba "Execução": pré-requisitos, geração das competências e lista por vigência. */
@Component({
  selector: 'app-aba-execucao',
  imports: [...PIPES_FORMATACAO],
  template: `
    @if (painel(); as p) {
      <section class="cartao-dados" aria-labelledby="titulo-execucao">
        <header>
          <div><h2 id="titulo-execucao">Execução</h2><small>Cada competência passa por medição, avaliação (se houver), nota fiscal, CADIN, checklist, download e OB.</small></div>
          @if (podeEditar()) {
            <button type="button" class="acao-primaria" (click)="gerar(p)">{{ p.geradas ? 'Atualizar competências' : 'Gerar competências' }}</button>
          }
        </header>
        @if (!p.requisitos.prontos) {
          <div class="aviso-bloco" style="margin: 16px 22px">
            <strong>Complete a base do contrato para gerar as competências:</strong>
            <ul>@for (m of p.requisitos.pendencias; track m) { <li>{{ m }}</li> }</ul>
          </div>
        }
        @for (g of p.grupos; track g.sequencia_vigencia) {
          @if (g.competencias.length) {
            <p class="secao-formulario" style="margin: 14px 22px 6px">{{ g.sequencia_vigencia }}ª vigência · {{ g.inicio | dataBr }} a {{ g.fim | dataBr }} · {{ g.competencias.length }} competência(s)</p>
            <div class="tabela-gestao-envoltorio">
              <table class="tabela-gestao">
                <thead><tr><th>Competência</th><th>Período</th><th>Situação</th><th>Etapa</th><th class="num">Medição</th></tr></thead>
                <tbody>
                  @for (c of g.competencias; track c.id) {
                    <tr class="linha-clicavel" (click)="abrir(c)">
                      <td><strong>{{ c.rotulo }}</strong></td>
                      <td>{{ c.periodo_inicio | dataBr }} a {{ c.periodo_fim | dataBr }}</td>
                      <td><span class="selo-situacao" [class]="'selo-situacao ' + c.situacao">{{ situacoes[c.situacao] }}</span></td>
                      <td>{{ c.situacao === 'pendente' ? '—' : etapas[c.etapa_atual] }}</td>
                      <td class="num">{{ c.valor_medicao | moeda }}</td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          }
        }
        @if (!p.geradas) { <p class="estado-vazio">As competências ainda não foram geradas.</p> }
      </section>
    } @else {
      <p class="estado-vazio">Carregando…</p>
    }
  `,
})
export class AbaExecucaoComponent implements OnInit {
  readonly contratoId = input.required<string>();
  readonly podeEditar = input(false);
  /** A geração bloqueia itens do contrato: o detalhe recarrega. */
  readonly alterado = output<void>();

  private readonly api = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);
  protected readonly painel = signal<PainelExecucao | null>(null);
  protected readonly situacoes = ROTULOS_SITUACAO_COMPETENCIA;
  protected readonly etapas = ROTULOS_ETAPA;

  ngOnInit(): void {
    this.api.painel(this.contratoId()).subscribe({ next: (p) => this.painel.set(p), error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected async gerar(painel: PainelExecucao): Promise<void> {
    if (!painel.requisitos.prontos) {
      this.dialogos.avisar('Complete a base do contrato', painel.requisitos.pendencias.join('\n'));
      return;
    }
    const ok = await this.dialogos.confirmar({
      titulo: painel.geradas ? 'Atualizar as competências?' : 'Gerar as competências de execução?',
      mensagem: 'Depois disso, os itens não poderão mais ser editados (só pelo SuperRoot). O checklist ativo será copiado para cada competência; o formulário de avaliação só será aplicado se houver versão ativa.',
      rotuloConfirmar: painel.geradas ? 'Atualizar' : 'Gerar',
      segundos: 5,
    });
    if (!ok) return;
    this.dialogos.executar(this.api.gerar(this.contratoId()), 'Gerando as competências…').subscribe({
      next: (p) => {
        this.painel.set(p);
        this.alterado.emit();
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível gerar as competências'),
    });
  }

  protected abrir(competencia: ResumoCompetencia): void {
    void this.roteador.navigate(['/contratos', this.contratoId(), 'execucao', competencia.identificador]);
  }
}
