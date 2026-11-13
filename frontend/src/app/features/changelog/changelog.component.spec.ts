/**
 * =============================================================================
 * ARQUIVO: changelog.component.spec.ts
 * AUTOR: José Eduardo Santana Martins
 *
 * FINALIDADE:
 * Testar a tela do Changelog: o dia aberto, a navegação entre dias e a bolinha
 * de novidade do menu apagada ao abrir.
 *
 * RESUMO TÉCNICO:
 * Usa o TestBed do Angular com provideRouter([]) e um dublê (useValue) de
 * NovidadesVistasService que só conta as chamadas de marcarVistas. A função
 * abrir() cria o ChangelogComponent, injeta a data pela entrada "data" e
 * devolve o HTML renderizado para conferir com querySelector.
 * Os casos usam datas reais de novidades.ts (o dia mais recente e 04/11/2026), então
 * precisam ser ajustados quando o primeiro dia da lista mudar.
 *
 * FINALIDADE DE NEGÓCIO:
 * Protege a leitura das novidades por quem usa o SGI: abre sempre no dia mais
 * recente, mostra o módulo de cada novidade, permite andar para o dia anterior
 * e seguinte e apaga o aviso de novidade depois que a pessoa viu.
 *
 * CONTEXTO NO SISTEMA:
 * Testa changelog.component.ts com os dados de novidades.ts e o serviço
 * core/changelog/novidades-vistas.service.ts. Roda com "npx ng test".
 *
 * =============================================================================
 */

import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { AcessoService } from '../../core/acesso/acesso.service';
import { AutenticacaoService } from '../../core/autenticacao/autenticacao.service';
import { NovidadesVistasService } from '../../core/changelog/novidades-vistas.service';
import { ChangelogComponent } from './changelog.component';
import { NOVIDADES } from './novidades';

// Dia mais recente das novidades no formato da tela (dd/mm/aaaa): o teste não precisa mudar a cada dia novo
const MAIS_RECENTE = NOVIDADES[0].data.split('-').reverse().join('/');

describe('ChangelogComponent', () => {
  // Conta quantas vezes a tela pediu para apagar a bolinha de novidade do menu.
  let marcadas = 0;
  // Dublês do acesso: por padrão, SuperRoot (vê todas as novidades); um teste troca para usuário comum
  let superRoot = true;

  // beforeEach roda antes de cada "it": troca o serviço real de novidades vistas por um dublê
  // (useValue) que só incrementa o contador, sem tocar no armazenamento do navegador.
  beforeEach(() => {
    marcadas = 0;
    superRoot = true;
    TestBed.configureTestingModule({
      providers: [provideRouter([]), { provide: NovidadesVistasService, useValue: { marcarVistas: () => marcadas++, temNova: () => false } },
        { provide: AutenticacaoService, useValue: { possuiPapel: () => superRoot } },
        // Usuário comum do teste: sem nenhum recurso da ACL, sem Chamados e sem Rede
        { provide: AcessoService, useValue: { pode: () => false, chamados: () => null, rede: () => null } }],
    });
  });

  /**
   * Cria o componente, opcionalmente com a data da rota (input "data"), roda a detecção de mudanças
   * e devolve o elemento HTML renderizado para as consultas com querySelector.
   */
  function abrir(data?: string) {
    const fixture = TestBed.createComponent(ChangelogComponent);
    if (data) fixture.componentRef.setInput('data', data);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  it('sem data abre o dia mais recente, lista só os dias com novidade e apaga a bolinha', () => {
    const tela = abrir();
    // A lista para pular de dia tem todos os dias; o escolhido é o mais recente
    const lista = tela.querySelector('#changelog-dia') as HTMLSelectElement;
    expect(lista.options.length).toBe(NOVIDADES.length);
    expect(lista.selectedOptions[0]?.textContent).toContain(MAIS_RECENTE);
    expect(tela.querySelectorAll('.changelog-novidade').length).toBe(NOVIDADES[0].novidades.length);
    expect(marcadas).toBe(1);
  });

  it('abre o dia da rota com o selo do módulo e oferece o dia mais recente e o mais antigo', () => {
    const tela = abrir('2026-11-04');
    expect(tela.querySelector('h2')?.textContent).toContain('4 de novembro de 2026');
    expect(tela.querySelector('.changelog-novidade .selo-nivel')?.textContent).toContain('Contratos');
    expect((tela.querySelector('#changelog-dia') as HTMLSelectElement).value).toBe('2026-11-04');
    // Seta ← = dia anterior (mais antigo); seta → = próximo dia (mais recente)
    const navegacao = tela.querySelector('.changelog-navegacao')?.textContent ?? '';
    expect(navegacao).toContain('← 03/11/2026');
    expect(navegacao).toContain('06/11/2026 →');
  });

  it('data inexistente cai no dia mais recente', () => {
    expect((abrir('2020-01-01').querySelector('#changelog-dia') as HTMLSelectElement).selectedOptions[0]?.textContent).toContain(MAIS_RECENTE);
  });

  it('usuário comum só vê as novidades dos módulos que usa', () => {
    superRoot = false;
    const tela = abrir();
    const selos = Array.from(tela.querySelectorAll('.changelog-novidade .selo-nivel')).map((e) => e.textContent?.trim());
    // Rede, Contratos, Patrimônio, Administração… ficam de fora; Geral, Tarefas e os demais abertos a todos aparecem
    expect(selos.every((m) => ['Geral', 'RH', 'Tarefas', 'Reserva de Espaços', 'Melhorias', 'Ramais', 'Notificações'].includes(m ?? ''))).toBe(true);
    expect((tela.querySelector('#changelog-dia') as HTMLSelectElement).options.length).toBeLessThan(NOVIDADES.length);
  });
});
