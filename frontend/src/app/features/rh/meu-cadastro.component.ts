// Criado por José Eduardo Santana Martins
// Este arquivo serve para a tela "Meu cadastro funcional": a bio opcional (com a opção de liberá-la na busca) e a ficha cadastral que o RH valida.

import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { DialogosService } from '../../shared/servicos/dialogos.service';
import { CabecalhoRhComponent } from './cabecalho-rh.component';
import { FichaPreCadastroComponent } from './ficha-pre-cadastro.component';
import { RhAdmissaoApiService } from './rh-admissao-api.service';

/** Meu cadastro funcional: a bio e a ficha cadastral da própria pessoa. Só a pessoa e o RH veem a ficha; a bio só aparece para os outros se for liberada. */
@Component({
  selector: 'app-meu-cadastro',
  imports: [FormsModule, CabecalhoRhComponent, FichaPreCadastroComponent],
  template: `
    <app-cabecalho-rh titulo="Meu cadastro funcional" [trilha]="['Meu cadastro']" descricao="Conte um pouco sobre você e mantenha seus dados cadastrais em dia." />

    <div class="parametros-rh"><div class="sem-borda">
      <section class="cartao-dados" aria-labelledby="sec-bio">
        <header><div><h2 id="sec-bio">Bio</h2><small>Idade, formação, experiências... É opcional.</small></div></header>
        <div class="corpo">
          <div class="campo"><label for="bio-texto">Sobre mim</label><textarea id="bio-texto" name="bio" rows="5" maxlength="3000" [(ngModel)]="texto"></textarea>
            <small class="ajuda">{{ texto.length }}/3000</small></div>
          <div class="opcoes-parametros" style="margin-top: 14px">
            <label class="opcao"><input type="checkbox" name="bio-visivel" [(ngModel)]="visivel" [disabled]="!texto.trim()" />
              <span><strong>Mostrar minha bio para os colegas</strong><small>Libera a bio na busca de usuários e no meu cartão de contato. Sem liberar, só eu a vejo.</small></span></label>
          </div>
          <div class="acoes-formulario" style="margin-top: 12px"><button type="button" class="acao-primaria" [class.carregando]="salvando()" (click)="salvar()">Salvar bio</button></div>
        </div>
      </section>
    </div></div>

    <app-ficha-pre-cadastro [minha]="true" />
  `,
})
export class MeuCadastroComponent implements OnInit {
  private readonly api = inject(RhAdmissaoApiService);
  private readonly dialogos = inject(DialogosService);

  protected readonly salvando = signal(false);
  protected texto = '';
  protected visivel = false;

  ngOnInit(): void {
    this.api.minhaBio().subscribe({ next: (b) => { this.texto = b.bio_texto; this.visivel = b.bio_visivel; }, error: (e) => this.dialogos.mostrarErro(e, 'Não foi possível carregar a sua bio') });
  }

  protected salvar(): void {
    this.salvando.set(true);
    this.api.salvarBio({ bio_texto: this.texto, bio_visivel: this.visivel }).subscribe({
      next: (b) => { this.salvando.set(false); this.texto = b.bio_texto; this.visivel = b.bio_visivel; this.dialogos.avisar('Bio salva', b.bio_visivel ? 'Sua bio aparece na busca e no cartão de contato.' : 'Só você vê a sua bio.'); },
      error: (e) => { this.salvando.set(false); this.dialogos.mostrarErro(e, 'Não foi possível salvar a bio'); },
    });
  }
}
