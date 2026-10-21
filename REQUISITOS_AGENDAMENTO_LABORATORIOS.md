# Requisitos de agendamento de laboratórios

## Objetivo

Evoluir a agenda de laboratórios do Helpdesk Manager para receber solicitações de professores, permitir análise pela equipe responsável e manter um histórico auditável de todas as solicitações e decisões.

## Laboratórios e capacidades

| Laboratório | Computadores |
|---|---:|
| Lab 05 | 32 |
| Lab 06 | 24 |
| Lab 07 | 24 |
| Lab 08 | 32 |

O sistema deve impedir confirmação de uma solicitação cuja quantidade de alunos seja superior à capacidade cadastrada para o laboratório.

## Solicitação pelo professor

Criar uma rota pública da intranet, protegida por autenticação, para professores:

```text
/agendamento-laboratorios
```

O formulário deve exigir:

- nome do professor;
- matrícula;
- laboratório solicitado;
- data e turno;
- título ou disciplina da aula;
- quantidade prevista de alunos;
- finalidade ou observações.

O link dessa rota poderá ser incluído posteriormente na intranet. A integração deve transmitir uma identidade autenticada do professor; não deve haver uma rota pública de envio sem autenticação.

## Fluxo de aprovação

1. O professor envia a solicitação.
2. O sistema grava data e hora de criação e atribui o status `solicitado`.
3. Uma notificação aparece para administradores e técnicos no Helpdesk Manager.
4. A equipe analisa as solicitações na ordem de chegada para o mesmo laboratório, data e turno.
5. A equipe confirma ou recusa a solicitação.
6. Quando confirmada, o status passa para `agendado` e o horário fica bloqueado.
7. O professor recebe uma mensagem de confirmação com laboratório, data, turno, quantidade de alunos e orientações.

Uma solicitação posterior para o mesmo horário não pode ultrapassar uma solicitação anterior. A confirmação deve usar bloqueio transacional para evitar duas confirmações concorrentes do mesmo slot.

## Painel de agenda

O painel deve mostrar, por laboratório e turno:

- estado: livre, solicitado, agendado ou indisponível;
- professor solicitante;
- disciplina ou atividade;
- quantidade de alunos e capacidade do laboratório;
- data e hora da solicitação;
- situação da análise;
- ações disponíveis para a equipe responsável.

## Notificações e confirmação

Ao receber uma nova solicitação, o sistema deve criar uma notificação interna para administradores e técnicos. A confirmação deve apresentar, no mínimo:

- código ou número da solicitação;
- laboratório confirmado;
- data e turno;
- nome do professor e matrícula;
- quantidade prevista de alunos;
- instruções de uso, cancelamento e contato de retorno.

## Histórico de solicitações e atendimentos

Criar um histórico vinculado a cada agendamento, registrando:

- criação da solicitação;
- confirmação, recusa, cancelamento ou exclusão;
- usuário responsável por cada ação;
- data e hora;
- justificativa ou observação da decisão;
- alterações de laboratório, data, turno ou quantidade de alunos.

O histórico deve funcionar como trilha de atendimento do chamado de agendamento e permanecer disponível mesmo se a reserva deixar de aparecer no painel ativo.

## Exclusão e cancelamento

Disponibilizar ação de excluir/cancelar agendamento para a equipe autorizada e, quando aplicável, para o professor que criou a solicitação.

Para preservar o histórico, a exclusão não deve apagar definitivamente os dados. O registro deve receber o status `cancelado` ou `excluido`, com o motivo, usuário responsável e data/hora da ação. Somente reservas com status `agendado` devem bloquear o horário.

## Dados a adicionar

Na solicitação ou agendamento:

- `professor_nome`;
- `professor_matricula`;
- `quantidade_alunos`;
- `status` com os valores `solicitado`, `agendado`, `recusado`, `cancelado` e `excluido`;
- `motivo_decisao`;
- `confirmado_por_id`;
- `confirmado_em`.

Em uma tabela de histórico:

- identificador do agendamento;
- tipo de evento;
- descrição ou justificativa;
- usuário responsável;
- data e hora.

## Critérios de aceite

- Professor autenticado consegue criar uma solicitação com todos os dados obrigatórios.
- Solicitação nova gera notificação interna para a equipe responsável.
- A equipe visualiza solicitações pendentes em ordem cronológica.
- O sistema não confirma duas reservas para o mesmo laboratório, data e turno.
- O sistema impede confirmação acima da capacidade do laboratório.
- A confirmação mostra a mensagem e as orientações de retorno.
- Cancelamento e exclusão preservam o histórico de atendimento.
- Painel mostra corretamente laboratórios livres, solicitados e agendados.
