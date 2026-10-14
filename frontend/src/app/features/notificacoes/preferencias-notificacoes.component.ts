// Criado por José Eduardo Santana Martins
// Este arquivo serve para a aba Preferências das Notificações: matriz evento × canal, e-mail em resumo, não perturbe, testes e silenciados.

import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { NotificacoesApiService } from '../../core/notificacoes/notificacoes-api.service';
import {
  CANAIS_NOTIFICACAO, CanalNotificacao, ConfiguracaoNotificacoes, ModuloPreferencia, Preferencias, ROTULOS_CANAL, SituacaoNavegador,
} from '../../core/notificacoes/notificacoes.models';
import { PushNotificacoesService } from '../../core/notificacoes/push-notificacoes.service';
import { DialogosService } from '../../shared/servicos/dialogos.service';

import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
/** Chave `evento|canal` das caixas marcadas. */
const chave = (evento: string, canal: CanalNotificacao) => `${evento}|${canal}`;

/**
 * Preferências de notificação. A caixa (o sino) recebe sempre; e-mail, navegador e desktop começam desmarcados e cada pessoa liga o que quiser,
 * por evento (agrupado por módulo). Obrigatórias (definidas pela administração) aparecem marcadas e travadas. Salvar substitui tudo de uma vez.
 */
@Component({
  selector: 'app-preferencias-notificacoes',
  imports: [EsqueletoComponent, FormsModule],
  templateUrl: './preferencias-notificacoes.component.html',
  styleUrl: './preferencias-notificacoes.component.scss',
})
export class PreferenciasNotificacoesComponent implements OnInit {
  private readonly api = inject(NotificacoesApiService);
  private readonly dialogos = inject(DialogosService);
  protected readonly push = inject(PushNotificacoesService);

  protected readonly canais = CANAIS_NOTIFICACAO;
  protected readonly rotulos = ROTULOS_CANAL;
  protected readonly dados = signal<Preferencias | null>(null);
  /** Caixas marcadas (inclui as obrigatórias, que não saem). */
  protected readonly marcadas = signal<ReadonlySet<string>>(new Set());
  protected configuracao: ConfiguracaoNotificacoes = { frequencia_email: 'imediato', silencio_inicio: null, silencio_fim: null, silencio_fins_de_semana: false };
  protected naoPerturbe = false;
  protected readonly salvando = signal(false);
  protected readonly alterado = signal(false);
  protected readonly testando = signal<CanalNotificacao | null>(null);
  protected readonly navegador = computed<SituacaoNavegador | null>(() => this.dados()?.navegador ?? null);

  ngOnInit(): void {
    this.carregar();
  }

  private carregar(): void {
    this.api.preferencias().subscribe({
      next: (p) => this.aplicar(p),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar as preferências'),
    });
  }

  private aplicar(p: Preferencias): void {
    this.dados.set(p);
    const ligadas = new Set<string>();
    for (const m of p.modulos) for (const e of m.eventos) for (const c of this.canais) if (e.canais[c].ligado) ligadas.add(chave(e.chave, c));
    this.marcadas.set(ligadas);
    this.configuracao = { ...p.configuracao };
    this.naoPerturbe = !!(p.configuracao.silencio_inicio && p.configuracao.silencio_fim);
    this.alterado.set(false);
    void this.push.atualizarEstado();
  }

  protected marcada(evento: string, canal: CanalNotificacao): boolean {
    return this.marcadas().has(chave(evento, canal));
  }

  /** Marca ou desmarca uma caixa. Ao ligar o navegador pela primeira vez, pede a permissão e inscreve este navegador. */
  protected alternar(evento: string, canal: CanalNotificacao): void {
    const ligar = !this.marcada(evento, canal);
    this.definir([chave(evento, canal)], ligar);
    if (ligar && canal === 'navegador') void this.garantirNavegador();
  }

  private definir(chaves: string[], ligar: boolean): void {
    const novas = new Set(this.marcadas());
    for (const k of chaves) { if (ligar) novas.add(k); else novas.delete(k); }
    this.marcadas.set(novas);
    this.alterado.set(true);
  }

  /** Chaves editáveis (disponíveis e não obrigatórias) de um módulo, de uma coluna ou das duas coisas. */
  private editaveis(modulo?: ModuloPreferencia, canal?: CanalNotificacao): string[] {
    const modulos = modulo ? [modulo] : (this.dados()?.modulos ?? []);
    const resultado: string[] = [];
    for (const m of modulos) for (const e of m.eventos) for (const c of canal ? [canal] : this.canais) {
      if (e.canais[c].disponivel && !e.canais[c].obrigatorio) resultado.push(chave(e.chave, c));
    }
    return resultado;
  }

  protected tudoMarcado(modulo?: ModuloPreferencia, canal?: CanalNotificacao): boolean {
    const chaves = this.editaveis(modulo, canal);
    return chaves.length > 0 && chaves.every((k) => this.marcadas().has(k));
  }

  /** "Marcar o módulo inteiro" ou "marcar a coluna inteira" (clicar de novo desmarca). */
  protected alternarGrupo(modulo?: ModuloPreferencia, canal?: CanalNotificacao): void {
    const ligar = !this.tudoMarcado(modulo, canal);
    this.definir(this.editaveis(modulo, canal), ligar);
    if (ligar && (canal === 'navegador' || (!canal && modulo))) void this.garantirNavegador();
  }

  private async garantirNavegador(): Promise<void> {
    const situacao = this.navegador();
    if (!situacao?.disponivel || !situacao.chave_publica_vapid) return;
    if (this.push.estado() === 'ativo' || this.push.estado() === 'bloqueado' || this.push.estado() === 'nao_suportado' || this.push.estado() === 'ios_sem_instalar') return;
    await this.ativarNavegador();
  }

  protected async ativarNavegador(): Promise<void> {
    const chavePublica = this.navegador()?.chave_publica_vapid;
    if (!chavePublica) return;
    try {
      await this.push.ativar(chavePublica);
      this.carregarNavegador();
    } catch (erro) {
      this.dialogos.avisar('Notificações do navegador', erro instanceof Error ? erro.message : 'Não foi possível ativar as notificações do navegador.');
    }
  }

  protected async desativarNavegador(): Promise<void> {
    try {
      await this.push.desativar();
      this.carregarNavegador();
    } catch (erro) {
      this.dialogos.avisar('Notificações do navegador', erro instanceof Error ? erro.message : 'Não foi possível desativar neste navegador.');
    }
  }

  private carregarNavegador(): void {
    this.api.preferencias().subscribe((p) => this.dados.update((d) => (d ? { ...d, navegador: p.navegador } : p)));
  }

  protected salvar(): void {
    if (this.salvando()) return;
    const canais: Record<string, CanalNotificacao[]> = {};
    for (const k of this.marcadas()) {
      const [evento, canal] = k.split('|') as [string, CanalNotificacao];
      (canais[evento] ??= []).push(canal);
    }
    const configuracao: ConfiguracaoNotificacoes = this.naoPerturbe
      ? { ...this.configuracao, silencio_inicio: this.configuracao.silencio_inicio || '19:00', silencio_fim: this.configuracao.silencio_fim || '07:00' }
      : { ...this.configuracao, silencio_inicio: null, silencio_fim: null };
    this.salvando.set(true);
    this.api.salvarPreferencias(canais, configuracao).subscribe({
      next: (p) => { this.salvando.set(false); this.aplicar(p); this.dialogos.avisar('Preferências salvas', 'Suas escolhas já valem para as próximas notificações.'); },
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível salvar as preferências'); },
    });
  }

  protected testar(canal: CanalNotificacao): void {
    this.testando.set(canal);
    this.api.testar(canal).subscribe({
      next: (r) => { this.testando.set(null); this.dialogos.avisar(r.enviado ? 'Teste enviado' : 'Teste não enviado', r.detalhe); },
      error: (e) => { this.testando.set(null); this.dialogos.mostrarErro(e, 'Não foi possível testar'); },
    });
  }

  protected voltarAAvisar(id: number): void {
    this.api.voltarAAvisar(id).subscribe({
      next: () => this.carregarSilenciados(),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível voltar a avisar'),
    });
  }

  private carregarSilenciados(): void {
    this.api.preferencias().subscribe((p) => this.dados.update((d) => (d ? { ...d, silenciados: p.silenciados } : p)));
  }
}
