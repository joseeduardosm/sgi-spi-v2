// Criado por José Eduardo Santana Martins
// Este arquivo serve para ler QR code e código de barras pela câmera do celular (BarcodeDetector nativo, com a biblioteca ZXing de reserva; lê QR code e códigos de barras).
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
  readonly mensagem = input('Aponte a câmera para o QR code ou código de barras do bem');
  readonly lido = output<string>();
  readonly fechar = output<void>();

  private readonly zona = inject(NgZone);
  private readonly video = viewChild.required<ElementRef<HTMLVideoElement>>('video');
  protected readonly erro = signal('');
  protected readonly ultimo = signal('');
  private fluxo: MediaStream | null = null;
  private parar = false;
  private anterior = { valor: '', em: 0 };
  private controleZxing: { stop: () => void } | null = null;

  constructor() {
    queueMicrotask(() => void this.iniciar());
  }

  private async iniciar(): Promise<void> {
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

  ngOnDestroy(): void {
    this.parar = true;
    this.controleZxing?.stop();
    this.fluxo?.getTracks().forEach((t) => t.stop());
  }
}
