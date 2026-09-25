// Criado por José Eduardo Santana Martins
// Este arquivo serve para editar um formulário de avaliação (escala, faixas de liberação e grupos com pesos).

import { Component, input, OnInit, output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DefinicaoFormulario, Modelo } from '../compartilhado/contratos.models';
import { paraDecimalApi } from '../compartilhado/rotulos';

/** Formulário inicial de exemplo: escala 0/5/10, três faixas e um grupo com um item de peso 100. */
export function definicaoVazia(): DefinicaoFormulario {
  return {
    escala: [{ valor: '0', legenda: 'Insatisfatório' }, { valor: '5', legenda: 'Regular' }, { valor: '10', legenda: 'Ótimo' }],
    faixas: [{ minimo: '0', maximo: '6.99', percentual: '80' }, { minimo: '7', maximo: '8.99', percentual: '95' }, { minimo: '9', maximo: null, percentual: '100' }],
    grupos: [{ nome: '', itens: [{ nome: '', descricao: '', peso: '100' }] }],
  };
}

/** Janela de edição do formulário de avaliação: escala, faixas de liberação e grupos com pesos. */
@Component({
  selector: 'app-editor-formulario',
  imports: [FormsModule],
  // Esc fecha o editor
  host: { '(document:keydown.escape)': 'fechar.emit()' },
  templateUrl: './editor-formulario.component.html',
})
export class EditorFormularioComponent implements OnInit {
  // Entradas: título, valores iniciais e modelos globais; saídas: salvar (com os dados) e fechar
  readonly titulo = input('Formulário de avaliação');
  readonly nomeInicial = input('');
  readonly definicaoInicial = input<DefinicaoFormulario>(definicaoVazia());
  readonly modelos = input<Modelo[]>([]);
  readonly rotuloSalvar = input('Salvar');
  readonly salvar = output<{ nome: string; definicao: DefinicaoFormulario }>();
  readonly fechar = output<void>();

  // Cópia editável; o original (input) não é alterado
  protected nome = '';
  protected definicao: DefinicaoFormulario = definicaoVazia();

  /** Copia os valores iniciais; `structuredClone` evita editar o objeto de quem chamou. */
  ngOnInit(): void {
    this.nome = this.nomeInicial();
    this.definicao = structuredClone(this.definicaoInicial());
  }

  /** Substitui a definição pela de um modelo global. */
  protected carregarModelo(id: string): void {
    const modelo = this.modelos().find((m) => m.id === id);
    if (!modelo) return;
    this.nome ||= modelo.nome;
    this.definicao = structuredClone({ escala: modelo.conteudo.escala ?? [], faixas: modelo.conteudo.faixas ?? [], grupos: modelo.conteudo.grupos ?? [] });
  }

  /** Soma dos pesos dos itens de um grupo (precisa dar 100). */
  protected somaPesos(indice: number): number {
    return this.definicao.grupos[indice].itens.reduce((t, i) => t + (Number(paraDecimalApi(i.peso)) || 0), 0);
  }

  /** Confere se o formulário pode ser salvo: nome, escala, faixas e grupos completos com pesos somando 100. */
  protected valido(): boolean {
    return !!this.nome.trim() && this.definicao.escala.length >= 2 && this.definicao.faixas.length >= 1 &&
      this.definicao.grupos.length >= 1 && this.definicao.grupos.every((g, i) => g.nome.trim() && g.itens.length && g.itens.every((it) => it.nome.trim()) && Math.abs(this.somaPesos(i) - 100) < 0.001);
  }

  /** Converte os números do formato brasileiro para o da API e emite o formulário. */
  protected enviar(): void {
    const definicao: DefinicaoFormulario = {
      escala: this.definicao.escala.map((n) => ({ valor: paraDecimalApi(n.valor), legenda: n.legenda.trim() })),
      faixas: this.definicao.faixas.map((f) => ({
        // Máximo vazio = faixa sem teto
        minimo: paraDecimalApi(f.minimo), maximo: f.maximo === null || f.maximo === '' ? null : paraDecimalApi(f.maximo), percentual: paraDecimalApi(f.percentual),
        notas_zero: f.notas_zero ? Number(f.notas_zero) : null,
      })),
      grupos: this.definicao.grupos.map((g) => ({
        id: g.id ?? null, nome: g.nome.trim(),
        itens: g.itens.map((i) => ({ id: i.id ?? null, nome: i.nome.trim(), descricao: (i.descricao ?? '').trim(), peso: paraDecimalApi(i.peso) })),
      })),
    };
    this.salvar.emit({ nome: this.nome.trim(), definicao });
  }
}
