// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela da caixa de mensagens (recebidas, nova mensagem e enviadas).

import { DatePipe } from '@angular/common';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { CaixaMensagensService } from '../../core/mensagens/caixa-mensagens.service';
import { MensagensApiService } from '../../core/mensagens/mensagens-api.service';
import {
  Destinatarios, EntregaDetalhe, EntregaResumo, EnviadaDetalhe, EnviadaResumo, EnvioMensagem, Pagina,
  ROTULOS_CATEGORIA, ROTULOS_ESTADO, ROTULOS_PRIORIDADE,
} from '../../core/mensagens/mensagens.models';
import { PaginacaoComponent } from '../../shared/componentes/paginacao/paginacao.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';

/** Minúsculas sem acento, para filtrar a lista de destinatários. */
function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

/** Formulário vazio de nova mensagem. */
function envioVazio(): EnvioMensagem {
  return {
    assunto: '', corpo: '', prioridade: 'normal', categoria: 'comunicado', usuarios_ids: [], setores_ids: [],
    expira_em: null, link: null, enviar_email: false,
  };
}

/**
 * Caixa de mensagens: aba Recebidas (pendentes, cientes, todas; busca; ciência) e aba Enviadas (situação de
 * cada destinatário e lembrete por e-mail). Nenhuma mensagem bloqueia a navegação.
 */
@Component({
  selector: 'app-mensagens',
  imports: [FormsModule, DatePipe, PaginacaoComponent],
  templateUrl: './mensagens.component.html',
  host: { '(document:keydown.escape)': 'fecharJanelas()' },
})
export class MensagensComponent implements OnInit {
  private readonly api = inject(MensagensApiService);
  private readonly caixa = inject(CaixaMensagensService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);

  protected readonly prioridades = ROTULOS_PRIORIDADE;
  protected readonly categorias = ROTULOS_CATEGORIA;
  protected readonly estados = ROTULOS_ESTADO;
  protected readonly listaPrioridades = Object.entries(ROTULOS_PRIORIDADE);
  protected readonly listaCategorias = Object.entries(ROTULOS_CATEGORIA);

  // Aba e filtros
  protected readonly aba = signal<'recebidas' | 'enviadas'>('recebidas');
  protected estado = 'pendentes';
  protected busca = '';
  protected readonly recebidas = signal<Pagina<EntregaResumo> | null>(null);
  protected readonly enviadas = signal<Pagina<EnviadaResumo> | null>(null);
  // Janelas: mensagem aberta, nova mensagem, acompanhamento de uma enviada
  protected readonly aberta = signal<EntregaDetalhe | null>(null);
  protected readonly novaAberta = signal(false);
  protected readonly acompanhamento = signal<EnviadaDetalhe | null>(null);
  protected readonly ocupado = signal(false);
  // Nova mensagem
  protected envio = envioVazio();
  protected expiraEm = '';
  protected readonly destinatarios = signal<Destinatarios | null>(null);
  protected readonly filtroUsuarios = signal('');
  protected readonly filtroSetores = signal('');
  protected readonly usuariosFiltrados = computed(() => {
    const termo = normalizar(this.filtroUsuarios());
    return (this.destinatarios()?.usuarios ?? []).filter((u) => normalizar(`${u.nome} ${u.detalhe}`).includes(termo));
  });
  protected readonly setoresFiltrados = computed(() => {
    const termo = normalizar(this.filtroSetores());
    return (this.destinatarios()?.setores ?? []).filter((s) => normalizar(s.nome).includes(termo));
  });

  ngOnInit(): void {
    this.carregar(1);
  }

  protected escolherAba(aba: 'recebidas' | 'enviadas'): void {
    this.aba.set(aba);
    this.carregar(1);
  }

  /** Carrega a página da aba atual. */
  protected carregar(pagina: number): void {
    if (this.aba() === 'recebidas') {
      this.api.listar(this.estado, this.busca.trim(), pagina).subscribe({
        next: (p) => this.recebidas.set(p),
        error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar as mensagens'),
      });
    } else {
      this.api.enviadas(pagina).subscribe({
        next: (p) => this.enviadas.set(p),
        error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar as mensagens enviadas'),
      });
    }
  }

  /** Abre a mensagem (conta como lida). */
  protected abrir(item: EntregaResumo): void {
    this.api.abrir(item.id).subscribe({
      next: (m) => {
        this.aberta.set(m);
        this.carregar(this.recebidas()?.pagina ?? 1);
        this.caixa.atualizar();
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível abrir a mensagem'),
    });
  }

  /** "Li e estou ciente". */
  protected ciente(m: EntregaDetalhe): void {
    this.ocupado.set(true);
    this.api.ciencia(m.id).subscribe({
      next: (atualizada) => {
        this.ocupado.set(false);
        this.aberta.set(atualizada);
        this.carregar(this.recebidas()?.pagina ?? 1);
        this.caixa.atualizar();
      },
      error: (e) => {
        this.ocupado.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível registrar a ciência');
      },
    });
  }

  protected irPara(link: string): void {
    this.fecharJanelas();
    void this.roteador.navigateByUrl(link);
  }

  // --- Nova mensagem ---------------------------------------------------------------------------

  protected abrirNova(): void {
    this.envio = envioVazio();
    this.expiraEm = '';
    this.filtroUsuarios.set('');
    this.filtroSetores.set('');
    this.api.destinatarios().subscribe({
      next: (d) => {
        this.destinatarios.set(d);
        this.novaAberta.set(true);
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar os destinatários'),
    });
  }

  protected alternar(lista: 'usuarios_ids' | 'setores_ids', id: number, marcado: boolean): void {
    this.envio[lista] = marcado ? [...this.envio[lista], id] : this.envio[lista].filter((x) => x !== id);
  }

  protected valida(): boolean {
    return !!this.envio.assunto.trim() && !!this.envio.corpo.trim() && (this.envio.usuarios_ids.length + this.envio.setores_ids.length) > 0;
  }

  protected enviar(): void {
    const dados: EnvioMensagem = {
      ...this.envio,
      link: this.envio.link?.trim() || null,
      // Fim do dia escolhido, no horário de Brasília
      expira_em: this.expiraEm ? `${this.expiraEm}T23:59:59-03:00` : null,
    };
    this.dialogos.executar(this.api.enviar(dados), 'Enviando a mensagem…').subscribe({
      next: (r) => {
        this.novaAberta.set(false);
        this.dialogos.avisar('Mensagem enviada', `Entregue a ${r.destinatarios} destinatário(s)${dados.enviar_email ? '; os e-mails estão sendo enviados' : ''}.`);
        this.escolherAba('enviadas');
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível enviar a mensagem'),
    });
  }

  // --- Enviadas ------------------------------------------------------------------------------

  protected acompanhar(item: EnviadaResumo): void {
    this.api.enviada(item.id).subscribe({
      next: (d) => this.acompanhamento.set(d),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível abrir o acompanhamento'),
    });
  }

  protected async lembrar(d: EnviadaDetalhe): Promise<void> {
    const faltam = d.destinatarios - d.cientes;
    const ok = await this.dialogos.confirmar({
      titulo: 'Lembrar quem não deu ciência?',
      mensagem: `Um e-mail de lembrete será enviado a ${faltam} destinatário(s) que ainda não registraram ciência.`,
      rotuloConfirmar: 'Enviar lembrete',
    });
    if (!ok) return;
    this.dialogos.executar(this.api.lembrar(d.id), 'Enviando os lembretes…').subscribe({
      next: (r) => this.dialogos.avisar('Lembrete enviado', `${r.lembrados} destinatário(s) receberão o e-mail.`),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível enviar o lembrete'),
    });
  }

  protected percentual(item: EnviadaResumo): number {
    return item.destinatarios ? Math.round((item.cientes * 100) / item.destinatarios) : 0;
  }

  protected fecharJanelas(): void {
    this.aberta.set(null);
    this.acompanhamento.set(null);
    if (!this.ocupado()) this.novaAberta.set(false);
  }
}
