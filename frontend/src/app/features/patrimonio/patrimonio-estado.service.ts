// Criado por José Eduardo Santana Martins
// Este arquivo serve para guardar o que várias telas do Patrimônio usam: acesso do usuário, salas e grupos de material.
import { computed, inject, Injectable, signal } from '@angular/core';
import { catchError, firstValueFrom, of } from 'rxjs';

import { AcessoPatrimonio, Grupo, Localizacao, PrefixoChapa } from './patrimonio.models';
import { PatrimonioApiService } from './patrimonio-api.service';

/** Uma sala escolhível, com o andar para agrupar a lista. */
export interface OpcaoSala { id: string; codigo: string | null; rotulo: string; andar: number | null; ativo: boolean; deposito: boolean; semResponsavel: boolean }

@Injectable({ providedIn: 'root' })
export class PatrimonioEstadoService {
  private readonly api = inject(PatrimonioApiService);

  readonly acesso = signal<AcessoPatrimonio | null>(null);
  readonly localizacoes = signal<Localizacao[]>([]);
  readonly grupos = signal<Grupo[]>([]);
  /** Prefixos ativos da chapa (o padrão primeiro). */
  readonly prefixos = signal<PrefixoChapa[]>([]);
  readonly prefixoPadrao = computed(() => this.prefixos().find((p) => p.padrao)?.codigo ?? this.prefixos()[0]?.codigo ?? '');
  readonly carregado = signal(false);

  readonly podeOperar = computed(() => this.acesso()?.pode_operar ?? false);
  readonly podeAdministrar = computed(() => this.acesso()?.pode_administrar ?? false);
  /** Salas em ordem de andar e código (o subsolo, andar -1, vem primeiro). */
  readonly salas = computed<OpcaoSala[]>(() => this.localizacoes().filter((l) => l.tipo === 'sala').map((l) => ({
    id: l.id, codigo: l.codigo, rotulo: l.rotulo, andar: l.andar, ativo: l.ativo, deposito: l.deposito_inservivel, semResponsavel: l.responsavel_id === null || l.setor_id === null,
  })));

  /** Carrega uma vez por sessão (com `forcar`, de novo, depois de mudar salas ou grupos). */
  async carregar(forcar = false): Promise<void> {
    if (this.carregado() && !forcar) return;
    try {
      const [acesso, locais, grupos, prefixos] = await Promise.all([firstValueFrom(this.api.acesso()), firstValueFrom(this.api.localizacoes()), firstValueFrom(this.api.grupos()), firstValueFrom(this.api.prefixos().pipe(catchError(() => of([] as PrefixoChapa[]))))]);
      this.acesso.set(acesso);
      this.localizacoes.set(locais);
      this.grupos.set(grupos);
      this.prefixos.set(prefixos);
      this.carregado.set(true);
    } catch { /* sem sinal: as telas usam o que o service worker guardou ou mostram o aviso de conexão */ }
  }

  rotuloDaSala(id: string | null | undefined): string {
    return this.localizacoes().find((l) => l.id === id)?.rotulo ?? '';
  }
}
