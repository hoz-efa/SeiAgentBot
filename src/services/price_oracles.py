from __future__ import annotations
import asyncio
import time
import logging
from typing import Dict, Optional
import httpx

log = logging.getLogger(__name__)

from src.config import settings

# Rivalz ADCS configuration from settings
RIVALZ_ADCS_BASE_URL = settings.RIVALZ_ADCS_BASE_URL
RIVALZ_ADCS_API_KEY = settings.RIVALZ_ADCS_API_KEY
RIVALZ_ADCS_TEST_MODE = settings.RIVALZ_ADCS_TEST_MODE

class PriceOracle:
    """
    Price oracle service using Rivalz ADCS as primary source with fallback mechanisms.
    
    Rivalz ADCS (Agentic Data Coordination Service) provides AI-native oracle infrastructure
    for verifiable on-chain data. Reference: https://blog.rivalz.ai/rivalz-ai-oracles-launch-on-base-unveiling-smart-contract-based-ai-agents/
    """
    
    def __init__(self):
        self._cache: Dict[str, tuple[float, float]] = {}  # symbol -> (price, timestamp)
        self._cache_ttl = 5.0  # 5 seconds TTL
        self._http_client: Optional[httpx.AsyncClient] = None
        
        # Fallback static prices for testnet (placeholder values)
        self._fallback_prices = {
            "SEI": 1.0,      # Testnet placeholder
            "USDC": 1.0,     # Stablecoin
            "ETH": 2000.0,   # Placeholder
            "BTC": 40000.0,  # Placeholder
            "SOL": 100.0,    # Placeholder
        }
        
        # Supported symbols
        self._supported_symbols = set(self._fallback_prices.keys())
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with proper configuration"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(10.0),  # 10 second timeout for API calls
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._http_client
    
    async def _try_rivalz_adcs(self, symbol: str) -> Optional[float]:
        """
        Try to get price from Rivalz ADCS endpoint.
        
        Rivalz ADCS provides AI-native oracle infrastructure for verifiable data.
        Reference: https://docs.rivalz.ai/
        """
        if not RIVALZ_ADCS_API_KEY:
            log.debug("Rivalz ADCS API key not configured, skipping primary source")
            return None
            
        try:
            client = await self._get_http_client()
            
            # Rivalz ADCS API endpoint for price data
            # Based on Rivalz documentation: https://console.rivalz.ai/
            url = f"{RIVALZ_ADCS_BASE_URL}/price/{symbol.upper()}"
            headers = {
                "Authorization": f"Bearer {RIVALZ_ADCS_API_KEY}",
                "Content-Type": "application/json"
            }
            

            
            log.info(f"Making Rivalz ADCS request to: {url}")
            
            # Simple GET request to price endpoint
            response = await client.get(url, headers=headers)
            
            log.info(f"Rivalz ADCS response status: {response.status_code}")
            log.info(f"Rivalz ADCS response headers: {response.headers}")
            log.info(f"Rivalz ADCS response text: {response.text[:500]}...")  # First 500 chars
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    log.info(f"Rivalz ADCS response data: {data}")
                    # Extract price from Rivalz ADCS response
                    price = data.get("price")
                    if price and isinstance(price, (int, float)):
                        log.info(f"Successfully fetched {symbol} price from Rivalz ADCS: ${price}")
                        return float(price)
                    else:
                        log.warning(f"Invalid price data in Rivalz ADCS response for {symbol}: {data}")
                except Exception as e:
                    log.error(f"Error parsing Rivalz ADCS JSON response: {e}")
                    log.error(f"Response text: {response.text}")
            
            log.warning(f"Rivalz ADCS returned status {response.status_code} for {symbol}: {response.text}")
            return None
            
        except httpx.TimeoutException:
            log.warning(f"Rivalz ADCS timeout for {symbol}")
            return None
        except httpx.HTTPStatusError as e:
            log.warning(f"Rivalz ADCS HTTP error for {symbol}: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            log.error(f"Unexpected error fetching {symbol} from Rivalz ADCS: {str(e)}")
            return None
    
    async def _try_rivalz_adcs_test_mode(self, symbol: str) -> Optional[float]:
        """
        Test mode for Rivalz ADCS - simulates real API responses
        Use this for development and testing when real API is not available
        """
        log.info(f"TEST MODE: Attempting to get price for {symbol}")
        
        # Simulate realistic Rivalz ADCS responses
        test_prices = {
            "SEI": 0.85,      # Realistic SEI price
            "USDC": 1.00,     # Stablecoin
            "ETH": 2150.25,   # Realistic ETH price
            "BTC": 43250.75,  # Realistic BTC price
            "SOL": 95.50,     # Realistic SOL price
        }
        
        # Simulate network delay
        await asyncio.sleep(0.1)
        
        price = test_prices.get(symbol.upper())
        log.info(f"TEST MODE: Found price for {symbol}: {price}")
        
        if price is not None:
            log.info(f"TEST MODE: Simulated {symbol} price from Rivalz ADCS: {price}")
            return price
        
        log.warning(f"TEST MODE: No price found for {symbol}")
        return None
    
    def _get_fallback_price(self, symbol: str) -> Optional[float]:
        """Get fallback price from static mapping"""
        price = self._fallback_prices.get(symbol.upper())
        if price is not None:
            log.info(f"Using fallback price for {symbol}: {price}")
        return price
    
    def _is_cache_valid(self, symbol: str) -> bool:
        """Check if cached price is still valid"""
        if symbol not in self._cache:
            return False
        
        price, timestamp = self._cache[symbol]
        return (time.time() - timestamp) < self._cache_ttl
    
    def _update_cache(self, symbol: str, price: float) -> None:
        """Update price cache with current timestamp"""
        self._cache[symbol] = (price, time.time())
        log.debug(f"Updated cache for {symbol}: {price}")
    
    async def get_price(self, symbol: str) -> float:
        """
        Get current price for a symbol with caching and fallback mechanisms.
        
        Args:
            symbol: Trading symbol (e.g., "SEI", "USDC", "ETH", "BTC", "SOL")
            
        Returns:
            Current price as float
            
        Raises:
            ValueError: If symbol is not supported
        """
        symbol = symbol.upper()
        
        # Validate symbol
        if symbol not in self._supported_symbols:
            raise ValueError(f"Unsupported symbol: {symbol}. Supported: {', '.join(self._supported_symbols)}")
        
        # Check cache first
        if self._is_cache_valid(symbol):
            price, _ = self._cache[symbol]
            log.debug(f"Returning cached price for {symbol}: {price}")
            return price
        
        # Try Rivalz ADCS first
        if RIVALZ_ADCS_TEST_MODE:
            price = await self._try_rivalz_adcs_test_mode(symbol)
        else:
            price = await self._try_rivalz_adcs(symbol)
        
        # Fallback to static prices if Rivalz unavailable
        if price is None:
            price = self._get_fallback_price(symbol)
        
        if price is None:
            raise ValueError(f"Unable to fetch price for {symbol} from any source")
        
        # Update cache
        self._update_cache(symbol, price)
        return price
    
    async def get_prices(self, symbols: list[str]) -> Dict[str, float]:
        """
        Get prices for multiple symbols efficiently.
        
        Args:
            symbols: List of trading symbols
            
        Returns:
            Dictionary mapping symbols to prices
        """
        results = {}
        for symbol in symbols:
            try:
                results[symbol] = await self.get_price(symbol)
            except ValueError as e:
                log.warning(f"Skipping {symbol}: {str(e)}")
                continue
        return results
    
    async def close(self) -> None:
        """Close HTTP client and cleanup resources"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        log.info("PriceOracle HTTP client closed")
    
    def __del__(self):
        """Cleanup on deletion"""
        if self._http_client:
            # Note: This is not ideal but prevents resource leaks
            try:
                asyncio.create_task(self.close())
            except RuntimeError:
                pass  # Event loop not running
