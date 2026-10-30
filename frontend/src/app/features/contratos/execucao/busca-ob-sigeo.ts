// Criado por José Eduardo Santana Martins
// Este arquivo serve para buscar, a pedido da tela, a OB de uma competência no SIGEO e mostrar o resultado.

import { DialogosService } from '../../../shared/servicos/dialogos.service';
import { DetalheCompetencia } from '../compartilhado/contratos.models';
import { ExecucaoApiService } from '../compartilhado/execucao-api.service';

/** Pergunta se a pessoa quer buscar a OB no SIGEO agora (usado ao juntar a nota fiscal de uma competência retroativa). */
export async function oferecerBuscaObSigeo(api: ExecucaoApiService, dialogos: DialogosService, d: DetalheCompetencia, aoAtualizar: (novo: DetalheCompetencia) => void): Promise<void> {
  const ok = await dialogos.confirmar({
    titulo: 'Buscar a OB no SIGEO agora?',
    mensagem: 'Esta competência é anterior ao corte de alertas: só precisa de medição, nota fiscal e OB.\n\nO contrato tem Processo Financeiro, então o SGI pode procurar agora a OB paga deste mês no SIGEO e concluir a competência. Se você cancelar, a OB é buscada na próxima conferência geral do sistema.',
    rotuloConfirmar: 'Sim, buscar agora',
  });
  if (ok) buscarObNoSigeo(api, dialogos, d, aoAtualizar);
}

/** Busca a OB no SIGEO e conta o que aconteceu (concluída, ainda não saiu ou motivo da dúvida); depois a tela recarrega a competência. */
export function buscarObNoSigeo(api: ExecucaoApiService, dialogos: DialogosService, d: DetalheCompetencia, aoAtualizar: (novo: DetalheCompetencia) => void): void {
  dialogos.executar(api.buscarObSigeo(d.contrato_id, d.id), 'Consultando o SIGEO…').subscribe({
    next: (r) => {
      // Recarrega a competência (se concluiu, a etapa mudou) e conta o resultado
      api.porIdentificador(d.contrato_id, d.identificador).subscribe((novo) => aoAtualizar(novo));
      dialogos.avisar(r.concluida ? 'OB encontrada' : 'OB ainda não conferida', r.mensagem);
    },
    error: (e) => dialogos.mostrarErro(e, 'Não foi possível buscar a OB no SIGEO'),
  });
}
