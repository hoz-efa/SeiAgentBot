from __future__ import annotations
from dataclasses import dataclass
import httpx
import json
import logging
import re

log = logging.getLogger(__name__)

@dataclass(slots=True)
class SeiTxResult:
    tx_hash: str
    explorer_url: str | None = None

class SeiClient:
    """Thin abstraction layer for Sei EVM interactions.
    Uses EVM RPC methods for blockchain interactions.
    """

    def __init__(self, rpc_url: str, chain_id: str, explorer_base: str | None = None):
        self.rpc_url = rpc_url
        self.chain_id = chain_id
        self.explorer_base = explorer_base

    def validate_address(self, address: str) -> tuple[bool, str]:
        """
        Validate address format and return (is_valid, error_message)
        """
        address = address.strip()
        
        # EVM address validation
        if address.startswith('0x'):
            if not re.match(r'^0x[a-fA-F0-9]{40}$', address):
                return False, "Invalid EVM address format. Must be 42 characters starting with 0x followed by 40 hex characters."
            return True, ""
        
        # SEI address validation
        elif address.startswith('sei'):
            if not re.match(r'^sei[a-zA-Z0-9]{38}$', address):
                return False, "Invalid SEI address format. Must start with 'sei' followed by 38 alphanumeric characters."
            return True, ""
        
        else:
            return False, "Address must start with '0x' (EVM) or 'sei' (SEI native)."

    async def get_chain_info(self) -> dict:
        """Get basic chain information"""
        return {"chain_id": self.chain_id, "rpc": self.rpc_url}

    async def send_dummy_tx(self) -> SeiTxResult:
        # TODO: hook up wallet + sign + broadcast
        fake_hash = "0xDEADBEEF..."
        url = f"{self.explorer_base}/tx/{fake_hash}" if self.explorer_base else None
        return SeiTxResult(tx_hash=fake_hash, explorer_url=url)

    async def get_balance(self, address: str) -> list:
        """
        Get balance for an address using EVM RPC eth_getBalance
        Returns list of balance objects with amount and denom
        """
        try:
            # Validate address format
            is_valid, error_msg = self.validate_address(address)
            if not is_valid:
                log.warning(f"Invalid address format: {address} - {error_msg}")
                return []
            
            # Convert sei address to EVM address if needed
            evm_address = address
            if address.startswith('sei'):
                # TODO: Implement sei to EVM address conversion
                # For now, return empty if it's a sei address
                log.warning(f"SEI address conversion not implemented yet: {address}")
                return []
            
            # Use EVM RPC method to get balance
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_getBalance",
                "params": [evm_address, "latest"],
                "id": 1
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.rpc_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "result" in result and result["result"]:
                        # Convert hex balance to decimal
                        balance_hex = result["result"]
                        balance_wei = int(balance_hex, 16)
                        balance_sei = balance_wei / (10 ** 18)  # Convert from wei to SEI
                        
                        return [{
                            "amount": str(balance_sei),
                            "denom": "usei"
                        }]
                    else:
                        log.error(f"Invalid response format: {result}")
                        return []
                else:
                    log.error(f"RPC request failed with status {response.status_code}: {response.text}")
                    return []
                    
        except Exception as e:
            log.error(f"Error getting balance for {address}: {str(e)}")
            return []

    async def get_native_balance(self, address: str) -> list:
        """
        Get native SEI balance using Cosmos REST API as fallback
        """
        try:
            # Use the correct REST API endpoint for Sei testnet
            # The REST API is available at a different URL than the EVM RPC
            rest_url = "https://rest-testnet.sei-apis.com"
            url = f"{rest_url}/cosmos/bank/v1beta1/balances/{address}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("balances", [])
                else:
                    log.warning(f"Cosmos REST API failed: {response.status_code} - {response.text}")
                    return []
        except Exception as e:
            log.error(f"Error getting native balance: {str(e)}")
            return []

    async def test_connection(self) -> bool:
        """
        Test if the RPC endpoint is accessible
        """
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_chainId",
                "params": [],
                "id": 1
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.rpc_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return "result" in result
                return False
                
        except Exception as e:
            log.error(f"Connection test failed: {str(e)}")
            return False

    async def get_evm_native_balance(self, address: str, rpc_url: str) -> int:
        """
        Get EVM native balance using eth_getBalance RPC method.
        
        Args:
            address: EVM address (0x...)
            rpc_url: EVM RPC endpoint URL
            
        Returns:
            Balance in wei (int)
        """
        try:
            # Validate EVM address format
            if not address.startswith('0x') or len(address) != 42:
                log.error(f"Invalid EVM address format: {address}")
                return 0
            
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_getBalance",
                "params": [address, "latest"],
                "id": 1
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    rpc_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "result" in result and result["result"]:
                        # Convert hex balance to decimal wei
                        balance_hex = result["result"]
                        balance_wei = int(balance_hex, 16)
                        log.info(f"EVM balance for {address}: {balance_wei} wei")
                        return balance_wei
                    else:
                        log.error(f"Invalid EVM RPC response format: {result}")
                        return 0
                else:
                    log.error(f"EVM RPC request failed with status {response.status_code}: {response.text}")
                    return 0
                    
        except Exception as e:
            log.error(f"Error getting EVM balance for {address}: {str(e)}")
            return 0

    async def get_native_sei_balance(self, address: str, lcd_base_url: str) -> int:
        """
        Get native SEI balance using Cosmos bank REST API.
        
        Args:
            address: SEI address (sei1...)
            lcd_base_url: LCD REST API base URL
            
        Returns:
            Balance in usei (int)
        """
        try:
            # Validate SEI address format
            if not address.startswith('sei') or len(address) != 41:
                log.error(f"Invalid SEI address format: {address}")
                return 0
            
            url = f"{lcd_base_url}/cosmos/bank/v1beta1/balances/{address}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    balances = data.get("balances", [])
                    
                    # Sum all "usei" denom balances
                    total_usei = 0
                    for balance in balances:
                        if balance.get("denom") == "usei":
                            try:
                                amount = int(balance.get("amount", "0"))
                                total_usei += amount
                            except ValueError:
                                log.warning(f"Invalid usei amount format: {balance.get('amount')}")
                    
                    log.info(f"Native SEI balance for {address}: {total_usei} usei")
                    return total_usei
                else:
                    log.error(f"LCD REST API failed: {response.status_code} - {response.text}")
                    return 0
                    
        except Exception as e:
            log.error(f"Error getting native SEI balance for {address}: {str(e)}")
            return 0
