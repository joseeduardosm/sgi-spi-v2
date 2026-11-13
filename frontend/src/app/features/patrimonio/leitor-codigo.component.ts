/**
 * =============================================================================
 * ARQUIVO: leitor-codigo.component.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Ler QR code e código de barras pela câmera do celular e devolver o código
 * lido (chapa ou número de série do bem) para a tela que abriu o leitor.
 *
 * RESUMO TÉCNICO:
 * Usa o BarcodeDetector nativo do navegador quando ele lê QR code; senão
 * carrega sob demanda a biblioteca ZXing (@zxing/browser). O laço de leitura
 * roda fora da zona do Angular (NgZone) para não redesenhar a tela a cada
 * quadro. Extrai o código de URLs de etiqueta e ignora leituras repetidas.
 *
 * FINALIDADE DE NEGÓCIO:
 * Agiliza inventário, recebimento de movimentação e montagem de listas: o
 * servidor aponta a câmera para a etiqueta do bem em vez de digitar a chapa.
 *
 * CONTEXTO NO SISTEMA:
 * Componente compartilhado das telas do Patrimônio (detalhe da movimentação,
 * listas de classificação e baixa, relacionar sala etc.). Emite os eventos
 * "lido" e "fechar" para o componente pai.
 *
 * =============================================================================
 */
import { Component, ElementRef, inject, input, NgZone, OnDestroy, output, signal, viewChild } from '@angular/core';

/** Câmera aberta que lê códigos continuamente e avisa a cada chapa lida (sem repetir a mesma leitura em sequência). */
@Component({
  selector: 'app-leitor-codigo',
  template: `
    <div class="leitor-codigo" role="dialog" aria-label="Leitura de código pela câmera">
      <video #video playsinline muted></video>
      <div class="mira" aria-hidden="true"></div>
      @if (erro()) { <p class="erro-leitor">{{ erro() }}</p> }
      <div class="barra-leitor">
        <span>{{ ultimo() ? 'Lido: ' + ultimo() : mensagem() }}</span>
        <button type="button" class="acao-secundaria" (click)="fechar.emit()">{{ continuo() ? 'Concluir' : 'Fechar' }}</button>
      </div>
    </div>
  `,
})
export class LeitorCodigoComponent implements OnDestroy {
  /** Leitura contínua (lista de bens): a câmera continua aberta depois de cada código. Desligada, fecha na primeira leitura. */
  readonly continuo = input(false);
  /** Texto de orientação mostrado na barra inferior enquanto nada foi lido. */
  readonly mensagem = input('Aponte a câmera para o QR code ou código de barras do bem');
  /** Evento emitido a cada código lido (output() avisa o componente pai). */
  readonly lido = output<string>();
  /** Evento para o pai fechar o leitor (botão ou fim da leitura única). */
  readonly fechar = output<void>();

  // NgZone controla quando o Angular atualiza a tela; usado para rodar o laço da câmera fora dele
  private readonly zona = inject(NgZone);
  /** Referência ao elemento video do template (viewChild busca o elemento marcado com #video). */
  private readonly video = viewChild.required<ElementRef<HTMLVideoElement>>('video');
  /** Mensagem de erro (câmera indisponível ou sem permissão). */
  protected readonly erro = signal('');
  /** Último código lido, exibido na barra. */
  protected readonly ultimo = signal('');
  /** Fluxo da câmera aberto pelo detector nativo (fechado no ngOnDestroy). */
  private fluxo: MediaStream | null = null;
  /** Sinal para o laço do detector nativo terminar. */
  private parar = false;
  /** Última leitura e quando ocorreu, para descartar repetições. */
  private anterior = { valor: '', em: 0 };
  /** Controle do ZXing, para parar a câmera quando ele é usado. */
  private controleZxing: { stop: () => void } | null = null;

  /** Inicia a câmera logo depois de o template existir (queueMicrotask adia para depois da criação). */
  constructor() {
    queueMicrotask(() => void this.iniciar());
  }

  /**
   * Abre a câmera traseira e começa a ler. Primeiro tenta o leitor nativo
   * (mais leve); se não houver, ou se ele não ler QR code, usa o ZXing.
   * Mostra mensagem de erro quando a câmera não pode ser usada.
   */
  private async iniciar(): Promise<void> {
    // getUserMedia só existe em HTTPS (ou localhost)
    if (!navigator.mediaDevices?.getUserMedia) { this.erro.set('Este navegador não permite usar a câmera (é preciso HTTPS). Digite a chapa.'); return; }
    try {
      const video = this.video().nativeElement;
      type Detector = new (o?: object) => { detect: (v: HTMLVideoElement) => Promise<{ rawValue: string }[]> };
      const Nativo = (window as unknown as { BarcodeDetector?: Detector & { getSupportedFormats?: () => Promise<string[]> } }).BarcodeDetector;
      // QR code e códigos de barras: só os formatos que este navegador realmente lê (pedir um formato sem suporte faz o detector falhar)
      const desejados = ['qr_code', 'code_128', 'code_39', 'ean_13', 'ean_8', 'itf', 'data_matrix'];
      const aceitos = Nativo?.getSupportedFormats ? await Nativo.getSupportedFormats().catch(() => desejados) : desejados;
      const formatos = desejados.filter((f) => aceitos.includes(f));
      // O leitor nativo só serve se lê QR code; senão entra o ZXing, que lê QR e barras em qualquer navegador
      const Detector = Nativo && formatos.includes('qr_code') ? Nativo : undefined;
      if (Detector) {
        this.fluxo = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
        video.srcObject = this.fluxo;
        await video.play();
        const detector = new Detector({ formats: formatos });
        const laco = async () => {
          while (!this.parar) {
            try {
              const achados = await detector.detect(video);
              if (achados.length) this.tratar(achados[0].rawValue);
            } catch { /* quadro sem imagem ainda */ }
            await new Promise((r) => setTimeout(r, 250));
          }
        };
        void this.zona.runOutsideAngular(laco);
        return;
      }
      // Reserva: ZXing (carregado só quando o navegador não tem o BarcodeDetector)
      const { BrowserMultiFormatReader } = await import('@zxing/browser');
      const leitor = new BrowserMultiFormatReader();
      this.controleZxing = await leitor.decodeFromConstraints({ video: { facingMode: { ideal: 'environment' } }, audio: false }, video, (resultado) => {
        if (resultado) this.zona.run(() => this.tratar(resultado.getText()));
      });
    } catch {
      this.erro.set('Não foi possível abrir a câmera. Libere a permissão no navegador ou digite a chapa.');
    }
  }

  /** QR code de etiqueta pode trazer um endereço (…/bens/SPI000231 ou ?chapa=SPI000231): vale o código no fim dele. */
  private extrair(valor: string): string {
    const texto = valor.trim();
    if (!/^https?:\/\//i.test(texto)) return texto;
    try {
      const url = new URL(texto);
      const parametro = url.searchParams.get('chapa') ?? url.searchParams.get('codigo');
      const ultimo = url.pathname.split('/').filter(Boolean).pop();
      return decodeURIComponent(parametro ?? ultimo ?? texto).trim();
    } catch { return texto; }
  }

  /**
   * Trata um código lido: extrai o código da URL, descarta repetição recente,
   * vibra o aparelho, emite "lido" e, na leitura única, pede para fechar.
   */
  private tratar(valor: string): void {
    const texto = this.extrair(valor);
    const agora = Date.now();
    // Ignora a mesma leitura repetida em menos de 2,5 s (a câmera "vê" o mesmo código vários quadros seguidos)
    if (!texto || (texto === this.anterior.valor && agora - this.anterior.em < 2500)) return;
    this.anterior = { valor: texto, em: agora };
    this.zona.run(() => {
      this.ultimo.set(texto);
      navigator.vibrate?.(60);
      this.lido.emit(texto);
      if (!this.continuo()) this.fechar.emit();
    });
  }

  /** Ao fechar o componente, para o laço e desliga a câmera (senão a luz da câmera continua acesa). */
  ngOnDestroy(): void {
    this.parar = true;
    this.controleZxing?.stop();
    this.fluxo?.getTracks().forEach((t) => t.stop());
  }
}
