// Criado por José Eduardo Santana Martins
// Este arquivo serve para baixar em segundo plano, quando o navegador está ocioso, as rotas dos módulos (só as definições, sem as telas).

import { Injectable } from '@angular/core';
import { PreloadingStrategy, Route } from '@angular/router';
import { Observable, of } from 'rxjs';
import { mergeMap } from 'rxjs/operators';

/**
 * Pré-carrega os módulos (`loadChildren`) quando o navegador está ocioso: o primeiro clique em Tarefas, Patrimônio ou Contratos não espera o download das rotas.
 * Não pré-carrega com "economizar dados" ligado nem em conexão 2G; as telas em si continuam sendo baixadas só quando abertas.
 */
@Injectable({ providedIn: 'root' })
export class PrecarregamentoOcioso implements PreloadingStrategy {
  preload(rota: Route, carregar: () => Observable<unknown>): Observable<unknown> {
    if (!rota.loadChildren || this.conexaoFraca()) return of(null);
    return new Observable<void>((assinante) => {
      const iniciar = () => { assinante.next(); assinante.complete(); };
      const ocioso = (globalThis as { requestIdleCallback?: (f: () => void, o?: { timeout: number }) => number }).requestIdleCallback;
      if (ocioso) ocioso(iniciar, { timeout: 4000 }); else setTimeout(iniciar, 2000);
    }).pipe(mergeMap(() => carregar()));
  }

  private conexaoFraca(): boolean {
    const conexao = (navigator as unknown as { connection?: { saveData?: boolean; effectiveType?: string } }).connection;
    return !!conexao && (conexao.saveData === true || /(^|-)2g$/.test(conexao.effectiveType ?? ''));
  }
}
