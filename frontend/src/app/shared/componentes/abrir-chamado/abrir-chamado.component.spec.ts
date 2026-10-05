// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar o modal "Abrir Chamado" (dados do cadastro, envio, sucesso e erro mantendo o texto).

import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ChamadoService } from '../../../core/chamados/chamado.service';
import { AbrirChamadoComponent } from './abrir-chamado.component';

const DADOS = { nome: 'Fulano de Tal', setor: 'Setor X', superior_imediato: 'Chefe Silva', email: 'fulano@sp.gov.br', telefone: '8123', celular: '', andar_lado: '5º andar - A', aguardando_validacao: [] as string[] };

describe('AbrirChamadoComponent', () => {
  beforeEach(() => TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] }));

  async function abrir() {
    const fixture = TestBed.createComponent(AbrirChamadoComponent);
    const http = TestBed.inject(HttpTestingController);
    TestBed.inject(ChamadoService).abrirModal();
    fixture.detectChanges();
    http.expectOne('/api/chamados/solicitante').flush(DADOS);
    fixture.detectChanges();
    // O ngModel inicializa o campo em um microtask: espera antes de digitar (como faz uma pessoa)
    await fixture.whenStable();
    return { fixture, http, elemento: fixture.nativeElement as HTMLElement };
  }

  async function preencher(fixture: Awaited<ReturnType<typeof abrir>>['fixture'], assunto: string, descricao: string) {
    const el = fixture.nativeElement as HTMLElement;
    const a = el.querySelector('#chamado-assunto') as HTMLInputElement;
    const d = el.querySelector('#chamado-descricao') as HTMLTextAreaElement;
    a.value = assunto; a.dispatchEvent(new Event('input'));
    d.value = descricao; d.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
  }

  it('mostra os dados do cadastro (sem celular quando vazio) e a assinatura', async () => {
    const { elemento } = await abrir();
    const texto = elemento.textContent ?? '';
    expect(texto).toContain('Fulano de Tal');
    expect(texto).toContain('Chefe Silva');
    expect(texto).toContain('5º andar - A');
    expect(texto).not.toContain('Celular');
    expect(texto).not.toContain('Aberto pelo SGI');
    // Campo de anexos presente
    expect(texto).toContain('Anexar arquivo');
    expect(texto).not.toContain('Local do problema');
    expect(texto).toContain('Seus dados');
    expect(texto).not.toContain('(do cadastro)');
  });

  it('mostra todos os dados mesmo se a API não mandar `aguardando_validacao` (versão anterior)', async () => {
    const fixture = TestBed.createComponent(AbrirChamadoComponent);
    const http = TestBed.inject(HttpTestingController);
    TestBed.inject(ChamadoService).abrirModal();
    fixture.detectChanges();
    const { aguardando_validacao: _, ...semCampo } = DADOS;
    http.expectOne('/api/chamados/solicitante').flush(semCampo);
    fixture.detectChanges();
    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto).toContain('Chefe Silva');
    expect(texto).toContain('fulano@sp.gov.br');
    expect(texto).toContain('5º andar - A');
  });

  it('envia assunto e descrição e mostra o número do chamado', async () => {
    const { fixture, http, elemento } = await abrir();
    await preencher(fixture, 'Sem rede', 'Meu computador está sem rede.');
    // Ctrl+V de uma imagem vira anexo (com miniatura) e some o texto colado
    const evento = new Event('paste', { bubbles: true, cancelable: true }) as Event & { clipboardData: unknown };
    const imagem = new File([new Uint8Array([137, 80, 78, 71])], 'qualquer.png', { type: 'image/png' });
    evento.clipboardData = { items: [{ kind: 'file', type: 'image/png', getAsFile: () => imagem }] };
    (elemento.querySelector('section') as HTMLElement).dispatchEvent(evento);
    fixture.detectChanges();
    expect(evento.defaultPrevented).toBe(true);
    expect(elemento.querySelectorAll('.anexos-chamado figure')).toHaveLength(1);
    (elemento.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    const req = http.expectOne('/api/chamados');
    const corpo = req.request.body as FormData;
    // Sem campo de local: o servidor usa o andar e lado do cadastro
    expect(JSON.parse(corpo.get('dados') as string)).toEqual({ assunto: 'Sem rede', descricao: 'Meu computador está sem rede.' });
    expect(corpo.getAll('arquivos')).toHaveLength(1);
    req.flush({ glpi_id: 1501, assunto: 'Sem rede', url: 'https://glpi/ticket?id=1501', aberto_em: '2026-10-05T10:00:00Z', anexos_enviados: 1, anexos_com_falha: [] });
    fixture.detectChanges();
    expect(elemento.textContent).toContain('#1501');
    expect(elemento.querySelector('a.link-texto')?.getAttribute('href')).toBe('https://glpi/ticket?id=1501');
  });

  it('em erro mantém o texto digitado e mostra a mensagem da API', async () => {
    const { fixture, http, elemento } = await abrir();
    await preencher(fixture, 'Sem rede', 'Meu computador está sem rede.');
    (elemento.querySelector('form') as HTMLFormElement).dispatchEvent(new Event('submit'));
    http.expectOne('/api/chamados').flush({ detalhe: 'Não foi possível abrir o chamado agora.', codigo: 'glpi_indisponivel' }, { status: 502, statusText: 'Bad Gateway' });
    fixture.detectChanges();
    expect(elemento.textContent).toContain('Não foi possível abrir o chamado agora.');
    expect((elemento.querySelector('#chamado-assunto') as HTMLInputElement).value).toBe('Sem rede');
  });
});
