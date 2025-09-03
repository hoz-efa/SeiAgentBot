from __future__ import annotations
import asyncio
import logging
import sys

from telegram import BotCommand
from telegram.ext import (
    Application, CommandHandler, AIORateLimiter
)

from src.config import settings
from src.services.sei_client import SeiClient
from src.handlers.start import start
from src.handlers.help import help_cmd
from src.handlers.ping import ping
from src.handlers.balance import balance
from src.handlers.watch import watch, unwatch, watches, test_monitor, rescan_watches, setup_watch_job
from src.handlers.portfolio import portfolio_add, portfolio_rm, portfolio, insights, targets, rebal
from src.handlers.alerts import alerts_on, alerts_off, setup_alerts_job
from src.db import init_db
from src.db_migrations import run_migrations
from src.services.eliza_client import ElizaClient
from logging.handlers import RotatingFileHandler

if sys.platform != "win32":
    try:
        import uvloop  # type: ignore
        uvloop.install()
    except Exception:
        pass

log_handler = RotatingFileHandler(
    "seiagentbot.log", maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
)
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[log_handler]
)
log = logging.getLogger("sei-bot")

async def chain_info(update, context):
    sei: SeiClient = context.bot_data["sei_client"]
    
    # Test connection
    is_connected = await sei.test_connection()
    status_emoji = "🟢" if is_connected else "🔴"
    status_text = "Connected" if is_connected else "Disconnected"
    
    info = await sei.get_chain_info()
    text = (
        f"<b>Sei Network Status</b>\n\n"
        f"🌐 <b>Network:</b> <code>{info['chain_id']}</code>\n"
        f"🔗 <b>RPC:</b> <code>{info['rpc']}</code>\n"
        f"📊 <b>Status:</b> {status_emoji} {status_text}\n\n"
        f"<b>Supported Address Formats:</b>\n"
        f"• EVM: <code>0x...</code> (recommended for testnet)\n"
        f"• SEI: <code>sei1...</code> (native format)\n\n"
        f"<b>Explorer:</b> <a href='{sei.explorer_base}'>SeiTrace</a>"
    )
    await update.message.reply_html(text, disable_web_page_preview=True)

async def refresh_commands(update, context):
    """Manually refresh bot commands"""
    try:
        commands = [
            BotCommand("start", "🚀 Start the bot"),
            BotCommand("help", "❓ Show help and commands"),
            BotCommand("ping", "🏓 Health check"),
            BotCommand("chain", "🌐 Show Sei network status"),
            BotCommand("balance", "💰 Check wallet balance"),
            BotCommand("watch", "👀 Watch an address"),
            BotCommand("unwatch", "❌ Stop watching address"),
            BotCommand("watches", "📋 List watched addresses"),
            BotCommand("portfolio_add", "➕ Add address to portfolio"),
            BotCommand("portfolio_rm", "➖ Remove address from portfolio"),
            BotCommand("portfolio", "💼 Show portfolio summary"),
            BotCommand("insights", "🔍 Portfolio insights & risk analysis"),
            BotCommand("targets", "🎯 Set stable allocation target"),
            BotCommand("rebal", "⚖️ Rebalancing advice"),
            BotCommand("alerts_on", "🔔 Enable portfolio drop alerts"),
            BotCommand("alerts_off", "🔕 Disable portfolio alerts"),
        ]
        
        await context.bot.set_my_commands(commands)
        await update.message.reply_text(
            f"✅ Successfully refreshed {len(commands)} commands!\n\n"
            "The bot commands should now appear in your Telegram menu."
        )
        log.info("Commands refreshed manually")
        
    except Exception as e:
        log.error(f"Error refreshing commands: {str(e)}")
        await update.message.reply_text(f"❌ Error refreshing commands: {str(e)}")

async def on_startup(app: Application) -> None:
    print(">>> on_startup called <<<")
    log.info("on_startup called")
    
    try:
        # Initialize ElizaOS client
        try:
            eliza_client = ElizaClient(
                base_url=settings.ELIZA_API_URL,
                api_key=settings.ELIZA_API_KEY,
                timeout_s=settings.ELIZA_TIMEOUT_S
            )
            app.bot_data["eliza_client"] = eliza_client
            log.info("ElizaOS client initialized")
        except Exception as e:
            log.error(f"Error initializing ElizaOS client: {e}")
            app.bot_data["eliza_client"] = None
        
        # Define all bot commands
        commands = [
            BotCommand("start", "🚀 Start the bot"),
            BotCommand("help", "❓ Show help and commands"),
            BotCommand("ping", "🏓 Health check"),
            BotCommand("chain", "🌐 Show Sei network status"),
            BotCommand("balance", "💰 Check wallet balance"),
            BotCommand("watch", "👀 Watch an address"),
            BotCommand("unwatch", "❌ Stop watching address"),
            BotCommand("watches", "📋 List watched addresses"),
            BotCommand("test_monitor", "🧪 Test transaction monitoring"),
            BotCommand("rescan_watches", "🔍 Extended scan for missed transactions"),

            BotCommand("portfolio_add", "➕ Add address to portfolio"),
            BotCommand("portfolio_rm", "➖ Remove address from portfolio"),
            BotCommand("portfolio", "💼 Show portfolio summary"),
            BotCommand("insights", "🔍 Portfolio insights & risk analysis"),
            BotCommand("targets", "🎯 Set stable allocation target"),
            BotCommand("rebal", "⚖️ Rebalancing advice"),
            BotCommand("alerts_on", "🔔 Enable portfolio drop alerts"),
            BotCommand("alerts_off", "🔕 Disable portfolio alerts"),
        ]
        
        # Set the commands
        await app.bot.set_my_commands(commands)
        log.info(f"Successfully registered {len(commands)} commands")
        
        # Also set the bot description and short description
        await app.bot.set_my_description(
            "🤖 Advanced DeFi Portfolio Management & AI-Powered Blockchain Monitoring for Sei Network\n\n"
            "Features:\n"
            "• 📊 Real-time portfolio tracking with USD valuations\n"
            "• 🤖 AI-powered analytics and risk assessment\n"
            "• 🔔 Intelligent portfolio drop alerts\n"
            "• ⚖️ Smart rebalancing recommendations\n"
            "• 🌐 Multi-network support (Testnet/Mainnet)\n"
            "• 📈 Price oracle integration with Rivalz ADCS\n"
            "• 🧠 ElizaOS AI advisory integration\n\n"
            "Built for AI/Accelathon 2024 - Where AI agents go from smart to sovereign!"
        )
        await app.bot.set_my_short_description("🤖 AI-Powered DeFi Portfolio Management for Sei Network")
        
        log.info("Bot startup completed successfully")
        
    except Exception as e:
        log.error(f"Error during startup: {str(e)}")
        print(f"Error during startup: {str(e)}")
        # Don't raise the exception, let the bot continue running

# Global app instance for background monitoring
_app_instance = None

def get_application():
    """Get the application instance for background monitoring"""
    return _app_instance

async def main() -> None:
    await init_db()  # Ensure DB and table are created before anything else
    await run_migrations()  # Run database migrations
    # Create application (JobQueue will be auto-created if available)
    app = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .rate_limiter(AIORateLimiter())
        .post_init(on_startup)
        .build()
    )

    # Inject shared clients into bot_data for handler access
    sei_client = SeiClient(
        rpc_url=settings.SEI_RPC_URL,
        chain_id=settings.SEI_CHAIN_ID,
        explorer_base=settings.SEI_EXPLORER_BASE,
    )
    app.bot_data["sei_client"] = sei_client

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("chain", chain_info))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("watch", watch))
    app.add_handler(CommandHandler("unwatch", unwatch))
    app.add_handler(CommandHandler("watches", watches))
    app.add_handler(CommandHandler("test_monitor", test_monitor))
    app.add_handler(CommandHandler("rescan_watches", rescan_watches))

    app.add_handler(CommandHandler("portfolio_add", portfolio_add))
    app.add_handler(CommandHandler("portfolio_rm", portfolio_rm))
    app.add_handler(CommandHandler("portfolio", portfolio))
    app.add_handler(CommandHandler("insights", insights))
    app.add_handler(CommandHandler("targets", targets))
    app.add_handler(CommandHandler("rebal", rebal))
    app.add_handler(CommandHandler("alerts_on", alerts_on))
    app.add_handler(CommandHandler("alerts_off", alerts_off))
    app.add_handler(CommandHandler("refresh", refresh_commands))

    # Store app instance for background monitoring
    global _app_instance
    _app_instance = app

    log.info("Starting bot (polling mode)...")
    await app.initialize()
    await app.start()
    
    # Setup job queues after application is initialized
    try:
        setup_alerts_job(app.job_queue)
        # Pass the application instance directly to the watch setup
        from src.handlers.watch import setup_watch_job_with_app
        setup_watch_job_with_app(app)
        log.info("Job queues setup completed")
    except Exception as e:
        log.error(f"Error setting up job queues: {e}")
    
    # Ensure commands are set after bot is fully started
    try:
        await on_startup(app)
    except Exception as e:
        log.error(f"Error setting commands after startup: {str(e)}")
    
    try:
        await app.updater.start_polling(allowed_updates=[])  # no webhook yet
        await asyncio.Event().wait()  # run forever
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped")
