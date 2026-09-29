# Especificação Matemática Avançada: Indicadores Geométricos, Newtonianos e Entrópicos

**Versão**: 1.0  
**Data**: 29/09/2026  
**Status**: Implementado e Validado em `strategy/trigonometric_adaptive_engine.py`  
**Escopo**: Transformação de Séries Temporais Financeiras em Espaço Vetorial Cartesiano com Mecânica Clássica, Geometria Diferencial e Termodinâmica Estatística  

---

## 1. Mapeamento Cartesiano Adimensional (Normalização por ATR)

A representação de preços de ativos com ordens de grandeza distintas (Bitcoin em dezenas de milhares de dólares e Dogecoin em frações de centavos) inviabiliza o cálculo angular ingênuo $\arctan(\Delta P / \Delta t)$.

Para tornar o espaço cartesiano universal e adimensional, cada incremento de preço é normalizado pelo Average True Range (ATR) de 14 períodos:

$$\Delta x = \Delta t \quad (\text{passos temporais em barras})$$
$$\Delta y = \frac{P_t - P_{t-\Delta t}}{\text{ATR}_{14}(t)} \quad (\text{deslocamento em unidades de volatilidade})$$

Desta forma, uma variação de 2 ATRs no Bitcoin e 2 ATRs no Cardano projetam vetores matematicamente idênticos no plano cartesiano $\mathbb{R}^2$.

---

## 2. Decomposição Trigonométrica e Identidade Fundamental

A partir do vetor $\vec{v} = (\Delta x, \Delta y)$, calculamos as projeções no círculo unitário:

1. **Inclinação Angular ($\theta$)**:
   $$\theta = \arctan\left(\frac{\Delta y}{\Delta x}\right) \in \left[-\frac{\pi}{2}, +\frac{\pi}{2}\right]$$
2. **Velocidade Linear Instantânea ($\tan(\theta)$)**:
   $$\tan(\theta) = \frac{\Delta y}{\Delta x} = \text{Slope}$$
3. **Força Direcional Vertical ($\sin(\theta)$)**:
   $$\sin(\theta) \in [-1.0, +1.0]$$
   Mede a tração vertical pura. Em quedas verticais, $\sin(\theta) \to -1.0$; em rallies parabólicos, $\sin(\theta) \to +1.0$.
4. **Inércia Temporal Horizontal ($\cos(\theta)$)**:
   $$\cos(\theta) \in [0.0, 1.0]$$
   Mede a persistência no tempo. Em consolidações horizontais, $\cos(\theta) \to 1.0$.
5. **Identidade Trigonométrica Invariante**:
   $$\sin^2(\theta) + \cos^2(\theta) = 1.0$$
6. **Aceleração Angular ($\alpha = \frac{d\theta}{dt}$)**:
   $$\alpha_t = \theta_t - \theta_{t-1}$$
   Sinaliza a derivada da força. Quando $\theta > 0$ mas $\alpha < 0$, o preço sobe porém a inclinação começa a achatar, gerando a **Divergência de Exaustão Angular**.

---

## 3. Momento Linear Newtoniano com Massa de Volume

Na mecânica clássica, momentum é o produto da massa pela velocidade ($p = m \cdot v$). No mercado financeiro, a velocidade pura sem volume é manipulável por livros de ofertas vazios.

Definimos a **Massa de Volume Normalizada ($m$)**:
$$m_t = \frac{\text{Volume}_t}{\text{SMA}_{20}(\text{Volume})}$$

A **Força de Momento Vetorial ($F_y$)**:
$$F_y = \sin(\theta) \cdot m_t$$

* **Interpretação**:
  * Rompimento com ângulo de $30^\circ$ ($\sin \approx 0.50$) e volume fraco ($m = 0.5$): $F_y = 0.25$ (sinal desconsiderado por falta de inércia institucional).
  * Rompimento com o mesmo ângulo e volume institucional ($m = 2.0$): $F_y = 1.00$ (sinal acionado com confiança máxima).

---

## 4. Geometria Diferencial: Curvatura ($\kappa$) e Raio de Curvatura ($R$)

A trajetória contínua do preço pode ser aproximada por uma função $y = f(x)$. A curvatura $\kappa$ descreve o quão rápido a reta tangente gira ao longo da curva:

$$\kappa = \frac{|y''|}{(1 + y'^2)^{3/2}} = \frac{\left|\frac{d(\tan\theta)}{dt}\right|}{(1 + \tan^2\theta)^{3/2}}$$

O **Raio de Curvatura ($R$)**:
$$R = \frac{1}{\kappa}$$

* **Aplicação em Topos e Fundos**:
  * Em consolidações retas: $\kappa \approx 0 \implies R \to \infty$.
  * Em topos arredondados (Rounding Tops) ou fundos em "U" (Rounding Bottoms): $R$ atinge um ponto de mínimo local. A desaceleração de $\kappa$ antecipa o ponto de inflexão antes do rompimento da média móvel.

---

## 5. Termodinâmica Estatística: Entropia Não-Extensiva de Tsallis

A Entropia de Shannon padrão assume a hipótese aditiva com distribuições gaussianas. Porém, retornos financeiros apresentam **caudas pesadas (fat tails)**.

A **Entropia de Tsallis ($S_q$)**:
$$S_q = \frac{1 - \sum_{i=1}^k p_i^q}{q - 1}$$

Com índice não-extensivo ajustado para $q = 1.5$:
* Normalizada no intervalo $[0, 1]$ dividindo pelo valor de entropia máxima uniforme:
  $$S_{q,\max} = \frac{1 - k^{1-q}}{q - 1}$$
* Maior sensibilidade na detecção de transições de fase e acúmulo de risco sistêmico antes de grandes descolamentos de preço.

---

## 6. Média Móvel Adaptativa Trigonométrica (TAMA)

A constante de suavização $\alpha$ adapta-se continuamente com base na componente perpendicular da força:

$$\alpha_t = \alpha_{\text{lento}} + (\alpha_{\text{rápido}} - \alpha_{\text{lento}}) \cdot \sin^2(\theta)$$

Onde $\alpha_{\text{rápido}} = \frac{2}{4 + 1} = 0.40$ e $\alpha_{\text{lento}} = \frac{2}{30 + 1} = 0.0645$.
* **Mercado Lateral**: $\sin(\theta) \to 0 \implies \alpha \to 0.0645$ (comportamento suave, sem oscilação).
* **Movimento Explosivo**: $|\theta| > 45^\circ \implies \sin^2(\theta) > 0.50 \implies \alpha \to 0.25 - 0.40$ (acompanhamento quase instantâneo, reduzindo o atraso para zero).

---

## 7. Trailing Stop Dinâmico Modularizado pelo Cosseno

Em tendências parabólicas, stops fixos em ATR devolvem grande parte dos lucros na reversão.
Modularizamos a distância do stop pela inércia temporal:

$$\text{Distância do Stop} = \text{ATR} \cdot 1.5 \cdot \max(0.40, \cos\theta)$$

Conforme $\theta \to 60^\circ \implies \cos(\theta) \to 0.50$, o stop loss encurta em 50%, colando na mínima da vela anterior e protegendo o lucro no ápice da parábola.
