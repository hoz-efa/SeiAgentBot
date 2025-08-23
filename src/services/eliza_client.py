from __future__ import annotations
import asyncio
import logging
import time
from typing import Dict, Any, Optional
import httpx

log = logging.getLogger(__name__)

class ElizaClient:
    """
    ElizaOS client for AI advisory services.
    
    Provides intelligent portfolio analysis and recommendations using ElizaOS AI agents.
    Reference: https://docs.elizaos.ai/ and https://github.com/elizaos-plugins/plugin-sei
    """
    
    def __init__(self, base_url: str, api_key: str, timeout_s: int = 6):
        """
        Initialize ElizaOS client.
        
        Args:
            base_url: ElizaOS API endpoint URL
            api_key: ElizaOS API key for authentication
            timeout_s: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout_s = timeout_s
        self._http_client: Optional[httpx.AsyncClient] = None
        
        # Retry configuration
        self.max_retries = 2
        self.base_delay = 0.5  # Start with 0.5s delay
        
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with proper configuration"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=2.0,  # 2s connect timeout
                    read=2.0,     # 2s read timeout
                    write=2.0,    # 2s write timeout
                    pool=10.0     # 10s pool timeout
                ),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._http_client
    
    async def advise(self, prompt: str, context: Dict[str, Any]) -> str:
        """
        Get AI advisory from ElizaOS.
        
        Args:
            prompt: The prompt/instruction for the AI
            context: Context data (portfolio analytics, etc.)
            
        Returns:
            AI advisory text (short, actionable insights)
        """
        if not self.base_url or not self.api_key:
            log.warning("ElizaOS not configured, using fallback advisory")
            return self._get_fallback_advice(context)
        
        log.info("Requesting ElizaOS AI advisory")
        
        for attempt in range(self.max_retries + 1):
            try:
                client = await self._get_http_client()
                
                url = f"{self.base_url}/advise"
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "prompt": prompt,
                    "context": context
                }
                
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    advice = data.get("advice", "")
                    if advice:
                        log.info("ElizaOS advisory received successfully")
                        return advice
                    else:
                        log.warning("ElizaOS returned empty advice")
                        return self._get_fallback_advice(context)
                
                log.warning(f"ElizaOS returned status {response.status_code}: {response.text}")
                
            except httpx.TimeoutException:
                log.warning(f"ElizaOS timeout on attempt {attempt + 1}")
            except httpx.HTTPStatusError as e:
                log.warning(f"ElizaOS HTTP error on attempt {attempt + 1}: {e.response.status_code}")
            except Exception as e:
                log.error(f"ElizaOS unexpected error on attempt {attempt + 1}: {str(e)}")
            
            # Exponential backoff before retry
            if attempt < self.max_retries:
                delay = self.base_delay * (2 ** attempt)
                log.info(f"Retrying ElizaOS in {delay:.1f}s...")
                await asyncio.sleep(delay)
        
        log.warning("ElizaOS advisory failed after all retries, using fallback")
        return self._get_fallback_advice(context)
    
    def _get_fallback_advice(self, context: Dict[str, Any]) -> str:
        """
        Generate fallback advisory when ElizaOS is unavailable.
        
        Args:
            context: Portfolio context data
            
        Returns:
            Basic fallback advisory text
        """
        total_usd = context.get("total_usd", 0)
        concentration = context.get("concentration", {})
        volatility = context.get("volatility", {})
        
        advice_parts = []
        
        # Basic portfolio summary
        if total_usd > 0:
            advice_parts.append(f"Your portfolio is valued at ${total_usd:.2f}.")
        
        # Concentration warning
        top_asset = concentration.get("top_asset", "")
        top_pct = concentration.get("top_pct", 0)
        if top_pct > 50:
            advice_parts.append(f"⚠️ High concentration in {top_asset} ({top_pct:.1f}%). Consider diversifying.")
        elif top_pct > 30:
            advice_parts.append(f"Moderate concentration in {top_asset} ({top_pct:.1f}%). Monitor for over-exposure.")
        
        # Volatility insight
        signal = volatility.get("signal", "ok")
        if signal == "alert":
            advice_parts.append("🚨 High volatility detected. Consider reducing risk exposure.")
        elif signal == "warn":
            advice_parts.append("⚠️ Moderate volatility. Stay alert to market changes.")
        
        if not advice_parts:
            advice_parts.append("Live advisory is temporarily unavailable. Here's a basic summary: Monitor your portfolio regularly and consider diversification for risk management.")
        
        return " ".join(advice_parts)
    
    async def close(self) -> None:
        """Close HTTP client and cleanup resources"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        log.info("ElizaOS client closed")
    
    def __del__(self):
        """Cleanup on deletion"""
        if self._http_client:
            try:
                asyncio.create_task(self.close())
            except RuntimeError:
                pass  # Event loop not running
