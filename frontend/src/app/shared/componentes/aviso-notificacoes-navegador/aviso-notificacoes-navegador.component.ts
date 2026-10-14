// Criado por José Eduardo Santana Martins
// Este arquivo serve para pedir, no acesso ao SGI, a permissão do navegador para as notificações (Web Push).

import { Component, inject, OnInit, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { NotificacoesApiService } from '../../../core/notificacoes/notificacoes-api.service';
import { PushNotificacoesService } from '../../../core/notificacoes/push-notificacoes.service';

/**
 * Aviso que aparece quando a pessoa tem o canal Navegador ligado nas Preferências mas este navegador ainda não está inscrito.
 * Navegadores só mostram o pedido de permissão depois de um clique, por isso o aviso tem o botão "Ativar". Se a permissão já foi dada,
 * a inscrição é feita sem perguntar. "Agora não" some só nesta visita: no próximo acesso o aviso volta.
 */
@Component({
  selector: 'app-aviso-notificacoes-navegador',
  templateUrl: './aviso-notificacoes-navegador.component.html',
  styleUrl: './aviso-notificacoes-navegador.component.scss',
})
export class AvisoNotificacoesNavegadorComponent implements OnInit {
  private readonly api = inject(NotificacoesApiService);
  private readonly push = inject(PushNotificacoesService);

  protected readonly visivel = signal(false);
  protected readonly ativando = signal(false);
  protected readonly erro = signal('');
  private chavePublica = '';

  async ngOnInit(): Promise<void> {
    try {
      const preferencias = await firstValueFrom(this.api.preferencias());
      const situacao = preferencias.navegador;
      if (!situacao?.disponivel || !situacao.chave_publica_vapid) return;
      const querNavegador = preferencias.modulos.some((m) => m.eventos.some((e) => e.canais['navegador'].ligado));
      if (!querNavegador) return;
      const estado = await this.push.atualizarEstado();
      if (estado !== 'inativo') return;
      this.chavePublica = situacao.chave_publica_vapid;
      // Permissão já concedida: só falta inscrever, sem perguntar nada
      if (Notification.permission === 'granted') {
        await this.push.ativar(this.chavePublica);
        return;
      }
      this.visivel.set(true);
    } catch {
      // Sem aviso: o canal continua disponível na tela de Preferências
    }
  }

  protected async ativar(): Promise<void> {
    this.ativando.set(true);
    this.erro.set('');
    try {
      await this.push.ativar(this.chavePublica);
      this.visivel.set(false);
    } catch (e) {
      this.erro.set(e instanceof Error ? e.message : 'Não foi possível ativar as notificações do navegador.');
    } finally {
      this.ativando.set(false);
    }
  }

  protected agoraNao(): void {
    this.visivel.set(false);
  }
}
