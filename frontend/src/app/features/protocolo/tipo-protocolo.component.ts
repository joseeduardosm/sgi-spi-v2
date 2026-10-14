// Criado por José Eduardo Santana Martins
// Este arquivo serve para a página dedicada de novo tipo de documento (ou novo exercício de um tipo): nome, exercício, faixa e "liberar a partir de".

import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Observable } from 'rxjs';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoProtocoloComponent } from './cabecalho-protocolo.component';
import { ProtocoloApiService } from './protocolo-api.service';

const MAXIMO_NUMEROS = 10000;

/**
 * Cria o tipo com a faixa do primeiro exercício (`/protocolo/administracao/tipos/novo`) ou acrescenta um exercício a um tipo existente
 * (`/protocolo/administracao/tipos/:tipoId/exercicio`). Do início da faixa até "Liberar a partir de" os números ficam **Reservado SAA**:
 * só o Serviço de Apoio Administrativo dá andamento neles; os demais usuários passam a reservar a partir desse número.
 */
@Component({
  selector: 'app-tipo-protocolo',
  imports: [FormsModule, RouterLink, CabecalhoProtocoloComponent],
  template: `
    <app-cabecalho-protocolo [titulo]="tipoId() ? 'Novo exercício' : 'Novo tipo de documento'" descricao="Nome, exercício, faixa de números e o ponto em que a numeração é liberada para todos." />
    <form class="painel-gestao pagina-tipo-protocolo" (ngSubmit)="salvar()">
      <section class="cartao-dados">
        <div class="grade-formulario">
          <div class="ocupa-duas"><label for="tp-nome">Nome do tipo de documento *</label>
            <input id="tp-nome" name="nome" maxlength="200" placeholder="Ex.: Portaria SPI SSGC" [ngModel]="nome()" (ngModelChange)="nome.set($event)" [readonly]="!!tipoId()" required /></div>
          <div><label for="tp-exercicio">Exercício *</label><input id="tp-exercicio" name="exercicio" type="number" min="2000" max="2200" [ngModel]="exercicio()" (ngModelChange)="exercicio.set($event)" required /></div>
          <div></div>
          <div><label for="tp-inicio">Início da faixa *</label><input id="tp-inicio" name="inicio" type="number" min="0" [ngModel]="inicio()" (ngModelChange)="inicio.set($event)" required /></div>
          <div><label for="tp-fim">Fim da faixa *</label><input id="tp-fim" name="fim" type="number" min="0" [ngModel]="fim()" (ngModelChange)="fim.set($event)" required /></div>
          <div class="ocupa-duas"><label for="tp-liberar">Liberar a partir de</label>
            <input id="tp-liberar" name="liberar" type="number" min="0" placeholder="Em branco: toda a faixa liberada desde o início" [ngModel]="liberar()" (ngModelChange)="liberar.set($event === '' ? null : $event)" />
            <small class="dica">Do início da faixa até o número anterior a este fica <b>Reservado SAA</b>: só quem está no setor Serviço de Apoio Administrativo reserva e sobe documento. A partir dele, todos os usuários reservam.</small></div>
        </div>
        <p class="previa-faixa" [class.erro]="!!erro()" role="status">{{ erro() || previa() }}</p>
      </section>
      <footer class="acoes-formulario">
        <a class="acao-secundaria" routerLink="/protocolo/administracao">Cancelar</a>
        <button [class.carregando]="salvando()" type="submit" class="acao-primaria" [disabled]="!!erro() || salvando()">{{ tipoId() ? 'Criar exercício' : 'Criar tipo' }}</button>
      </footer>
    </form>
  `,
  styles: `
    .pagina-tipo-protocolo { max-width: 860px; }
    .cartao-dados { padding: 18px 20px; }
    .dica { display: block; margin-top: 4px; color: var(--spi-apagado); }
    .previa-faixa { margin: 4px 0 0; padding: 10px 12px; border-radius: var(--spi-raio-m); background: #f1ecfb; color: #4a3a78; font-size: 13px; &.erro { background: var(--spi-vermelho-suave); color: var(--spi-vermelho); } }
    footer.acoes-formulario { margin-top: 0; padding: 16px 20px; }
  `,
})
export class TipoProtocoloComponent implements OnInit {
  /** Id do tipo (rota `tipos/:tipoId/exercicio`); ausente ao criar um tipo novo. */
  readonly tipoId = input<string>();

  private readonly api = inject(ProtocoloApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);

  protected readonly salvando = signal(false);
  protected readonly nome = signal('');
  protected readonly exercicio = signal<number>(new Date().getFullYear());
  protected readonly inicio = signal<number | null>(1);
  protected readonly fim = signal<number | null>(100);
  protected readonly liberar = signal<number | null>(null);

  /** Mensagem do primeiro problema da faixa (espelha a validação da API); vazia quando está tudo certo. */
  protected readonly erro = computed(() => this.validar());

  protected readonly previa = computed(() => {
    const i = this.inicio(), f = this.fim(), l = this.liberar();
    if (i === null || f === null || !(f >= i)) return 'Informe a faixa de números.';
    const total = f - i + 1;
    if (l === null || l <= i) return `${total} número(s), de ${i} a ${f}, liberados para todos desde o início.`;
    if (l > f) return `${total} número(s), de ${i} a ${f}: a faixa inteira fica Reservado SAA.`;
    return `Reservado SAA: ${i} a ${l - 1} (${l - i} número(s)) · liberado para todos: ${l} a ${f} (${f - l + 1} número(s)).`;
  });

  ngOnInit(): void {
    if (this.tipoId()) {
      this.api.tipos().subscribe({
        next: (r) => {
          const tipo = r.itens.find((t) => t.id === this.tipoId());
          if (tipo) {
            this.nome.set(tipo.nome);
            this.exercicio.set(Math.max(new Date().getFullYear(), ...tipo.sequencias.map((s) => s.exercicio + 1)));
          } else void this.roteador.navigate(['/protocolo/administracao']);
        },
        error: (e) => this.dialogos.mostrarErro(e),
      });
    }
  }

  private validar(): string {
    if (!this.tipoId() && !this.nome().trim()) return 'Informe o nome do tipo de documento.';
    const e = this.exercicio();
    if (!Number.isInteger(e) || e < 2000 || e > 2200) return 'Exercício entre 2000 e 2200.';
    const i = this.inicio(), f = this.fim(), l = this.liberar();
    if (i === null || f === null || i < 0 || f < i) return 'Informe um intervalo válido (o fim não pode ser menor que o início).';
    if (f - i + 1 > MAXIMO_NUMEROS) return `O intervalo pode conter no máximo ${MAXIMO_NUMEROS.toLocaleString('pt-BR')} números.`;
    if (l !== null && (l < i || l > f + 1)) return `"Liberar a partir de" deve ficar entre ${i} e ${f + 1}.`;
    return '';
  }

  protected salvar(): void {
    if (this.validar()) return;
    this.salvando.set(true);
    const dados = { exercicio: this.exercicio(), inicio: this.inicio()!, fim: this.fim()!, liberar_a_partir_de: this.liberar() };
    const chamada: Observable<unknown> = this.tipoId() ? this.api.criarSequencia(this.tipoId()!, dados) : this.api.criarTipo(this.nome().trim(), dados);
    chamada.subscribe({
      next: () => void this.roteador.navigate(['/protocolo/administracao']),
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível salvar'); },
    });
  }
}
