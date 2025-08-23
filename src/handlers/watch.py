from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from src.db import add_watch, list_watches, remove_watch, get_all_watches, set_last_tx_hash
from src.services.transaction_monitor import TransactionMonitor
import logging
import asyncio

log = logging.getLogger(__name__)

USAGE = "Usage: /watch <address> | /unwatch <address> | /watches\n\nSupports EVM (0x...) and SEI (sei1...) addresses"

# Global transaction monitor instance
transaction_monitor = TransactionMonitor()

# Global monitoring task
_monitoring_task = None
_app_instance = None

# Semaphore to limit concurrent requests (prevent rate limiting)
_request_semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests

async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(USAGE)
        return
    
    sei = context.bot_data["sei_client"]
    address = context.args[0].strip()
    
    # Validate address format
    is_valid, error_msg = sei.validate_address(address)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {error_msg}\n\n"
            "Please provide a valid:\n"
            "• EVM address (0x followed by 40 hex characters)\n"
            "• SEI address (sei1 followed by 38 alphanumeric characters)"
        )
        return
    
    try:
        await add_watch(update.effective_user.id, address)
        
        # Send initial confirmation
        await update.message.reply_text(
            f"✅ Now watching: {address}\n\n"
            f"Setting up monitoring..."
        )
        
        # Log the action
        log.info(f"User {update.effective_user.id} added watch for address: {address[:10]}...")
        
        # Do a quick initial scan for very recent transactions (non-blocking)
        try:
            # Use a smaller block range for faster initial scan
            await transaction_monitor.check_new_transactions(context, extended_scan=False, quick_scan=True)
            await update.message.reply_text(
                f"✅ Watch setup complete!\n\n"
                f"You'll be notified of new transactions for this address.\n\n"
                f"💡 Use /rescan_watches to check for older transactions."
            )
        except Exception as e:
            log.error(f"Error in initial transaction scan: {e}")
            await update.message.reply_text(
                f"✅ Watch added successfully!\n\n"
                f"You'll be notified of new transactions for this address.\n\n"
                f"💡 Use /rescan_watches to check for older transactions."
            )
        
    except Exception as e:
        log.error(f"Error adding watch: {str(e)}")
        await update.message.reply_text("❌ Error adding watch. Please try again.")

async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(USAGE)
        return
    
    address = context.args[0].strip()
    
    try:
        removed = await remove_watch(update.effective_user.id, address)
        if removed:
            await update.message.reply_text(
                f"✅ Removed watch: {address}"
            )
            # Log the action
            log.info(f"User {update.effective_user.id} removed watch for address: {address[:10]}...")
        else:
            await update.message.reply_text(
                f"❌ Not found: {address}\n\n"
                f"This address wasn't in your watch list."
            )
    except Exception as e:
        log.error(f"Error removing watch: {str(e)}")
        await update.message.reply_text("❌ Error removing watch. Please try again.")

async def watches(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        rows = await list_watches(update.effective_user.id)
        if not rows:
            await update.message.reply_text(
                "📋 No watches yet.\n\n"
                "Add one with:\n"
                "• /watch 0x1234567890abcdef... (EVM address)\n"
                "• /watch sei1abcdefghijklmnopqrstuvwxyz1234567890 (SEI address)"
            )
            return
        
        watch_list = "\n".join([f"• {address}" for address in rows])
        await update.message.reply_text(
            f"📋 Your watched addresses:\n\n{watch_list}\n\n"
            f"Total: {len(rows)} address{'es' if len(rows) > 1 else ''}"
        )
    except Exception as e:
        log.error(f"Error listing watches: {str(e)}")
        await update.message.reply_text("❌ Error listing watches. Please try again.")

async def rescan_watches(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually trigger an extended scan for all watched addresses"""
    try:
        await update.message.reply_text("🔍 Starting extended scan for all watched addresses...")
        
        # Run the transaction check with extended scan
        await transaction_monitor.check_new_transactions(context, extended_scan=True)
        
        await update.message.reply_text("✅ Extended scan completed! Check for notifications.")
        
        # Log the action
        log.info(f"User {update.effective_user.id} triggered extended scan")
        
    except Exception as e:
        log.error(f"Error in extended scan: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def test_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test command to manually check for transactions"""
    try:
        await update.message.reply_text("🔍 Testing transaction monitoring...")
        
        # Run the transaction check
        await transaction_monitor.check_new_transactions(context)
        
        await update.message.reply_text("✅ Test completed! Check logs for details.")
        
        # Log the action
        log.info(f"User {update.effective_user.id} triggered test monitor")
        
    except Exception as e:
        log.error(f"Error in test monitor: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

def setup_watch_job_with_app(app) -> None:
    """Setup the watch monitoring job with application instance"""
    global _monitoring_task, _app_instance
    
    try:
        log.info("Setting up watch monitoring with application instance")
        
        # Cancel existing task if running
        if _monitoring_task and not _monitoring_task.done():
            _monitoring_task.cancel()
            log.info("Cancelled existing monitoring task")
        
        # Store the application instance
        _app_instance = app
        
        # Start new monitoring task in background
        loop = asyncio.get_event_loop()
        _monitoring_task = loop.create_task(background_monitoring())
        _monitoring_task.add_done_callback(lambda t: log.info("Background monitoring task completed"))
        
        log.info("Watch monitoring task started (every 5 seconds)")
        
    except Exception as e:
        log.error(f"Error setting up watch monitoring: {e}")
        import traceback
        log.error(f"Traceback: {traceback.format_exc()}")

def setup_watch_job(job_queue) -> None:
    """Setup the watch monitoring job using asyncio task"""
    global _monitoring_task, _app_instance
    
    try:
        log.info("Setting up watch monitoring using asyncio task")
        
        # Cancel existing task if running
        if _monitoring_task and not _monitoring_task.done():
            _monitoring_task.cancel()
            log.info("Cancelled existing monitoring task")
        
        # Get the application instance from the job queue
        if hasattr(job_queue, '_application'):
            _app_instance = job_queue._application
        elif hasattr(job_queue, 'application'):
            _app_instance = job_queue.application
        else:
            # Try to get it from the global instance
            from src.bot import get_application
            _app_instance = get_application()
            
        if not _app_instance:
            log.error("Could not get application instance for monitoring")
            return
        
        # Start new monitoring task in background
        loop = asyncio.get_event_loop()
        _monitoring_task = loop.create_task(background_monitoring())
        _monitoring_task.add_done_callback(lambda t: log.info("Background monitoring task completed"))
        
        log.info("Watch monitoring task started (every 5 seconds)")
        
    except Exception as e:
        log.error(f"Error setting up watch monitoring: {e}")
        import traceback
        log.error(f"Traceback: {traceback.format_exc()}")

async def background_monitoring():
    """Background task that monitors for transactions with parallel processing"""
    global _app_instance
    
    while True:
        try:
            if _app_instance and _app_instance.bot:
                # Create a proper context for sending notifications
                class NotificationContext:
                    def __init__(self, app):
                        self.bot = app.bot
                        self.bot_data = app.bot_data
                
                context = NotificationContext(_app_instance)
                
                # Get all watched addresses
                watches = await get_all_watches()
                if not watches:
                    await asyncio.sleep(5)
                    continue
                
                log.debug(f"Checking {len(watches)} addresses in parallel")
                
                # Create tasks for parallel processing of each address
                tasks = []
                for user_id, address, last_tx_hash in watches:
                    task = asyncio.create_task(
                        check_single_address(context, user_id, address, last_tx_hash)
                    )
                    tasks.append(task)
                
                # Wait for all tasks to complete (with timeout)
                try:
                    await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=10.0)
                except asyncio.TimeoutError:
                    log.warning("Some address checks timed out, continuing...")
                
                log.debug("Parallel monitoring check completed")
            else:
                log.warning("No application instance available for monitoring")
            
            # Wait 3 seconds before next check (faster than 5 seconds)
            await asyncio.sleep(3)
            
        except asyncio.CancelledError:
            log.info("Background monitoring task cancelled")
            break
        except Exception as e:
            log.error(f"Error in background monitoring: {e}")
            await asyncio.sleep(3)  # Wait before retrying
        except KeyboardInterrupt:
            log.info("Background monitoring interrupted")
            break

async def check_single_address(context, user_id: int, address: str, last_tx_hash: str):
    """Check a single address for new transactions (optimized for speed)"""
    async with _request_semaphore:  # Limit concurrent requests
        try:
            new_transactions = []
            
            if address.startswith('0x'):
                # EVM address - use optimized block range
                block_range = 20  # Increased for better detection
                log.debug(f"Checking EVM address {address[:10]}... (blocks: {block_range})")
                
                # Get transactions with timeout
                try:
                    transactions = await asyncio.wait_for(
                        transaction_monitor.get_evm_transactions(address, block_range),
                        timeout=5.0
                    )
                    
                    for tx in transactions:
                        tx_hash = tx.get("hash", "")
                        if tx_hash and tx_hash != last_tx_hash:
                            # Determine transaction type
                            from_addr = tx.get("from", "")
                            to_addr = tx.get("to", "")
                            
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
                            log.info(f"New EVM transaction found: {tx_hash[:10]}... ({tx_type}) for {address[:10]}...")
                    
                except asyncio.TimeoutError:
                    log.warning(f"Timeout checking EVM address {address[:10]}...")
                except Exception as e:
                    log.error(f"Error checking EVM address {address[:10]}...: {e}")
                    
            else:
                # SEI native address
                log.debug(f"Checking SEI address {address[:10]}...")
                
                try:
                    transactions = await asyncio.wait_for(
                        transaction_monitor.get_sei_transactions(address),
                        timeout=5.0
                    )
                    
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
                            log.info(f"New SEI transaction found: {tx_hash[:10]}... ({direction}) for {address[:10]}...")
                    
                except asyncio.TimeoutError:
                    log.warning(f"Timeout checking SEI address {address[:10]}...")
                except Exception as e:
                    log.error(f"Error checking SEI address {address[:10]}...: {e}")
            
            # Send notifications for new transactions
            for tx in new_transactions:
                try:
                    await transaction_monitor._send_transaction_notification(context, user_id, address, tx)
                    
                    # Update the last transaction hash in database
                    await set_last_tx_hash(user_id, address, tx["hash"])
                    log.info(f"Updated last transaction hash for {address[:10]}... to {tx['hash'][:10]}...")
                    
                except Exception as e:
                    log.error(f"Error sending notification for {address[:10]}...: {e}")
            
            if new_transactions:
                log.info(f"Found {len(new_transactions)} new transactions for {address[:10]}...")
            
        except Exception as e:
            log.error(f"Error in check_single_address for {address[:10]}...: {e}")

def get_application():
    """Get the application instance for background monitoring"""
    return _app_instance
