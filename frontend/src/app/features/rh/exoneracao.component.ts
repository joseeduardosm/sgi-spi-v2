// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela dos chamados da exoneração: pedir às equipes o inverso do que a nomeação pediu (rede, e-mail, crachá...).

import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRhComponent } from './cabecalho-rh.component';
import { RhCargosApiService } from './rh-cargos-api.service';
import { LeituraExoneracao, LinkChamadoExoneracao } from './rh-cargos.models';

@Component({
  selector: 'app-exoneracao',
  imports: [FormsModule, DatePipe, RouterLink, CabecalhoRhComponent, EsqueletoComponent],
  template: `
    <app-cabecalho-rh [titulo]="x()?.nome ?? 'Exoneração'" [trilha]="['Cargos', x()?.nome ?? '']" descricao="Chamados para desfazer o que a nomeação pediu." />

    @if (x(); as x) {
      <section class="cartao-dados" aria-label="Exoneração">
        <header>
          <div><h2>{{ x.cargo_rotulo }}</h2>
            <small>{{ x.setor_nome }} · login <span class="texto-codigo">{{ x.login }}</span>@if (x.fim) { · saída em {{ x.fim | date: 'dd/MM/yyyy' }} }@if (x.ato_fim) { · {{ x.ato_fim }} }</small></div>
          <div class="acoes-formulario"><a class="acao-secundaria acao-pequena" [routerLink]="['/rh/historico', x.usuario_id]">Histórico funcional</a></div>
        </header>
      </section>

      <div class="parametros-rh">
        <div class="sem-borda">
          <section class="cartao-dados" aria-labelledby="ex-chamados">
            <header><div><h2 id="ex-chamados">Chamados da exoneração</h2>
              <small>O inverso da nomeação: o que foi pedido quando a pessoa entrou é pedido de volta agora (desativar a rede, recolher o crachá...). Um chamado por serviço, já na equipe certa.</small></div></header>
            <div class="corpo">
              @if (x.chamados.length) {
                <p class="resumo-chamado"><span class="selo-situacao">Chamados abertos</span> {{ x.chamados.length }} chamado(s) no SGI</p>
                <div class="tabela-gestao-envoltorio">
                  <table class="tabela-gestao">
                    <thead><tr><th>Serviço</th><th>Chamado</th></tr></thead>
                    <tbody>
                      @for (l of x.chamados; track l.url) {
                        <tr><td><strong>{{ rotulo(l) }}</strong></td>
                          <td><a class="acao-secundaria acao-pequena" [routerLink]="l.url">Chamado #{{ l.numero }}</a>
                            <span class="selo-status" [attr.data-chamado]="l.status_cor || 'info'">{{ l.status_nome }}</span></td></tr>
                      }
                    </tbody>
                  </table>
                </div>
              } @else if (x.destino === 'glpi') {
                <p class="aviso-formulario">Os chamados do RH ainda vão para o GLPI: faça a exoneração pelo formulário "Exoneração" do GLPI. Depois da virada (Parâmetros dos Chamados › RH), ela passa a ser aberta aqui.</p>
              } @else {
                <p class="dica-formulario">{{ x.sugestao_da_nomeacao ? 'Vieram marcados os serviços pedidos na nomeação desta pessoa.' : 'Esta pessoa não tem nomeação registrada no SGI, então vieram todos marcados.' }} Desmarque o que não se aplica.</p>
                <div class="opcoes-parametros">
                  @for (s of servicos(); track s[0]) {
                    <label class="opcao"><input type="checkbox" [name]="'ex-' + s[0]" [(ngModel)]="pedir[s[0]]" /><span><strong>{{ s[1] }}</strong></span></label>
                  }
                </div>
                <div class="campo" style="margin-top: 14px"><label for="ex-obs">Observações para as equipes</label>
                  <textarea id="ex-obs" name="obs" rows="3" maxlength="4000" placeholder="Ex.: último dia de trabalho na sexta; o notebook fica com a chefia." [(ngModel)]="observacoes"></textarea></div>
                <div class="acoes-formulario" style="margin-top: 12px">
                  <button type="button" class="acao-primaria" [class.carregando]="enviando()" [disabled]="enviando() || !algumMarcado()" (click)="abrir()">Abrir os chamados</button>
                </div>
              }
            </div>
          </section>
        </div>
      </div>
    } @else {
      <app-esqueleto tipo="painel" />
    }
  `,
})
export class ExoneracaoComponent implements OnInit {
  private readonly api = inject(RhCargosApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly id = Number(inject(ActivatedRoute).snapshot.paramMap.get('id'));

  protected readonly x = signal<LeituraExoneracao | null>(null);
  protected readonly enviando = signal(false);
  protected pedir: Record<string, boolean> = {};
  protected observacoes = '';

  ngOnInit(): void {
    this.api.exoneracao(this.id).subscribe({
      next: (x) => { this.x.set(x); this.pedir = { ...x.sugestao }; },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível abrir a exoneração'),
    });
  }

  protected servicos(): [string, string][] {
    return Object.entries(this.x()?.servicos ?? {});
  }

  protected algumMarcado(): boolean {
    return Object.values(this.pedir).some(Boolean);
  }

  protected rotulo(l: LinkChamadoExoneracao): string {
    return (l.chave && this.x()?.servicos[l.chave]) || l.texto;
  }

  protected abrir(): void {
    this.enviando.set(true);
    this.api.abrirChamadosExoneracao(this.id, this.pedir, this.observacoes).subscribe({
      next: (x) => { this.enviando.set(false); this.x.set(x); },
      error: (e) => { this.enviando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível abrir os chamados'); },
    });
  }
}
