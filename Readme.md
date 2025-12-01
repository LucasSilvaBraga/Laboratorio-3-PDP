# Sistema Distribuído de Mineração com Eleição de Líder

## 1. Introdução

**Alunos: Lucas Silva Braga e Davi Vittore Loriato**

Este projeto implementa um sistema distribuído baseado no modelo de comunicação indireta Publish/Subscribe (Pub/Sub) utilizando o protocolo MQTT. O sistema simula um resolvedor de provas de trabalho (proof-of-work) similar ao utilizado em mineradores de criptomoedas, com eleição distribuída de um coordenador (líder) e coordenação para resolução de desafios criptográficos.



## 2. Objetivos

- Utilizar comunicação indireta por meio de middleware Pub/Sub com filas de mensagens.
- Realizar eleição de coordenador em sistemas distribuídos por meio de troca de mensagens.
- Realizar votação sobre o estado de transações distribuídas por meio de troca de mensagens.

## 3. Metodologia de Implementação

### 3.1 Arquitetura do Sistema

O sistema é composto por múltiplos nós (processos) que se comunicam através de um broker MQTT. Cada nó executa simultaneamente os papéis de minerador e controlador, alternando entre eles conforme o resultado de uma eleição distribuída.

### 3.2 Estados do Sistema

Cada nó passa por três estados principais:

1. **INIT**: Fase de inicialização e descoberta dos demais nós.
2. **ELECTION**: Fase de eleição do líder utilizando votação distribuída.
3. **CHALLENGE**: Fase de mineração, onde o líder publica desafios e os mineradores tentam resolvê-los.

### 3.3 Comunicação MQTT

Foram definidos os seguintes tópicos para comunicação:

- `sd_{session_id}/init`: Mensagens de inicialização dos nós.
- `sd_{session_id}/voting`: Mensagens de votação para eleição do líder.
- `sd_{session_id}/challenge`: Desafios criptográficos publicados pelo líder.
- `sd_{session_id}/solution`: Soluções propostas pelos mineradores.
- `sd_{session_id}/result`: Resultados da validação das soluções pelo líder.

### 3.4 Algoritmo de Eleição

1. Cada nó gera um ID único de 16 bits (ClientID) e um número aleatório de 16 bits (VoteID).
2. Os nós trocam mensagens de inicialização até que todos estejam cientes dos demais.
3. Cada nó publica seu voto (VoteID) no tópico de votação.
4. Após receber todos os votos, o nó com maior VoteID é eleito líder (em caso de empate, usa-se o maior ClientID).
5. Todos os nós transitam para o estado de desafio, com o líder assumindo o papel de controlador.

### 3.5 Mineração e Validação

- O líder gera desafios criptográficos com diferentes níveis de dificuldade (número de zeros iniciais no hash SHA-1).
- Os mineradores tentam encontrar uma string cujo hash SHA-1 comece com a quantidade especificada de zeros.
- Quando um minerador encontra uma solução, a envia ao líder para validação.
- O líder verifica se a transação está pendente e se a solução atende aos requisitos do desafio.
- O resultado da validação é publicado para todos os nós.

### 3.6 Tolerância a Falhas

- Implementação de timeout na fase de eleição para evitar travamentos caso mensagens sejam perdidas.
- Reenvio periódico de mensagens de inicialização até que todos os nós estejam sincronizados.

## 4. Testes e Resultados

### 4.1 Ambiente de Teste

- Sistema operacional: Windows 11
- Linguagem: Python 3.x
- Broker MQTT: broker.hivemq.com (público) na porta 1883
- Bibliotecas: paho-mqtt

### 4.2 Cenários de Teste

#### Teste 1: Sincronização Inicial
**Objetivo:** Verificar se os nós conseguem se descobrir mutuamente e sincronizar.
**Resultado:** Todos os três nós trocaram mensagens de INIT e alcançaram a condição de sincronização, passando para a fase de eleição.

#### Teste 2: Eleição do Líder
**Objetivo:** Validar o algoritmo de eleição distribuída.
**Resultado:** O nó com maior VoteID foi corretamente eleito líder, e todos os nós concordaram com o resultado. Em casos de perda de mensagens, o timeout garantiu a continuidade do sistema.

#### Teste 3: Mineração Colaborativa
**Objetivo:** Testar a geração de desafios, mineração e validação de soluções.
**Resultado:** O líder publicou três desafios com diferentes dificuldades. Os mineradores encontraram soluções e o líder validou corretamente, aceitando apenas soluções que atendiam aos critérios criptográficos.

#### Teste 4: Tolerância a Falhas
**Objetivo:** Verificar a recuperação do sistema em caso de perda de mensagens.
**Resultado:** O timeout de 10 segundos na eleição permitiu que nós que não receberam todos os votos continuassem o processamento, mantendo a consistência do sistema.

### 4.3 Métricas Coletadas

- **Tempo de sincronização:** 2-5 segundos para 3 nós
- **Tempo de eleição:** 1-10 segundos (dependendo da entrega de mensagens)
- **Tempo de mineração:** Variável conforme a dificuldade (dificuldade 1: <1s, dificuldade 2: 0-5s)
- **Taxa de sucesso na mineração:** 100% dos desafios foram resolvidos

## 5. Conclusões

O sistema implementado atende a todos os requisitos do laboratório, demonstrando:

1. **Comunicação indireta eficiente** utilizando o padrão Pub/Sub sobre MQTT.
2. **Eleição distribuída robusta** que seleciona um líder de forma consensual.
3. **Coordenação eficaz** para resolução de desafios criptográficos.
4. **Tolerância a falhas** com mecanismos de timeout e reenvio de mensagens.

A arquitetura proposta mostrou-se adequada para sistemas distribuídos que requerem coordenação e processamento colaborativo, sendo extensível para um maior número de nós e cenários mais complexos.

## 6. Instruções de Execução

### Pré-requisitos
- Python 3.x instalado
- Biblioteca paho-mqtt instalada (`pip install paho-mqtt`)

### Execução
1. Clone o repositório ou copie os arquivos do projeto.
2. Execute o script principal:
   ```bash
   python run_corrected_system.py