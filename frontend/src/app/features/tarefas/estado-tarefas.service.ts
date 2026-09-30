// Criado por José Eduardo Santana Martins
// Este arquivo serve para guardar o estado compartilhado do Módulo Tarefas (lista de equipes da navegação lateral e do cabeçalho).

import { computed, inject, Injectable, signal } from '@angular/core';

import { TarefasApiService } from './tarefas-api.service';
import { Equipe } from './tarefas.models';

/** Equipe na árvore da navegação lateral: a própria equipe e o nível (0 = principal, 1 = subequipe…). */
export interface EquipeNaArvore { equipe: Equipe; nivel: number }

/**
 * Estado do módulo que várias telas usam ao mesmo tempo: as equipes visíveis ao usuário.
 * A casca do módulo recarrega a cada navegação; as telas só leem os sinais.
 */
@Injectable({ providedIn: 'root' })
export class EstadoTarefasService {
  private readonly api = inject(TarefasApiService);

  /** Equipes visíveis (membro, liderança ou SuperRoot), com indicadores. */
  readonly equipes = signal<Equipe[]>([]);

  /** Equipes em árvore: principais em ordem de nome, cada uma seguida das subequipes (recuadas). */
  readonly arvore = computed<EquipeNaArvore[]>(() => {
    const todas = [...this.equipes()].sort((a, b) => a.nome.localeCompare(b.nome));
    const ids = new Set(todas.map((e) => e.id));
    const resultado: EquipeNaArvore[] = [];
    const incluir = (e: Equipe, nivel: number) => {
      resultado.push({ equipe: e, nivel });
      todas.filter((f) => f.equipe_pai_id === e.id).forEach((f) => incluir(f, nivel + 1));
    };
    // Raiz: sem equipe pai, ou com equipe pai que o usuário não vê
    todas.filter((e) => !e.equipe_pai_id || !ids.has(e.equipe_pai_id)).forEach((e) => incluir(e, 0));
    return resultado;
  });

  /** Entregas aguardando a validação do usuário (somadas nas equipes que ele lidera). */
  readonly paraValidar = computed(() => this.equipes().filter((e) => e.lider).reduce((total, e) => total + e.indicadores.em_validacao, 0));

  /** Busca as equipes de novo (depois de navegar, criar ou configurar). Erros aqui não interrompem a tela. */
  recarregar(): void {
    this.api.equipes().subscribe({ next: (l) => this.equipes.set(l), error: () => undefined });
  }
}
