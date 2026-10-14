// Criado por José Eduardo Santana Martins
// Este arquivo serve para ativar e desativar as notificações do navegador (Web Push): permissão, service worker e inscrição.

import { inject, Injectable, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { NotificacoesApiService } from './notificacoes-api.service';

/** Situação das notificações do navegador neste aparelho. */
export type EstadoPush = 'nao_suportado' | 'ios_sem_instalar' | 'bloqueado' | 'inativo' | 'ativo';

const ENDERECO_SW = '/sw-notificacoes.js';

/** A chave pública VAPID chega em base64 URL; `pushManager.subscribe` quer bytes. */
function paraBytes(base64Url: string): Uint8Array<ArrayBuffer> {
  const preenchida = (base64Url + '='.repeat((4 - (base64Url.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/');
  const bruto = atob(preenchida);
  const bytes = new Uint8Array(new ArrayBuffer(bruto.length));
  for (let i = 0; i < bruto.length; i += 1) bytes[i] = bruto.charCodeAt(i);
  return bytes;
}

/** Converte a chave da inscrição (ArrayBuffer) em base64 URL, como o servidor espera. */
function paraBase64Url(buffer: ArrayBuffer | null): string {
  if (!buffer) return '';
  let texto = '';
  for (const byte of new Uint8Array(buffer)) texto += String.fromCharCode(byte);
  return btoa(texto).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/**
 * Notificações do navegador (Web Push). Ativar pede a permissão do navegador, registra o service worker (`/sw-notificacoes.js`, escopo `/`),
 * faz o `pushManager.subscribe` com a chave VAPID do servidor e envia a inscrição à API. No iPhone/iPad (iOS 16.4 ou mais) só funciona com
 * o SGI instalado na tela inicial.
 */
@Injectable({ providedIn: 'root' })
export class PushNotificacoesService {
  private readonly api = inject(NotificacoesApiService);

  readonly estado = signal<EstadoPush>('inativo');

  private suportado(): boolean {
    return typeof navigator !== 'undefined' && 'serviceWorker' in navigator && typeof window !== 'undefined' && 'PushManager' in window && 'Notification' in window;
  }

  /** iPhone ou iPad (o iPadOS novo se apresenta como Mac com toque). */
  ehIos(): boolean {
    return /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  }

  /** O SGI está aberto como aplicativo instalado (tela inicial)? */
  instalado(): boolean {
    return window.matchMedia?.('(display-mode: standalone)').matches || (navigator as unknown as { standalone?: boolean }).standalone === true;
  }

  /** Navegador e sistema, para a pessoa reconhecer o aparelho na lista (ex.: "Chrome no Windows"). */
  rotuloDoAparelho(): string {
    const ua = navigator.userAgent;
    const navegador = /Edg\//.test(ua) ? 'Edge' : /OPR\//.test(ua) ? 'Opera' : /Firefox\//.test(ua) ? 'Firefox' : /Chrome\//.test(ua) ? 'Chrome' : /Safari\//.test(ua) ? 'Safari' : 'Navegador';
    const sistema = /Windows/.test(ua) ? 'Windows' : /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iOS' : /Mac OS X/.test(ua) ? 'macOS' : /Linux/.test(ua) ? 'Linux' : '';
    return sistema ? `${navegador} no ${sistema}` : navegador;
  }

  /** Confere a permissão e se este navegador já está inscrito. */
  async atualizarEstado(): Promise<EstadoPush> {
    let estado: EstadoPush;
    if (this.ehIos() && !this.instalado()) estado = 'ios_sem_instalar';
    else if (!this.suportado()) estado = 'nao_suportado';
    else if (Notification.permission === 'denied') estado = 'bloqueado';
    else {
      const registro = await navigator.serviceWorker.getRegistration('/').catch(() => undefined);
      const inscricao = registro ? await registro.pushManager.getSubscription().catch(() => null) : null;
      estado = inscricao && Notification.permission === 'granted' ? 'ativo' : 'inativo';
    }
    this.estado.set(estado);
    return estado;
  }

  /** Pede a permissão, registra o service worker, inscreve e avisa o servidor. Lança erro com texto pronto para mostrar. */
  async ativar(chavePublica: string): Promise<void> {
    if (!this.suportado()) throw new Error('Este navegador não suporta notificações.');
    const permissao = await Notification.requestPermission();
    if (permissao !== 'granted') {
      this.estado.set(permissao === 'denied' ? 'bloqueado' : 'inativo');
      throw new Error(permissao === 'denied' ? 'A permissão foi negada. Libere as notificações nas configurações do site.' : 'A permissão não foi concedida.');
    }
    const registro = await navigator.serviceWorker.register(ENDERECO_SW, { scope: '/' });
    await navigator.serviceWorker.ready;
    const existente = await registro.pushManager.getSubscription();
    const inscricao = existente ?? await registro.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: paraBytes(chavePublica) });
    await firstValueFrom(this.api.inscreverNavegador({
      endpoint: inscricao.endpoint,
      p256dh: paraBase64Url(inscricao.getKey('p256dh')),
      auth: paraBase64Url(inscricao.getKey('auth')),
      rotulo: this.rotuloDoAparelho(),
    }));
    this.estado.set('ativo');
  }

  /** Cancela a inscrição deste navegador (no navegador e no servidor). */
  async desativar(): Promise<void> {
    const registro = await navigator.serviceWorker.getRegistration('/');
    const inscricao = registro ? await registro.pushManager.getSubscription() : null;
    if (inscricao) {
      await firstValueFrom(this.api.removerNavegador(inscricao.endpoint));
      await inscricao.unsubscribe();
    }
    this.estado.set('inativo');
  }
}
