# Sei Agent Bot Setup Guide

## 1. Environment Configuration

Create a `.env` file in the root directory with the following content:

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Server Configuration (optional)
HOST=0.0.0.0
PORT=8080
WEBHOOK_URL=

# Logging
LOG_LEVEL=INFO

# Network Configuration
NETWORK=testnet  # or "mainnet" - defaults to testnet

# Sei Network Configuration (automatically selected based on NETWORK)
# Testnet Configuration (default)
SEI_TESTNET_RPC_URL=https://evm-rpc-testnet.sei-apis.com
SEI_TESTNET_LCD_URL=https://rest-testnet.sei-apis.com
SEI_TESTNET_CHAIN_ID=13280x530
SEI_TESTNET_EXPLORER=https://seitrace.com/?chain=atlantic-2

# Mainnet Configuration
SEI_MAINNET_RPC_URL=https://evm-rpc.sei-apis.com
SEI_MAINNET_LCD_URL=https://rest.sei-apis.com
SEI_MAINNET_CHAIN_ID=13290x531
SEI_MAINNET_EXPLORER=https://seitrace.com/?chain=pacific-1

# API Keys (Optional)
RIVALZ_API_KEY=your_rivalz_api_key_here
SEITRACE_API_KEY=your_seitrace_api_key_here

# ElizaOS AI Configuration (Optional - for AI advisory features)
# Reference: https://docs.elizaos.ai/ and https://github.com/elizaos-plugins/plugin-sei
ELIZA_API_URL=https://api.elizaos.ai
ELIZA_API_KEY=your_eliza_api_key_here
ELIZA_TIMEOUT_S=6

# Rivalz ADCS Configuration (Optional - for price oracle features)
# Reference: https://docs.rivalz.ai/ and https://blog.rivalz.ai/rivalz-ai-oracles-launch-on-base-unveiling-smart-contract-based-ai-agents/
RIVALZ_ADCS_BASE_URL=https://api.rivalz.ai/adcs/v1
RIVALZ_ADCS_TEST_MODE=true  # Set to false when you have API key
```

## 2. Getting Your Bot Token

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` command
3. Follow the instructions to create your bot
4. Copy the token and replace `your_bot_token_here` in the `.env` file

## 3. Installation

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Note: The bot requires the job-queue extension for portfolio alerts functionality
```

## 4. Running the Bot

```bash
python -m src.bot
```

## 5. Testing

Once the bot is running, test these commands in Telegram:

- `/start` - Welcome message
- `/help` - Show all available commands
- `/ping` - Check if bot is responsive
- `/chain` - Show Sei chain information
- `/balance 0x1234567890abcdef...` - Check balance (use a valid EVM address)

## 6. Supported Address Formats

The bot now supports:
- **EVM addresses**: `0x1234567890abcdef...` (recommended for testnet)
- **SEI addresses**: `sei1...` (native Sei format)

## 7. Network Configuration

The bot now supports both Sei Testnet and Mainnet with automatic configuration based on the `NETWORK` environment variable.

### Testnet (Default)
- **Network**: Sei Testnet (Atlantic-2)
- **Chain ID**: 13280x530
- **EVM RPC URL**: https://evm-rpc-testnet.sei-apis.com
- **LCD REST URL**: https://rest-testnet.sei-apis.com
- **Explorer**: https://seitrace.com/?chain=atlantic-2

### Mainnet
- **Network**: Sei Mainnet (Pacific-1)
- **Chain ID**: 13290x531
- **EVM RPC URL**: https://evm-rpc.sei-apis.com
- **LCD REST URL**: https://rest.sei-apis.com
- **Explorer**: https://seitrace.com/?chain=pacific-1

### Switching Networks
To switch between networks, simply update your `.env` file:
```env
# For testnet (default)
NETWORK=testnet

# For mainnet
NETWORK=mainnet
```

The bot will automatically use the correct RPC endpoints, chain IDs, and explorer URLs based on this setting.

## 8. Troubleshooting

### Balance Check Issues
- Make sure you're using valid EVM addresses (0x...)
- The bot will automatically try both EVM and native SEI balance methods
- Check the logs in `seiagentbot.log` for detailed error messages

### Connection Issues
- Verify your internet connection
- Check if the Sei testnet RPC is accessible
- Ensure your `.env` file is properly configured

## 9. Price Oracle Service

The bot now includes a `PriceOracle` service that provides real-time cryptocurrency prices:

### Features
- **Primary Source**: Rivalz ADCS (Agentic Data Coordination Service) for AI-native oracle data
- **Fallback**: Static prices for testnet development
- **Caching**: 5-second in-memory cache for performance
- **Supported Symbols**: SEI, USDC, ETH, BTC, SOL
- **Defensive Network**: 3 retries, 2-second timeout, automatic backoff

### Configuration
The PriceOracle supports three modes:

#### 1. Fallback Mode (Default)
Uses static prices for testnet development:
```env
RIVALZ_ADCS_API_KEY=
RIVALZ_ADCS_TEST_MODE=false
```

#### 2. Test Mode (Development)
Simulates Rivalz API responses for testing:
```env
RIVALZ_ADCS_API_KEY=
RIVALZ_ADCS_TEST_MODE=true
```

#### 3. Production Mode
Uses real Rivalz ADCS API:
```env
RIVALZ_ADCS_API_KEY=your_actual_api_key_here
RIVALZ_ADCS_TEST_MODE=false
```

### Testing Rivalz Integration
To test the Rivalz integration:

1. **Enable Test Mode**: Set `RIVALZ_ADCS_TEST_MODE=true` in your `.env` file
2. **Test Prices**: The service will simulate realistic market prices
3. **Performance**: Test caching and response times
4. **Fallback**: Verify fallback behavior when API is unavailable

### Usage
The PriceOracle service is available for integration with new bot commands and features.

## 10. Analytics Service

The bot now includes an `Analytics` service that provides comprehensive portfolio analysis:

### Features
- **Portfolio Concentration**: Analyzes asset concentration and diversification
- **Rebalancing Advice**: Provides smart rebalancing recommendations
- **Volatility Analysis**: Monitors price volatility and drawdown signals
- **Comprehensive Metrics**: Herfindahl-Hirschman Index (HHI) and portfolio health
- **Human-Readable Reports**: Formatted analysis for easy understanding

### Analytics Functions
- `compute_concentration()` - Analyzes portfolio concentration and warnings
- `compute_rebalance_advice()` - Provides rebalancing recommendations
- `volatility_signal()` - Monitors volatility and drawdown signals
- `compute_portfolio_metrics()` - Comprehensive portfolio analysis
- `format_portfolio_report()` - Human-readable report generation

### Usage
The Analytics service is available for integration with portfolio management commands and features.

## 11. Extended Sei Client

The Sei client has been extended with additional balance checking capabilities:

### New Functions
- **`get_evm_native_balance(address, rpc_url)`** - Get EVM balance in wei using `eth_getBalance`
- **`get_native_sei_balance(address, lcd_base_url)`** - Get native SEI balance in usei using Cosmos REST API

### Network Configuration
The bot now supports both testnet and mainnet configurations:

#### Testnet (Default)
- **EVM RPC**: `https://evm-rpc-testnet.sei-apis.com`
- **LCD REST**: `https://rest-testnet.sei-apis.com`
- **Chain ID**: `13280x530`
- **Explorer**: `https://seitrace.com/?chain=atlantic-2`

#### Mainnet
- **EVM RPC**: `https://evm-rpc.sei-apis.com`
- **LCD REST**: `https://rest.sei-apis.com`
- **Chain ID**: `13290x531`
- **Explorer**: `https://seitrace.com/?chain=pacific-1`

### Features
- ✅ Configurable RPC and LCD URLs for both networks
- ✅ Proper address validation for EVM (0x...) and SEI (sei1...) formats
- ✅ Returns balances in native units (wei for EVM, usei for SEI)
- ✅ Comprehensive error handling and logging
- ✅ Backward compatibility with existing configuration

## 12. Portfolio Management

The bot now includes comprehensive portfolio management capabilities:

### Portfolio Commands
- **`/portfolio_add <address> [label]`** - Add EVM or SEI address to your portfolio
- **`/portfolio_rm <address>`** - Remove address from portfolio
- **`/portfolio`** - Show portfolio summary with balances and USD values
- **`/insights`** - Portfolio risk analysis and concentration insights
- **`/targets <stable_pct>`** - Set target stablecoin allocation (0-100%)
- **`/rebal`** - Get rebalancing advice based on current target

### Features
- ✅ **Address Validation**: Supports both EVM (0x...) and SEI (sei1...) addresses
- ✅ **Real-time Balances**: Fetches current balances using extended Sei client
- ✅ **Price Integration**: Uses PriceOracle for real-time USD conversion
- ✅ **Risk Analysis**: Concentration analysis and volatility signals
- ✅ **Rebalancing**: Smart rebalancing advice with configurable targets
- ✅ **User Preferences**: Per-user target allocation settings
- ✅ **Compact Responses**: All responses under 15 lines with minimal emojis

## 13. Portfolio Alerts

The bot now includes real-time portfolio monitoring and alerting capabilities:

### Alert Commands
- **`/alerts_on <drop_pct>`** - Enable portfolio drop monitoring
- **`/alerts_off`** - Disable portfolio alerts

### Features
- ✅ **Real-time Monitoring**: Checks portfolio value every 30 seconds
- ✅ **5-minute Moving Anchor**: Updates baseline every 5 minutes
- ✅ **Smart Alerting**: Warns only once per 5-minute window
- ✅ **Cached Prices**: Uses PriceOracle for efficient price fetching
- ✅ **In-memory Storage**: Fast anchor tracking per user
- ✅ **Spam Prevention**: Prevents alert flooding

### How It Works
1. **Enable Alerts**: `/alerts_on 10` sets 10% drop threshold
2. **Background Monitoring**: Job runs every 30 seconds
3. **Anchor Updates**: Baseline updates every 5 minutes
4. **Drop Detection**: Compares current vs anchor value
5. **Smart Alerts**: Sends warning once per window if threshold exceeded

### Alert Message Format
```
⚠️ **Portfolio Alert**

Your portfolio has dropped 12.5% from $100.00 to $87.50

Alert threshold: 10%
Consider reviewing your positions.
```

### Database Tables
The portfolio system uses two database tables:
- **`portfolio_addresses`**: Stores user addresses and optional labels
- **`user_prefs`**: Stores user preferences like target stable allocation

### Usage Examples
```
/portfolio_add 0x1234567890abcdef1234567890abcdef12345678 wallet1
/portfolio_add sei1abcdefghijklmnopqrstuvwxyz1234567890 cold_storage
/portfolio
/insights
/targets 40
/rebal
/alerts_on 10
/alerts_off
```

## 14. ElizaOS AI Integration

The Sei Agent Bot now includes advanced AI advisory capabilities powered by ElizaOS, providing intelligent portfolio analysis and risk assessment.

### **🤖 AI-Powered Features**

#### **Portfolio Insights (`/insights`)**
- **AI Advisory**: Intelligent analysis of portfolio concentration and risk
- **Context-Aware**: Sends rich portfolio data to ElizaOS for personalized advice
- **Professional Tone**: Friendly, actionable insights without financial guarantees
- **Fallback System**: Graceful degradation when AI services are unavailable

#### **Smart Alert System**
- **Intelligent Explanations**: AI-powered context analysis for portfolio drops
- **Calming Responses**: Professional tone that reduces panic during volatility
- **Market Context**: Explains whether drops are normal or concerning
- **Actionable Advice**: Suggests appropriate responses to market movements

#### **Rebalancing Intelligence**
- **AI-Enhanced Advice**: ElizaOS provides context-aware rebalancing recommendations
- **Risk Assessment**: Considers market conditions and volatility in recommendations
- **Timing Guidance**: Suggests optimal timing for rebalancing actions

### **🔧 Technical Implementation**

#### **ElizaOS Client**
- **Robust HTTP Client**: Async client with retry logic and exponential backoff
- **Timeout Management**: 2-second timeouts with comprehensive error handling
- **Fallback Mechanisms**: Intelligent fallback analysis when AI is unavailable
- **Context Building**: Rich portfolio data sent to ElizaOS for analysis

#### **AI Prompts**
The bot uses specialized ElizaOS prompts for different scenarios:
- **Portfolio Analysis**: Analyzes concentration, volatility, and provides actionable advice
- **Alert Context**: Explains market movements and suggests appropriate responses
- **Rebalancing Guidance**: Provides intelligent rebalancing recommendations

#### **Configuration**
```env
# ElizaOS AI Configuration
ELIZA_API_URL=https://api.elizaos.ai
ELIZA_API_KEY=your_eliza_api_key_here
ELIZA_TIMEOUT_S=6
```

### **📊 Example AI Advisory Output**

#### **Portfolio Insights**
```
🔍 Portfolio Insights

💰 Total Value: $1,250.50
📊 Assets: 2
🎯 Top Asset: 0x1234... (64.0%)

🧠 AI Advisory
Your portfolio shows moderate concentration risk with 64% in your top asset. 
Consider diversifying across multiple positions to reduce volatility exposure. 
Current market conditions suggest maintaining a defensive stance while monitoring 
for rebalancing opportunities.
```

#### **Intelligent Alerts**
```
⚠️ Portfolio Alert

Your portfolio has dropped 5.2% from $1,250.50 to $1,185.47

Alert threshold: 5%
🧠 AI Insight: This appears to be normal market volatility within expected ranges. 
Consider this a good opportunity to review your allocation strategy rather than 
making hasty decisions.
```

### **🛡️ Fallback System**

- **Graceful Degradation**: If ElizaOS is unavailable, bot uses intelligent fallback analysis
- **No Service Interruption**: Portfolio functionality continues without AI features
- **Basic Insights**: Provides concentration warnings and volatility signals
- **Error Logging**: Comprehensive logging for debugging AI integration issues

### **🔗 Integration Points**

- **`/insights` Command**: Enhanced with AI advisory powered by ElizaOS
- **Portfolio Alerts**: Include intelligent context analysis and market explanations
- **Bot Startup**: ElizaOS client initialized at startup with proper error handling
- **Context Building**: Rich portfolio data automatically sent to ElizaOS

## 15. DeFi Assistant Features

The Sei Agent Bot provides comprehensive DeFi portfolio management and monitoring capabilities:

### **📊 Portfolio Management Commands**

| Command | Description | Example |
|---------|-------------|---------|
| `/portfolio_add` | Add address to portfolio | `/portfolio_add 0xabc... "trading"` |
| `/portfolio_rm` | Remove address from portfolio | `/portfolio_rm 0xabc...` |
| `/portfolio` | Show portfolio summary with USD values | `/portfolio` |
| `/insights` | Portfolio risk analysis & AI advisory | `/insights` |
| `/targets` | Set target stablecoin allocation | `/targets 40` |
| `/rebal` | Get rebalancing advice | `/rebal` |

### **🔔 Portfolio Alerts**

| Command | Description | Example |
|---------|-------------|---------|
| `/alerts_on` | Enable portfolio drop monitoring | `/alerts_on 5` |
| `/alerts_off` | Disable portfolio alerts | `/alerts_off` |

### **🌐 Data Sources**

The bot integrates multiple data sources for comprehensive portfolio tracking:

- **Sei EVM RPC**: Native EVM balance queries (`eth_getBalance`)
- **Sei LCD REST**: Native SEI balance queries (`/cosmos/bank/v1beta1/balances/{address}`)
- **Rivalz ADCS**: Real-time price oracle with fallback caching
- **ElizaOS AI**: Intelligent portfolio analysis and advisory services
- **In-Memory Analytics**: Portfolio concentration and volatility analysis

### **🔄 Network Switching**

To switch between testnet and mainnet:

```env
# For testnet (default)
NETWORK=testnet

# For mainnet
NETWORK=mainnet
```

The bot automatically uses the correct endpoints:
- **Testnet**: `https://evm-rpc-testnet.sei-apis.com`
- **Mainnet**: `https://evm-rpc.sei-apis.com`

### **⚠️ Known Limitations**

- **Native Balances Only**: Currently supports SEI native token balances only
- **No Token Tracking**: ERC-20 tokens and other assets not yet supported
- **Price Oracle**: Uses Rivalz ADCS with test mode fallback
- **AI Advisory**: ElizaOS integration requires valid API key for full functionality
- **Alert Frequency**: Limited to one alert per 5-minute window per user

### **🧪 Smoke Test Commands**

Test the complete DeFi assistant workflow:

```bash
# 1. Add your testnet address
/portfolio_add 0x44dd9cCA62845775f5EF3Ce01eaF90b43d8f1Ce2 "test wallet"

# 2. View portfolio summary
/portfolio

# 3. Set target and get rebalancing advice
/targets 40
/rebal

# 4. Enable alerts and test monitoring
/alerts_on 5
```

## 16. Next Steps

After testing on testnet, you can switch to mainnet by updating the configuration:

```env
# Sei Mainnet Configuration
SEI_RPC_URL=https://evm-rpc.sei-apis.com
SEI_CHAIN_ID=13290x531
SEI_EXPLORER_BASE=https://seitrace.com/?chain=pacific-1
```
