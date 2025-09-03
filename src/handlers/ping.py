from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
import time

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    start = time.perf_counter()
    sent_message = await update.message.reply_text("Pinging...")
    end = time.perf_counter()
    latency_ms = (end - start) * 1000
    await sent_message.edit_text(f"pong \u26a1 {latency_ms:.2f} ms")
