// Criado por José Eduardo Santana Martins
// Este arquivo serve para iniciar a aplicação Angular no navegador (ponto de entrada do frontend).

import { bootstrapApplication } from '@angular/platform-browser';

import { Aplicacao } from './app/app';
import { configuracaoAplicacao } from './app/app.config';

// Monta o componente raiz com a configuração global (rotas, HTTP, inicialização da sessão).
// Qualquer falha ao iniciar aparece no console do navegador.
bootstrapApplication(Aplicacao, configuracaoAplicacao).catch((erro) => console.error(erro));
