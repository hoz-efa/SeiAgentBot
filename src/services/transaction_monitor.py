from __future__ import annotations
import asyncio
import logging
import time
from typing import List, Dict, Optional, Tuple
import httpx
from src.db import get_all_watches, set_last_tx_hash
from src.config import settings

log = logging.getLogger(__name__)

class TransactionMonitor:
    """Monitor watched addresses for new transactions"""
    
    def __init__(self):
        self._http_client: Optional[httpx.AsyncClient] = None
        self.last_check_time = time.time()
        
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return self._http_client
    
    async def get_evm_transactions(self, address: str, block_range: int = 10) -> List[Dict]:
        """Get EVM transactions for an address with optimized performance"""
        try:
            client = await self._get_http_client()
            
            # Get latest block number
            try:
                response = await asyncio.wait_for(
                    client.post(
                        settings.SEI_EVM_RPC_URL,
                        json={
                            "jsonrpc": "2.0",
                            "method": "eth_blockNumber",
                            "params": [],
                            "id": 1
                        }
                    ),
                    timeout=3.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        latest_block = int(data["result"], 16)
                        log.debug(f"Latest block: {latest_block}")
                    else:
                        log.error(f"Error getting latest block: {data}")
                        return []
                else:
                    log.error(f"Failed to get latest block: {response.status_code}")
                    return []
                    
            except asyncio.TimeoutError:
                log.warning("Timeout getting latest block")
                return []
            except Exception as e:
                log.error(f"Error getting latest block: {e}")
                return []
            
            # Get transactions from recent blocks
            transactions = []
            start_block = max(0, latest_block - block_range)
            
            # Process blocks in parallel for better performance
            block_tasks = []
            for block_num in range(start_block, latest_block + 1):
                task = asyncio.create_task(self._get_block_transactions(client, block_num, address))
                block_tasks.append(task)
            
            # Wait for all block tasks with timeout
            try:
                block_results = await asyncio.wait_for(
                    asyncio.gather(*block_tasks, return_exceptions=True),
                    timeout=8.0
                )
                
                for result in block_results:
                    if isinstance(result, list):
                        transactions.extend(result)
                    elif isinstance(result, Exception):
                        log.debug(f"Block check failed: {result}")
                        
            except asyncio.TimeoutError:
                log.warning("Timeout processing blocks, returning partial results")
            
            log.info(f"Found {len(transactions)} EVM transactions for {address}")
            return transactions
            
        except Exception as e:
            log.error(f"Error getting EVM transactions for {address}: {e}")
            return []
    
    async def _get_block_transactions(self, client, block_num: int, address: str) -> List[Dict]:
        """Get transactions from a specific block for an address"""
        try:
            # Add small delay to prevent rate limiting
            await asyncio.sleep(0.05)
            
            response = await asyncio.wait_for(
                client.post(
                    settings.SEI_EVM_RPC_URL,
                    json={
                        "jsonrpc": "2.0",
                        "method": "eth_getBlockByNumber",
                        "params": [hex(block_num), True],
                        "id": 1
                    }
                ),
                timeout=2.0
            )
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data and data["result"]:
                    block_data = data["result"]
                    block_transactions = []
                    
                    for tx in block_data.get("transactions", []):
                        from_addr = tx.get("from", "").lower()
                        to_addr = tx.get("to", "").lower()
                        address_lower = address.lower()
                        
                        if from_addr == address_lower or to_addr == address_lower:
                            block_transactions.append({
                                "hash": tx.get("hash", ""),
                                "from": tx.get("from", ""),
                                "to": tx.get("to", ""),
                                "value": tx.get("value", "0"),
                                "blockNumber": hex(block_num),
                                "timestamp": block_data.get("timestamp", "0")
                            })
                    
                    return block_transactions
            
            return []
            
        except asyncio.TimeoutError:
            log.debug(f"Timeout getting block {block_num}")
            return []
        except Exception as e:
            log.debug(f"Error getting block {block_num}: {e}")
            return []
    
    async def get_sei_transactions(self, address: str) -> List[Dict]:
        """Get SEI native transactions for an address"""
        try:
            client = await self._get_http_client()
            
            # Try multiple approaches to get transactions
            transactions = []
            
            # Method 1: Get transactions by address
            try:
                response = await client.get(
                    f"{settings.SEI_LCD_URL}/cosmos/tx/v1beta1/txs",
                    params={
                        "events": f"transfer.recipient='{address}' OR transfer.sender='{address}'",
                        "pagination.limit": "20",
                        "order_by": "ORDER_BY_DESC"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "txs" in data:
                        for tx in data["txs"]:
                            transactions.append({
                                "hash": tx.get("txhash", ""),
                                "height": tx.get("height", ""),
                                "timestamp": tx.get("timestamp", ""),
                                "data": tx
                            })
                        log.info(f"Found {len(transactions)} SEI transactions via LCD for {address}")
            except Exception as e:
                log.error(f"Error getting SEI transactions via LCD: {e}")
            
            # Method 2: Try alternative endpoint if first one fails
            if not transactions:
                try:
                    response = await client.get(
                        f"{settings.SEI_LCD_URL}/cosmos/tx/v1beta1/txs",
                        params={
                            "events": f"message.sender='{address}'",
                            "pagination.limit": "20",
                            "order_by": "ORDER_BY_DESC"
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if "txs" in data:
                            for tx in data["txs"]:
                                transactions.append({
                                    "hash": tx.get("txhash", ""),
                                    "height": tx.get("height", ""),
                                    "timestamp": tx.get("timestamp", ""),
                                    "data": tx
                                })
                            log.info(f"Found {len(transactions)} SEI transactions via alternative method for {address}")
                except Exception as e:
                    log.error(f"Error getting SEI transactions via alternative method: {e}")
            
            return transactions
            
        except Exception as e:
            log.error(f"Error getting SEI transactions for {address}: {e}")
            return []
    
    async def check_new_transactions(self, context=None, extended_scan: bool = False, quick_scan: bool = False) -> None:
        """Check for new transactions for all watched addresses"""
        try:
            watches = await get_all_watches()
            if not watches:
                return
            
            log.debug(f"Checking {len(watches)} watched addresses for new transactions")
            
            for user_id, address, last_tx_hash in watches:
                try:
                    new_transactions = []
                    
                    if address.startswith('0x'):
                        # EVM address - determine block range based on scan type
                        if quick_scan:
                            block_range = 5  # Very quick scan for recent transactions only
                        elif extended_scan or last_tx_hash is None:
                            block_range = 10000  # Extended scan for very old transactions
                        else:
                            block_range = 10   # Regular monitoring
                        log.debug(f"Getting EVM transactions for {address[:10]}... (block range: {block_range})")
                        transactions = await self.get_evm_transactions(address, block_range)
                        log.debug(f"Found {len(transactions)} EVM transactions for {address[:10]}...")
                        
                        for tx in transactions:
                            tx_hash = tx.get("hash", "")
                            if tx_hash and tx_hash != last_tx_hash:
                                # Determine transaction type
                                from_addr = tx.get("from", "")
                                to_addr = tx.get("to", "")
                                
                                # Add null checks for address comparison
                                if from_addr and from_addr.lower() == address.lower():
                                    tx_type = "OUTGOING"
                                elif to_addr and to_addr.lower() == address.lower():
                                    tx_type = "INCOMING"
                                else:
                                    tx_type = "UNKNOWN"
                                
                                new_transactions.append({
                                    "hash": tx_hash,
                                    "type": "EVM",
                                    "direction": tx_type,
                                    "block": tx.get("blockNumber", ""),
                                    "from": from_addr,
                                    "to": to_addr,
                                    "value": tx.get("value", "0"),
                                    "data": tx
                                })
                                log.info(f"New EVM transaction found: {tx_hash[:10]}... ({tx_type})")
                    else:
                        # SEI native address
                        log.debug(f"Getting SEI transactions for {address[:10]}...")
                        transactions = await self.get_sei_transactions(address)
                        log.debug(f"Found {len(transactions)} SEI transactions for {address[:10]}...")
                        
                        for tx in transactions:
                            tx_hash = tx.get("hash", "")
                            if tx_hash and tx_hash != last_tx_hash:
                                # Try to determine direction from transaction data
                                tx_data = tx.get("data", {})
                                tx_body = tx_data.get("tx", {})
                                messages = tx_body.get("body", {}).get("messages", [])
                                
                                direction = "UNKNOWN"
                                for msg in messages:
                                    if msg.get("@type") == "/cosmos.bank.v1beta1.MsgSend":
                                        if msg.get("from_address") == address:
                                            direction = "OUTGOING"
                                        elif msg.get("to_address") == address:
                                            direction = "INCOMING"
                                        break
                                
                                new_transactions.append({
                                    "hash": tx_hash,
                                    "type": "SEI",
                                    "direction": direction,
                                    "block": tx.get("height", ""),
                                    "data": tx
                                })
                                log.info(f"New SEI transaction found: {tx_hash[:10]}... ({direction})")
                    
                    # Send notifications for new transactions
                    for tx in new_transactions:
                        try:
                            if context and hasattr(context, 'bot') and context.bot:
                                await self._send_transaction_notification(context, user_id, address, tx)
                            else:
                                log.info(f"Would send notification for transaction {tx['hash'][:10]}... to user {user_id} (no context)")
                            
                            # Update last transaction hash
                            await set_last_tx_hash(user_id, address, tx["hash"])
                            
                            log.info(f"Processed transaction {tx['hash'][:10]}... for user {user_id}")
                        except Exception as e:
                            log.error(f"Error processing transaction {tx.get('hash', 'unknown')}: {e}")
                        
                        # Small delay to avoid rate limiting
                        await asyncio.sleep(0.2)
                
                except Exception as e:
                    log.error(f"Error checking transactions for {address}: {e}")
                    continue
            
            self.last_check_time = time.time()
            log.debug("Transaction monitoring check completed")
            
        except Exception as e:
            log.error(f"Error in transaction monitoring: {e}")
            import traceback
            log.error(f"Traceback: {traceback.format_exc()}")
    
    async def _send_transaction_notification(self, context, user_id: int, address: str, transaction: Dict) -> None:
        """Send notification about new transaction"""
        try:
            tx_type = transaction["type"]
            tx_hash = transaction["hash"]
            block = transaction["block"]
            direction = transaction.get("direction", "UNKNOWN")
            
            # Create correct explorer link
            explorer_url = f"https://seitrace.com/tx/{tx_hash}?chain=atlantic-2"
            
            # Format the notification message
            direction_emoji = "📤" if direction == "OUTGOING" else "📥" if direction == "INCOMING" else "❓"
            
            # Get transaction details
            tx_details = await self._get_transaction_details(tx_hash, tx_type)
            
            message = (
                f"🔔 New Transaction Detected!\n\n"
                f"📍 Address: {address[:10]}...\n"
                f"🔗 Type: {tx_type}\n"
                f"{direction_emoji} Direction: {direction}\n"
                f"📦 Block: {block}\n"
                f"🔍 Hash: {tx_hash[:10]}...\n\n"
            )
            
            # Add transaction details if available
            if tx_details:
                message += f"💰 Value: {tx_details.get('value', 'N/A')}\n"
                message += f"⛽ Gas Used: {tx_details.get('gas_used', 'N/A')}\n"
                message += f"💸 Fee: {tx_details.get('fee', 'N/A')}\n\n"
            
            message += f"🌐 View on Explorer: {explorer_url}"
            
            # Try to send the message with better error handling
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    disable_web_page_preview=True
                )
                log.info(f"✅ Sent transaction notification to user {user_id} for {address} - {direction} {tx_type} transaction")
            except Exception as send_error:
                if "Chat not found" in str(send_error):
                    log.warning(f"⚠️ Chat not found for user {user_id}. User may need to start the bot first.")
                elif "Forbidden" in str(send_error):
                    log.warning(f"⚠️ Bot blocked by user {user_id}")
                else:
                    log.error(f"❌ Error sending notification to user {user_id}: {send_error}")
            
        except Exception as e:
            log.error(f"Error in transaction notification: {e}")
            import traceback
            log.error(f"Traceback: {traceback.format_exc()}")
    
    async def _get_transaction_details(self, tx_hash: str, tx_type: str) -> Dict:
        """Get detailed transaction information"""
        try:
            client = await self._get_http_client()
            
            if tx_type == "EVM":
                # Get EVM transaction receipt
                response = await client.post(
                    settings.SEI_EVM_RPC_URL,
                    json={
                        "jsonrpc": "2.0",
                        "method": "eth_getTransactionReceipt",
                        "params": [tx_hash],
                        "id": 1
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data and data["result"]:
                        receipt = data["result"]
                        
                        # Get transaction details
                        tx_response = await client.post(
                            settings.SEI_EVM_RPC_URL,
                            json={
                                "jsonrpc": "2.0",
                                "method": "eth_getTransactionByHash",
                                "params": [tx_hash],
                                "id": 1
                            }
                        )
                        
                        if tx_response.status_code == 200:
                            tx_data = tx_response.json()
                            if "result" in tx_data and tx_data["result"]:
                                tx = tx_data["result"]
                                
                                # Calculate values
                                gas_used = int(receipt.get("gasUsed", "0"), 16)
                                gas_price = int(tx.get("gasPrice", "0"), 16)
                                value = int(tx.get("value", "0"), 16)
                                
                                # Convert to SEI (assuming 18 decimals)
                                gas_fee_wei = gas_used * gas_price
                                gas_fee_sei = gas_fee_wei / (10 ** 18)
                                value_sei = value / (10 ** 18)
                                
                                return {
                                    "value": f"{value_sei:.6f} SEI" if value_sei > 0 else "0 SEI",
                                    "gas_used": f"{gas_used:,}",
                                    "fee": f"{gas_fee_sei:.8f} SEI"
                                }
            
            return {}
            
        except Exception as e:
            log.error(f"Error getting transaction details: {e}")
            return {}
    
    async def close(self) -> None:
        """Close HTTP client"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
