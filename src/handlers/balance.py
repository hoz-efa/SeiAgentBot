from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
import logging

log = logging.getLogger(__name__)

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "Usage: /balance <address>\n\n"
            "Supports:\n"
            "• EVM addresses (0x...)\n"
            "• SEI addresses (sei1...)\n\n"
            "Example: /balance 0x1234567890abcdef..."
        )
        return
    
    sei = context.bot_data["sei_client"]
    address = context.args[0].strip()
    
    # Validate address format using the new validation method
    is_valid, error_msg = sei.validate_address(address)
    if not is_valid:
        await update.message.reply_text(
            f"❌ {error_msg}\n\n"
            "Please provide a valid:\n"
            "• EVM address (0x followed by 40 hex characters)\n"
            "• SEI address (sei1 followed by 38 alphanumeric characters)"
        )
        return
    
    # Show loading message
    loading_msg = await update.message.reply_text("🔍 Fetching balance...")
    
    try:
        # Test connection first
        if not await sei.test_connection():
            await loading_msg.edit_text(
                "❌ Unable to connect to Sei network.\n\n"
                "Please check:\n"
                "• Your internet connection\n"
                "• Network status\n"
                "• Try again later"
            )
            return
        
        # Try EVM balance first
        data = await sei.get_balance(address)
        
        if not data:
            # Try native SEI balance as fallback
            data = await sei.get_native_balance(address)
        
        if not data:
            await loading_msg.edit_text(
                f"❌ No balance found for address: `{address}`\n\n"
                "This could mean:\n"
                "• The address has no tokens\n"
                "• The address format is incorrect\n"
                "• Network connection issue",
                parse_mode='Markdown'
            )
            return
        
        # Format balance response
        balance_lines = []
        for balance_item in data:
            amount = balance_item.get('amount', '0')
            denom = balance_item.get('denom', 'unknown')
            
            # Format large numbers
            try:
                amount_float = float(amount)
                
                # Convert usei to SEI (1 SEI = 1,000,000 usei)
                if denom == 'usei':
                    sei_amount = amount_float / 1_000_000
                    if sei_amount >= 1:
                        formatted_amount = f"{sei_amount:.4f} SEI ({amount_float:,.0f} usei)"
                    else:
                        formatted_amount = f"{sei_amount:.8f} SEI ({amount_float:,.0f} usei)"
                else:
                    # For other tokens, format normally
                    if amount_float >= 1000000:
                        formatted_amount = f"{amount_float:,.2f}"
                    elif amount_float >= 1:
                        formatted_amount = f"{amount_float:.4f}"
                    else:
                        formatted_amount = f"{amount_float:.8f}"
                    formatted_amount = f"{formatted_amount} {denom}"
            except ValueError:
                formatted_amount = f"{amount} {denom}"
            
            balance_lines.append(f"💰 **{formatted_amount}**")
        
        response_text = (
            f"💳 **Balance for:** `{address}`\n"
            f"🌐 **Network:** Sei Testnet (Atlantic-2)\n\n" +
            "\n".join(balance_lines) +
            f"\n\n🔗 [View on Explorer](https://seitrace.com/address/{address}?chain=atlantic-2)"
        )
        
        await loading_msg.edit_text(
            response_text,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    except Exception as e:
        log.error(f"Error in balance handler: {str(e)}")
        await loading_msg.edit_text(
            f"❌ Error fetching balance for `{address}`\n\n"
            "Please try again later or check the address format.",
            parse_mode='Markdown'
        )
