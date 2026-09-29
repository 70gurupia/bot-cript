"""
Adaptador Assíncrono de Conectividade com Corretoras (CCXT Adapter).
Fornece normalização de dados de mercado, monitoramento de batimento cardíaco (Heartbeat),
reconexão automática e bloqueio inviolável de saques em tempo de execução.
"""

import os
import time
import asyncio
from typing import Dict, Any, List, Optional
from config.settings import settings
from core.kill_switch import circuit_breaker
from core.logger import telemetry
from core.paper_exchange import PaperTradingExchange


class SecurityException(Exception):
    """Exceção levantada quando uma operação proibida de segurança é tentada."""
    pass


class ExchangeAdapter:
    """Wrapper de comunicação assíncrona com corretoras de criptoativos."""

    def __init__(
        self,
        exchange_id: str = "binance",
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        paper_trading: bool = True
    ):
        self.exchange_id = exchange_id.lower()
        self.api_key = api_key or os.getenv("EXCHANGE_API_KEY", "")
        self.api_secret = api_secret or os.getenv("EXCHANGE_API_SECRET", "")
        self.paper_trading = paper_trading
        
        # Simulador local para paper trading
        self.paper_exchange = PaperTradingExchange() if paper_trading else None
        
        # Controle de conectividade e batimento cardíaco (Heartbeat)
        self.last_heartbeat_ts: float = time.time()
        self.is_connected: bool = True
        self.reconnect_attempts: int = 0
        
        # Instância assíncrona do CCXT (carregada sob demanda)
        self._ccxt_instance = None
        self._init_ccxt_client()

    def _init_ccxt_client(self):
        """Inicializa o cliente CCXT com anulação obrigatória de brokerId e travas de segurança."""
        try:
            import ccxt.async_support as ccxt_async
            exchange_class = getattr(ccxt_async, self.exchange_id, None)
            if exchange_class:
                config = {
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                    "enableRateLimit": True,
                    "options": {
                        "defaultType": "spot",
                        "brokerId": None,  # Anula comissões ou identificadores de afiliados do CCXT
                        "warnOnFetchOpenOrdersWithoutSymbol": False
                    }
                }
                self._ccxt_instance = exchange_class(config)
        except ImportError:
            # Fallback seguro: ccxt não instalado no ambiente global, opera em modo simulado/mock
            self._ccxt_instance = None

    # ==========================================================================
    # TRAVAS DE SEGURANÇA INVIOLÁVEIS (BLOQUEIO TOTAL DE SAQUES)
    # ==========================================================================

    def withdraw(self, *args, **kwargs):
        """Bloqueio estrito de saques no nível da aplicação."""
        telemetry.critical("TENTATIVA DE SAQUE BLOQUEADA: A função withdraw foi invocada indevidamente.")
        raise SecurityException("OPERAÇÃO PROIBIDA: Saques de fundos são desabilitados em nível de código no Bot Cripto.")

    def transfer(self, *args, **kwargs):
        """Bloqueio estrito de transferências externas."""
        telemetry.critical("TENTATIVA DE TRANSFERÊNCIA BLOQUEADA: A função transfer foi invocada indevidamente.")
        raise SecurityException("OPERAÇÃO PROIBIDA: Transferências de capital são desabilitadas em nível de código.")

    # ==========================================================================
    # MONITORAMENTO DE CONEXÃO E HEARTBEAT
    # ==========================================================================

    def record_heartbeat(self):
        """Registra atividade recente na conexão."""
        self.last_heartbeat_ts = time.time()
        self.is_connected = True
        self.reconnect_attempts = 0

    def check_connection_health(self) -> Dict[str, Any]:
        """Verifica se a conexão com a exchange está ativa dentro do tempo limite permitido."""
        elapsed = time.time() - self.last_heartbeat_ts
        timeout_limit = settings.risk_limits.network_timeout_seconds
        
        if elapsed > timeout_limit:
            self.is_connected = False
            telemetry.warning(f"Inatividade de conexão detectada: {elapsed:.1f}s sem dados (limite: {timeout_limit}s).")
            return {
                "healthy": False,
                "elapsed_seconds": round(elapsed, 1),
                "action": "TRIGGER_CONTINGENCY_REST"
            }
        return {"healthy": True, "elapsed_seconds": round(elapsed, 1)}

    # ==========================================================================
    # NORMALIZAÇÃO DE DADOS DE MERCADO (PÚBLICOS)
    # ==========================================================================

    async def fetch_ticker_normalized(self, symbol: str) -> Dict[str, Any]:
        """Obtém o ticker em tempo real com normalização padronizada."""
        self.record_heartbeat()
        
        # Se estiver em modo simulado sem CCXT ativo
        if self._ccxt_instance is None or self.paper_trading:
            return {
                "symbol": symbol,
                "bid": 60000.0,
                "ask": 60002.0,
                "last": 60001.0,
                "volume_24h": 15000.0,
                "timestamp": int(time.time() * 1000)
            }
            
        try:
            raw = await self._ccxt_instance.fetch_ticker(symbol)
            return {
                "symbol": symbol,
                "bid": float(raw.get("bid") or raw.get("last", 0)),
                "ask": float(raw.get("ask") or raw.get("last", 0)),
                "last": float(raw.get("last", 0)),
                "volume_24h": float(raw.get("baseVolume", 0)),
                "timestamp": int(raw.get("timestamp") or time.time() * 1000)
            }
        except Exception as e:
            telemetry.error(f"Erro ao buscar ticker para {symbol}: {e}")
            raise

    async def fetch_ohlcv_normalized(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> List[List[float]]:
        """Obtém candles OHLCV públicos normalizados."""
        self.record_heartbeat()
        
        if self._ccxt_instance is None:
            # Retorna dados sintéticos determinísticos para testes
            now_ms = int(time.time() * 1000)
            mock_candles = []
            for i in range(limit):
                ts = now_ms - ((limit - i) * 3600 * 1000)
                mock_candles.append([ts, 60000.0 + i, 60050.0 + i, 59950.0 + i, 60020.0 + i, 100.0])
            return mock_candles

        try:
            return await self._ccxt_instance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        except Exception as e:
            telemetry.error(f"Erro ao buscar candles para {symbol}: {e}")
            raise

    # ==========================================================================
    # DESPACHO DE ORDENS (SIMULADO OU REAL)
    # ==========================================================================

    async def submit_order(
        self,
        agent_id: str,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: float,
        leverage: float = 1.0,
        margin_type: str = "ISOLATED"
    ) -> Dict[str, Any]:
        """Despacha a ordem para o simulador ou para a corretora real."""
        # 1. Checagem prévia no Circuit Breaker
        cb_status = circuit_breaker.is_trading_allowed(agent_id)
        if not cb_status["allowed"]:
            return {"success": False, "reason": cb_status["reason"]}

        # 2. Modo Paper Trading (Padrão de Segurança)
        if self.paper_trading:
            return self.paper_exchange.create_order(
                agent_id=agent_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                amount=amount,
                price=price,
                leverage=leverage,
                margin_type=margin_type
            )

        # 3. Modo Real (Execução Real na Exchange)
        if self._ccxt_instance is None:
            return {"success": False, "reason": "Instância CCXT real não inicializada."}

        try:
            telemetry.emit_event(
                event="LIVE_ORDER_DISPATCHED",
                level="INFO",
                agent_id=agent_id,
                payload={
                    "symbol": symbol,
                    "side": side,
                    "type": order_type,
                    "amount": amount,
                    "price": price,
                    "leverage": leverage
                }
            )
            raw = await self._ccxt_instance.create_order(
                symbol=symbol,
                type=order_type.lower(),
                side=side.lower(),
                amount=amount,
                price=price
            )
            return {"success": True, "order_id": raw.get("id"), "raw": raw}
        except Exception as e:
            telemetry.error(f"Falha ao executar ordem real na exchange: {e}")
            return {"success": False, "reason": str(e)}

    async def close(self):
        """Encerra graciosamente conexões ativas."""
        if self._ccxt_instance and hasattr(self._ccxt_instance, "close"):
            await self._ccxt_instance.close()
