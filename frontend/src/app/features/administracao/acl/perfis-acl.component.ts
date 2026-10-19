// Criado por José Eduardo Santana Martins
// Este arquivo serve para administrar os perfis de acesso: lista, dados gerais, matriz de permissões e usuários do perfil.

import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, inject, input, OnInit, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AutenticacaoService } from '../../../core/autenticacao/autenticacao.service';
import { OpcaoUsuario } from '../../../core/modelos/usuario.model';
import { EsqueletoComponent } from '../../../shared/componentes/esqueleto/esqueleto.component';
import { SeletorUsuariosComponent } from '../../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { UsuariosApiService } from '../../usuarios/usuarios-api.service';
import { switchMap } from 'rxjs';
import { Setor, SetoresApiService } from '../../setores/setores-api.service';
import { AcaoModulo, AclApiService, DetalhePerfil, DireitoPerfilModulo, PerfilAcl, RecursoAcl } from './acl-api.service';

/** Seção aberta na barra lateral do perfil: dados gerais, usuários ou o id de um módulo. */
type Secao = 'geral' | 'usuarios' | number;

/** Aba "Perfis" da administração de ACL: lista de perfis à esquerda e o detalhe (Geral, Permissões, Usuários) à direita. */
@Component({
  selector: 'app-perfis-acl',
  imports: [FormsModule, SeletorUsuariosComponent, EsqueletoComponent],
  templateUrl: './perfis-acl.component.html',
})
export class PerfisAclComponent implements OnInit {
  private readonly api = inject(AclApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly autenticacao = inject(AutenticacaoService);
  protected readonly usuariosApi = inject(UsuariosApiService);
  private readonly setoresApi = inject(SetoresApiService);

  /** Módulos cadastrados (a matriz tem uma linha para cada). */
  readonly recursos = input.required<RecursoAcl[]>();
  /** Avisa a tela mãe para recarregar os recursos (o total de perfis de cada módulo muda). */
  readonly alterou = output<void>();
  /** Mensagem para o aviso da tela mãe. */
  readonly mensagem = output<{ texto: string; erro: boolean }>();

  protected readonly perfis = signal<PerfilAcl[] | null>(null);
  protected readonly detalhe = signal<DetalhePerfil | null>(null);
  protected readonly novo = signal(false);
  protected readonly secao = signal<Secao>('geral');
  protected readonly salvando = signal(false);
  protected readonly erro = signal<string | null>(null);

  // Formulário "Geral"
  protected nome = '';
  protected descricao = '';
  protected ativo = true;

  // Módulo aberto na barra lateral: ações marcadas (ainda não salvas)
  protected readonly acoesMarcadas = signal<Set<string>>(new Set());
  protected readonly erroModulo = signal<string | null>(null);

  // Usuários do perfil (aba Usuários)
  protected readonly usuariosDoPerfil = signal<OpcaoUsuario[]>([]);

  // Setores e grupos do perfil (aba Usuários): árvore com marcação independente; marcar o pai marca os filhos
  private readonly todosSetores = signal<Setor[]>([]);
  protected readonly setoresMarcados = signal<Set<number>>(new Set());
  protected buscaSetor = '';
  private readonly buscaSetorSinal = signal('');

  /** Setores ativos em ordem de árvore (pai antes dos filhos, filhos por nome), com o nível de recuo; a busca mostra também os ancestrais dos achados. */
  protected readonly arvoreSetores = computed(() => {
    const ativos = this.todosSetores().filter((s) => s.ativo);
    const idsAtivos = new Set(ativos.map((s) => s.id));
    const filhos = new Map<number | null, Setor[]>();
    for (const s of ativos) {
      const pai = s.setor_pai_id !== null && idsAtivos.has(s.setor_pai_id) ? s.setor_pai_id : null;
      filhos.set(pai, [...(filhos.get(pai) ?? []), s]);
    }
    const termo = this.buscaSetorSinal().trim().toLowerCase();
    const linhas: { setor: Setor; nivel: number }[] = [];
    // Devolve true se o ramo tem algum setor que casa com a busca (para manter os ancestrais visíveis)
    const percorrer = (pai: number | null, nivel: number): boolean => {
      let achou = false;
      for (const s of [...(filhos.get(pai) ?? [])].sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'))) {
        const posicao = linhas.length;
        linhas.push({ setor: s, nivel });
        const filhoAchou = percorrer(s.id, nivel + 1);
        if (!termo || filhoAchou || s.nome.toLowerCase().includes(termo)) achou = true;
        else linhas.splice(posicao, 1);
      }
      return achou;
    };
    percorrer(null, 0);
    return linhas;
  });

  /** Módulo ativos que oferecem ações aos perfis, para a barra lateral (todos aparecem, com ou sem ações no perfil). */
  protected readonly modulos = computed(() => this.recursos().filter((r) => r.ativo && (r.acoes?.length ?? 0) > 0));

  /** Módulo aberto (quando a seção é um id). */
  protected readonly moduloAberto = computed(() => {
    const secao = this.secao();
    return typeof secao === 'number' ? (this.recursos().find((r) => r.id === secao) ?? null) : null;
  });

  /** Quantas ações o perfil já tem no módulo (selo na barra lateral). */
  protected totalNoPerfil(recursoId: number): number {
    return this.detalhe()?.direitos.find((d) => d.recurso_id === recursoId)?.acoes.length ?? 0;
  }

  ngOnInit(): void {
    this.carregar();
    this.setoresApi.listar().subscribe({ next: (l) => this.todosSetores.set(l), error: (e) => this.falhar(e, 'Não foi possível carregar os setores.') });
  }

  protected carregar(): void {
    this.api.listarPerfis().subscribe({
      next: (lista) => this.perfis.set(lista),
      error: (e) => this.falhar(e, 'Não foi possível carregar os perfis.'),
    });
  }

  protected abrir(perfil: PerfilAcl): void {
    this.novo.set(false);
    this.secao.set('geral');
    this.erro.set(null);
    this.api.detalharPerfil(perfil.id).subscribe({
      next: (d) => this.preencher(d),
      error: (e) => this.falhar(e, 'Não foi possível abrir o perfil.'),
    });
  }

  protected criar(): void {
    this.detalhe.set(null);
    this.novo.set(true);
    this.secao.set('geral');
    this.erro.set(null);
    this.nome = '';
    this.descricao = '';
    this.ativo = true;
  }

  private preencher(d: DetalhePerfil): void {
    this.detalhe.set(d);
    this.nome = d.nome;
    this.descricao = d.descricao;
    this.ativo = d.ativo;
    this.setoresMarcados.set(new Set(d.setores.map((x) => x.id)));
    this.usuariosDoPerfil.set(d.usuarios.map((u) => ({ id: u.id, login: u.login, nome_completo: u.nome_completo, cargo: u.cargo ?? '', ativo: u.ativo })));
  }

  protected salvarGeral(): void {
    if (!this.nome.trim()) return this.erro.set('Informe o nome do perfil.');
    this.executar(this.api.gravarPerfil({ nome: this.nome, descricao: this.descricao, ativo: this.ativo }, this.detalhe()?.id), 'Perfil salvo.', (d) => {
      this.novo.set(false);
      this.preencher(d);
    });
  }

  // --- Módulos do perfil ---
  /** Abre a página do módulo na barra lateral, já com as ações que o perfil tem nele marcadas. */
  protected abrirSecao(secao: Secao): void {
    this.secao.set(secao);
    this.erro.set(null);
    this.erroModulo.set(null);
    if (typeof secao === 'number') {
      this.acoesMarcadas.set(new Set(this.detalhe()?.direitos.find((d) => d.recurso_id === secao)?.acoes ?? []));
    }
  }

  protected alternarAcao(codigo: string): void {
    this.acoesMarcadas.update((c) => {
      const novo = new Set(c);
      if (novo.has(codigo)) novo.delete(codigo);
      else novo.add(codigo);
      return novo;
    });
  }

  /** "Marcar/desmarcar todos" do módulo. */
  protected alternarTodas(): void {
    const todas = (this.moduloAberto()?.acoes ?? []).map((a) => a.codigo);
    this.acoesMarcadas.set(todas.every((c) => this.acoesMarcadas().has(c)) ? new Set() : new Set(todas));
  }

  protected todasMarcadas(): boolean {
    const todas = this.moduloAberto()?.acoes ?? [];
    return todas.length > 0 && todas.every((a) => this.acoesMarcadas().has(a.codigo));
  }

  /** Grava o módulo: com ações marcadas, adiciona/atualiza; sem nenhuma, retira o módulo do perfil. */
  protected async salvarModulo(): Promise<void> {
    const perfil = this.detalhe();
    const recurso = this.moduloAberto();
    if (!perfil || !recurso) return;
    const acoes = (recurso.acoes ?? []).map((a) => a.codigo).filter((c) => this.acoesMarcadas().has(c));
    const jaNoPerfil = this.totalNoPerfil(recurso.id) > 0;
    if (!acoes.length && !jaNoPerfil) return this.erroModulo.set('Marque ao menos uma ação.');
    // Primeiro uso do módulo ainda aberto a todos: avisa que ele passa a ser restrito
    if (acoes.length && !jaNoPerfil && recurso.total_regras === 0 && (recurso.total_perfis ?? 0) === 0) {
      const ok = await this.dialogos.confirmar({
        titulo: 'Fechar módulo hoje aberto?',
        mensagem: `Hoje todos os usuários acessam "${recurso.nome}". Ao incluí-lo neste perfil, só quem tiver perfil, regra ou setor contemplado continuará acessando.`,
        rotuloConfirmar: 'Continuar',
        perigo: true,
      });
      if (!ok) return;
    }
    this.salvando.set(true);
    this.erroModulo.set(null);
    const chamada = acoes.length ? this.api.definirModuloPerfil(perfil.id, recurso.id, acoes) : this.api.removerModuloPerfil(perfil.id, recurso.id);
    chamada.subscribe({
      next: (d) => {
        this.salvando.set(false);
        this.preencher(d);
        this.acoesMarcadas.set(new Set(d.direitos.find((x) => x.recurso_id === recurso.id)?.acoes ?? []));
        this.mensagem.emit({ texto: `Permissões de "${recurso.nome}" salvas.`, erro: false });
        this.carregar();
        this.alterou.emit();
      },
      error: (e) => {
        this.salvando.set(false);
        this.erroModulo.set(this.texto(e, 'Não foi possível salvar o módulo.'));
      },
    });
  }

  protected salvarUsuarios(): void {
    const perfil = this.detalhe();
    if (!perfil) return;
    // Usuários primeiro; depois os setores/grupos (cada chamada devolve o detalhe atualizado)
    const gravacao = this.api
      .definirUsuariosPerfil(perfil.id, this.usuariosDoPerfil().map((u) => u.id))
      .pipe(switchMap(() => this.api.definirSetoresPerfil(perfil.id, [...this.setoresMarcados()])));
    this.executar(gravacao, 'Usuários e setores do perfil salvos.', (d) => this.preencher(d));
  }

  protected filtrarSetores(texto: string): void {
    this.buscaSetor = texto;
    this.buscaSetorSinal.set(texto);
  }

  /** Ids do setor e de todos os descendentes dele. */
  private descendentes(id: number): number[] {
    const saida = [id];
    for (const s of this.todosSetores()) if (s.setor_pai_id === id && s.ativo) saida.push(...this.descendentes(s.id));
    return saida;
  }

  /** Marca ou desmarca o setor e, junto, todos os filhos (cada filho ainda pode ser alterado depois, sozinho). */
  protected alternarSetor(id: number): void {
    const novo = new Set(this.setoresMarcados());
    const marcar = !novo.has(id);
    for (const i of this.descendentes(id)) marcar ? novo.add(i) : novo.delete(i);
    this.setoresMarcados.set(novo);
  }

  protected async excluir(): Promise<void> {
    const perfil = this.detalhe();
    if (!perfil) return;
    const ok = await this.dialogos.confirmar({ titulo: 'Excluir perfil', mensagem: `Excluir o perfil "${perfil.nome}"?`, rotuloConfirmar: 'Excluir', perigo: true });
    if (!ok) return;
    this.api.excluirPerfil(perfil.id).subscribe({
      next: () => {
        this.detalhe.set(null);
        this.mensagem.emit({ texto: 'Perfil excluído.', erro: false });
        this.carregar();
        this.alterou.emit();
      },
      error: (e) => this.falhar(e, 'Não foi possível excluir o perfil.'),
    });
  }

  /** O SuperRoot entra como o usuário para testar o que o perfil libera. */
  protected personificar(usuarioId: number): void {
    this.autenticacao.personificar(usuarioId).subscribe({
      next: () => window.location.assign('/'),
      error: (e) => this.falhar(e, 'Não foi possível personificar o usuário.'),
    });
  }

  private executar(chamada: import('rxjs').Observable<DetalhePerfil>, sucesso: string, aoSalvar: (d: DetalhePerfil) => void): void {
    this.salvando.set(true);
    this.erro.set(null);
    chamada.subscribe({
      next: (d) => {
        this.salvando.set(false);
        aoSalvar(d);
        this.mensagem.emit({ texto: sucesso, erro: false });
        this.carregar();
        this.alterou.emit();
      },
      error: (e) => {
        this.salvando.set(false);
        this.erro.set(this.texto(e, 'Não foi possível salvar.'));
      },
    });
  }

  private falhar(erro: unknown, padrao: string): void {
    this.mensagem.emit({ texto: this.texto(erro, padrao), erro: true });
  }

  private texto(erro: unknown, padrao: string): string {
    return erro instanceof HttpErrorResponse && typeof erro.error?.detalhe === 'string' ? erro.error.detalhe : padrao;
  }
}
