import { Component, computed, inject, input, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { forkJoin, of } from 'rxjs';

import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { OpcaoUsuario } from '../../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { formatarData } from '../../../shared/utilitarios/formatadores';
import { PIPES_FORMATACAO } from '../../../shared/utilitarios/formatadores.pipes';
import { CabecalhoModuloComponent } from '../compartilhado/cabecalho-modulo.component';
import { ContratosApiService } from '../compartilhado/contratos-api.service';
import { DetalheContrato, GravacaoContrato, GravacaoItem, OpcaoEmpresa, Papel, Situacao, TipoItem } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';
import { MESES, PAPEIS, PERIODICIDADES, paraDecimalApi, paraDecimalTela, ROTULOS_SITUACAO, ROTULOS_TIPO_ITEM } from '../compartilhado/rotulos';

interface ItemEdicao extends GravacaoItem {
  /** Item já salvo: nome, tipo e faturamento não mudam. */
  salvo: boolean;
}

const ITEM_VAZIO: ItemEdicao = {
  id: null,
  descricao: '',
  tipo: 'continuo',
  calcula_pro_rata: true,
  codigo_classe: '',
  codigo_natureza_despesa: '',
  codigo_siafisico: '',
  codigo_catmat_catser: '',
  quantidade_mensal: '',
  quantidade_total: '',
  valor_unitario: '',
  salvo: false,
};

/** Tela 2: cadastro e edição do contrato (dados, processos SEI, equipe e itens financeiros). */
@Component({
  selector: 'app-formulario-contrato',
  imports: [FormsModule, RouterLink, CabecalhoModuloComponent, SeletorUsuariosComponent, ...PIPES_FORMATACAO],
  templateUrl: './formulario-contrato.component.html',
  host: { '(document:keydown.escape)': 'fecharItem()' },
})
export class FormularioContratoComponent implements OnInit {
  /** Parâmetro de rota `:id` (ausente no cadastro). */
  readonly id = input<string>();

  protected readonly api = inject(ContratosApiService);
  private readonly execucao = inject(ExecucaoApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly roteador = inject(Router);
  private readonly autenticacao = inject(AutenticacaoService);

  protected readonly papeis = PAPEIS;
  protected readonly periodicidades = PERIODICIDADES;
  protected readonly meses = MESES;
  protected readonly situacoes = Object.entries(ROTULOS_SITUACAO) as [Situacao, string][];
  protected readonly rotulosTipo = ROTULOS_TIPO_ITEM;

  protected readonly carregando = signal(true);
  protected readonly salvando = signal(false);
  protected readonly empresas = signal<OpcaoEmpresa[]>([]);
  protected readonly original = signal<DetalheContrato | null>(null);
  protected readonly execucaoGerada = signal(false);
  protected readonly superRoot = computed(() => this.autenticacao.possuiPapel('SuperRoot'));
  protected readonly itensBloqueados = computed(() => this.execucaoGerada() && !this.superRoot());
  protected readonly datasBloqueadas = computed(() => (this.original()?.vigencias.length ?? 1) > 1);

  protected dados = {
    numero: '',
    empresa_id: '',
    apelido: '',
    objeto: '',
    data_inicio: '',
    vigencia_inicial_meses: 12,
    vigencia_maxima_meses: 60,
    periodicidade_meses: 1,
    mes_reajuste: new Date().getMonth() + 1,
    sei_gestao_numero: '',
    sei_gestao_link: '',
    sei_execucao_numero: '',
    sei_execucao_link: '',
    situacao_forcada: null as Situacao | null,
  };
  protected readonly equipe: Record<Papel, ReturnType<typeof signal<OpcaoUsuario[]>>> = Object.fromEntries(
    PAPEIS.map((p) => [p.papel, signal<OpcaoUsuario[]>([])]),
  ) as Record<Papel, ReturnType<typeof signal<OpcaoUsuario[]>>>;
  protected readonly itens = signal<ItemEdicao[]>([]);

  // Janela do item (2 passos)
  protected readonly itemAberto = signal<{ passo: 1 | 2; indice: number | null } | null>(null);
  protected item: ItemEdicao = { ...ITEM_VAZIO };
  private arrastando: number | null = null;

  protected readonly baseMensal = computed(() =>
    this.itens().filter((i) => i.tipo === 'continuo').reduce((t, i) => t + this.numero(i.quantidade_mensal) * this.numero(i.valor_unitario), 0),
  );

  ngOnInit(): void {
    const id = this.id();
    forkJoin({
      empresas: this.api.opcoesEmpresas(true),
      contrato: id ? this.api.consultar(id) : of(null),
      execucao: id ? this.execucao.painel(id) : of(null),
    }).subscribe({
      next: ({ empresas, contrato, execucao }) => {
        this.empresas.set(empresas);
        this.execucaoGerada.set(!!execucao?.geradas);
        if (contrato) this.preencher(contrato);
        else this.sugerirNumero();
        this.carregando.set(false);
      },
      error: (e) => {
        this.carregando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível carregar o contrato');
      },
    });
  }

  private preencher(c: DetalheContrato): void {
    this.original.set(c);
    this.dados = {
      numero: c.numero, empresa_id: c.empresa.id, apelido: c.apelido, objeto: c.objeto, data_inicio: c.data_inicio,
      vigencia_inicial_meses: c.vigencia_inicial_meses, vigencia_maxima_meses: c.vigencia_maxima_meses,
      periodicidade_meses: c.periodicidade_meses, mes_reajuste: c.mes_reajuste, sei_gestao_numero: c.sei_gestao_numero,
      sei_gestao_link: c.sei_gestao_link, sei_execucao_numero: c.sei_execucao_numero, sei_execucao_link: c.sei_execucao_link,
      situacao_forcada: c.situacao_forcada,
    };
    for (const membro of c.equipe) {
      this.equipe[membro.papel].set([{ id: membro.usuario_id, login: membro.login, nome_completo: membro.nome, cargo: '', ativo: true }]);
    }
    this.itens.set(
      c.itens.map((i) => ({
        id: i.id, descricao: i.descricao, tipo: i.tipo, calcula_pro_rata: i.calcula_pro_rata, codigo_classe: i.codigo_classe,
        codigo_natureza_despesa: i.codigo_natureza_despesa, codigo_siafisico: i.codigo_siafisico, codigo_catmat_catser: i.codigo_catmat_catser,
        quantidade_mensal: paraDecimalTela(i.quantidade_mensal),
        // Para sob demanda, a quantidade total da vigência inicial é o teto original do item
        quantidade_total: i.tipo === 'sob_demanda' ? paraDecimalTela(i.quantidade_original) : '',
        valor_unitario: paraDecimalTela(i.valor_unitario), salvo: true,
      })),
    );
  }

  protected sugerirNumero(): void {
    if (this.original()) return;
    const ano = this.dados.data_inicio ? Number(this.dados.data_inicio.slice(0, 4)) : new Date().getFullYear();
    this.api.proximoNumero(ano).subscribe((r) => (this.dados.numero = r.numero));
  }

  protected dataFinal(): string {
    if (!this.dados.data_inicio || !this.dados.vigencia_inicial_meses) return '—';
    const [ano, mes, dia] = this.dados.data_inicio.split('-').map(Number);
    const alvo = new Date(Date.UTC(ano, mes - 1 + Number(this.dados.vigencia_inicial_meses), 1));
    const ultimo = new Date(Date.UTC(alvo.getUTCFullYear(), alvo.getUTCMonth() + 1, 0)).getUTCDate();
    alvo.setUTCDate(Math.min(dia, ultimo));
    alvo.setUTCDate(alvo.getUTCDate() - 1);
    return formatarData(alvo.toISOString().slice(0, 10));
  }

  protected numero(valor: string | number): number {
    const n = Number(paraDecimalApi(valor));
    return Number.isFinite(n) ? n : 0;
  }

  protected valorGlobal(): number {
    const meses = this.original()?.vigencias.at(-1)?.meses ?? Number(this.dados.vigencia_inicial_meses || 0);
    return this.itens().reduce(
      (t, i) => t + (i.tipo === 'continuo' ? this.numero(i.quantidade_mensal) * meses : this.numero(i.quantidade_total)) * this.numero(i.valor_unitario),
      0,
    );
  }

  // --- Itens ---
  protected novoItem(): void {
    this.item = { ...ITEM_VAZIO };
    this.itemAberto.set({ passo: 1, indice: null });
  }

  protected editarItem(indice: number): void {
    this.item = { ...this.itens()[indice] };
    this.itemAberto.set({ passo: this.item.salvo ? 2 : 1, indice });
  }

  protected continuarItem(): void {
    if (!this.item.descricao.trim()) return;
    this.itemAberto.update((a) => (a ? { ...a, passo: 2 } : a));
  }

  protected concluirItem(): void {
    const aberto = this.itemAberto();
    if (!aberto) return;
    const lista = [...this.itens()];
    if (aberto.indice === null) lista.push({ ...this.item });
    else lista[aberto.indice] = { ...this.item };
    this.itens.set(lista);
    this.itemAberto.set(null);
  }

  protected fecharItem(): void {
    this.itemAberto.set(null);
  }

  protected itemCompleto(): boolean {
    const i = this.item;
    const codigos = [i.codigo_classe, i.codigo_natureza_despesa, i.codigo_siafisico, i.codigo_catmat_catser].every((c) => c.trim());
    const quantidades = i.tipo === 'continuo' ? this.numero(i.quantidade_mensal) > 0 : this.numero(i.quantidade_total) > 0;
    return codigos && quantidades && i.valor_unitario !== '' && this.numero(i.valor_unitario) >= 0;
  }

  protected async removerItem(indice: number): Promise<void> {
    const item = this.itens()[indice];
    if (item.salvo) {
      const ok = await this.dialogos.confirmar({
        titulo: `Excluir o item "${item.descricao}"?`,
        mensagem: 'O item será removido quando você salvar o contrato.',
        rotuloConfirmar: 'Excluir item',
      });
      if (!ok) return;
    }
    this.itens.update((l) => l.filter((_, i) => i !== indice));
  }

  protected mover(indice: number, deslocamento: number): void {
    const destino = indice + deslocamento;
    const lista = [...this.itens()];
    if (destino < 0 || destino >= lista.length) return;
    [lista[indice], lista[destino]] = [lista[destino], lista[indice]];
    this.itens.set(lista);
  }

  protected aoArrastar(indice: number): void {
    this.arrastando = indice;
  }

  protected aoSoltar(indice: number): void {
    if (this.arrastando === null || this.arrastando === indice) return;
    const lista = [...this.itens()];
    const [movido] = lista.splice(this.arrastando, 1);
    lista.splice(indice, 0, movido);
    this.itens.set(lista);
    this.arrastando = null;
  }

  protected tipoItem(tipo: TipoItem): string {
    return this.rotulosTipo[tipo];
  }

  // --- Gravação ---
  protected salvar(): void {
    const original = this.original();
    const corpo: GravacaoContrato = {
      ...this.dados,
      vigencia_inicial_meses: Number(this.dados.vigencia_inicial_meses),
      vigencia_maxima_meses: Number(this.dados.vigencia_maxima_meses),
      periodicidade_meses: Number(this.dados.periodicidade_meses),
      mes_reajuste: Number(this.dados.mes_reajuste),
      situacao_forcada: this.dados.situacao_forcada || null,
      equipe: Object.fromEntries(PAPEIS.map((p) => [p.papel, this.equipe[p.papel]()[0]?.id ?? null])),
      itens: this.itens().map((i) => ({
        id: i.id, descricao: i.descricao.trim(), tipo: i.tipo, calcula_pro_rata: i.calcula_pro_rata, codigo_classe: i.codigo_classe.trim(),
        codigo_natureza_despesa: i.codigo_natureza_despesa.trim(), codigo_siafisico: i.codigo_siafisico.trim(),
        codigo_catmat_catser: i.codigo_catmat_catser.trim(), quantidade_mensal: paraDecimalApi(i.quantidade_mensal),
        quantidade_total: i.tipo === 'sob_demanda' ? paraDecimalApi(i.quantidade_total) : '0', valor_unitario: paraDecimalApi(i.valor_unitario),
      })),
      versao: original?.versao ?? null,
    };
    this.salvando.set(true);
    const requisicao = original ? this.api.alterar(original.id, corpo) : this.api.criar(corpo);
    requisicao.subscribe({
      next: (contrato) => void this.roteador.navigate(['/contratos', contrato.id]),
      error: (e) => {
        this.salvando.set(false);
        this.dialogos.mostrarErro(e, 'Não foi possível salvar o contrato');
      },
    });
  }
}
