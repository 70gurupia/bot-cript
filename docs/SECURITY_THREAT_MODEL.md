# Modelo de Ameaças e Segurança Cibernética (Threat Model)

Este documento estabelece a análise formal de ameaças baseada na metodologia STRIDE e nos controles defensivos OWASP Proactive Controls para o ecossistema do Bot Cripto.

---

## 1. Princípios Fundamentais de Segurança

1. **Defesa em Profundidade (Zero-Trust)**: Nenhuma decisão proveniente de inteligência artificial ou de algoritmos genéticos tem permissão direta para enviar ordens sem validação por um validador determinístico imutável.
2. **Menor Privilégio Operacional (Least Privilege)**: As credenciais de acesso à exchange possuem apenas permissão de consulta e negociação. A permissão de saque (withdrawal) é estritamente proibida e desabilitada no painel da corretora.
3. **Imutabilidade e Restrição de Código**: Não é permitida a execução de strings geradas dinamicamente via interpretador. Todo código executado deriva de módulos estáticos predefinidos.

---

## 2. Matriz de Ameaças STRIDE

| Categoria STRIDE | Vetor de Ameaça Específico | Impacto Potencial | Mitigação Implementada |
|---|---|---|---|
| **Spoofing (Falsificação)** | Falsificação de mensagens de WebSocket ou ordens injetadas por intermediários na rede. | Execução de trades forçados ou manipulação de book de ofertas. | Conexão estrita via TLS 1.3, validação de certificados SSL e autenticação por assinaturas criptográficas HMAC-SHA256 geradas localmente. |
| **Tampering (Adulteração)** | Injeção de código malicioso no crossover genético ou modificação de arquivos de regras por agentes. | Execução Remota de Código (RCE) e sequestro do servidor de execução. | Proibição categórica de `eval()`, `exec()` e `__import__()`. O motor genético manipula apenas Árvores de Sintaxe Abstrata (AST) tipadas com validação via Pydantic. |
| **Repudiation (Repúdio)** | Incerteza sobre qual agente ou qual decisão de LLM gerou determinado prejuízo financeiro. | Dificuldade em auditar bugs ou responsabilizar estratégias defeituosas. | Registro imutável de auditoria local (SQLite) contendo ID do agente, ID do genitor, timestamp exato, justificativa do sinal e hash do estado de mercado. |
| **Information Disclosure (Vazamento de Informação)** | Vazamento de chaves secretas de API em logs, mensagens de erro ou capturas de tela do dashboard. | Terceiros realizam operações arbitrárias esgotando o saldo de margem. | Sanitizador central de logs com mascaramento de tokens, isolamento de chaves em variáveis de ambiente em memória não expostas no dashboard e restrição estrita de IP na exchange. |
| **Denial of Service (Negação de Serviço)** | Inundação de requisições à corretora gerando banimento temporário por Rate Limit ou travamento de CPU por mutações recursivas. | Perda de oportunidade, incapacidade de fechar posições abertas e liquidação forçada. | Rate limiter local baseado em Leaky Bucket, controle de concorrência com semáforos assíncronos e limitação de profundidade máxima de nós da AST (teto de 10 níveis). |
| **Elevation of Privilege (Elevação de Privilégio)** | Um agente em quarentena (incubadora) consegue acionar endpoints da exchange com saldo de dinheiro real. | Estratégia não testada perde capital financeiro real. | Separação física de adaptadores: a classe `PaperTradingExchange` simula ordens localmente sem instanciar chaves da corretora real. |

---

## 3. Segurança no Motor Genético: Prevenção de RCE

A maioria dos sistemas experimentais de programação genética em Python comete o erro crítico de manipular strings de código e executá-las dinamicamente. No Bot Cripto, isso é estruturalmente impedido.

### 3.1 Gramática Tipada em Árvore (DSL Declarativa)
O comportamento de um agente é representado exclusivamente como uma estrutura de dados de nós lógicos predefinidos:

```text
OperadorCondicional:
  - Condicao: Comparador(IndicadorA, OperadorLogico, IndicadorB)
  - AcaoVerdadeira: Ordem(Tipo, Ativo, LimiteRisco)
  - AcaoFalsa: ManterPosicao()
```

### 3.2 Validação Pré-Execução via Pydantic
Antes de qualquer avaliação de regras pelo motor, a árvore sintática é submetida a um esquema rígido de validação:
* **Profundidade Máxima**: A árvore não pode exceder 8 níveis de aninhamento para impedir estouro de pilha de recursão.
* **Catálogo Fechado de Nós**: Somente operadores matemáticos presentes em uma lista permitida (`ALLOWLIST_OPERATORS = {'maior', 'menor', 'cruzamento_alta', 'cruzamento_baixa', 'dentro_canal'}`) são aceitos.
* **Parâmetros Numéricos Delimitados**: Cada indicador técnico possui faixas válidas de operação (ex: período de média móvel restrito a inteiros entre 3 e 500).

---

## 4. Segurança do Supervisor LLM (OWASP LLM Top 10)

1. **LLM01: Prompt Injection**: Dados ingeridos da internet (notícias, posts em mídias sociais ou relatórios de análise) são tratados exclusivamente como conteúdo passivo (dados), nunca como instruções de execução.
2. **LLM02: Ação Excessiva (Excessive Agency)**: O supervisor LLM não possui ferramentas (tools) para enviar ordens diretamente à exchange. O seu único retorno aceito é uma estrutura JSON de classificação de regime de mercado (`BAIXA_VOLATILIDADE`, `ALTA_VOLATILIDADE`, `TENDENCIA_ALTA`, `TENDENCIA_BAIXA`) que ajusta apenas multiplicadores de risco no motor determinístico.
3. **LLM08: Manipulação Insegura de Saída (Insecure Output Handling)**: Toda resposta da LLM é parseada por um validador Pydantic. Se a resposta contiver campos inesperados ou valores fora do padrão pré-estabelecido, a saída é descartada e o sistema adota o modo padrão conservador.

---

## 5. Circuit Breaker Determinístico em Três Níveis

O Circuit Breaker opera de forma totalmente independente das estratégias e não pode ser desativado por nenhum agente:

```text
+--------------------------------------------------------------------------------+
|                         NÍVEL 1: PROTEÇÃO INDIVIDUAL (AGENTE)                  |
| Gatilho: Drawdown diário do agente individual >= 2.0%                          |
| Ação: Cancela ordens ativas do agente e transita o agente para estado PAUSED.  |
+--------------------------------------------------------------------------------+
                                       |
                                       v
+--------------------------------------------------------------------------------+
|                         NÍVEL 2: PROTEÇÃO GLOBAL DE PORTFÓLIO                  |
| Gatilho: Drawdown da carteira consolidada real >= 4.0% em 24 horas             |
| Ação: Encerramento a mercado de TODAS as posições abertas, cancelamento de    |
| todas as ordens pendentes e bloqueio de novos trades por 24 horas.             |
| Alerta vermelho imediato despachado via Telegram com hash de estado.           |
+--------------------------------------------------------------------------------+
                                       |
                                       v
+--------------------------------------------------------------------------------+
|                         NÍVEL 3: PROTEÇÃO DE INFRAESTRUTURA E REDE             |
| Gatilho: Inatividade de WebSocket / Heartbeat sem resposta por mais de 10 seg. |
| Ação: Ativação imediata de contingência via chamadas REST síncronas para checar|
| integridade de ordens e fechar posições alavancadas em risco.                  |
+--------------------------------------------------------------------------------+
```

---

## 6. Blindagem de Infraestrutura e Conexão com Corretora

* **Restrição de IP na Exchange**: A exchange é configurada para aceitar comandos de negociação exclusivamente do endereço IP estático associado ao servidor do usuário. Tentativas de acesso originadas de outros IPs são bloqueadas pelo servidor da exchange.
* **Isolamento de Container Docker Rootless**: O processo da aplicação roda sob usuário sem privilégios administrativos (`UID 1000`), sem permissão de escrita no sistema de arquivos do sistema operacional, exceto no diretório montado de dados do banco SQLite local.
* **Regras de Rede do Host (UFW)**: Portas de entrada fechadas por padrão. Apenas a porta do painel web local (ex: `127.0.0.1:8000`) é acessível via interface local (localhost).
