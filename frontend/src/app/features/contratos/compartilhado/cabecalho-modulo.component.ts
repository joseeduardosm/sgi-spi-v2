// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o cabeçalho comum das telas de contratos (trilha, título, atalhos e relatórios).

import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { ContratosApiService } from './contratos-api.service';

/**
 * Cabeçalho de todas as telas do módulo: trilha, título e os atalhos Painel/Contratos/Empresas.
 * O SuperRoot vê também o menu "Relatórios" (previsão consolidada e NEs).
 */
@Component({
  selector: 'app-cabecalho-modulo',
  imports: [RouterLink, RouterLinkActive, FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  // Esc fecha a janela de relatório e o menu
  host: { '(document:keydown.escape)': 'janela.set(null); menuRelatorios.set(false)' },
  templateUrl: './cabecalho-modulo.component.html',
})
export class CabecalhoModuloComponent {
  // Entradas definidas por cada tela: título, trilha (breadcrumb) e descrição
  readonly titulo = input('Carteira de contratos');
  readonly trilha = input<string[]>([]);
  readonly descricao = input('');

  private readonly autenticacao = inject(AutenticacaoService);
  private readonly api = inject(ContratosApiService);
  private readonly dialogos = inject(DialogosService);

  // Estado do menu "Relatórios" e da janela aberta (previsão consolidada ou NEs)
  protected readonly superRoot = computed(() => this.autenticacao.possuiPapel('SuperRoot'));
  protected readonly janela = signal<'previsao' | 'notas' | null>(null);
  protected readonly menuRelatorios = signal(false);
  protected formato: 'xlsx' | 'pdf' = 'xlsx';
  // Opções da previsão consolidada (ligadas aos campos da janela por [(ngModel)])
  protected previsao = {
    exercicio: new Date().getFullYear(),
    resumo_anual: true,
    detalhamento_mensal: true,
    cenario_reajustes: false,
    cenario_aditamentos: false,
    cenario_supressoes: false,
    cenario_prorrogacoes: false,
  };

  /** Fecha o menu e abre a janela do relatório escolhido. */
  protected abrirRelatorio(relatorio: 'previsao' | 'notas'): void {
    this.menuRelatorios.set(false);
    this.janela.set(relatorio);
  }

  /** Gera e baixa a previsão consolidada, mostrando "Gerando…" enquanto a API trabalha. */
  protected gerarPrevisao(): void {
    this.dialogos
      .executar(this.api.relatorioPrevisao({ ...this.previsao, formato: this.formato }), 'Gerando a previsão orçamentária…')
      .subscribe({ next: () => this.janela.set(null), error: (e) => this.dialogos.mostrarErro(e) });
  }

  /** Gera e baixa o relatório de Notas de Empenho. */
  protected gerarNotas(): void {
    this.dialogos
      .executar(this.api.relatorioNotas(this.formato), 'Gerando o relatório de Notas de Empenho…')
      .subscribe({ next: () => this.janela.set(null), error: (e) => this.dialogos.mostrarErro(e) });
  }
}
