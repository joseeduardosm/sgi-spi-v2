// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela de uma admissão: a trilha (chamado, documentos, resolução, Protocolo, publicação, e-mail, posse, entrada no SGI) e a ação de cada etapa.

import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { CampoArquivoComponent } from '../../shared/componentes/campo-arquivo/campo-arquivo.component';
import { EsqueletoComponent } from '../../shared/componentes/esqueleto/esqueleto.component';
import { EditorRicoComponent } from '../contratacoes/editor-rico.component';
import { ImagemAutenticadaDirective } from '../noticias/gestao/imagem-autenticada.directive';
import { EstadoEtapa, EtapaTrilha, TrilhaEtapasComponent } from '../../shared/componentes/trilha-etapas/trilha-etapas.component';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRhComponent } from './cabecalho-rh.component';
import { RhAdmissaoApiService } from './rh-admissao-api.service';
import { ChaveEtapa, DocumentoAdmissao, LeituraAdmissao, TipoProtocoloResolucao } from './rh-admissao.models';
import { Observable } from 'rxjs';

const ESTADO: Record<string, EstadoEtapa> = { feita: 'concluida', atual: 'atual', pendente: 'aguardando' };

/** Uma admissão: a trilha no topo e, abaixo, um cartão por etapa (a atual com a ação; as feitas com o resumo; as seguintes bloqueadas). */
@Component({
  selector: 'app-admissao',
  imports: [FormsModule, DatePipe, RouterLink, CabecalhoRhComponent, CampoArquivoComponent, EsqueletoComponent, TrilhaEtapasComponent, EditorRicoComponent, ImagemAutenticadaDirective],
  template: `
    <app-cabecalho-rh [titulo]="a()?.nome ?? 'Admissão'" [trilha]="['Admissões', a()?.nome ?? '']" descricao="Cada etapa só abre depois da anterior." />

    @if (a(); as x) {
      <section class="cartao-dados" aria-label="Andamento da admissão">
        <header>
          <div><h2>{{ x.cargo_rotulo }}</h2><small>{{ x.setor_nome }} · login proposto <span class="texto-codigo">{{ x.login_proposto }}</span></small></div>
          <div class="acoes-formulario">
            <a class="acao-secundaria acao-pequena" [routerLink]="['/rh/pre-cadastros', x.ficha_id]">Ver ficha</a>
            @if (x.status === 'andamento') { <button type="button" class="acao-recusar acao-pequena" (click)="cancelar()">Cancelar admissão</button> }
          </div>
        </header>
        <div class="corpo">
          <app-trilha-etapas [etapas]="trilha()" ariaLabel="Etapas da admissão" />
          @if (x.status === 'cancelada') { <p><span class="selo-origem">Cancelada</span></p> }
          @if (x.status === 'concluida') { <p><span class="selo-situacao">Concluída em {{ x.concluida_em | date: 'dd/MM/yyyy HH:mm' }}</span></p> }
        </div>
      </section>

      <div class="parametros-rh">
        <div class="sem-borda">

          <!-- 1. Formulário de nomeação do GLPI -->
          <section class="cartao-dados" [class.etapa-bloqueada]="bloqueada('chamado')" aria-labelledby="et-chamado">
            <header><div><h2 id="et-chamado">1. Formulário de nomeação no GLPI</h2><small>O SGI preenche o formulário "CGP - Nomeações" com os dados da ficha; o próprio formulário abre os chamados e dispara os e-mails (rede, e-mail, SEI, Compras SP, equipamento, estação, crachá, telefone e mobiliário).</small></div></header>
            <div class="corpo">
              @if (x.status === 'andamento') {
                <div class="bloco-foto">
                  @if (x.tem_foto) { <img class="foto-admissao" [appImagemAutenticada]="urlFoto()" alt="Foto da pessoa" /> } @else { <span class="foto-admissao vazia" aria-hidden="true">Sem foto</span> }
                  <div class="acoes-foto">
                    <strong>Foto da pessoa (opcional)</strong>
                    <small class="ajuda">{{ x.etapas[0].estado === 'feita' ? 'O formulário já foi enviado ao GLPI: trocar a foto atualiza só a intranet.' : 'Vai no formulário do GLPI e, quando a conta existir, vira a foto da pessoa na intranet (Diretório).' }} PNG ou JPG, até 5 MB.</small>
                    <div class="acoes-formulario" style="justify-content: flex-start">
                      <label class="acao-secundaria acao-pequena seletor-arquivo">{{ x.tem_foto ? 'Trocar a foto' : 'Escolher a foto' }}
                        <input type="file" accept="image/png,image/jpeg,.png,.jpg,.jpeg" (change)="escolherFoto($any($event.target))" /></label>
                      @if (x.tem_foto) { <button type="button" class="acao-secundaria acao-pequena" (click)="executar(api.removerFoto(x.id))">Remover</button> }
                    </div>
                  </div>
                </div>
              }
              @if (x.etapas[0].estado === 'feita') {
                <p class="resumo-chamado">
                  <span class="selo-situacao">Formulário enviado</span>
                  em {{ x.etapas[0].em | date: 'dd/MM/yyyy HH:mm' }} · {{ x.chamado_links.length }} chamado(s) aberto(s) pelo GLPI · login de rede proposto <span class="texto-codigo">{{ x.login_proposto }}</span>
                </p>
                <div class="tabela-gestao-envoltorio">
                  <table class="tabela-gestao">
                    <thead><tr><th>Serviço</th><th>Pedido</th><th>Chamado no GLPI</th></tr></thead>
                    <tbody>
                      @for (l of linhasChamado(x); track l.chave) {
                        <tr>
                          <td><strong>{{ l.servico }}</strong></td>
                          <td><span [class]="l.pedido ? 'selo-situacao' : 'selo-situacao inativo'">{{ l.pedido ? 'Sim' : 'Não' }}</span></td>
                          <td>
                            @if (l.link) { <a class="acao-secundaria acao-pequena" [href]="l.link.url" target="_blank" rel="noopener" [title]="l.link.texto">Chamado #{{ l.numero }}</a> }
                            @else if (l.pedido) { <small>Chamado não identificado</small> }
                            @else { <small>—</small> }
                          </td>
                        </tr>
                      }
                    </tbody>
                  </table>
                </div>
                @if (chamadosSemServico(x).length) {
                  <p class="dica-formulario">Outros itens criados pelo formulário:
                    @for (l of chamadosSemServico(x); track l.url) { <a [href]="l.url" target="_blank" rel="noopener">{{ l.texto }}</a>{{ $last ? '' : ', ' }} }</p>
                }
              } @else if (!bloqueada('chamado')) {
                <div class="opcoes-parametros">
                  @for (s of solicitacoesLista(); track s[0]) {
                    <label class="opcao"><input type="checkbox" [name]="'sol-' + s[0]" [(ngModel)]="solicitar[s[0]]" /><span><strong>{{ s[1] }}</strong></span></label>
                  }
                </div>
                <div class="grade-parametros" style="margin-top: 14px">
                  <div class="campo"><label for="chamado-espelho">Usuário espelho (login)</label><input id="chamado-espelho" name="espelho" maxlength="100" placeholder="Opcional: quem tem o acesso que servirá de modelo" [(ngModel)]="usuarioEspelho" /></div>
                </div>
                <div class="campo" style="margin-top: 14px"><label for="chamado-obs">Observações adicionais para a TI</label><textarea id="chamado-obs" name="obs" rows="3" maxlength="4000" [(ngModel)]="observacoesChamado"></textarea>
                  <small class="ajuda">O login proposto e o e-mail pessoal da ficha já vão junto.</small></div>
                <div class="acoes-formulario" style="margin-top: 12px"><button type="button" class="acao-primaria" [class.carregando]="ocupado()" (click)="abrirChamado()">Enviar o formulário ao GLPI</button></div>
              }
            </div>
          </section>

          <!-- 2. Documentos -->
          <section class="cartao-dados" [class.etapa-bloqueada]="bloqueada('documentos')" aria-labelledby="et-documentos">
            <header><div><h2 id="et-documentos">2. Documentos</h2><small>O envio ao Portal de Indicações (sistema externo) é feito lá: aqui se registra a data e se anexa o comprovante.</small></div></header>
            <div class="corpo">
              @if (!x.documentos.length) {
                <p class="dica-formulario">Nenhum documento no checklist deste tipo de cargo (cadastre em RH &gt; Modelos &gt; Checklists). Dá para incluir documentos só nesta admissão.</p>
              } @else if (!bloqueada('documentos')) {
                <div class="tabela-gestao-envoltorio">
                  <table class="tabela-gestao">
                    <thead><tr><th>Documento</th><th>Envio</th><th class="coluna-acoes">Ações</th></tr></thead>
                    <tbody>
                      @for (d of x.documentos; track d.id) {
                        <tr>
                          <td><strong>{{ d.descricao }}</strong>@if (!d.obrigatorio) { <small>opcional</small> }
                            @if (d.incluido_no_processo) {
                              <span class="selo-situacao info">Incluído nesta admissão</span>
                              @if (d.detalhe) { <small>{{ d.detalhe }}</small> }
                              <small>Incluído por {{ d.incluido_por_nome }}@if (d.incluido_em) { em {{ d.incluido_em | date: 'dd/MM/yyyy HH:mm' }} }</small>
                            }</td>
                          <td>@if (d.enviado_em) { <span class="selo-situacao">Enviado em {{ dataBr(d.enviado_em) }}</span><small>{{ d.enviado_por_nome }}@if (d.observacao) { · {{ d.observacao }} }</small> } @else { <span class="selo-situacao alerta">Pendente</span> }</td>
                          <td class="coluna-acoes"><div class="acoes-linha">
                            @if (d.tem_arquivo) { <button type="button" class="acao-secundaria acao-pequena" (click)="arquivoDocumento(d)">Arquivo</button> }
                            @if (d.tem_comprovante) { <button type="button" class="acao-secundaria acao-pequena" (click)="comprovante(d)">Comprovante</button> }
                            @if (x.etapa === 'documentos') {
                              @if (d.enviado_em) { <button type="button" class="acao-secundaria acao-pequena" (click)="desfazerDocumento(d)">Desfazer</button> }
                              @else { <button type="button" class="acao-secundaria acao-pequena" (click)="abrirDocumento(d)">Registrar envio</button> }
                              @if (d.incluido_no_processo) { <button type="button" class="acao-perigo acao-pequena" (click)="excluirDocumentoIncluido(d)">Excluir</button> }
                            }
                          </div></td>
                        </tr>
                        @if (documentoAberto() === d.id) {
                          <tr><td colspan="3">
                            <div class="grade-parametros">
                              <div class="campo"><label [for]="'doc-data-' + d.id">Data do envio</label><input [id]="'doc-data-' + d.id" type="date" [(ngModel)]="docData" [max]="hoje" /></div>
                              <div class="campo"><label [for]="'doc-obs-' + d.id">Observação</label><input [id]="'doc-obs-' + d.id" maxlength="500" [(ngModel)]="docObs" /></div>
                              <div class="campo"><span class="rotulo">Comprovante (opcional)</span>
                                <div class="escolha-comprovante">
                                  <label class="acao-secundaria acao-pequena seletor-arquivo">Escolher arquivo
                                    <input type="file" accept=".pdf,.png,.jpg,.jpeg,.docx,.xlsx,.txt" (change)="docArquivo = $any($event.target).files?.[0] ?? null" /></label>
                                  <small class="ajuda">{{ docArquivo ? docArquivo.name : 'Nenhum arquivo escolhido' }}</small>
                                </div></div>
                            </div>
                            <div class="acoes-formulario" style="margin-top: 12px">
                              <button type="button" class="acao-secundaria acao-pequena" (click)="documentoAberto.set(null)">Cancelar</button>
                              <button type="button" class="acao-primaria acao-pequena" [disabled]="!docData" (click)="registrarDocumento(d)">Registrar</button>
                            </div>
                          </td></tr>
                        }
                      }
                    </tbody>
                  </table>
                </div>
              }
              <!-- Checklist "a partir de…": documento fora do checklist do cargo, só nesta admissão (nunca obrigatório) -->
              @if (x.etapa === 'documentos' && incluindoDocumento()) {
                <div class="grade-parametros" style="margin-top: 12px">
                  <div class="campo"><label for="incluir-doc-nome">Nome do documento *</label><input id="incluir-doc-nome" maxlength="300" [(ngModel)]="novoDocNome" /></div>
                  <div class="campo"><label for="incluir-doc-descricao">Descrição</label><input id="incluir-doc-descricao" maxlength="1000" [(ngModel)]="novoDocDescricao" /></div>
                  <div class="campo"><span class="rotulo">Arquivo (PDF) *</span>
                    <div class="escolha-comprovante">
                      <label class="acao-secundaria acao-pequena seletor-arquivo">Escolher arquivo
                        <input type="file" accept=".pdf,application/pdf" (change)="novoDocArquivo = $any($event.target).files?.[0] ?? null" /></label>
                      <small class="ajuda">{{ novoDocArquivo ? novoDocArquivo.name : 'Nenhum arquivo escolhido' }}</small>
                    </div></div>
                </div>
                <p class="dica-formulario">O documento entra só nesta admissão, como opcional (não trava a conclusão). O checklist do cargo não muda.</p>
                <div class="acoes-formulario">
                  <button type="button" class="acao-secundaria acao-pequena" (click)="incluindoDocumento.set(false)">Cancelar</button>
                  <button type="button" class="acao-primaria acao-pequena" [disabled]="!novoDocNome.trim() || !novoDocArquivo" (click)="incluirDocumento()">Incluir documento</button>
                </div>
              }
              @if (x.etapa === 'documentos') { <div class="acoes-formulario" style="margin-top: 12px">
                @if (!incluindoDocumento()) { <button type="button" class="acao-secundaria" (click)="abrirInclusaoDocumento()">+ Incluir documento</button> }
                <button type="button" class="acao-primaria" (click)="executar(api.concluirDocumentos(x.id))">Concluir documentos</button></div> }
            </div>
          </section>

          <!-- 3. Resolução -->
          <section class="cartao-dados" [class.etapa-bloqueada]="bloqueada('resolucao')" aria-labelledby="et-resolucao">
            <header><div><h2 id="et-resolucao">3. Resolução</h2><small>Texto do modelo, editável. Número, datas e nomes entram na hora do PDF (com a marca MINUTA até a publicação).</small></div></header>
            <div class="corpo">
              @if (!bloqueada('resolucao')) {
                @if (!x.resolucao_html) {
                  <div class="acoes-formulario"><button type="button" class="acao-primaria" (click)="executar(api.gerarResolucao(x.id))">Gerar o texto da resolução</button></div>
                } @else {
                  @defer (on idle) { <app-editor-rico [(html)]="resolucaoHtml" rotulo="Texto da resolução" [somenteLeitura]="!!x.numero_protocolo_id && x.etapas[4].estado === 'feita'" /> } @placeholder { <app-esqueleto tipo="formulario" [linhas]="4" /> }
                  <p class="dica-formulario">Placeholders: <span class="texto-codigo">#nome #cpf #rg #cargo #nivel #setor #datainicio #numeroresolucao #anoresolucao #datapublicacao #hoje</span> (lista completa em RH &gt; Modelos).</p>
                  <div class="acoes-formulario">
                    <button type="button" class="acao-secundaria" title="Copia o texto com a formatação, para colar no SEI" (click)="copiarResolucao()">Copiar para o SEI</button>
                    <button type="button" class="acao-secundaria" (click)="baixar(api.baixarResolucao(x.id))">Baixar PDF</button>
                    @if (x.status === 'andamento') { <button type="button" class="acao-primaria" (click)="executar(api.salvarResolucao(x.id, resolucaoHtml))">Salvar texto</button> }
                  </div>
                }
              }
            </div>
          </section>

          <!-- 4. Protocolo -->
          <section class="cartao-dados" [class.etapa-bloqueada]="bloqueada('protocolo')" aria-labelledby="et-protocolo">
            <header><div><h2 id="et-protocolo">4. Número no Protocolo</h2><small>Reserva o próximo número do tipo de Resolução, na faixa do ano.</small></div></header>
            <div class="corpo">
              @if (x.sem_numero) {
                <p>Resolução <strong>sem número</strong>, conforme os Parâmetros do RH. Não há reserva no Protocolo.</p>
              } @else if (x.numero_protocolo) {
                <p>Número reservado: <strong class="texto-codigo">{{ x.numero_protocolo }}</strong></p>
                @if (x.status === 'andamento' && !x.posse_em) {
                  @if (liberandoNumero()) {
                    <div class="grade-parametros"><div class="campo"><label for="lib-motivo">Motivo da liberação do número *</label>
                      <input id="lib-motivo" name="motivoLiberacao" maxlength="2000" [(ngModel)]="motivoLiberacao" />
                      <small class="ajuda">O número volta ao Protocolo{{ x.tem_publicacao ? ' e o PDF da publicação é excluído' : '' }}. Só quem reservou o número ou o Serviço de Apoio Administrativo pode liberar.</small></div></div>
                    <div class="acoes-formulario" style="margin-top: 12px">
                      <button type="button" class="acao-recusar" [disabled]="!motivoLiberacao.trim()" (click)="liberarNumero(x.id)">Liberar número</button>
                      <button type="button" class="acao-secundaria" (click)="liberandoNumero.set(false)">Cancelar</button>
                    </div>
                  } @else {
                    <div class="acoes-formulario" style="margin-top: 12px"><button type="button" class="acao-secundaria" (click)="abrirLiberacao()">Liberar número</button></div>
                  }
                }
              } @else if (!bloqueada('protocolo')) {
                <div class="grade-parametros">
                  <div class="campo"><label for="tipo-protocolo">Tipo de Resolução</label>
                    <select id="tipo-protocolo" name="tipo" [(ngModel)]="tipoProtocolo">
                      <option value="">Escolher…</option>
                      @for (t of tiposProtocolo(); track t.id) { <option [value]="t.id" [disabled]="!t.tem_faixa_no_ano">{{ t.nome }}{{ t.tem_faixa_no_ano ? '' : ' (sem faixa neste ano)' }}</option> }
                    </select></div>
                </div>
                <div class="acoes-formulario" style="margin-top: 12px"><button type="button" class="acao-primaria" [disabled]="!tipoProtocolo" (click)="executar(api.reservarNumero(x.id, tipoProtocolo))">Reservar número</button></div>
              }
            </div>
          </section>

          <!-- 5. Publicação -->
          <section class="cartao-dados" [class.etapa-bloqueada]="bloqueada('publicacao')" aria-labelledby="et-publicacao">
            <header><div><h2 id="et-publicacao">5. Publicação no D.O.E.</h2><small>O PDF da publicação fica anexado ao número do Protocolo (se o Protocolo anexar direto, também vale) ou, na resolução sem número, à própria admissão. Ao registrar, o e-mail "Sua nomeação foi publicada" sai sozinho para a pessoa, com o PDF.</small></div></header>
            <div class="corpo">
              @if (x.tem_publicacao) {
                <p>Publicada em <strong>{{ dataBr(x.publicado_em) }}</strong>. <button type="button" class="acao-secundaria acao-pequena" (click)="baixar(api.baixarPublicacao(x.id))">Baixar PDF</button></p>
                <div class="aviso-email" [class.com-erro]="!x.email_enviado_em">
                  @if (x.email_enviado_em) {
                    <span class="selo-situacao">E-mail de nomeação enviado</span>
                    <span>automaticamente em {{ x.email_enviado_em | date: 'dd/MM/yyyy HH:mm' }} para <strong>{{ x.email_destino }}</strong>, com o PDF da publicação.</span>
                  } @else {
                    <span class="selo-origem">E-mail de nomeação não enviado</span>
                    <span>{{ x.email_erro || 'Ainda não foi enviado.' }}@if (!x.email_destino) { Cadastre o e-mail pessoal na ficha. }</span>
                    @if (x.status === 'andamento') { <button type="button" class="acao-secundaria acao-pequena" [disabled]="!x.email_destino" (click)="executar(api.reenviarEmail(x.id))">Reenviar</button> }
                  }
                </div>
                @if (x.status === 'andamento') {
                  <div class="grade-parametros"><div class="campo"><label for="pub-ajuste">Corrigir a data da publicação</label><input id="pub-ajuste" type="date" [(ngModel)]="publicadoEm" [max]="hoje" /></div></div>
                  <div class="acoes-formulario" style="margin-top: 12px"><button type="button" class="acao-secundaria" [disabled]="!publicadoEm" (click)="executar(api.ajustarPublicacao(x.id, publicadoEm))">Salvar a data</button></div>
                }
              } @else if (!bloqueada('publicacao')) {
                <div class="grade-parametros">
                  <div class="campo"><label for="pub-data">Data da publicação</label><input id="pub-data" type="date" [(ngModel)]="publicadoEm" [max]="hoje" /></div>
                  <div class="campo"><app-campo-arquivo tipo="pdf" rotulo="PDF do D.O.E." [obrigatorio]="true" (selecionado)="pubArquivo = $event" /></div>
                </div>
                <div class="acoes-formulario" style="margin-top: 12px"><button type="button" class="acao-primaria" [disabled]="!publicadoEm || !pubArquivo" (click)="registrarPublicacao()">Registrar publicação</button></div>
              }
            </div>
          </section>

          <!-- 6. Posse -->
          <section class="cartao-dados" [class.etapa-bloqueada]="bloqueada('posse')" aria-labelledby="et-posse">
            <header><div><h2 id="et-posse">6. Posse</h2><small>Data da posse e termo em PDF.</small></div></header>
            <div class="corpo">
              @if (x.posse_em) {
                <p>Posse em <strong>{{ dataBr(x.posse_em) }}</strong>.</p>
                @defer (on idle) { <app-editor-rico [(html)]="termoHtml" rotulo="Texto do termo de posse" [somenteLeitura]="x.status !== 'andamento'" /> } @placeholder { <app-esqueleto tipo="formulario" [linhas]="3" /> }
                <div class="acoes-formulario" style="margin-top: 12px">
                  <button type="button" class="acao-secundaria" (click)="baixar(api.baixarTermo(x.id))">Baixar termo (PDF)</button>
                  @if (x.status === 'andamento') { <button type="button" class="acao-primaria" (click)="executar(api.salvarTermo(x.id, termoHtml))">Salvar texto</button> }
                </div>
              } @else if (!bloqueada('posse')) {
                <div class="grade-parametros"><div class="campo"><label for="posse-data">Data da posse</label><input id="posse-data" type="date" [(ngModel)]="posseEm" /></div></div>
                <div class="acoes-formulario" style="margin-top: 12px"><button type="button" class="acao-primaria" [disabled]="!posseEm" (click)="executar(api.registrarPosse(x.id, posseEm))">Registrar posse</button></div>
              }
            </div>
          </section>

          <!-- 7. Entrada no SGI -->
          <section class="cartao-dados" [class.etapa-bloqueada]="bloqueada('concluida')" aria-labelledby="et-concluida">
            <header><div><h2 id="et-concluida">7. Entrada no SGI</h2><small>A pessoa assume o cargo na data da posse e o histórico funcional registra a admissão.</small></div></header>
            <div class="corpo">
              @if (x.status === 'concluida') {
                <p>Concluída em {{ x.concluida_em | date: 'dd/MM/yyyy HH:mm' }}. <a [routerLink]="['/rh/historico', x.usuario_id]">Ver histórico funcional</a></p>
              } @else if (!bloqueada('concluida')) {
                @if (x.conta_vinculada) { <p class="selo-situacao">Conta localizada e ligada à ficha</p> }
                @else { <p class="aviso-bloco">A conta <span class="texto-codigo">{{ x.login_proposto }}</span> ainda não apareceu no AD/SGI. Quando a TI criar o login, a ficha se liga sozinha e a admissão pode ser concluída.</p> }
                <div class="acoes-formulario" style="margin-top: 12px"><button type="button" class="acao-positiva" [disabled]="!x.conta_vinculada" (click)="executar(api.concluir(x.id))">Concluir admissão</button></div>
              }
            </div>
          </section>
        </div>
      </div>
    } @else { <app-esqueleto tipo="formulario" [linhas]="6" /> }
  `,
})
export class AdmissaoComponent implements OnInit {
  private readonly rota = inject(ActivatedRoute);
  private readonly dialogos = inject(DialogosService);
  protected readonly api = inject(RhAdmissaoApiService);

  protected readonly a = signal<LeituraAdmissao | null>(null);
  protected readonly ocupado = signal(false);
  protected readonly tiposProtocolo = signal<TipoProtocoloResolucao[]>([]);
  protected readonly documentoAberto = signal<number | null>(null);
  private readonly rotulosSolicitacoes = signal<Record<string, string>>({});
  protected readonly hoje = new Date().toISOString().slice(0, 10);

  protected solicitar: Record<string, boolean> = {};
  protected observacoesChamado = '';
  protected usuarioEspelho = '';
  protected docData = '';
  protected docObs = '';
  protected docArquivo: File | null = null;
  protected resolucaoHtml = '';
  protected tipoProtocolo = '';
  protected readonly liberandoNumero = signal(false);
  protected motivoLiberacao = '';
  protected publicadoEm = '';
  protected pubArquivo: File | null = null;
  protected termoHtml = '';
  protected posseEm = '';

  ngOnInit(): void {
    this.api.solicitacoes().subscribe((s) => this.rotulosSolicitacoes.set(s));
    this.api.tiposProtocolo().subscribe((t) => this.tiposProtocolo.set(t));
    this.api.obter(Number(this.rota.snapshot.paramMap.get('id'))).subscribe({ next: (x) => this.atualizar(x), error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível abrir a admissão') });
  }

  protected solicitacoesLista(): [string, string][] {
    return Object.entries(this.rotulosSolicitacoes());
  }

  protected trilha(): EtapaTrilha[] {
    return (this.a()?.etapas ?? []).map((e) => ({ id: e.chave, rotulo: e.rotulo, estado: ESTADO[e.estado], titulo: e.em ?? undefined }));
  }

  /** Etapa ainda não liberada (à frente da atual) ou admissão fora de andamento sem a etapa feita. */
  protected bloqueada(chave: ChaveEtapa): boolean {
    const etapa = this.a()?.etapas.find((e) => e.chave === chave);
    return !etapa || etapa.estado === 'pendente';
  }

  protected dataBr(iso: string | null): string {
    return iso ? iso.split('-').reverse().join('/') : '';
  }

  /** Aplica o que a API devolveu e sincroniza os campos de edição. */
  private atualizar(x: LeituraAdmissao): void {
    this.a.set(x);
    this.resolucaoHtml = x.resolucao_html ?? '';
    this.termoHtml = x.termo_html ?? '';
    this.publicadoEm = x.publicado_em ?? '';
    this.documentoAberto.set(null);
    if (!Object.keys(this.solicitar).length) this.solicitar = { ...x.solicitacoes };
  }

  protected executar(chamada: Observable<LeituraAdmissao>): void {
    this.ocupado.set(true);
    this.dialogos.executar(chamada, 'Salvando…').subscribe({
      next: (x) => { this.ocupado.set(false); this.atualizar(x); },
      error: (e) => { this.ocupado.set(false); this.dialogos.mostrarErro(e, 'Não foi possível concluir a operação'); },
    });
  }

  protected abrirLiberacao(): void {
    this.motivoLiberacao = '';
    this.liberandoNumero.set(true);
  }

  protected liberarNumero(id: number): void {
    const motivo = this.motivoLiberacao.trim();
    if (!motivo) return;
    this.liberandoNumero.set(false);
    this.executar(this.api.liberarNumero(id, motivo));
  }

  protected baixar(chamada: Observable<unknown>): void {
    chamada.subscribe({ error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível baixar o arquivo') });
  }

  /** Copia a resolução (com os placeholders já trocados) em HTML e texto simples: o SEI recebe a formatação ao colar. Texto editado e ainda não salvo é gravado antes. */
  protected copiarResolucao(): void {
    const x = this.a();
    if (!x) return;
    const copiar = () => this.api.resolucaoParaCopiar(x.id).subscribe({
      next: (t) => void this.colar(t.html, t.texto),
      error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível copiar o texto'),
    });
    if (x.status === 'andamento' && this.resolucaoHtml !== (x.resolucao_html ?? '')) {
      this.api.salvarResolucao(x.id, this.resolucaoHtml).subscribe({ next: (n) => { this.atualizar(n); copiar(); }, error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível salvar o texto') });
    } else {
      copiar();
    }
  }

  private async colar(html: string, texto: string): Promise<void> {
    try {
      if (navigator.clipboard && typeof ClipboardItem !== 'undefined') {
        await navigator.clipboard.write([new ClipboardItem({ 'text/html': new Blob([html], { type: 'text/html' }), 'text/plain': new Blob([texto], { type: 'text/plain' }) })]);
      } else {
        this.copiarPeloNavegadorAntigo(html);
      }
      this.dialogos.avisar('Texto copiado', 'Cole no SEI: a formatação vai junto.');
    } catch {
      this.dialogos.mostrarErro(new Error('O navegador não permitiu copiar. Use o botão de novo ou baixe o PDF.'), 'Não foi possível copiar');
    }
  }

  /** Alternativa para navegadores sem `ClipboardItem`: seleciona um trecho oculto e copia o que está selecionado. */
  private copiarPeloNavegadorAntigo(html: string): void {
    const area = document.createElement('div');
    area.contentEditable = 'true';
    area.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0';
    area.innerHTML = html;
    document.body.appendChild(area);
    const selecao = window.getSelection();
    const faixa = document.createRange();
    faixa.selectNodeContents(area);
    selecao?.removeAllRanges();
    selecao?.addRange(faixa);
    const ok = document.execCommand('copy');
    selecao?.removeAllRanges();
    document.body.removeChild(area);
    if (!ok) throw new Error('copia recusada');
  }

  /** Palavras (sem acento, em maiúsculas) que identificam, no título do chamado criado pelo GLPI, o serviço pedido. */
  private readonly palavrasServico: Record<string, RegExp> = {
    rede: /USUARIO DE REDE/, email: /E-?MAIL/, sei: /\bSEI\b/, compras_sp: /COMPRAS SP/, equipamento: /EQUIPAMENTO/, estacao: /ESTACAO/, cracha: /CRACHA/, telefone: /TELEFONIA/, mobiliario: /MOBILIARIO/,
  };

  private semAcento(texto: string): string {
    return texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase();
  }

  /** Uma linha por serviço do formulário: se foi pedido e o chamado que o GLPI abriu para ele (achado pelo título). */
  protected linhasChamado(x: LeituraAdmissao) {
    return this.solicitacoesLista().map(([chave, servico]) => {
      const link = x.chamado_links.find((l) => this.palavrasServico[chave]?.test(this.semAcento(l.texto))) ?? null;
      return { chave, servico, pedido: !!x.solicitacoes[chave], link, numero: link ? (/id=(\d+)/.exec(link.url)?.[1] ?? '') : '' };
    });
  }

  /** Itens criados que não casam com nenhum serviço conhecido (o formulário pode ganhar destinos novos). */
  protected chamadosSemServico(x: LeituraAdmissao) {
    return x.chamado_links.filter((l) => !Object.values(this.palavrasServico).some((r) => r.test(this.semAcento(l.texto))));
  }

  /** Endereço da foto (muda a cada troca, para a prévia não ficar em cache). */
  protected urlFoto(): string {
    return `${this.api.urlFoto(this.a()!.id)}?v=${this.fotoVersao}`;
  }

  private fotoVersao = 0;

  protected escolherFoto(campo: HTMLInputElement): void {
    const arquivo = campo.files?.[0];
    campo.value = '';
    if (!arquivo) return;
    this.fotoVersao++;
    this.executar(this.api.enviarFoto(this.a()!.id, arquivo));
  }

  protected abrirChamado(): void {
    this.executar(this.api.abrirChamado(this.a()!.id, this.solicitar, this.observacoesChamado, this.usuarioEspelho.trim()));
  }

  protected abrirDocumento(d: DocumentoAdmissao): void {
    this.docData = '';
    this.docObs = '';
    this.docArquivo = null;
    this.documentoAberto.set(d.id);
  }

  protected registrarDocumento(d: DocumentoAdmissao): void {
    this.executar(this.api.registrarDocumento(this.a()!.id, d.id, this.docData, this.docObs, this.docArquivo));
  }

  protected desfazerDocumento(d: DocumentoAdmissao): void {
    this.executar(this.api.desfazerDocumento(this.a()!.id, d.id));
  }

  // Inclusão de documento fora do checklist do cargo (formulário aberto e campos)
  protected readonly incluindoDocumento = signal(false);
  protected novoDocNome = '';
  protected novoDocDescricao = '';
  protected novoDocArquivo: File | null = null;

  protected abrirInclusaoDocumento(): void {
    this.novoDocNome = '';
    this.novoDocDescricao = '';
    this.novoDocArquivo = null;
    this.incluindoDocumento.set(true);
  }

  /** Inclui o documento nesta admissão e fecha o formulário. */
  protected incluirDocumento(): void {
    if (!this.novoDocNome.trim() || !this.novoDocArquivo) return;
    this.incluindoDocumento.set(false);
    this.executar(this.api.incluirDocumento(this.a()!.id, this.novoDocNome.trim(), this.novoDocDescricao.trim(), this.novoDocArquivo));
  }

  /** Exclui um documento incluído durante a admissão, depois de confirmar. */
  protected async excluirDocumentoIncluido(d: DocumentoAdmissao): Promise<void> {
    if (!(await this.dialogos.confirmar({ titulo: `Excluir "${d.descricao}"?`, mensagem: 'O documento sai desta admissão e o arquivo é descartado.', rotuloConfirmar: 'Excluir documento', perigo: true }))) return;
    this.executar(this.api.excluirDocumentoIncluido(this.a()!.id, d.id));
  }

  protected arquivoDocumento(d: DocumentoAdmissao): void {
    this.baixar(this.api.baixarArquivoDocumento(this.a()!.id, d.id));
  }

  protected comprovante(d: DocumentoAdmissao): void {
    this.baixar(this.api.baixarComprovante(this.a()!.id, d.id));
  }

  protected registrarPublicacao(): void {
    this.executar(this.api.registrarPublicacao(this.a()!.id, this.pubArquivo!, this.publicadoEm));
  }

  protected async cancelar(): Promise<void> {
    if (!(await this.dialogos.confirmar({ titulo: 'Cancelar esta admissão?', mensagem: 'O número do Protocolo ainda sem documento volta para a fila. A ficha continua cadastrada.', rotuloConfirmar: 'Cancelar admissão', perigo: true }))) return;
    this.executar(this.api.cancelar(this.a()!.id));
  }
}
