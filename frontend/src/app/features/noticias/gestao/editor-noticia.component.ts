// Criado por José Eduardo Santana Martins
// Este arquivo serve para escrever e revisar uma notícia: texto, capa 2:1, publicação, aviso, anexos e o fluxo de aprovação.

import { DatePipe } from '@angular/common';
import { Component, computed, DestroyRef, inject, OnInit, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { concatMap, Observable, of } from 'rxjs';

import { OpcaoUsuario } from '../../../core/modelos/usuario.model';
import { SeletorUsuariosComponent } from '../../../shared/componentes/seletor-usuarios/seletor-usuarios.component';
import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { NoticiasApiService } from '../noticias-api.service';
import {
  Categoria, Ciencias, deCampo, GravacaoNoticia, ModoCapa, NoticiaGestao, paraCampo, Revisao, ROTULOS_SITUACAO, SetorResumo, tamanhoLegivel,
} from '../noticias.models';
import { CabecalhoNoticiasComponent } from './cabecalho-noticias.component';
import { EditorTextoComponent } from './editor-texto.component';
import { ImagemAutenticadaDirective } from './imagem-autenticada.directive';
import { Recorte, RecorteCapaComponent } from './recorte-capa.component';

@Component({
  selector: 'app-editor-noticia',
  imports: [FormsModule, RouterLink, DatePipe, SeletorUsuariosComponent, CabecalhoNoticiasComponent, EditorTextoComponent,
            ImagemAutenticadaDirective, RecorteCapaComponent],
  templateUrl: './editor-noticia.component.html',
})
export class EditorNoticiaComponent implements OnInit {
  protected readonly api = inject(NoticiasApiService);
  private readonly dialogos = inject(DialogosService);
  private readonly rota = inject(ActivatedRoute);
  private readonly roteador = inject(Router);
  private readonly destruir = inject(DestroyRef);
  private readonly editorTexto = viewChild(EditorTextoComponent);
  protected readonly rotulos = ROTULOS_SITUACAO;
  protected readonly tamanho = tamanhoLegivel;

  protected readonly noticia = signal<NoticiaGestao | null>(null);
  protected readonly carregando = signal(true);
  protected readonly categorias = signal<Categoria[]>([]);
  protected readonly setores = signal<SetorResumo[]>([]);

  // Campos do formulário
  protected titulo = '';
  protected linhaFina = '';
  protected corpo = '';
  protected categoriaId: number | null = null;
  protected publicacao: 'imediata' | 'agendada' = 'imediata';
  protected publicarEm = '';
  protected destaqueAte = '';
  protected fixada = false;
  protected exigeCiencia = false;
  protected readonly setoresAviso = signal<Set<number>>(new Set());
  protected usuariosAviso: OpcaoUsuario[] = [];
  protected capaAlt = '';

  // Capa: arquivo escolhido (ainda não enviado), modo e recorte
  protected readonly capaLocal = signal<string | null>(null);
  private arquivoCapa: File | null = null;
  protected readonly modoCapa = signal<ModoCapa>('recortar');
  private recorte: Recorte | null = null;
  private capaAlterada = false;

  // Janelas e painéis
  protected readonly janela = signal<'aprovar' | 'devolver' | 'previa' | null>(null);
  protected aprovarEm = '';
  protected motivo = '';
  protected readonly revisoes = signal<Revisao[] | null>(null);
  protected readonly ciencias = signal<Ciencias | null>(null);

  protected readonly nova = computed(() => !this.noticia());
  protected readonly editavel = computed(() => this.nova() || !!this.noticia()?.acoes.includes('editar'));
  protected readonly pode = (acao: string) => !!this.noticia()?.acoes.includes(acao);
  protected readonly setoresFiltrados = computed(() => {
    const termo = this.filtroSetoresSinal().trim().toLowerCase();
    return this.setores().filter((s) => !termo || s.nome.toLowerCase().includes(termo) || this.setoresAviso().has(s.id));
  });
  protected readonly filtroSetoresSinal = signal('');
  /** URL da imagem para o recorte: a escolhida agora ou a original já enviada (via blob autenticado). */
  protected readonly capaOriginal = signal<string | null>(null);

  ngOnInit(): void {
    this.api.categorias().subscribe({ next: (c) => this.categorias.set(c.filter((x) => x.ativa)), error: () => undefined });
    this.api.setores().subscribe({ next: (s) => this.setores.set(s), error: () => undefined });
    this.rota.paramMap.pipe(takeUntilDestroyed(this.destruir)).subscribe((p) => {
      const id = p.get('id');
      if (!id || id === 'nova') { this.carregando.set(false); return; }
      this.api.detalhe(id).subscribe({
        next: (n) => { this.aplicar(n); this.carregando.set(false); },
        error: (e) => { this.carregando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível abrir a notícia'); },
      });
    });
  }

  private aplicar(n: NoticiaGestao): void {
    this.noticia.set(n);
    this.titulo = n.titulo; this.linhaFina = n.linha_fina; this.corpo = n.corpo_html; this.categoriaId = n.categoria_id;
    this.publicacao = n.publicar_em && (n.situacao !== 'aprovada' || !n.visivel) ? 'agendada' : 'imediata';
    this.publicarEm = paraCampo(n.publicar_em); this.destaqueAte = paraCampo(n.destaque_ate);
    this.fixada = n.fixada; this.exigeCiencia = n.exige_ciencia; this.capaAlt = n.capa_alt;
    this.setoresAviso.set(new Set(n.setores_aviso.map((s) => s.id)));
    this.usuariosAviso = n.usuarios_aviso.map((u) => ({ id: u.id, login: u.login, nome_completo: u.nome, cargo: '', ativo: true }));
    this.modoCapa.set(n.capa_modo); this.recorte = n.capa_recorte; this.capaAlterada = false; this.arquivoCapa = null;
    this.editorTexto()?.definir(n.corpo_html);
    if (this.capaLocal()) { URL.revokeObjectURL(this.capaLocal()!); this.capaLocal.set(null); }
    if (n.capa_original) this.api.blob(n.capa_original).subscribe({ next: (b) => this.capaOriginal.set(b), error: () => undefined });
    else this.capaOriginal.set(null);
    document.title = `${n.titulo} | Notícias | SGI SPI`;
  }

  protected recorteInicial(): Recorte | null {
    return this.capaLocal() ? null : this.noticia()?.capa_recorte ?? null;
  }

  // --- Capa -----------------------------------------------------------------------------------------

  protected escolherCapa(evento: Event): void {
    const campo = evento.target as HTMLInputElement;
    const arquivo = campo.files?.[0];
    campo.value = '';
    if (!arquivo) return;
    if (!/^image\/(jpeg|png|webp)$/.test(arquivo.type)) { this.dialogos.avisar('Formato não aceito', 'Envie a capa em JPG, PNG ou WebP.'); return; }
    if (arquivo.size > 15 * 1024 * 1024) { this.dialogos.avisar('Imagem grande demais', 'A capa pode ter até 15 MB.'); return; }
    if (this.capaLocal()) URL.revokeObjectURL(this.capaLocal()!);
    this.arquivoCapa = arquivo;
    this.capaLocal.set(URL.createObjectURL(arquivo));
    this.recorte = null;
    this.capaAlterada = true;
    if (!this.capaAlt) this.capaAlt = this.titulo;
  }

  protected aoRecortar(r: Recorte | null): void {
    this.recorte = r;
    if (this.capaLocal() || this.noticia()?.capa_original) this.capaAlterada = true;
  }

  protected trocarModo(m: ModoCapa): void {
    this.modoCapa.set(m);
    this.capaAlterada = true;
  }

  // --- Gravação e fluxo -----------------------------------------------------------------------------

  private dados(): GravacaoNoticia {
    return {
      titulo: this.titulo.trim(), linha_fina: this.linhaFina.trim(), corpo_html: this.corpo, categoria_id: this.categoriaId,
      publicar_em: this.publicacao === 'agendada' ? deCampo(this.publicarEm) : null, destaque_ate: deCampo(this.destaqueAte),
      fixada: this.fixada, exige_ciencia: this.exigeCiencia, usuarios_aviso: this.usuariosAviso.map((u) => u.id),
      setores_aviso: [...this.setoresAviso()], capa_alt: this.capaAlt.trim(), versao: this.noticia()?.versao,
    };
  }

  /** Salva o texto e, se a capa mudou, envia a imagem e o recorte. */
  private gravar(): Observable<NoticiaGestao> {
    if (!this.titulo.trim()) throw new Error('titulo');
    if (this.publicacao === 'agendada' && !this.publicarEm) throw new Error('data');
    const atual = this.noticia();
    const salvar$ = !this.editavel() && atual ? of(atual) : atual ? this.api.salvar(atual.id, this.dados()) : this.api.criar(this.dados());
    return salvar$.pipe(concatMap((n) => (this.capaAlterada ? this.api.capa(n.id, this.modoCapa(), this.recorte, this.arquivoCapa) : of(n))));
  }

  private validar(): boolean {
    if (!this.titulo.trim()) { this.dialogos.avisar('Falta o título', 'Informe o título da notícia.'); return false; }
    if (this.publicacao === 'agendada' && !this.publicarEm) {
      if (this.campoIncompleto('nt-publicar')) { this.dialogos.avisar('Falta o horário', 'Preencha também o horário em "Publicar em" (hora e minuto).'); return false; }
      this.dialogos.avisar('Falta a data', 'Informe quando a notícia deve ser publicada.'); return false;
    }
    if (!this.destaqueAte && this.campoIncompleto('nt-destaque')) { this.dialogos.avisar('Falta o horário', 'Preencha também o horário em "Tirar do slider em" (hora e minuto) ou limpe o campo.'); return false; }
    return true;
  }

  /** Campo datetime-local com data mas sem hora (ou o inverso): o navegador entrega valor vazio ao formulário. */
  private campoIncompleto(id: string): boolean {
    const campo = document.getElementById(id) as HTMLInputElement | null;
    return !!campo && campo.validity.badInput;
  }

  protected salvar(): void {
    if (!this.validar()) return;
    const eraNova = this.nova();
    this.dialogos.executar(this.gravar(), 'Salvando a notícia…').subscribe({
      next: (n) => { this.aplicar(n); if (eraNova) void this.roteador.navigate(['/noticias/gestao', n.id], { replaceUrl: true }); },
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  protected enviar(): void {
    if (!this.validar()) return;
    const eraNova = this.nova();
    this.dialogos.executar(this.gravar().pipe(concatMap((n) => this.api.acao(n.id, 'enviar-revisao'))), 'Enviando para aprovação…').subscribe({
      next: (n) => {
        this.aplicar(n);
        if (eraNova) void this.roteador.navigate(['/noticias/gestao', n.id], { replaceUrl: true });
        this.dialogos.avisar('Enviada para aprovação', 'Os aprovadores foram avisados por e-mail e pela caixa de mensagens. Você será avisado quando a notícia for aprovada ou devolvida.');
      },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível enviar'),
    });
  }

  protected abrirAprovacao(): void {
    if (!this.validar()) return;
    this.aprovarEm = this.publicacao === 'agendada' ? this.publicarEm : '';
    this.janela.set('aprovar');
  }

  protected aprovar(): void {
    const eraNova = this.nova();
    // Data vazia na janela = publicar agora (mesmo que o redator tenha pedido outra data)
    const quando = deCampo(this.aprovarEm) ?? new Date().toISOString();
    if (!this.aprovarEm && this.editavel()) this.publicacao = 'imediata';
    const operacao = this.gravar().pipe(concatMap((n) => this.api.aprovar(n.id, quando)));
    this.dialogos.executar(operacao, 'Aprovando…').subscribe({
      next: (n) => { this.janela.set(null); this.aplicar(n); if (eraNova) void this.roteador.navigate(['/noticias/gestao', n.id], { replaceUrl: true }); },
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível aprovar'),
    });
  }

  protected devolver(): void {
    const n = this.noticia()!;
    this.dialogos.executar(this.api.devolver(n.id, this.motivo.trim())).subscribe({
      next: (x) => { this.janela.set(null); this.motivo = ''; this.aplicar(x); },
      error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  protected async arquivar(arquivar: boolean): Promise<void> {
    const n = this.noticia()!;
    if (arquivar && !(await this.dialogos.confirmar({ titulo: 'Arquivar notícia', mensagem: 'Ela sai do portal (pode ser desarquivada depois).', rotuloConfirmar: 'Arquivar' }))) return;
    this.dialogos.executar(this.api.acao(n.id, arquivar ? 'arquivar' : 'desarquivar')).subscribe({
      next: (x) => this.aplicar(x), error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  protected async excluir(): Promise<void> {
    const n = this.noticia()!;
    if (!(await this.dialogos.confirmar({ titulo: 'Excluir notícia', mensagem: `"${n.titulo}" e o histórico serão apagados. Não há como desfazer.`, rotuloConfirmar: 'Excluir', segundos: 3 }))) return;
    this.dialogos.executar(this.api.excluir(n.id)).subscribe({
      next: () => void this.roteador.navigate(['/noticias/gestao']), error: (e) => this.dialogos.mostrarErro(e),
    });
  }

  // --- Anexos, histórico e ciência ------------------------------------------------------------------

  protected anexar(evento: Event): void {
    const campo = evento.target as HTMLInputElement;
    const arquivos = Array.from(campo.files ?? []);
    campo.value = '';
    const n = this.noticia();
    if (!n || !arquivos.length) return;
    let fluxo: Observable<NoticiaGestao> = of(n);
    for (const a of arquivos) fluxo = fluxo.pipe(concatMap(() => this.api.anexar(n.id, a)));
    this.dialogos.executar(fluxo, 'Enviando anexos…').subscribe({ next: (x) => this.noticia.set(x), error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected removerAnexo(anexoId: string): void {
    const n = this.noticia()!;
    this.api.removerAnexo(n.id, anexoId).subscribe({ next: (x) => this.noticia.set(x), error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected abrirAnexo(url: string): void {
    this.api.blob(url).subscribe({ next: (b) => window.open(b, '_blank'), error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected verHistorico(): void {
    this.api.revisoes(this.noticia()!.id).subscribe({ next: (r) => this.revisoes.set(r), error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected verCiencias(): void {
    this.api.ciencias(this.noticia()!.id).subscribe({ next: (c) => this.ciencias.set(c), error: (e) => this.dialogos.mostrarErro(e) });
  }

  protected alternarSetor(id: number): void {
    this.setoresAviso.update((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  }
}
