# Protocolo experimental — ADIA-CognitiveLoop

Protocolo do estudo, janelas temporais e regime de retenção de dados.

> **Estado deste documento.** As seções
> [Fase 7](#fase-7--piloto-com-estudantes-reais-depende-de-aprovação-externa) e
> [Retenção e exclusão](#retenção-e-exclusão-de-dados-de-estudante) são a entrega da tarefa
> 1.1 e cumprem R25.9 e R25.7: estão completas e são autoritativas. As demais seções estão
> em esqueleto e serão preenchidas pelas tarefas que produzem o comportamento
> correspondente, indicadas em cada uma.

---

## Fase 7 — piloto com estudantes reais depende de aprovação externa

**Cumpre R25.9.**

A **Fase 7 do roteiro — o piloto com estudantes reais — está fora do escopo desta spec e
não pode começar com base em nenhuma autorização concedida dentro deste software.** Ela
depende de duas condições obtidas **fora** do protótipo:

1. **Consentimento informado** de cada participante e, para participante menor de idade,
   consentimento do responsável legal somado ao assentimento do próprio participante.
2. **Aprovação ética institucional**, emitida pelo comitê competente da instituição
   responsável pelo estudo, cobrindo o instrumento, o protocolo, o tratamento de dados e o
   prazo de retenção.

Três consequências que o leitor precisa levar daqui:

- **Nenhum controle deste software substitui essas condições.** O protótipo não tem tela de
  consentimento, não grava termo assinado e não verifica aprovação de comitê. A ausência
  dessas funções é deliberada: um registro de consentimento dentro da aplicação criaria a
  aparência de conformidade sem o processo que a produz, e seria a pior das duas falhas
  possíveis.
- **O que esta spec entrega é o instrumento, não a autorização para usá-lo com pessoas.**
  As Fases 0 a 6 tornam o protótipo capaz de coletar dados válidos. A decisão de coletar
  com estudantes reais é externa, anterior e de outra natureza.
- **Dados sintéticos não dependem de nada disso.** As trajetórias do `Simulador_de_Alunos`
  são geradas e marcadas como sintéticas, e as exportações permitem separá-las de sessões
  humanas. Validação técnica, análise de poder e treino exploratório do `Modelo_DKT` rodam
  inteiramente sobre esses dados, sem participante humano.

O piloto será tratado em **spec separada**, cuja primeira pré-condição é a existência
documentada das duas aprovações acima.

---

## Retenção e exclusão de dados de estudante

**Cumpre R25.7.** O valor e a justificativa do prazo estão registrados em
[`decisoes.md`](decisoes.md) como **DO-14**.

**Prazo de retenção: 180 dias contados da conclusão do teste de retenção da sessão.**

| Aspecto | Regra |
| --- | --- |
| Marco inicial da contagem | Conclusão do teste de retenção da sessão do participante, não a criação do participante |
| Prazo padrão | 180 dias |
| Onde o prazo é gravado | Campo `retencao_ate` do registro de participante, preenchido na criação |
| Ação ao expirar | Exclusão dos dados de estudante daquele participante, por comando dedicado da interface de linha de comando |
| Registro da exclusão | A execução da exclusão é ela própria registrada, com data e escopo do que foi excluído |
| Prevalência | Prazo menor imposto pela aprovação ética institucional **prevalece** sobre os 180 dias |

Pontos de regime que acompanham o prazo:

- **Processamento exclusivamente local.** Todos os dados de estudante são processados e
  armazenados na máquina local. Nenhum serviço externo ou em nuvem participa de nenhum
  caminho de código (R25.1).
- **Pseudonimização em todo registro operacional.** O log de eventos armazena apenas
  pseudônimos gerados pelo sistema, sem nome, documento, endereço de e-mail ou qualquer
  outro identificador direto (R25.2, R25.3).
- **Mapa de identidade fora do banco e fora das exportações.** A associação entre
  pseudônimo e identidade, quando necessária, vive em arquivo separado do banco
  operacional, em `data/identidade/`, fora do escopo de qualquer exportação (R25.4, R25.5).
  Esse diretório é mantido fora do controle de versão (ver DO-13 em
  [`decisoes.md`](decisoes.md)).
- **Minimização.** São coletados apenas os dados necessários ao cálculo das métricas
  declaradas e ao registro de proveniência (R25.6).
- **Limite de interpretação declarado na interface.** Onde métrica de confiança ou de
  desempenho é apresentada, a interface declara que as métricas descrevem desempenho em
  tarefas do estudo e **não** constituem diagnóstico psicológico, avaliação clínica nem
  medida de inteligência (R25.8).

---

## Janelas temporais do protocolo

A janela do teste de retenção é decisão registrada e já vale como especificação:

| Janela | Regra | Origem |
| --- | --- | --- |
| Teste de retenção | Abaixo de 168 h após a conclusão do pós-teste não libera; de 168 a 216 h libera dentro do protocolo; acima de 216 h libera, aceita as respostas e marca a sessão como fora de protocolo com o desvio em horas registrado | R12.4 a R12.6; DO-08 |
| Inatividade que interrompe a sessão | A definir | DO pendente |

---

## Seções em esqueleto

As seções abaixo têm destino declarado neste arquivo mas conteúdo produzido por tarefas
posteriores. Nenhuma delas é pré-condição da tarefa 1.1.

### Condições experimentais

Composição de A, B e C, o que cada uma mantém de registro sombra e como a condição é
atribuída a uma sessão. A regra de atribuição balanceada já está registrada como DO-07 em
[`decisoes.md`](decisoes.md). O diagrama canônico é
`diagramas/condicoes-experimentais.excalidraw`.

*Preenchida pela tarefa que implementa o `Gestor_de_Sessão` e a atribuição de condição.*

### Estrutura de uma sessão

Onboarding, linha de base, os três ciclos de prática assistida e desafio independente,
pós-teste, projeto STEAM e teste de retenção, com a máquina de estados e a matriz de
operações permitidas por etapa.

*Preenchida pela tarefa que implementa o `Gestor_de_Sessão`.*

### Regra de regulação do teto de suporte

Condições de *fading* e de *onloading*, precedência entre elas, saturação nas bordas e o
registro sombra. O diagrama canônico é `diagramas/regra-regulacao.excalidraw`.

*Preenchida pela tarefa que implementa o `Núcleo_de_Regulação`.*

### Métricas do estudo

TAI, TT, ICM, DSS, IIC e retenção: definição, escopo de cálculo e limites de interpretação
de cada uma.

*Preenchida pela tarefa que implementa a `Calculadora_de_Métricas`.*
