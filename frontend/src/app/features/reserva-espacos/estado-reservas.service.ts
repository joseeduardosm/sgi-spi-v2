// Criado por José Eduardo Santana Martins
// Este arquivo serve para guardar o papel do usuário (fiscal ou não) e os espaços cadastrados da Reserva de Espaços.

import { inject, Injectable, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { ReservasApiService } from './reservas-api.service';
import { Contexto, Espaco } from './reservas.models';

@Injectable({ providedIn: 'root' })
export class EstadoReservasService {
  private readonly api = inject(ReservasApiService);
  readonly ehFiscal = signal(false);
  readonly podeSolicitar = signal(true);
  readonly podeAdministrar = signal(false);
  readonly espacos = signal<Espaco[]>([]);

  /** Recarrega o papel e os espaços (chame depois de criar, alterar ou excluir espaço). */
  carregar(): Observable<Contexto> {
    return this.api.contexto().pipe(tap((c) => { this.ehFiscal.set(c.eh_fiscal); this.podeSolicitar.set(c.pode_solicitar); this.podeAdministrar.set(c.pode_administrar); this.espacos.set(c.espacos); }));
  }
}
