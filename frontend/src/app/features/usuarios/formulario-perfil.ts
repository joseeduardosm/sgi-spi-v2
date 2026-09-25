// Criado por José Eduardo Santana Martins
// Este arquivo serve para criar, preencher e ler o formulário do perfil institucional (funções reutilizáveis).

import { FormGroup, NonNullableFormBuilder, Validators } from '@angular/forms';

import { OpcaoUsuario } from '../../core/modelos/usuario.model';
import { CAMPOS_OBRIGATORIOS_PERFIL, DadosPerfil, PerfilLeitura } from './usuarios.models';

/** Formulário do perfil institucional, compartilhado por "Meu perfil" e pelo cadastro de usuários. */
export function criarFormularioPerfil(construtor: NonNullableFormBuilder, exigirObrigatorios: boolean) {
  // Validação "obrigatório" só nos campos obrigatórios, e só quando a tela exige (em "Meu perfil")
  const obrigatorio = (campo: string) =>
    exigirObrigatorios && CAMPOS_OBRIGATORIOS_PERFIL.includes(campo) ? [Validators.required] : [];
  return construtor.group({
    nome_completo: ['', [...obrigatorio('nome_completo'), Validators.maxLength(200)]],
    email: ['', [...obrigatorio('email'), Validators.email, Validators.maxLength(254)]],
    ramal: ['', [...obrigatorio('ramal'), Validators.maxLength(20)]],
    celular: ['', Validators.maxLength(30)],
    cargo: ['', [...obrigatorio('cargo'), Validators.maxLength(150)]],
    departamento: ['', [...obrigatorio('departamento'), Validators.maxLength(150)]],
    andar: ['', [...obrigatorio('andar'), Validators.maxLength(30)]],
    predio: ['', [...obrigatorio('predio'), Validators.maxLength(100)]],
    data_nascimento: [''],
  });
}

/** Tipo do formulário criado acima (deduzido automaticamente pelo TypeScript). */
export type FormularioPerfil = ReturnType<typeof criarFormularioPerfil>;

/** Preenche o formulário com o perfil (ou limpa, se vier vazio). */
export function preencherFormularioPerfil(formulario: FormularioPerfil, perfil: Partial<PerfilLeitura> | null): void {
  formulario.reset({
    nome_completo: perfil?.nome_completo ?? '',
    email: perfil?.email ?? '',
    ramal: perfil?.ramal ?? '',
    celular: perfil?.celular ?? '',
    cargo: perfil?.cargo ?? '',
    departamento: perfil?.departamento ?? '',
    andar: perfil?.andar ?? '',
    predio: perfil?.predio ?? '',
    data_nascimento: perfil?.data_nascimento ?? '',
  });
}

/** Lê o formulário no formato da API: data vazia vira null e o gestor vem do seletor. */
export function dadosDoFormularioPerfil(formulario: FormGroup, gestorId: number | null): DadosPerfil {
  const valores = formulario.getRawValue();
  return { ...valores, data_nascimento: valores.data_nascimento || null, gestor_id: gestorId };
}

/** Gestor atual como opção do seletor (a API devolve só id e nome). */
export function gestorComoOpcao(perfil: Partial<PerfilLeitura> | null | undefined): OpcaoUsuario[] {
  return perfil?.gestor_id
    ? [{ id: perfil.gestor_id, nome_completo: perfil.gestor_nome ?? '', login: '', cargo: '', ativo: true }]
    : [];
}
