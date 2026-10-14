// Criado por José Eduardo Santana Martins
// Este arquivo serve para a administração do Protocolo: cartões dos tipos de documento por exercício (o clique abre a página de detalhe).

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoProtocoloComponent } from './cabecalho-protocolo.component';
import { ProtocoloApiService } from './protocolo-api.service';
import { SequenciaProtocolo, TipoProtocolo } from './protocolo.models';

/** Só CONTROLE_TOTAL (a API confere em cada chamada). */
@Component({
  selector: 'app-administracao-protocolo',
  imports: [FormsModule, RouterLink, CabecalhoProtocoloComponent],
  template: `
    <app-cabecalho-protocolo titulo="Administração do Protocolo" descricao="Tipos de documento, sequências por exercício, faixa reservada ao SAA e ampliação das faixas." />
    <section class="painel-gestao protocolo">
      <div class="barra-protocolo">
        <div class="campo busca"><label for="busca-tipo">Pesquisar</label>
          <input id="busca-tipo" type="search" name="busca" autocomplete="off" placeholder="Nome, exercício ou número (ex.: Portaria, 2026, 150)" aria-label="Pesquisar tipos de documento" [ngModel]="busca()" (ngModelChange)="busca.set($event)" /></div>
        <span class="espacador"></span>
        <a class="acao-primaria" routerLink="/protocolo/administracao/tipos/novo">+ Novo tipo de documento</a>
      </div>

      <!-- Um cartão (proporção de cartão de visita) por tipo e exercício; o clique abre o detalhe com a edição -->
      <div class="grade-cartoes-protocolo">
        @for (c of cartoes(); track c.chave) {
          <a class="cartao-tipo-protocolo" [routerLink]="['/protocolo/administracao/tipos', c.tipo.id]" [queryParams]="c.seq ? { sequencia: c.seq.id } : null">
            <span class="cv-nome">{{ c.tipo.nome }}</span>
            <span class="cv-exercicio">{{ c.seq ? c.seq.exercicio : 'Sem exercício' }}</span>
            <span class="cv-faixa">@if (c.seq) { Números {{ c.seq.inicio }} a {{ c.seq.fim }} } @else { Nenhuma sequência ainda }</span>
          </a>
        } @empty { <p class="estado-vazio">{{ busca().trim() ? 'Nenhum tipo encontrado para a pesquisa.' : 'Nenhum tipo cadastrado.' }}</p> }
      </div>
    </section>
  `,
  styles: `
    .campo.busca { flex: 1 1 320px; max-width: 460px; }
    .grade-cartoes-protocolo { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 18px; padding-bottom: 18px; }
    /* Proporção de cartão de visita (89 x 51 mm) */
    .cartao-tipo-protocolo { display: flex; flex-direction: column; justify-content: space-between; aspect-ratio: 89 / 51; padding: 18px 20px; border: 1px solid var(--cor-e2e5e8); border-left: 5px solid #af3741; border-radius: var(--spi-raio-g); background: var(--cor-ffffff); text-decoration: none; color: inherit; cursor: pointer;  transition: box-shadow .15s, transform .15s;
      &:hover, &:focus-visible { border-color: var(--spi-borda-campo); transform: translateY(-2px); } }
    .cv-nome { font-size: 17px; font-weight: 700; color: var(--cor-1a1e22, #1a1e22); }
    .cv-exercicio { font-size: 28px; font-weight: 700; color: #af3741; line-height: 1; }
    .cv-faixa { color: var(--cor-5a6673); font-size: 13px; }
  `,
})
export class AdministracaoProtocoloComponent implements OnInit {
  private readonly api = inject(ProtocoloApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly tipos = signal<TipoProtocolo[]>([]);
  /** Um cartão por tipo e exercício; o tipo sem sequência ganha um cartão só dele. */
  protected readonly busca = signal('');
  protected readonly cartoes = computed(() => {
    const todos = this.tipos().flatMap((tipo) =>
      tipo.sequencias.length ? tipo.sequencias.map((seq) => ({ chave: seq.id, tipo, seq })) : [{ chave: tipo.id, tipo, seq: null as SequenciaProtocolo | null }]);
    const termo = this.busca().trim().toLowerCase();
    if (!termo) return todos;
    // Casa o nome, o exercício ou qualquer número dentro da faixa (quando o termo é numérico)
    const numero = /^\d+$/.test(termo) ? Number(termo) : null;
    return todos.filter((c) => c.tipo.nome.toLowerCase().includes(termo) || (!!c.seq && (String(c.seq.exercicio).includes(termo) || (numero !== null && numero >= c.seq.inicio && numero <= c.seq.fim))));
  });

  ngOnInit(): void {
    this.carregar();
  }

  private carregar(): void {
    this.api.tipos().subscribe({
      next: (r) => {
        this.tipos.set(r.itens);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar a administração'),
    });
  }
}
