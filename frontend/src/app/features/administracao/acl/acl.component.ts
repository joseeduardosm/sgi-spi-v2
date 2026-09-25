// Criado por José Eduardo Santana Martins
// Este arquivo serve para controlar a tela de administração da ACL: regras, recursos e consulta de acesso efetivo.

import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, OnInit, signal } from '@angular/core';
import { FormsModule, NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { AcessoEfetivo, NIVEIS_ACL, NivelAcl, ROTULOS_NIVEL } from '../../../core/acesso/acesso.service';
import { OpcaoUsuario } from '../../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { Setor, SetoresApiService } from '../../setores/setores-api.service';
import { UsuariosApiService } from '../../usuarios/usuarios-api.service';
import { AclApiService, RecursoAcl, RegraAcl } from './acl-api.service';

/** Abas da tela. */
type Aba = 'regras' | 'recursos' | 'efetivo';

/** Administração de ACL: recursos, regras e consulta de acesso efetivo (SuperRoot). */
@Component({
  selector: 'app-acl',
  imports: [FormsModule, ReactiveFormsModule, DatePipe, SeletorUsuariosComponent],
  templateUrl: './acl.component.html',
  host: { '(document:keydown.escape)': 'fecharFormularios()' },
})
export class AclComponent implements OnInit {
  private readonly api = inject(AclApiService);
  private readonly setoresApi = inject(SetoresApiService);
  protected readonly usuarios = inject(UsuariosApiService);
  private readonly construtor = inject(NonNullableFormBuilder);

  // Listas fixas para os seletores de nível
  protected readonly niveis = NIVEIS_ACL;
  protected readonly rotulosNivel = ROTULOS_NIVEL;
  protected readonly aba = signal<Aba>('regras');
  protected readonly aviso = signal<{ texto: string; erro: boolean } | null>(null);

  // Dados carregados e o filtro de regras por recurso
  protected readonly recursos = signal<RecursoAcl[]>([]);
  protected readonly regras = signal<RegraAcl[]>([]);
  protected readonly setores = signal<Setor[]>([]);
  protected filtroRecurso = 0;
  protected readonly recursoFiltrado = signal(0);
  protected readonly regrasVisiveis = computed(() => {
    const id = this.recursoFiltrado();
    return id ? this.regras().filter((r) => r.recurso_id === id) : this.regras();
  });

  // Regra (modal)
  protected readonly regraAberta = signal(false);
  protected readonly regraEmEdicao = signal<RegraAcl | null>(null);
  protected readonly usuariosDaRegra = signal<OpcaoUsuario[]>([]);
  protected readonly setoresDaRegra = signal<Set<number>>(new Set());
  protected buscaSetor = '';
  protected readonly termoSetor = signal('');
  // Setores filtrados pelo texto digitado na janela da regra
  protected readonly opcoesSetor = computed(() => {
    const termo = this.termoSetor().toLowerCase();
    return this.setores().filter((s) => !termo || s.nome.toLowerCase().includes(termo));
  });
  protected readonly formularioRegra = this.construtor.group({
    recurso_id: [0, [Validators.min(1)]],
    nivel: ['LEITURA' as NivelAcl],
  });

  // Recurso (modal)
  protected readonly recursoAberto = signal(false);
  protected readonly recursoEmEdicao = signal<RecursoAcl | null>(null);
  protected readonly formularioRecurso = this.construtor.group({
    nome: ['', [Validators.required, Validators.maxLength(100)]],
    slug: ['', [Validators.required, Validators.maxLength(60)]],
    descricao: [''],
    url_base: [''],
    ativo: [true],
  });

  protected readonly salvando = signal(false);
  protected readonly erroFormulario = signal<string | null>(null);

  // Acesso efetivo
  protected readonly usuarioConsultado = signal<OpcaoUsuario[]>([]);
  protected readonly acessosEfetivos = signal<AcessoEfetivo[] | null>(null);

  constructor() {
    // Sempre que o usuário consultado muda, busca o acesso efetivo dele
    effect(() => {
      const usuario = this.usuarioConsultado()[0];
      this.acessosEfetivos.set(null);
      if (usuario) this.api.acessoEfetivo(usuario.id).subscribe((itens) => this.acessosEfetivos.set(itens));
    });
  }

  /** Ao abrir a tela: recursos, regras e setores. */
  ngOnInit(): void {
    this.recarregar();
    this.setoresApi.listar().subscribe((s) => this.setores.set(s));
  }

  /** Recarrega recursos e regras (depois de qualquer gravação). */
  protected recarregar(): void {
    this.api.listarRecursos().subscribe({
      next: (r) => this.recursos.set(r),
      error: (erro) => this.falhar(erro, 'Não foi possível carregar os recursos.'),
    });
    this.api.listarRegras().subscribe({
      next: (r) => this.regras.set(r),
      error: (erro) => this.falhar(erro, 'Não foi possível carregar as regras.'),
    });
  }

  /** Filtra a tabela de regras pelo recurso escolhido (0 = todos). */
  protected filtrarPorRecurso(valor: number): void {
    this.recursoFiltrado.set(Number(valor));
  }

  /** Texto que explica a política atual do recurso (aberto, lista positiva ou inativo). */
  protected politica(r: RecursoAcl): string {
    if (!r.ativo) return 'Inativo: acesso aberto';
    return r.total_regras ? `Lista positiva · ${r.total_regras} regra(s)` : 'Aberto: sem regras';
  }

  // --- Regras ---
  /** Abre a janela da regra: vazia (nova) ou preenchida (edição). */
  protected abrirRegra(regra?: RegraAcl): void {
    this.regraEmEdicao.set(regra ?? null);
    this.erroFormulario.set(null);
    this.formularioRegra.reset({ recurso_id: regra?.recurso_id ?? (this.recursoFiltrado() || 0), nivel: regra?.nivel ?? 'LEITURA' });
    this.usuariosDaRegra.set(regra?.usuarios ?? []);
    this.setoresDaRegra.set(new Set(regra?.setores.map((s) => s.id) ?? []));
    this.buscaSetor = '';
    this.termoSetor.set('');
    this.regraAberta.set(true);
  }

  /** Marca ou desmarca um setor na regra. */
  protected alternarSetor(id: number): void {
    this.setoresDaRegra.update((conjunto) => {
      const novo = new Set(conjunto);
      if (novo.has(id)) novo.delete(id);
      else novo.add(id);
      return novo;
    });
  }

  /** Valida e grava a regra; na primeira regra de um recurso, avisa que ele deixará de ser aberto. */
  protected salvarRegra(): void {
    const valores = this.formularioRegra.getRawValue();
    if (!Number(valores.recurso_id)) return this.erroFormulario.set('Selecione o recurso.');
    if (!this.usuariosDaRegra().length && !this.setoresDaRegra().size) return this.erroFormulario.set('Selecione ao menos um usuário ou setor.');
    const dados = {
      recurso_id: Number(valores.recurso_id),
      nivel: valores.nivel,
      usuarios_ids: this.usuariosDaRegra().map((u) => u.id),
      setores_ids: [...this.setoresDaRegra()],
    };
    const atual = this.regraEmEdicao();
    const recurso = this.recursos().find((r) => r.id === dados.recurso_id);
    const primeiraRegra = !atual && recurso && recurso.total_regras === 0;
    // A primeira regra muda a política do recurso para "lista positiva": pede confirmação
    if (
      primeiraRegra &&
      !confirm(`Esta é a primeira regra de "${recurso.nome}". A partir dela, somente os usuários e setores contemplados terão acesso. Continuar?`)
    )
      return;
    this.salvando.set(true);
    this.erroFormulario.set(null);
    this.api.gravarRegra(dados, atual?.id).subscribe({
      next: () => {
        this.salvando.set(false);
        this.regraAberta.set(false);
        this.aviso.set({ texto: `Regra ${atual ? 'atualizada' : 'criada'}.`, erro: false });
        this.recarregar();
      },
      error: (erro) => {
        this.salvando.set(false);
        this.erroFormulario.set(this.mensagem(erro, 'Não foi possível salvar a regra.'));
      },
    });
  }

  /** Pede confirmação e exclui a regra. */
  protected excluirRegra(regra: RegraAcl): void {
    if (!confirm(`Excluir a regra de ${this.rotulosNivel[regra.nivel]} em "${regra.recurso_nome}"?`)) return;
    this.api.excluirRegra(regra.id).subscribe({
      next: () => {
        this.aviso.set({ texto: 'Regra excluída.', erro: false });
        this.recarregar();
      },
      error: (erro) => this.falhar(erro, 'Não foi possível excluir a regra.'),
    });
  }

  // --- Recursos ---
  /** Abre a janela do recurso: vazia (novo) ou preenchida (edição). */
  protected abrirRecurso(recurso?: RecursoAcl): void {
    this.recursoEmEdicao.set(recurso ?? null);
    this.erroFormulario.set(null);
    this.formularioRecurso.reset({
      nome: recurso?.nome ?? '',
      slug: recurso?.slug ?? '',
      descricao: recurso?.descricao ?? '',
      url_base: recurso?.url_base ?? '',
      ativo: recurso?.ativo ?? true,
    });
    this.recursoAberto.set(true);
  }

  /** Valida e grava o recurso. */
  protected salvarRecurso(): void {
    if (this.formularioRecurso.invalid) {
      this.formularioRecurso.markAllAsTouched();
      return this.erroFormulario.set('Nome e slug são obrigatórios.');
    }
    const atual = this.recursoEmEdicao();
    this.salvando.set(true);
    this.erroFormulario.set(null);
    this.api.gravarRecurso(this.formularioRecurso.getRawValue(), atual?.id).subscribe({
      next: (r) => {
        this.salvando.set(false);
        this.recursoAberto.set(false);
        this.aviso.set({ texto: `Recurso "${r.nome}" salvo (slug: ${r.slug}).`, erro: false });
        this.recarregar();
      },
      error: (erro) => {
        this.salvando.set(false);
        this.erroFormulario.set(this.mensagem(erro, 'Não foi possível salvar o recurso.'));
      },
    });
  }

  /** Pede confirmação e exclui o recurso (e suas regras). */
  protected excluirRecurso(recurso: RecursoAcl): void {
    if (!confirm(`Excluir o recurso "${recurso.nome}" e suas ${recurso.total_regras} regra(s)? O módulo volta a ficar aberto.`)) return;
    this.api.excluirRecurso(recurso.id).subscribe({
      next: () => {
        this.aviso.set({ texto: `Recurso "${recurso.nome}" excluído.`, erro: false });
        this.recarregar();
      },
      error: (erro) => this.falhar(erro, 'Não foi possível excluir o recurso.'),
    });
  }

  /** Fecha as janelas abertas (Esc), a menos que esteja salvando. */
  protected fecharFormularios(): void {
    if (this.salvando()) return;
    this.regraAberta.set(false);
    this.recursoAberto.set(false);
  }

  /** Mostra a mensagem de erro no aviso da tela. */
  private falhar(erro: unknown, padrao: string): void {
    this.aviso.set({ texto: this.mensagem(erro, padrao), erro: true });
  }

  /** Mensagem da API, se houver, ou a padrão da operação. */
  private mensagem(erro: unknown, padrao: string): string {
    if (erro instanceof HttpErrorResponse && typeof erro.error?.detalhe === 'string') return erro.error.detalhe;
    return padrao;
  }
}
