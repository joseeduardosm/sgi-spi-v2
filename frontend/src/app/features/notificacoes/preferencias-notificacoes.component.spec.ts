// Criado por José Eduardo Santana Martins
// Este arquivo serve para testar a aba Preferências das Notificações: matriz evento × canal, marcar módulo/coluna, obrigatórias travadas e o que é salvo.
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { NotificacoesApiService } from '../../core/notificacoes/notificacoes-api.service';
import { CanalNotificacao, Preferencias } from '../../core/notificacoes/notificacoes.models';
import { PushNotificacoesService } from '../../core/notificacoes/push-notificacoes.service';
import { DialogosService } from '../../shared/servicos/dialogos.service';
import { PreferenciasNotificacoesComponent } from './preferencias-notificacoes.component';

const celula = (disponivel = true, ligado = false, obrigatorio = false) => ({ disponivel, ligado, obrigatorio });
const evento = (chave: string, email = celula(), navegador = celula(), desktop = celula()) => ({ chave, rotulo: chave, descricao: '', canais: { email, navegador, desktop } });

function preferencias(): Preferencias {
  return {
    modulos: [
      { chave: 'contratos', rotulo: 'Contratos', eventos: [evento('contratos.a'), evento('contratos.b', celula(true, true, true))] },
      { chave: 'sistema', rotulo: 'Sistema', eventos: [evento('sistema.novidades', celula(), celula(false), celula(false))] },
    ],
    configuracao: { frequencia_email: 'imediato', silencio_inicio: null, silencio_fim: null, silencio_fins_de_semana: false },
    navegador: { disponivel: false, chave_publica_vapid: null, inscricoes: 0, aparelhos: [], explicacao: 'Sem VAPID.' },
    silenciados: [],
  };
}

describe('PreferenciasNotificacoesComponent', () => {
  let api: { preferencias: ReturnType<typeof vi.fn>; salvarPreferencias: ReturnType<typeof vi.fn> };

  function criar() {
    api = { preferencias: vi.fn(() => of(preferencias())), salvarPreferencias: vi.fn(() => of(preferencias())) };
    TestBed.configureTestingModule({
      providers: [
        { provide: NotificacoesApiService, useValue: api },
        { provide: DialogosService, useValue: { avisar: vi.fn(), mostrarErro: vi.fn() } },
        { provide: PushNotificacoesService, useValue: { estado: () => 'inativo', atualizarEstado: vi.fn(async () => 'inativo'), ativar: vi.fn(), desativar: vi.fn() } },
      ],
    });
    const fixture = TestBed.createComponent(PreferenciasNotificacoesComponent);
    fixture.detectChanges();
    return fixture.componentInstance as unknown as {
      marcada(e: string, c: CanalNotificacao): boolean; alternar(e: string, c: CanalNotificacao): void; alternarGrupo(m?: unknown, c?: CanalNotificacao): void;
      tudoMarcado(m?: unknown, c?: CanalNotificacao): boolean; salvar(): void; dados(): Preferencias;
    };
  }

  it('começa só com o que já está ligado (obrigatório incluído) e marca uma caixa', () => {
    const c = criar();
    expect(c.marcada('contratos.a', 'email')).toBe(false);
    expect(c.marcada('contratos.b', 'email')).toBe(true);
    c.alternar('contratos.a', 'email');
    expect(c.marcada('contratos.a', 'email')).toBe(true);
  });

  it('marcar a coluna inteira liga só o que está disponível e não é obrigatório (e desmarca na segunda vez)', () => {
    const c = criar();
    c.alternarGrupo(undefined, 'navegador');
    expect(c.marcada('contratos.a', 'navegador') && c.marcada('contratos.b', 'navegador')).toBe(true);
    // O evento só por e-mail não tem a caixa de navegador
    expect(c.marcada('sistema.novidades', 'navegador')).toBe(false);
    expect(c.tudoMarcado(undefined, 'navegador')).toBe(true);
    c.alternarGrupo(undefined, 'navegador');
    expect(c.marcada('contratos.a', 'navegador')).toBe(false);
  });

  it('o obrigatório continua marcado mesmo ao desmarcar o módulo e é enviado ao salvar só o que a pessoa escolheu', () => {
    const c = criar();
    c.alternar('contratos.a', 'desktop');
    c.salvar();
    expect(api.salvarPreferencias).toHaveBeenCalledTimes(1);
    const [canais] = api.salvarPreferencias.mock.calls[0];
    expect(canais['contratos.a']).toEqual(['desktop']);
    // O obrigatório não sai do conjunto (o servidor o mantém de qualquer jeito)
    expect(c.marcada('contratos.b', 'email')).toBe(true);
  });
});
