from __future__ import annotations
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

START_TEXT = (
    "\U0001f44b\U0001f3fb <b>Welcome to Sei Agent Hub (Python)</b>\n\n"
    "Use /help to see available commands.\n"
    "We'll add Sei, swaps, NFT, governance, and alerts step-by-step."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(START_TEXT, parse_mode=ParseMode.HTML)
