from __future__ import annotations
import aiosqlite
import logging
import time
from typing import Dict, Optional
from telegram import Update
from telegram.ext import ContextTypes, JobQueue
from src.db import DB_PATH
from src.services.sei_client import SeiClient
from src.services.price_oracles import PriceOracle
from src.services.eliza_prompts import alert_prompt
from src.config import settings

log = logging.getLogger(__name__)

# In-memory storage for user portfolio anchors
# Structure: {user_id: {"anchor_usd": float, "last_check": float}}
user_anchors: Dict[int, Dict[str, float]] = {}

# Track sent alerts to prevent spam
# Structure: {user_id: {"last_alert": float}}
sent_alerts: Dict[int, Dict[str, float]] = {}

async def alerts_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enable portfolio drop alerts"""
    if not context.args:
        await update.message.reply_text("Usage: /alerts_on <drop_pct> (e.g., /alerts_on 10)")
        return
    
    try:
        drop_pct = float(context.args[0])
        if not 0 <= drop_pct <= 100:
            await update.message.reply_text("❌ Drop percentage must be between 0-100")
            return
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO user_prefs (user_id, alerts_enabled, alert_drop_pct)
                VALUES (?, 1, ?)
            """, (update.effective_user.id, drop_pct))
            await db.commit()
        
        # Initialize anchor for this user
        user_anchors[update.effective_user.id] = {
            "anchor_usd": 0.0,
            "last_check": time.time()
        }
        
        await update.message.reply_text(f"✅ Alerts enabled! Will warn if portfolio drops {drop_pct}%")
        
        # Log the action
        log.info(f"User {update.effective_user.id} enabled portfolio alerts with {drop_pct}% threshold")
        
    except ValueError:
        await update.message.reply_text("❌ Invalid percentage")
    except Exception as e:
        log.error(f"Error enabling alerts: {e}")
        await update.message.reply_text("❌ Failed to enable alerts")

async def alerts_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Disable portfolio drop alerts"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                UPDATE user_prefs 
                SET alerts_enabled = 0 
                WHERE user_id = ?
            """, (update.effective_user.id,))
            await db.commit()
        
        # Clean up in-memory data
        user_id = update.effective_user.id
        if user_id in user_anchors:
            del user_anchors[user_id]
        if user_id in sent_alerts:
            del sent_alerts[user_id]
        
        await update.message.reply_text("✅ Alerts disabled")
        
        # Log the action
        log.info(f"User {update.effective_user.id} disabled portfolio alerts")
        
    except Exception as e:
        log.error(f"Error disabling alerts: {e}")
        await update.message.reply_text("❌ Failed to disable alerts")

async def get_user_portfolio_value(user_id: int) -> float:
    """Get total USD value of user's portfolio"""
    try:
        # Get user's portfolio addresses
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT address FROM portfolio_addresses 
                WHERE user_id = ?
            """, (user_id,))
            addresses = await cursor.fetchall()
        
        if not addresses:
            return 0.0
        
        # Initialize services
        sei = SeiClient(settings.SEI_EVM_RPC_URL, settings.SEI_CHAIN_ID, settings.SEI_EXPLORER_BASE)
        oracle = PriceOracle()
        
        total_usd = 0.0
        
        for (address,) in addresses:
            address = address.strip()
            
            # Get balance based on address type
            if address.startswith('0x'):
                # EVM address
                balance_wei = await sei.get_evm_native_balance(address, settings.SEI_EVM_RPC_URL)
                balance_sei = balance_wei / (10**18)
                if balance_sei > 0:
                    sei_price = await oracle.get_price("SEI")
                    total_usd += balance_sei * sei_price
            else:
                # SEI address
                balance_usei = await sei.get_native_sei_balance(address, settings.SEI_LCD_URL)
                balance_sei = balance_usei / (10**6)
                if balance_sei > 0:
                    sei_price = await oracle.get_price("SEI")
                    total_usd += balance_sei * sei_price
        
        return total_usd
        
    except Exception as e:
        log.error(f"Error getting portfolio value for user {user_id}: {e}")
        return 0.0

async def check_alerts_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job to check portfolio alerts for all users"""
    try:
        # Get all users with alerts enabled
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT user_id, alert_drop_pct FROM user_prefs 
                WHERE alerts_enabled = 1
            """)
            users = await cursor.fetchall()
        
        if not users:
            return
        
        current_time = time.time()
        
        for user_id, alert_drop_pct in users:
            try:
                # Get current portfolio value
                current_usd = await get_user_portfolio_value(user_id)
                
                if current_usd <= 0:
                    continue
                
                # Initialize or update anchor
                if user_id not in user_anchors:
                    user_anchors[user_id] = {
                        "anchor_usd": current_usd,
                        "last_check": current_time
                    }
                    continue
                
                anchor_data = user_anchors[user_id]
                anchor_usd = anchor_data["anchor_usd"]
                last_check = anchor_data["last_check"]
                
                # Update anchor every 5 minutes (300 seconds)
                if current_time - last_check >= 300:
                    anchor_data["anchor_usd"] = current_usd
                    anchor_data["last_check"] = current_time
                    anchor_usd = current_usd
                
                # Check for drop
                if anchor_usd > 0:
                    drop_pct = ((anchor_usd - current_usd) / anchor_usd) * 100
                    
                    if drop_pct >= alert_drop_pct:
                        # Check if we already sent an alert recently (5-minute window)
                        if user_id in sent_alerts:
                            last_alert = sent_alerts[user_id]["last_alert"]
                            if current_time - last_alert < 300:  # 5 minutes
                                continue
                        
                        # Build alert context for ElizaOS
                        alert_context = {
                            "drop_pct": drop_pct,
                            "anchor_usd": anchor_usd,
                            "current_usd": current_usd,
                            "alert_threshold": alert_drop_pct,
                            "network": settings.NETWORK
                        }
                        
                        # Get ElizaOS AI advisory for alert
                        eliza_advice = ""
                        try:
                            eliza_client = context.bot_data.get("eliza_client")
                            if eliza_client:
                                eliza_advice = await eliza_client.advise(alert_prompt(), alert_context)
                            else:
                                eliza_advice = "This appears to be normal market volatility."
                        except Exception as e:
                            log.error(f"ElizaOS alert advisory failed: {e}")
                            eliza_advice = "This appears to be normal market volatility."
                        
                        # Send alert with AI advisory
                        alert_message = (
                            f"⚠️ Portfolio Alert\n\n"
                            f"Your portfolio has dropped {drop_pct:.1f}% from ${anchor_usd:.2f} to ${current_usd:.2f}\n\n"
                            f"Alert threshold: {alert_drop_pct}%\n"
                            f"🧠 AI Insight: {eliza_advice}"
                        )
                        
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=alert_message
                        )
                        
                        # Record sent alert
                        sent_alerts[user_id] = {"last_alert": current_time}
                        
                        log.info(f"Sent alert to user {user_id}: {drop_pct:.1f}% drop")
                
            except Exception as e:
                log.error(f"Error checking alerts for user {user_id}: {e}")
                continue
                
    except Exception as e:
        log.error(f"Error in check_alerts_job: {e}")

def setup_alerts_job(job_queue: JobQueue) -> None:
    """Setup the alerts checking job"""
    try:
        # Remove existing job if it exists
        job_queue.get_jobs_by_name("check_alerts_job")
        for job in job_queue.get_jobs_by_name("check_alerts_job"):
            job.schedule_removal()
        
        # Add new job that runs every 30 seconds
        job_queue.run_repeating(
            check_alerts_job,
            interval=30,
            first=10,  # Start after 10 seconds
            name="check_alerts_job"
        )
        
        log.info("Alerts job scheduled (every 30 seconds)")
        
    except Exception as e:
        log.error(f"Error setting up alerts job: {e}")

def cleanup_user_data(user_id: int) -> None:
    """Clean up in-memory data for a user"""
    if user_id in user_anchors:
        del user_anchors[user_id]
    if user_id in sent_alerts:
        del sent_alerts[user_id]
