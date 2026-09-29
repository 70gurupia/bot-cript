# Arquitetura do Pipeline Alfa Unificado (Unified Alpha Pipeline)

**Status**: 100% Implementado, Testado e Integrado  
**Módulo**: `strategy/unified_alpha_pipeline.py`  
**Suíte de Testes**: `tests/test_unified_alpha_pipeline.py` (31/31 suítes aprovadas)  
**Complexidade Ciclomática**: 413 funções auditadas, todas `<= 10`  

---

## 1. Visão Geral da Arquitetura de Ponta a Ponta

O Pipeline Alfa Unificado resolve o elo entre os modelos matemáticos teóricos e a execução real de ordens no mercado cripto, orquestrando cinco camadas em uma única chamada determinística `process_market_tick()`:

```
Vela Atual (OHLCV 15m) + Livro de Ofertas + Funding Rate
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│ 1. Camada Física e Geométrica (Geração 3 Newtoniana)   │
│    • Vetor Cartesiano Normalizado: theta, sin, cos     │
│    • Massa de Volume e Momento: Fy = sin(theta) * m    │
│    • Entropia de Tsallis q = 1.5 (Caudas Pesadas)      │
│    • Média Móvel Adaptativa TAMA (Modulação sin^2)     │
└────────────────────────────┬───────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────┐
│ 2. Camada de Microestrutura e Macro-Sentimento         │
│    • Filtro Contracíclico de Funding Rate (Anti-Squeeze)│
│    • Desequilíbrio do Livro (Order Book Imbalance OBI) │
└────────────────────────────┬───────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────┐
│ 3. Camada de Dimensionamento e Gestão de Capital       │
│    • Motor Anti-Martingale (Expansão Geométrica +25%)  │
│    • Travas do Cofre Inviolável (Ratchet Vault)        │
└────────────────────────────┬───────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────┐
│ 4. Camada de Execução Inteligente (Maker Post-Only)    │
│    • Smart Order Router: Entrada no Best Bid / Ask     │
│    • Economia de 50% de Taxas (0.02% vs 0.04%)         │
│    • Trailing Stop Dinâmico Modularizado por Cosseno   │
│    • Trava de Fuga de Preço (Máximo 0.20 ATR)          │
└────────────────────────────┬───────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────┐
│ 5. Camada de Telemetria e Alertas (Telegram / Webhook) │
│    • Mensagens Ricas Formatadas                        │
│    • Notificações de Travamento de Cofre e Streaks     │
│    • Fechamento Diário EOD Flat (23:45 UTC)            │
└────────────────────────────────────────────────────────┘
```

---

## 2. Invariantes de Segurança Garantidos por Código

1. **Invariante do Cofre**: O capital transferido para o Cofre Inviolável (Ratchet Vault) nunca sofre drawdown posterior.
2. **Invariante de Execução Maker**: Ordens de mercado nunca são enviadas de forma agressiva (Taker), garantindo que as taxas não consumam a micro-banca.
3. **Invariante de Exclusão de Ruído**: Sinais sem confluência de volume ($|F_y| < 0.45$) ou com divergência no livro de ofertas ($\text{OBI} < -0.30$ para compras) são descartados na origem.
