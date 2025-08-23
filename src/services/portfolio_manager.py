"""
Async-optimized Portfolio Manager with real-time data integration
"""
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.services.sei_client import SeiClient
from src.services.price_oracles import PriceOracle
from src.services.eliza_client import ElizaClient
from src.services.eliza_prompts import insights_prompt, rebalancing_prompt
from src.config import settings

log = logging.getLogger(__name__)

@dataclass
class PortfolioPosition:
    """Portfolio position data"""
    address: str
    label: str
    balance_sei: float
    balance_usd: float
    last_updated: datetime

@dataclass
class PortfolioSummary:
    """Portfolio summary data"""
    total_usd: float
    positions: Dict[str, PortfolioPosition]
    concentration: Dict
    volatility: Dict
    last_updated: datetime

class PortfolioManager:
    """Async-optimized portfolio manager with real-time data"""
    
    def __init__(self):
        self.sei_client = SeiClient(
            settings.SEI_EVM_RPC_URL, 
            settings.SEI_CHAIN_ID, 
            settings.SEI_EXPLORER_BASE
        )
        self.price_oracle = PriceOracle()
        self._price_cache = {}
        self._cache_ttl = 30  # 30 seconds cache
        
    async def get_real_time_price(self, symbol: str = "SEI") -> float:
        """Get real-time price with caching"""
        cache_key = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        if cache_key in self._price_cache:
            return self._price_cache[cache_key]
        
        try:
            price = await self.price_oracle.get_price(symbol)
            self._price_cache[cache_key] = price
            
            # Clean old cache entries
            current_time = datetime.now()
            expired_keys = []
            for k in self._price_cache.keys():
                try:
                    # Parse the timestamp from cache key
                    key_parts = k.split('_')
                    if len(key_parts) >= 3:
                        date_str = key_parts[1] + '_' + key_parts[2]
                        key_time = datetime.strptime(date_str, '%Y%m%d_%H%M')
                        if current_time - key_time > timedelta(minutes=1):
                            expired_keys.append(k)
                except (ValueError, IndexError):
                    # If we can't parse the key, remove it
                    expired_keys.append(k)
            
            for key in expired_keys:
                del self._price_cache[key]
                
            return price
        except Exception as e:
            log.error(f"Error fetching real-time price for {symbol}: {e}")
            return 0.85  # Fallback price
    
    async def get_address_balance(self, address: str) -> Tuple[float, float]:
        """Get address balance with async optimization"""
        try:
            balance_sei = 0.0
            
            if address.startswith('0x'):
                # EVM address
                balance_wei = await self.sei_client.get_evm_native_balance(
                    address, settings.SEI_EVM_RPC_URL
                )
                balance_sei = balance_wei / (10**18)
            else:
                # SEI address
                balance_usei = await self.sei_client.get_native_sei_balance(
                    address, settings.SEI_LCD_URL
                )
                balance_sei = balance_usei / (10**6)
            
            if balance_sei > 0:
                price = await self.get_real_time_price("SEI")
                balance_usd = balance_sei * price
                return balance_sei, balance_usd
            
            return 0.0, 0.0
            
        except Exception as e:
            log.error(f"Error fetching balance for {address}: {e}")
            return 0.0, 0.0
    
    async def get_portfolio_positions(self, addresses: List[Tuple[str, str]]) -> Dict[str, PortfolioPosition]:
        """Get portfolio positions with parallel processing"""
        positions = {}
        
        # Create tasks for parallel balance fetching with rate limiting
        tasks = []
        for i, (address, label) in enumerate(addresses):
            # Add delay between requests to prevent rate limiting
            if i > 0:
                await asyncio.sleep(0.2)  # 200ms delay between requests
            
            task = asyncio.create_task(self.get_address_balance(address))
            tasks.append((address, label, task))
        
        # Wait for all tasks with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*[task for _, _, task in tasks], return_exceptions=True),
                timeout=15.0  # Increased timeout
            )
            
            for i, (address, label, _) in enumerate(tasks):
                try:
                    if isinstance(results[i], Exception):
                        log.warning(f"Balance fetch failed for {address}: {results[i]}")
                        # Add position with zero balance to show it's being tracked
                        positions[address] = PortfolioPosition(
                            address=address,
                            label=label,
                            balance_sei=0.0,
                            balance_usd=0.0,
                            last_updated=datetime.now()
                        )
                        continue
                        
                    balance_sei, balance_usd = results[i]
                    
                    positions[address] = PortfolioPosition(
                        address=address,
                        label=label,
                        balance_sei=balance_sei,
                        balance_usd=balance_usd,
                        last_updated=datetime.now()
                    )
                    
                except Exception as e:
                    log.error(f"Error processing result for {address}: {e}")
                    # Add position with zero balance to show it's being tracked
                    positions[address] = PortfolioPosition(
                        address=address,
                        label=label,
                        balance_sei=0.0,
                        balance_usd=0.0,
                        last_updated=datetime.now()
                    )
                    continue
                    
        except asyncio.TimeoutError:
            log.warning("Portfolio balance fetch timed out")
            # Add remaining addresses with zero balance
            for address, label, _ in tasks:
                if address not in positions:
                    positions[address] = PortfolioPosition(
                        address=address,
                        label=label,
                        balance_sei=0.0,
                        balance_usd=0.0,
                        last_updated=datetime.now()
                    )
        except Exception as e:
            log.error(f"Error in parallel balance fetching: {e}")
            # Add all addresses with zero balance
            for address, label, _ in tasks:
                if address not in positions:
                    positions[address] = PortfolioPosition(
                        address=address,
                        label=label,
                        balance_sei=0.0,
                        balance_usd=0.0,
                        last_updated=datetime.now()
                    )
        
        return positions
    
    async def compute_concentration(self, positions: Dict[str, PortfolioPosition]) -> Dict:
        """Compute portfolio concentration metrics"""
        if not positions:
            return {
                "top_asset": "None",
                "top_pct": 0.0,
                "warnings": []
            }
        
        total_usd = sum(pos.balance_usd for pos in positions.values())
        if total_usd <= 0:
            return {
                "top_asset": "None",
                "top_pct": 0.0,
                "warnings": []
            }
        
        # Calculate percentages
        position_pcts = {}
        for address, pos in positions.items():
            if pos.balance_usd > 0:
                pct = (pos.balance_usd / total_usd) * 100
                position_pcts[address] = pct
        
        if not position_pcts:
            return {
                "top_asset": "None",
                "top_pct": 0.0,
                "warnings": []
            }
        
        # Find top asset
        top_asset = max(position_pcts.items(), key=lambda x: x[1])
        
        # Generate warnings
        warnings = []
        if top_asset[1] > 80:
            warnings.append(f"Extremely high concentration in {top_asset[0][:10]}... ({top_asset[1]:.1f}%)")
        elif top_asset[1] > 60:
            warnings.append(f"High concentration in {top_asset[0][:10]}... ({top_asset[1]:.1f}%)")
        
        return {
            "top_asset": top_asset[0][:10] + "...",
            "top_pct": round(top_asset[1], 2),
            "warnings": warnings
        }
    
    async def get_market_data(self) -> Dict:
        """Get real-time market data for AI analysis"""
        try:
            # Get current price and market data
            current_price = await self.get_real_time_price("SEI")
            
            # Get market trend (simplified - in production you'd fetch from multiple sources)
            market_data = {
                "current_price": current_price,
                "price_change_24h": 0.0,  # Would fetch from API
                "market_cap": 0.0,  # Would fetch from API
                "volume_24h": 0.0,  # Would fetch from API
                "market_sentiment": "neutral",  # Would analyze from multiple sources
                "timestamp": datetime.now().isoformat()
            }
            
            return market_data
            
        except Exception as e:
            log.error(f"Error fetching market data: {e}")
            return {
                "current_price": 0.85,
                "price_change_24h": 0.0,
                "market_cap": 0.0,
                "volume_24h": 0.0,
                "market_sentiment": "unknown",
                "timestamp": datetime.now().isoformat()
            }
    
    async def get_ai_insights(self, portfolio_summary: PortfolioSummary, eliza_client: Optional[ElizaClient]) -> str:
        """Get AI insights with real-time market data"""
        try:
            if not eliza_client:
                return "AI advisory temporarily unavailable. Consider diversifying your portfolio to reduce concentration risk."
            
            # Get real-time market data
            market_data = await self.get_market_data()
            
            # Build comprehensive context for AI
            ai_context = {
                "portfolio": {
                    "total_value": portfolio_summary.total_usd,
                    "num_positions": len(portfolio_summary.positions),
                    "positions": {
                        pos.address[:10] + "...": pos.balance_usd 
                        for pos in portfolio_summary.positions.values()
                    },
                    "concentration": portfolio_summary.concentration,
                    "volatility": portfolio_summary.volatility
                },
                "market": market_data,
                "network": settings.NETWORK,
                "analysis_timestamp": datetime.now().isoformat()
            }
            
            # Get AI advisory
            advice = await eliza_client.advise(insights_prompt(), ai_context)
            return advice
            
        except Exception as e:
            log.error(f"Error getting AI insights: {e}")
            return "AI advisory temporarily unavailable. Consider diversifying your portfolio to reduce concentration risk."
    
    async def get_rebalancing_advice(self, portfolio_summary: PortfolioSummary, target_stable_pct: float, eliza_client: Optional[ElizaClient]) -> str:
        """Get rebalancing advice with real-time market data"""
        try:
            if not eliza_client:
                return "Consider diversifying your SEI holdings or exploring DeFi yield opportunities for better risk management."
            
            # Get real-time market data
            market_data = await self.get_market_data()
            
            # Build rebalancing context
            rebalancing_context = {
                "portfolio": {
                    "total_value": portfolio_summary.total_usd,
                    "positions": {
                        pos.address[:10] + "...": pos.balance_usd 
                        for pos in portfolio_summary.positions.values()
                    },
                    "concentration": portfolio_summary.concentration
                },
                "targets": {
                    "stable_pct": target_stable_pct,
                    "current_stable_pct": 0.0  # No stablecoins in SEI DeFi
                },
                "market": market_data,
                "network": settings.NETWORK,
                "portfolio_type": "defi_sei",
                "analysis_timestamp": datetime.now().isoformat()
            }
            
            # Get AI rebalancing advice
            advice = await eliza_client.advise(rebalancing_prompt(), rebalancing_context)
            return advice
            
        except Exception as e:
            log.error(f"Error getting rebalancing advice: {e}")
            return "Consider diversifying your SEI holdings or exploring DeFi yield opportunities for better risk management."

# Global portfolio manager instance
portfolio_manager = PortfolioManager()
