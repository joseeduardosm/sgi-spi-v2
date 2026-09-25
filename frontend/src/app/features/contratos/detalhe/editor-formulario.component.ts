import { Component, input, OnInit, output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DefinicaoFormulario, Modelo } from '../compartilhado/contratos.models';
import { paraDecimalApi } from '../compartilhado/rotulos';

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
  host: { '(document:keydown.escape)': 'fechar.emit()' },
  templateUrl: './editor-formulario.component.html',
})
export class EditorFormularioComponent implements OnInit {
  readonly titulo = input('Formulário de avaliação');
  readonly nomeInicial = input('');
  readonly definicaoInicial = input<DefinicaoFormulario>(definicaoVazia());
  readonly modelos = input<Modelo[]>([]);
  readonly rotuloSalvar = input('Salvar');
  readonly salvar = output<{ nome: string; definicao: DefinicaoFormulario }>();
  readonly fechar = output<void>();

  protected nome = '';
  protected definicao: DefinicaoFormulario = definicaoVazia();

  ngOnInit(): void {
    this.nome = this.nomeInicial();
    this.definicao = structuredClone(this.definicaoInicial());
  }

  protected carregarModelo(id: string): void {
    const modelo = this.modelos().find((m) => m.id === id);
    if (!modelo) return;
    this.nome ||= modelo.nome;
    this.definicao = structuredClone({ escala: modelo.conteudo.escala ?? [], faixas: modelo.conteudo.faixas ?? [], grupos: modelo.conteudo.grupos ?? [] });
  }

  protected somaPesos(indice: number): number {
    return this.definicao.grupos[indice].itens.reduce((t, i) => t + (Number(paraDecimalApi(i.peso)) || 0), 0);
  }

  protected valido(): boolean {
    return !!this.nome.trim() && this.definicao.escala.length >= 2 && this.definicao.faixas.length >= 1 &&
      this.definicao.grupos.length >= 1 && this.definicao.grupos.every((g, i) => g.nome.trim() && g.itens.length && g.itens.every((it) => it.nome.trim()) && Math.abs(this.somaPesos(i) - 100) < 0.001);
  }

  protected enviar(): void {
    const definicao: DefinicaoFormulario = {
      escala: this.definicao.escala.map((n) => ({ valor: paraDecimalApi(n.valor), legenda: n.legenda.trim() })),
      faixas: this.definicao.faixas.map((f) => ({
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
