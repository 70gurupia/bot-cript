"""
Módulo de configurações e limites invariantes de risco do Bot Cripto.
Utiliza Pydantic v2 com ConfigDict(frozen=True) para impedir adulteração em tempo de execução.
"""

import json
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
RISK_LIMITS_FILE = CONFIG_DIR / "risk_limits.json"


class RiskLimits(BaseModel):
    """Limites invariantes de proteção financeira (Imutáveis após carregamento)."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_leverage_ceiling: float = Field(default=3.0, ge=1.0, le=5.0)
    forced_margin_type: str = Field(default="ISOLATED")
    max_agent_daily_loss_pct: float = Field(default=2.0, gt=0.0, le=5.0)
    max_portfolio_daily_drawdown_pct: float = Field(default=4.0, gt=0.0, le=10.0)
    circuit_breaker_l2_cooling_off_hours: int = Field(default=24, ge=1, le=72)
    max_kelly_fraction: float = Field(default=0.25, gt=0.0, le=0.5)
    max_single_trade_risk_pct: float = Field(default=1.0, gt=0.0, le=2.0)
    network_timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)
    max_open_positions_global: int = Field(default=10, ge=1, le=50)


def load_risk_limits(filepath: Path = RISK_LIMITS_FILE) -> RiskLimits:
    """Carrega os limites invariantes do arquivo JSON ou usa padrões imutáveis seguros."""
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return RiskLimits(**data)
    return RiskLimits()


class SystemSettings(BaseModel):
    """Configurações globais de ambiente e execução do bot."""
    model_config = ConfigDict(frozen=True, extra="ignore")

    app_name: str = "Bot Cripto Autoevolutivo"
    version: str = "1.0.0"
    base_dir: Path = BASE_DIR
    data_dir: Path = DATA_DIR
    historical_db_path: Path = DATA_DIR / "historical" / "market_data.db"
    circuit_breaker_state_file: Path = DATA_DIR / "circuit_breaker_state.json"
    
    # Parâmetros operacionais padrão
    paper_trading_mode: bool = True
    active_exchange: str = "binance"
    opencode_base_url: str = "http://127.0.0.1:4096"
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8000
    
    # Instância imutável dos limites de risco
    risk_limits: RiskLimits = Field(default_factory=load_risk_limits)


# Instância global imutável de configurações
settings = SystemSettings()
