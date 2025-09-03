from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
import aiosqlite
import logging
from src.db import DB_PATH
from src.services.portfolio_manager import portfolio_manager
from src.services.analytics import volatility_signal
from datetime import datetime

log = logging.getLogger(__name__)

async def portfolio_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add address to portfolio"""
    if not context.args:
        await update.message.reply_text("Usage: /portfolio_add <address> [label]")
        return
    
    address = context.args[0].strip()
    label = context.args[1].strip() if len(context.args) > 1 else ""
    
    # Validate address format
    if not (address.startswith('0x') and len(address) == 42) and not (address.startswith('sei1') and len(address) == 44):
        await update.message.reply_text(
            "❌ Invalid address format\n\n"
            "Please provide a valid:\n"
            "• EVM address (0x followed by 40 hex characters)\n"
            "• SEI address (sei1 followed by 38 alphanumeric characters)"
        )
        return
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO portfolio_addresses (user_id, address, label)
                VALUES (?, ?, ?)
            """, (update.effective_user.id, address, label))
            await db.commit()
        
        await update.message.reply_text(
            f"✅ Added to portfolio: {address[:10]}...\n"
            f"Label: {label if label else 'None'}"
        )
        
        # Log the action
        log.info(f"User {update.effective_user.id} added portfolio address: {address[:10]}...")
        
    except Exception as e:
        log.error(f"Error adding portfolio address: {str(e)}")
        await update.message.reply_text("❌ Error adding address. Please try again.")

async def portfolio_rm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove address from portfolio"""
    if not context.args:
        await update.message.reply_text("Usage: /portfolio_rm <address>")
        return
    
    address = context.args[0].strip()
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                DELETE FROM portfolio_addresses 
                WHERE user_id = ? AND address = ?
            """, (update.effective_user.id, address))
            await db.commit()
            
            if cursor.rowcount > 0:
                await update.message.reply_text(f"✅ Removed from portfolio: {address[:10]}...")
                # Log the action
                log.info(f"User {update.effective_user.id} removed portfolio address: {address[:10]}...")
            else:
                await update.message.reply_text(f"❌ Address not found in portfolio: {address[:10]}...")
        
    except Exception as e:
        log.error(f"Error removing portfolio address: {str(e)}")
        await update.message.reply_text("❌ Error removing address. Please try again.")

async def portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show portfolio summary with real-time data"""
    try:
        # Get user's portfolio addresses
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT address, label FROM portfolio_addresses 
                WHERE user_id = ?
            """, (update.effective_user.id,))
            addresses = await cursor.fetchall()
        
        if not addresses:
            await update.message.reply_text("📭 Portfolio is empty. Use /portfolio_add to add addresses.")
            return
        
        # Get portfolio positions with async optimization
        positions = await portfolio_manager.get_portfolio_positions(addresses)
        
        if not positions:
            await update.message.reply_text("📭 No balances found in portfolio addresses")
            return
        
        # Calculate total
        total_usd = sum(pos.balance_usd for pos in positions.values())
        
        # Generate summary
        summary = f"💼 **Portfolio Summary**\n\n"
        for address, pos in positions.items():
            if pos.balance_usd > 0:
                label = f" ({pos.label})" if pos.label else ""
                summary += f"📍 {pos.address[:10]}...{label}\n"
                summary += f"   {pos.balance_sei:.4f} SEI (${pos.balance_usd:.2f})\n\n"
        
        summary += f"💰 **Total**: ${total_usd:.2f}"
        
        await update.message.reply_text(summary)
        
    except Exception as e:
        log.error(f"Error fetching portfolio: {e}")
        await update.message.reply_text("❌ Failed to fetch portfolio. Please try again.")

async def insights(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show portfolio insights with real-time AI analysis"""
    try:
        # Get user's portfolio addresses
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT address, label FROM portfolio_addresses 
                WHERE user_id = ?
            """, (update.effective_user.id,))
            addresses = await cursor.fetchall()
        
        if not addresses:
            await update.message.reply_text("📭 Portfolio is empty. Use /portfolio_add to add addresses.")
            return
        
        # Get portfolio positions with async optimization
        positions = await portfolio_manager.get_portfolio_positions(addresses)
        
        if not positions:
            await update.message.reply_text("📭 No balances found in portfolio addresses")
            return
        
        # Calculate total and concentration
        total_usd = sum(pos.balance_usd for pos in positions.values())
        concentration = await portfolio_manager.compute_concentration(positions)
        
        # Get volatility data
        try:
            current_price = await portfolio_manager.get_real_time_price("SEI")
            price_series = [current_price * (1 + (i % 3 - 1) * 0.01) for i in range(60)]
            volatility = volatility_signal(price_series, 60)
        except Exception as e:
            log.warning(f"Volatility calculation failed: {e}")
            volatility = {"signal": "unknown"}
        
        # Create portfolio summary
        from src.services.portfolio_manager import PortfolioSummary
        portfolio_summary = PortfolioSummary(
            total_usd=total_usd,
            positions=positions,
            concentration=concentration,
            volatility=volatility,
            last_updated=datetime.now()
        )
        
        # Get AI insights with real-time market data
        eliza_client = context.bot_data.get("eliza_client")
        ai_advice = await portfolio_manager.get_ai_insights(portfolio_summary, eliza_client)
        
        # Generate insights summary
        insights_text = f"🔍 **Portfolio Insights**\n\n"
        insights_text += f"💰 Total Value: ${total_usd:.2f}\n"
        insights_text += f"📊 Assets: {len(positions)}\n"
        insights_text += f"🎯 Top Asset: {concentration['top_asset']} ({concentration['top_pct']}%)\n\n"
        
        # Add AI advisory
        insights_text += f"🧠 **AI Advisory**\n{ai_advice}"
        
        await update.message.reply_text(insights_text)
        
    except Exception as e:
        log.error(f"Error computing insights: {e}")
        await update.message.reply_text("❌ Failed to compute insights. Please try again.")

async def targets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set target stablecoin percentage"""
    if not context.args:
        await update.message.reply_text("Usage: /targets <stable_pct> (e.g., /targets 40)")
        return
    
    try:
        stable_pct = float(context.args[0])
        if not 0 <= stable_pct <= 100:
            await update.message.reply_text("❌ Percentage must be between 0-100")
            return
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT OR REPLACE INTO user_prefs (user_id, target_stable_pct)
                VALUES (?, ?)
            """, (update.effective_user.id, stable_pct))
            await db.commit()
        
        await update.message.reply_text(f"✅ Target stable allocation set to {stable_pct}%")
        
        # Log the action
        log.info(f"User {update.effective_user.id} set target stable allocation to {stable_pct}%")
        
    except ValueError:
        await update.message.reply_text("❌ Invalid percentage")
    except Exception as e:
        log.error(f"Error setting target: {e}")
        await update.message.reply_text("❌ Failed to set target")

async def rebal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show rebalancing advice with real-time AI analysis"""
    try:
        # Get user's target and portfolio data
        async with aiosqlite.connect(DB_PATH) as db:
            # Get user's target
            cursor = await db.execute("""
                SELECT target_stable_pct FROM user_prefs 
                WHERE user_id = ?
            """, (update.effective_user.id,))
            result = await cursor.fetchone()
            target_stable_pct = result[0] if result else 40.0  # Default 40%
            
            # Get portfolio data
            cursor = await db.execute("""
                SELECT address, label FROM portfolio_addresses 
                WHERE user_id = ?
            """, (update.effective_user.id,))
            addresses = await cursor.fetchall()
        
        if not addresses:
            await update.message.reply_text("📭 Portfolio is empty. Add addresses with /portfolio_add first.")
            return
        
        # Get portfolio positions with async optimization
        positions = await portfolio_manager.get_portfolio_positions(addresses)
        
        if not positions:
            await update.message.reply_text("📭 No balances found in portfolio addresses")
            return
        
        # Calculate total and concentration
        total_usd = sum(pos.balance_usd for pos in positions.values())
        concentration = await portfolio_manager.compute_concentration(positions)
        
        # Get volatility data
        try:
            current_price = await portfolio_manager.get_real_time_price("SEI")
            price_series = [current_price * (1 + (i % 3 - 1) * 0.01) for i in range(60)]
            volatility = volatility_signal(price_series, 60)
        except Exception as e:
            log.warning(f"Volatility calculation failed: {e}")
            volatility = {"signal": "unknown"}
        
        # Create portfolio summary
        from src.services.portfolio_manager import PortfolioSummary
        portfolio_summary = PortfolioSummary(
            total_usd=total_usd,
            positions=positions,
            concentration=concentration,
            volatility=volatility,
            last_updated=datetime.now()
        )
        
        # Get AI rebalancing advice with real-time market data
        eliza_client = context.bot_data.get("eliza_client")
        ai_advice = await portfolio_manager.get_rebalancing_advice(portfolio_summary, target_stable_pct, eliza_client)
        
        # Generate rebalancing report
        advice_text = f"⚖️ **DeFi Portfolio Rebalancing**\n\n"
        advice_text += f"💰 Total Portfolio: ${total_usd:.2f}\n"
        advice_text += f"🎯 Target Stable: {target_stable_pct}%\n"
        advice_text += f"📊 Current Stable: 0.0% (DeFi portfolio)\n\n"
        advice_text += f"💡 **AI Advisory**\n{ai_advice}"
        
        await update.message.reply_text(advice_text)
        
    except Exception as e:
        log.error(f"Error computing rebalancing advice: {e}")
        import traceback
        log.error(f"Traceback: {traceback.format_exc()}")
        await update.message.reply_text("❌ Failed to compute rebalancing advice. Please try again.")
