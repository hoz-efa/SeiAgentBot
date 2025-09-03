from __future__ import annotations
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, computed_field

class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str = Field(..., description="BotFather token")

    # Optional server settings (webhook later; polling for now)
    HOST: str = Field("0.0.0.0")
    PORT: int = Field(8080)
    WEBHOOK_URL: str | None = None

    # Logging
    LOG_LEVEL: str = Field("INFO")

    # Network Configuration
    NETWORK: Literal["testnet", "mainnet"] = Field("testnet", description="Sei network to use")

    # Sei Network Configuration (from https://docs.sei.io/evm/networks)
    # Testnet Configuration
    SEI_TESTNET_RPC_URL: str = Field("https://evm-rpc-testnet.sei-apis.com", description="Sei Testnet EVM RPC URL")
    SEI_TESTNET_LCD_URL: str = Field("https://rest-testnet.sei-apis.com", description="Sei Testnet LCD REST API URL")
    SEI_TESTNET_CHAIN_ID: str = Field("13280x530", description="Sei Testnet Chain ID")
    SEI_TESTNET_EXPLORER: str = Field("https://seitrace.com/?chain=atlantic-2", description="Sei Testnet Explorer")
    
    # Mainnet Configuration
    SEI_MAINNET_RPC_URL: str = Field("https://evm-rpc.sei-apis.com", description="Sei Mainnet EVM RPC URL")
    SEI_MAINNET_LCD_URL: str = Field("https://rest.sei-apis.com", description="Sei Mainnet LCD REST API URL")
    SEI_MAINNET_CHAIN_ID: str = Field("13290x531", description="Sei Mainnet Chain ID")
    SEI_MAINNET_EXPLORER: str = Field("https://seitrace.com/?chain=pacific-1", description="Sei Mainnet Explorer")

    # API Keys (Optional)
    RIVALZ_API_KEY: str | None = Field("", description="Rivalz ADCS API key for price oracle access")
    SEITRACE_API_KEY: str | None = Field("", description="SeiTrace API key for enhanced explorer features")
    ELIZA_OS_API_KEY: str | None = Field("", description="ElizaOS API key for enhanced AI recommendations")
    
    # ElizaOS Configuration
    ELIZA_API_URL: str = Field("https://elizaos.ai/api", description="ElizaOS API endpoint URL")
    ELIZA_API_KEY: str = Field("", description="ElizaOS API key for AI advisory services")
    ELIZA_TIMEOUT_S: int = Field(10, description="ElizaOS API timeout in seconds")

    # Rivalz ADCS Configuration (AI Oracle infrastructure)
    # Reference: https://docs.rivalz.ai/ and https://blog.rivalz.ai/rivalz-ai-oracles-launch-on-base-unveiling-smart-contract-based-ai-agents/
    RIVALZ_ADCS_BASE_URL: str = Field("https://api.rivalz.ai/adcs/v1", description="Rivalz ADCS API base URL")
    RIVALZ_ADCS_TEST_MODE: bool = Field(True, description="Enable test mode for Rivalz ADCS (simulates API responses)")

    # Computed fields for current network
    @computed_field
    @property
    def SEI_EVM_RPC_URL(self) -> str:
        """Current Sei EVM RPC URL based on network setting"""
        return self.SEI_MAINNET_RPC_URL if self.NETWORK == "mainnet" else self.SEI_TESTNET_RPC_URL
    
    @computed_field
    @property
    def SEI_LCD_URL(self) -> str:
        """Current Sei LCD REST API URL based on network setting"""
        return self.SEI_MAINNET_LCD_URL if self.NETWORK == "mainnet" else self.SEI_TESTNET_LCD_URL
    
    @computed_field
    @property
    def SEI_CHAIN_ID(self) -> str:
        """Current Sei Chain ID based on network setting"""
        return self.SEI_MAINNET_CHAIN_ID if self.NETWORK == "mainnet" else self.SEI_TESTNET_CHAIN_ID
    
    @computed_field
    @property
    def SEI_EXPLORER_BASE(self) -> str:
        """Current Sei Explorer URL based on network setting"""
        return self.SEI_MAINNET_EXPLORER if self.NETWORK == "mainnet" else self.SEI_TESTNET_EXPLORER

    # Backward compatibility aliases
    @computed_field
    @property
    def SEI_RPC_URL(self) -> str:
        """Alias for SEI_EVM_RPC_URL (backward compatibility)"""
        return self.SEI_EVM_RPC_URL
    
    @computed_field
    @property
    def RIVALZ_ADCS_API_KEY(self) -> str | None:
        """Alias for RIVALZ_API_KEY (backward compatibility)"""
        return self.RIVALZ_API_KEY

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

settings = Settings()  # singleton-style import
