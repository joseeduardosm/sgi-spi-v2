// Criado por José Eduardo Santana Martins
// Este arquivo serve para exibir o modal "Abrir Chamado": assunto e descrição, mais os dados do cadastro do usuário.

import { Component, effect, inject, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ChamadoAberto, ChamadoService, DadosSolicitante, LocalChamado } from '../../../core/chamados/chamado.service';
import { erroExibivel } from '../../utilitarios/erros-api';

/** Anexo escolhido ou colado; imagens ganham miniatura. */
interface AnexoEscolhido {
  arquivo: File;
  previa: string | null;
}

const MAXIMO_ANEXOS = 5;
const TAMANHO_MAXIMO = 5 * 1024 * 1024;
const EXTENSOES = ['.png', '.jpg', '.jpeg', '.pdf', '.docx', '.xlsx', '.csv'];

/**
 * Modal de abertura de chamado (aberto pelo item "Abrir Chamado" da barra lateral). O usuário escreve só o assunto e a
 * descrição; nome, setor, superior imediato, e-mail, telefone, celular (se houver) e andar - lado vêm do cadastro e
 * aparecem somente leitura. O chamado é criado no GLPI e termina com a assinatura "Aberto pelo SGI". Em erro, o texto
 * digitado é mantido para tentar de novo.
 */
@Component({
  selector: 'app-abrir-chamado',
  imports: [FormsModule],
  host: { '(document:keydown.escape)': 'fechar()' },
  template: `
    @if (servico.modalAberto()) {
      <div class="fundo-modal" role="presentation" (click)="fechar()"></div>
      <section class="modal-portal modal-chamado" role="dialog" aria-modal="true" aria-labelledby="titulo-abrir-chamado" (paste)="aoColar($event)">
        <header>
          <div><span class="modal-sobretitulo">Chamados</span><h2 id="titulo-abrir-chamado">Abrir chamado</h2></div>
          <button type="button" aria-label="Fechar" [disabled]="enviando()" (click)="fechar()">×</button>
        </header>

        @if (aberto(); as c) {
          <div class="corpo-chamado">
            <p class="aviso-bloco" role="status">Chamado <strong>#{{ c.glpi_id }}</strong> aberto. A equipe de atendimento recebeu o seu pedido.</p>
            @if (c.anexos_com_falha.length) {
              <p class="aviso-bloco erro" role="alert">O chamado foi aberto, mas o GLPI não aceitou: {{ c.anexos_com_falha.join(', ') }}. Envie-os pelo próprio chamado no GLPI.</p>
            }
            <p><a class="link-texto" [href]="c.url" target="_blank" rel="noopener noreferrer">Acompanhar o chamado no GLPI</a></p>
          </div>
          <footer><button type="button" class="acao-primaria" (click)="fechar()">Fechar</button></footer>
        } @else {
          <form (ngSubmit)="enviar()" #formulario="ngForm">
            <div class="corpo-chamado">
              <div class="campo-formulario">
                <label for="chamado-assunto">Assunto *</label>
                <input id="chamado-assunto" name="assunto" class="form-control" maxlength="200" required minlength="3" [(ngModel)]="assunto" [disabled]="enviando()" />
              </div>
              <div class="campo-formulario">
                <label for="chamado-descricao">Descrição do problema *</label>
                <textarea id="chamado-descricao" name="descricao" class="form-control" rows="9" maxlength="5000" required minlength="10"
                          placeholder="Conte o que está acontecendo, onde e desde quando." [(ngModel)]="descricao" [disabled]="enviando()"></textarea>
                <small class="dica-formulario">{{ descricao.length }} / 5000</small>
              </div>

              <div class="campo-formulario">
                <label for="chamado-local">Local do problema *</label>
                <select id="chamado-local" name="local" class="form-control" required [(ngModel)]="localId" [disabled]="enviando()">
                  <option [ngValue]="null" disabled>{{ locais().length ? 'Selecione o local…' : 'Carregando os locais…' }}</option>
                  @for (l of locais(); track l.id) { <option [ngValue]="l.id">{{ l.nome }}</option> }
                </select>
              </div>

              <p class="secao-formulario">Anexos (opcional)</p>
              <div class="anexos-chamado">
                @for (a of anexos(); track a.arquivo) {
                  <figure>
                    @if (a.previa) { <img [src]="a.previa" [alt]="a.arquivo.name" /> } @else { <span class="arquivo-anexo" aria-hidden="true">{{ a.arquivo.name.split('.').pop() }}</span> }
                    <figcaption>{{ a.arquivo.name }}</figcaption>
                    <button type="button" class="link-arquivo" [attr.aria-label]="'Remover ' + a.arquivo.name" [disabled]="enviando()" (click)="remover($index)">remover</button>
                  </figure>
                }
                @if (anexos().length < maximoAnexos) {
                  <input #campoAnexo type="file" [accept]="aceitos" multiple hidden (change)="aoEscolher(campoAnexo)" />
                  <button type="button" class="adicionar-print" [disabled]="enviando()" (click)="campoAnexo.click()">+ Anexar arquivo<small>ou cole uma imagem com Ctrl+V</small></button>
                }
              </div>
              <small class="dica-formulario">Até {{ maximoAnexos }} arquivos de 5 MB: PNG, JPG, PDF, Word (.docx), Excel (.xlsx) ou CSV.</small>

              <p class="secao-formulario">Seus dados (do cadastro)</p>
              @if (dados(); as d) {
                <dl class="dados-chamado">
                  <div><dt>Nome</dt><dd>{{ d.nome }}</dd></div>
                  <div><dt>Setor</dt><dd>{{ d.setor || '—' }}@if (temp(d, 'departamento')) { <small class="temporario">temporário</small> }</dd></div>
                  <div><dt>Superior imediato</dt><dd>{{ d.superior_imediato || '—' }}@if (temp(d, 'gestor_id')) { <small class="temporario">temporário</small> }</dd></div>
                  <div><dt>E-mail</dt><dd>{{ d.email || '—' }}@if (temp(d, 'email')) { <small class="temporario">temporário</small> }</dd></div>
                  <div><dt>Telefone</dt><dd>{{ d.telefone || '—' }}@if (temp(d, 'ramal')) { <small class="temporario">temporário</small> }</dd></div>
                  @if (d.celular) { <div><dt>Celular</dt><dd>{{ d.celular }}</dd></div> }
                  <div><dt>Andar - Lado</dt><dd>{{ d.andar_lado || '—' }}@if (temp(d, 'andar') || temp(d, 'predio')) { <small class="temporario">temporário</small> }</dd></div>
                </dl>
                @if (d.aguardando_validacao?.length) {
                  <p class="dica-formulario">Os dados marcados como <em>temporário</em> são os que você informou e ainda aguardam validação da CGP; seguem no chamado assim mesmo.</p>
                }
              } @else {
                <p class="dica-formulario">Carregando seus dados…</p>
              }

              @if (erro()) { <p class="aviso-bloco erro" role="alert">{{ erro() }}</p> }
            </div>
            <footer>
              <button type="button" class="acao-secundaria" [disabled]="enviando()" (click)="fechar()">Cancelar</button>
              <button type="submit" class="acao-primaria" [disabled]="enviando() || formulario.invalid || !assunto.trim() || !descricao.trim() || localId === null">
                {{ enviando() ? 'Enviando…' : 'Abrir chamado' }}
              </button>
            </footer>
          </form>
        }
      </section>
    }
  `,
})
export class AbrirChamadoComponent {
  protected readonly servico = inject(ChamadoService);

  protected assunto = '';
  protected descricao = '';
  protected localId: number | null = null;
  protected readonly locais = signal<LocalChamado[]>([]);
  protected readonly dados = signal<DadosSolicitante | null>(null);
  protected readonly enviando = signal(false);
  protected readonly erro = signal<string | null>(null);
  protected readonly aberto = signal<ChamadoAberto | null>(null);
  protected readonly anexos = signal<AnexoEscolhido[]>([]);
  protected readonly maximoAnexos = MAXIMO_ANEXOS;
  protected readonly aceitos = EXTENSOES.join(',');

  constructor() {
    // A cada abertura do modal: formulário limpo e dados do cadastro recarregados (podem ter mudado no perfil)
    effect(() => {
      if (!this.servico.modalAberto()) return;
      this.assunto = this.descricao = '';
      this.localId = null;
      // `untracked`: limpar os anexos lê e escreve o sinal deles, e isso não pode reabrir o formulário a cada anexo novo
      untracked(() => this.limparAnexos());
      this.erro.set(null);
      this.aberto.set(null);
      this.dados.set(null);
      this.locais.set([]);
      this.servico.solicitante().subscribe({ next: (d) => { this.dados.set(d); this.sugerirLocal(); }, error: (e) => this.erro.set(this.textoErro(e)) });
      this.servico.locais().subscribe({ next: (r) => { this.locais.set(r.itens); this.sugerirLocal(); }, error: (e) => this.erro.set(this.textoErro(e)) });
    });
  }

  protected enviar(): void {
    if (this.enviando()) return;
    this.enviando.set(true);
    this.erro.set(null);
    this.servico.abrir(this.assunto.trim(), this.descricao.trim(), this.localId!, this.anexos().map((a) => a.arquivo)).subscribe({
      next: (chamado) => {
        this.enviando.set(false);
        this.aberto.set(chamado);
      },
      error: (e) => {
        // O texto digitado fica no formulário
        this.enviando.set(false);
        this.erro.set(this.textoErro(e));
      },
    });
  }

  /** Sugere o local pelo andar e lado do cadastro (ex.: "5º andar - B" → "05º Andar > Lado B"), sem sobrescrever uma escolha já feita. */
  private sugerirLocal(): void {
    const d = this.dados();
    if (this.localId !== null || !d || !this.locais().length) return;
    const m = /^(\d+)º andar(?: - (\w+))?$/i.exec(d.andar_lado.trim());
    if (!m) return;
    const alvo = `${m[1].padStart(2, '0')}º Andar${m[2] ? ' > Lado ' + m[2].toUpperCase() : ''}`;
    this.localId = this.locais().find((l) => l.nome === alvo)?.id ?? null;
  }

  /** O campo do cadastro está aguardando validação (valor temporário)? */
  protected temp(d: DadosSolicitante, campo: string): boolean {
    // `?.`: uma API em versão anterior não manda este campo, e a lista de dados não pode parar de ser desenhada
    return d.aguardando_validacao?.includes(campo) ?? false;
  }

  protected aoEscolher(campo: HTMLInputElement): void {
    this.incluir(Array.from(campo.files ?? []));
    campo.value = '';
  }

  /** Ctrl+V com imagem na área de transferência vira anexo (como em Melhorias); colar texto segue normal. */
  protected aoColar(evento: ClipboardEvent): void {
    const imagens = Array.from(evento.clipboardData?.items ?? []).filter((i) => i.kind === 'file' && i.type.startsWith('image/'))
      .map((i) => i.getAsFile()).filter((f): f is File => !!f)
      .map((f, i) => new File([f], `imagem-colada-${Date.now()}-${i + 1}.png`, { type: f.type }));
    if (!imagens.length) return;
    evento.preventDefault();
    this.incluir(imagens);
  }

  protected remover(indice: number): void {
    const removido = this.anexos()[indice];
    if (removido?.previa) URL.revokeObjectURL(removido.previa);
    this.anexos.update((l) => l.filter((_, i) => i !== indice));
  }

  /** Confere extensão, tamanho e quantidade antes de aceitar (a API confere de novo, pelo conteúdo). */
  private incluir(arquivos: File[]): void {
    this.erro.set(null);
    const validos = arquivos.filter((a) => {
      if (!EXTENSOES.some((e) => a.name.toLowerCase().endsWith(e))) { this.erro.set(`Formato não aceito (${a.name}): envie PNG, JPG, PDF, Word (.docx), Excel (.xlsx) ou CSV.`); return false; }
      if (a.size > TAMANHO_MAXIMO) { this.erro.set(`O arquivo ${a.name} passa de 5 MB.`); return false; }
      return a.size > 0;
    });
    const livres = MAXIMO_ANEXOS - this.anexos().length;
    if (validos.length > livres) this.erro.set(`No máximo ${MAXIMO_ANEXOS} anexos por chamado.`);
    this.anexos.update((l) => [...l, ...validos.slice(0, livres).map((arquivo) => ({ arquivo, previa: arquivo.type.startsWith('image/') ? URL.createObjectURL(arquivo) : null }))]);
  }

  private limparAnexos(): void {
    for (const a of this.anexos()) if (a.previa) URL.revokeObjectURL(a.previa);
    this.anexos.set([]);
  }

  /** Mensagem da API, com o código de correlação (para o suporte) quando houver. */
  private textoErro(e: unknown): string {
    const { mensagem, correlacao } = erroExibivel(e);
    return correlacao ? `${mensagem} (código para o suporte: ${correlacao})` : mensagem;
  }

  protected fechar(): void {
    if (!this.enviando()) this.servico.fecharModal();
  }
}
