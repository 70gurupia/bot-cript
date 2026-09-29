"""
Gerador de Alertas Operacionais e Telemetria para Telegram e Webhook.
Formata mensagens ricas com métricas determinísticas para o acompanhamento
da aceleração de banca (R$ 500 para R$ 3.000).
"""

from __future__ import annotations
from typing import Dict, Any, Optional


def format_trade_entry_alert(
    symbol: str,
    side: str,
    entry_price: float,
    take_profit: float,
    stop_loss: float,
    angle_deg: float,
    momentum_force: float,
    order_book_imbalance: float
) -> str:
    """Gera mensagem formatada de entrada de operação."""
    side_emoji = "🟢 COMPRA" if side == "BUY" else "🔴 VENDA (SHORT)"
    return (
        f"⚡ SINAL EXECUTADO: {side_emoji}\n"
        f"• Par: {symbol}\n"
        f"• Entrada: ${entry_price:,.4f}\n"
        f"• Alvo (TP 2.0x ATR): ${take_profit:,.4f}\n"
        f"• Stop (1.0x ATR): ${stop_loss:,.4f}\n"
        f"• Ângulo Cartesiano (Theta): {angle_deg:+.1f}°\n"
        f"• Força de Momento (Fy): {momentum_force:+.2f}\n"
        f"• Pressão Book (OBI): {order_book_imbalance:+.2f}\n"
        f"• Tipo de Ordem: LIMIT MAKER (Economia de 50% de Taxa)"
    )


def format_streak_milestone_alert(
    streak_count: int,
    current_stake: float,
    current_bankroll: float
) -> str:
    """Gera mensagem de avanço na progressão Anti-Martingale."""
    return (
        f"🔥 PROGRESSÃO ANTI-MARTINGALE\n"
        f"• Vitórias Consecutivas: {streak_count}/3\n"
        f"• Próxima Mão Dimensionada: R$ {current_stake:,.2f} (+25%)\n"
        f"• Capital Líquido Atual: R$ {current_bankroll:,.2f}\n"
        f"• Status: Acelerando capital sem expor o cofre."
    )


def format_vault_ratchet_alert(
    total_locked: float,
    transferred_amount: float,
    liquid_bankroll: float
) -> str:
    """Gera alerta de travamento de lucro no Cofre Inviolável (Ratchet Vault)."""
    total_equity = total_locked + liquid_bankroll
    return (
        f"🔒 COFRE INVIOLÁVEL ACIONADO (RATCHET VAULT)\n"
        f"• Transferido para o Cofre: R$ {transferred_amount:,.2f}\n"
        f"• Total Trancado no Cofre: R$ {total_locked:,.2f} (100% Protegido)\n"
        f"• Banca Líquida em Operação: R$ {liquid_bankroll:,.2f}\n"
        f"• Patrimônio Total: R$ {total_equity:,.2f}\n"
        f"• Invariante de Segurança: Lucro travado não pode sofrer drawdown."
    )


def format_eod_summary_alert(
    date_str: str,
    daily_pnl_brl: float,
    daily_trades: int,
    win_rate_pct: float,
    total_equity: float,
    vault_locked: float
) -> str:
    """Gera o resumo de fechamento diário (EOD Flat às 23:45 UTC)."""
    pnl_sign = "+" if daily_pnl_brl >= 0 else ""
    return (
        f"🏁 FECHAMENTO DIÁRIO EOD FLAT (23:45 UTC)\n"
        f"• Data: {date_str}\n"
        f"• Resultado do Dia: {pnl_sign}R$ {daily_pnl_brl:,.2f}\n"
        f"• Operações Realizadas: {daily_trades} (Taxa de Acerto: {win_rate_pct:.1f}%)\n"
        f"• Posições Overnight Abertas: 0 (Risco Zerado)\n"
        f"• Patrimônio Total Consolidado: R$ {total_equity:,.2f}\n"
        f"• Lucro Protegido no Cofre: R$ {vault_locked:,.2f}"
    )
