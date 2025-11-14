"""
Commission Helper - Facilita configuração de esquemas de comissão do backtrader

Features:
- Presets de comissão para diferentes mercados (stocks, futures, forex, crypto)
- Configuração via arquivo JSON
- Suporte a comissão por percentual, fixa, e baseada em margem
- Esquemas de comissão customizados
"""
import json
from pathlib import Path
from typing import Dict, Optional, Any
import backtrader as bt


class CommissionPresets:
    """
    Presets de comissão para diferentes mercados e brokers
    """
    
    # US Stocks - Typical broker commissions
    US_STOCKS_INTERACTIVE_BROKERS = {
        'commission': 0.005,  # $0.005 per share
        'stocklike': True,
        'percabs': False,  # Absolute value (not percentage)
        'commtype': bt.CommInfoBase.COMM_FIXED,
    }
    
    US_STOCKS_ZERO_COMMISSION = {
        'commission': 0.0,
        'stocklike': True,
        'percabs': True,
    }
    
    US_STOCKS_PERCENT = {
        'commission': 0.001,  # 0.1%
        'stocklike': True,
        'percabs': True,  # Percentage
    }
    
    # Futures
    FUTURES_EUROSTOXX50 = {
        'commission': 2.0,  # €2 per contract
        'margin': 2000.0,  # €2000 margin per contract
        'mult': 10.0,  # €10 per point
        'stocklike': False,
        'commtype': bt.CommInfoBase.COMM_FIXED,
    }
    
    FUTURES_ES_MINI = {
        'commission': 2.5,  # $2.50 per contract
        'margin': 12000.0,  # $12000 margin
        'mult': 50.0,  # $50 per point
        'stocklike': False,
        'commtype': bt.CommInfoBase.COMM_FIXED,
    }
    
    FUTURES_NQ_MINI = {
        'commission': 2.5,
        'margin': 15000.0,
        'mult': 20.0,
        'stocklike': False,
        'commtype': bt.CommInfoBase.COMM_FIXED,
    }
    
    # Forex
    FOREX_STANDARD = {
        'commission': 0.00002,  # 2 pips spread
        'margin': None,
        'mult': 1.0,
        'stocklike': False,
        'percabs': True,
    }
    
    # Crypto
    CRYPTO_BINANCE = {
        'commission': 0.001,  # 0.1% taker fee
        'stocklike': True,
        'percabs': True,
    }
    
    CRYPTO_COINBASE = {
        'commission': 0.005,  # 0.5% fee
        'stocklike': True,
        'percabs': True,
    }
    
    # Brazilian Market
    BR_STOCKS_B3 = {
        'commission': 0.0003,  # 0.03% typical
        'stocklike': True,
        'percabs': True,
    }
    
    BR_FUTURES_B3 = {
        'commission': 0.5,  # R$0.50 per contract
        'margin': 5000.0,
        'mult': 1.0,
        'stocklike': False,
        'commtype': bt.CommInfoBase.COMM_FIXED,
    }


class CommissionHelper:
    """
    Helper para gerenciar esquemas de comissão
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize CommissionHelper
        
        Args:
            config_path: Path to commission config JSON file
        """
        self.config_path = config_path or 'config/commission.json'
        self.custom_schemes = {}
        self.load_config()
    
    def load_config(self) -> bool:
        """
        Load commission schemes from config file
        """
        config_file = Path(self.config_path)
        
        if not config_file.exists():
            print(f"[CommissionHelper] Config not found: {self.config_path}")
            self.create_default_config()
            return False
        
        try:
            with open(config_file, 'r') as f:
                self.custom_schemes = json.load(f)
            
            print(f"[CommissionHelper] Loaded {len(self.custom_schemes)} custom schemes")
            return True
            
        except Exception as e:
            print(f"[CommissionHelper] Failed to load config: {e}")
            return False
    
    def create_default_config(self):
        """
        Create default commission config file
        """
        default_config = {
            'us_stocks': {
                'commission': 0.0,
                'stocklike': True,
                'percabs': True,
                'description': 'Zero commission for US stocks (Robinhood style)'
            },
            'br_stocks': {
                'commission': 0.0003,
                'stocklike': True,
                'percabs': True,
                'description': 'Brazilian stocks - 0.03% commission'
            },
            'futures': {
                'commission': 2.0,
                'margin': 5000.0,
                'mult': 1.0,
                'stocklike': False,
                'commtype': 'fixed',
                'description': 'Generic futures contract'
            },
            'crypto': {
                'commission': 0.001,
                'stocklike': True,
                'percabs': True,
                'description': 'Crypto exchange - 0.1% fee'
            }
        }
        
        try:
            config_file = Path(self.config_path)
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            
            print(f"[CommissionHelper] Created default config: {self.config_path}")
            self.custom_schemes = default_config
            
        except Exception as e:
            print(f"[CommissionHelper] Failed to create default config: {e}")
    
    def get_preset(self, preset_name: str) -> Optional[Dict]:
        """
        Get a preset commission scheme
        
        Args:
            preset_name: Name of the preset
        
        Returns:
            Commission parameters dict
        
        Available presets:
            - 'us_stocks_ib': Interactive Brokers US stocks
            - 'us_stocks_zero': Zero commission
            - 'us_stocks_percent': Percentage-based
            - 'futures_es': ES Mini futures
            - 'futures_nq': NQ Mini futures
            - 'futures_euro': EuroStoxx50 futures
            - 'forex': Standard forex
            - 'crypto_binance': Binance crypto
            - 'crypto_coinbase': Coinbase crypto
            - 'br_stocks': Brazilian stocks
            - 'br_futures': Brazilian futures
        """
        preset_map = {
            'us_stocks_ib': CommissionPresets.US_STOCKS_INTERACTIVE_BROKERS,
            'us_stocks_zero': CommissionPresets.US_STOCKS_ZERO_COMMISSION,
            'us_stocks_percent': CommissionPresets.US_STOCKS_PERCENT,
            'futures_es': CommissionPresets.FUTURES_ES_MINI,
            'futures_nq': CommissionPresets.FUTURES_NQ_MINI,
            'futures_euro': CommissionPresets.FUTURES_EUROSTOXX50,
            'forex': CommissionPresets.FOREX_STANDARD,
            'crypto_binance': CommissionPresets.CRYPTO_BINANCE,
            'crypto_coinbase': CommissionPresets.CRYPTO_COINBASE,
            'br_stocks': CommissionPresets.BR_STOCKS_B3,
            'br_futures': CommissionPresets.BR_FUTURES_B3,
        }
        
        if preset_name in preset_map:
            return preset_map[preset_name].copy()
        
        # Try custom schemes from config
        if preset_name in self.custom_schemes:
            scheme = self.custom_schemes[preset_name].copy()
            # Remove description if present
            scheme.pop('description', None)
            return scheme
        
        print(f"[CommissionHelper] Unknown preset: {preset_name}")
        return None
    
    def apply_to_broker(self,
                       broker: bt.brokers.BackBroker,
                       preset_name: Optional[str] = None,
                       name: Optional[str] = None,
                       **custom_params) -> bool:
        """
        Apply commission scheme to broker
        
        Args:
            broker: Backtrader broker instance
            preset_name: Name of preset to use
            name: Name for the commission scheme (to apply to specific instruments)
            **custom_params: Custom commission parameters (override preset)
        
        Returns:
            True if applied successfully
        
        Examples:
            # Apply zero commission to all instruments
            CommissionHelper().apply_to_broker(cerebro.broker, 'us_stocks_zero')
            
            # Apply specific commission to a named instrument
            CommissionHelper().apply_to_broker(
                cerebro.broker, 
                'futures_es', 
                name='ES'
            )
            
            # Custom commission parameters
            CommissionHelper().apply_to_broker(
                cerebro.broker,
                commission=0.002,
                stocklike=True,
                percabs=True
            )
        """
        try:
            # Get preset if specified
            params = {}
            if preset_name:
                params = self.get_preset(preset_name) or {}
            
            # Override with custom params
            params.update(custom_params)
            
            # Convert commtype string to constant if needed
            if 'commtype' in params and isinstance(params['commtype'], str):
                if params['commtype'].lower() == 'fixed':
                    params['commtype'] = bt.CommInfoBase.COMM_FIXED
                elif params['commtype'].lower() == 'perc':
                    params['commtype'] = bt.CommInfoBase.COMM_PERC
            
            # Add name if specified
            if name:
                params['name'] = name
            
            # Apply to broker
            broker.setcommission(**params)
            
            scheme_info = f"{preset_name}" if preset_name else "custom"
            if name:
                scheme_info += f" (name='{name}')"
            
            print(f"[CommissionHelper] Applied commission scheme: {scheme_info}")
            return True
            
        except Exception as e:
            print(f"[CommissionHelper] Failed to apply commission: {e}")
            return False
    
    def apply_multiple(self,
                      broker: bt.brokers.BackBroker,
                      schemes: Dict[str, str]) -> int:
        """
        Apply multiple commission schemes to different instruments
        
        Args:
            broker: Backtrader broker instance
            schemes: Dict mapping instrument names to preset names
        
        Returns:
            Number of schemes successfully applied
        
        Example:
            schemes = {
                'AAPL': 'us_stocks_zero',
                'ES': 'futures_es',
                'BTCUSDT': 'crypto_binance'
            }
            CommissionHelper().apply_multiple(cerebro.broker, schemes)
        """
        applied = 0
        
        for name, preset in schemes.items():
            if self.apply_to_broker(broker, preset_name=preset, name=name):
                applied += 1
        
        print(f"[CommissionHelper] Applied {applied}/{len(schemes)} commission schemes")
        return applied
    
    def list_presets(self) -> Dict[str, str]:
        """
        List all available presets with descriptions
        
        Returns:
            Dict mapping preset names to descriptions
        """
        presets = {
            'us_stocks_ib': 'Interactive Brokers - $0.005 per share',
            'us_stocks_zero': 'Zero commission (Robinhood style)',
            'us_stocks_percent': '0.1% of operation value',
            'futures_es': 'ES Mini - $2.50 per contract',
            'futures_nq': 'NQ Mini - $2.50 per contract',
            'futures_euro': 'EuroStoxx50 - €2.00 per contract',
            'forex': 'Standard Forex - 2 pips spread',
            'crypto_binance': 'Binance - 0.1% taker fee',
            'crypto_coinbase': 'Coinbase - 0.5% fee',
            'br_stocks': 'Brazilian stocks - 0.03%',
            'br_futures': 'Brazilian futures - R$0.50 per contract',
        }
        
        # Add custom schemes from config
        for name, scheme in self.custom_schemes.items():
            desc = scheme.get('description', 'Custom scheme')
            presets[name] = desc
        
        return presets
    
    def print_presets(self):
        """
        Print all available presets
        """
        print("\n" + "="*60)
        print("  Available Commission Presets")
        print("="*60)
        
        presets = self.list_presets()
        
        for name, description in presets.items():
            print(f"\n{name}:")
            print(f"  {description}")
        
        print("\n" + "="*60 + "\n")


# Convenience function
def setup_commission(cerebro_or_broker,
                    preset: Optional[str] = None,
                    **params) -> bool:
    """
    Quick function to setup commission on cerebro or broker
    
    Args:
        cerebro_or_broker: Cerebro or Broker instance
        preset: Preset name
        **params: Custom parameters
    
    Returns:
        True if applied successfully
    
    Example:
        setup_commission(cerebro, 'us_stocks_zero')
        setup_commission(cerebro.broker, commission=0.001, stocklike=True)
    """
    # Get broker from cerebro if needed
    if hasattr(cerebro_or_broker, 'broker'):
        broker = cerebro_or_broker.broker
    else:
        broker = cerebro_or_broker
    
    helper = CommissionHelper()
    return helper.apply_to_broker(broker, preset_name=preset, **params)
