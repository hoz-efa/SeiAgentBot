from __future__ import annotations
import math
import statistics
from typing import Dict, List, Optional

def compute_concentration(positions: Dict[str, float]) -> Dict:
    """
    Compute portfolio concentration analysis.
    
    Args:
        positions: Dictionary mapping asset symbols to USD values
        
    Returns:
        Dictionary with concentration analysis:
        {
            "top_asset": str,
            "top_pct": float,
            "warnings": List[str]
        }
    """
    if not positions:
        return {
            "top_asset": "",
            "top_pct": 0.0,
            "warnings": ["No positions found"]
        }
    
    total_value = sum(positions.values())
    if total_value <= 0:
        return {
            "top_asset": "",
            "top_pct": 0.0,
            "warnings": ["Total portfolio value is zero or negative"]
        }
    
    # Find top asset
    top_asset = max(positions.items(), key=lambda x: x[1])
    top_pct = (top_asset[1] / total_value) * 100
    
    warnings = []
    
    # Concentration warnings
    if top_pct > 50:
        warnings.append(f"High concentration: {top_asset[0]} is {top_pct:.1f}% of portfolio")
    elif top_pct > 30:
        warnings.append(f"Moderate concentration: {top_asset[0]} is {top_pct:.1f}% of portfolio")
    
    # Diversification check
    if len(positions) < 3:
        warnings.append("Low diversification: Consider adding more assets")
    elif len(positions) < 5:
        warnings.append("Moderate diversification: Portfolio could benefit from more assets")
    
    # Check for very small positions (less than 1% each)
    small_positions = [asset for asset, value in positions.items() 
                      if (value / total_value) * 100 < 1.0]
    if small_positions:
        warnings.append(f"Small positions detected: {', '.join(small_positions)} (< 1% each)")
    
    return {
        "top_asset": top_asset[0],
        "top_pct": round(top_pct, 2),
        "warnings": warnings
    }

def compute_rebalance_advice(total_usd: float, stable_usd: float, target_stable_pct: float) -> Dict:
    """
    Compute rebalancing advice for stablecoin allocation.
    
    Args:
        total_usd: Total portfolio value in USD
        stable_usd: Current stablecoin allocation in USD
        target_stable_pct: Target percentage for stablecoins (0-100)
        
    Returns:
        Dictionary with rebalancing advice:
        {
            "delta_usd": float,
            "suggestion": str,
            "current_pct": float,
            "target_pct": float
        }
    """
    if total_usd <= 0:
        return {
            "delta_usd": 0.0,
            "suggestion": "Portfolio value is zero or negative",
            "current_pct": 0.0,
            "target_pct": target_stable_pct
        }
    
    current_pct = (stable_usd / total_usd) * 100
    target_stable_usd = (target_stable_pct / 100) * total_usd
    delta_usd = target_stable_usd - stable_usd
    
    # Generate human-readable suggestion
    if abs(delta_usd) < total_usd * 0.01:  # Less than 1% difference
        suggestion = "Portfolio is well-balanced. No rebalancing needed."
    elif delta_usd > 0:
        if delta_usd > total_usd * 0.1:  # More than 10% difference
            suggestion = f"Consider adding ${delta_usd:,.0f} to stablecoins for safety"
        else:
            suggestion = f"Consider adding ${delta_usd:,.0f} to stablecoins"
    else:
        if abs(delta_usd) > total_usd * 0.1:  # More than 10% difference
            suggestion = f"Consider reducing stablecoins by ${abs(delta_usd):,.0f} for growth"
        else:
            suggestion = f"Consider reducing stablecoins by ${abs(delta_usd):,.0f}"
    
    return {
        "delta_usd": round(delta_usd, 2),
        "suggestion": suggestion,
        "current_pct": round(current_pct, 2),
        "target_pct": target_stable_pct
    }

def volatility_signal(series: List[float], lookback: int = 60) -> Dict:
    """
    Compute volatility signal based on price series.
    
    Args:
        series: List of price values (most recent last)
        lookback: Number of periods to analyze (default: 60)
        
    Returns:
        Dictionary with volatility analysis:
        {
            "stdev": float,
            "drawdown_pct": float,
            "signal": "ok" | "warn" | "alert",
            "volatility_pct": float
        }
    """
    if not series or len(series) < 2:
        return {
            "stdev": 0.0,
            "drawdown_pct": 0.0,
            "signal": "ok",
            "volatility_pct": 0.0,
            "error": "Insufficient data for analysis"
        }
    
    # Use only the last 'lookback' periods
    recent_series = series[-lookback:] if len(series) > lookback else series
    
    if len(recent_series) < 2:
        return {
            "stdev": 0.0,
            "drawdown_pct": 0.0,
            "signal": "ok",
            "volatility_pct": 0.0,
            "error": "Insufficient data for analysis"
        }
    
    # Calculate standard deviation
    stdev = statistics.stdev(recent_series)
    mean_price = statistics.mean(recent_series)
    volatility_pct = (stdev / mean_price) * 100 if mean_price > 0 else 0
    
    # Calculate maximum drawdown
    peak = recent_series[0]
    max_drawdown = 0.0
    
    for price in recent_series:
        if price > peak:
            peak = price
        drawdown = (peak - price) / peak * 100 if peak > 0 else 0
        max_drawdown = max(max_drawdown, drawdown)
    
    # Determine signal based on thresholds
    signal = "ok"
    
    # Volatility thresholds
    if volatility_pct > 50:
        signal = "alert"
    elif volatility_pct > 25:
        signal = "warn"
    
    # Drawdown thresholds
    if max_drawdown > 30:
        signal = "alert"
    elif max_drawdown > 15:
        signal = "warn"
    
    # If both volatility and drawdown are high, prioritize alert
    if volatility_pct > 25 and max_drawdown > 15:
        signal = "alert"
    
    return {
        "stdev": round(stdev, 4),
        "drawdown_pct": round(max_drawdown, 2),
        "signal": signal,
        "volatility_pct": round(volatility_pct, 2)
    }

def compute_portfolio_metrics(positions: Dict[str, float], 
                            stable_usd: float = 0.0,
                            target_stable_pct: float = 20.0) -> Dict:
    """
    Compute comprehensive portfolio metrics.
    
    Args:
        positions: Dictionary mapping asset symbols to USD values
        stable_usd: Current stablecoin allocation in USD
        target_stable_pct: Target percentage for stablecoins
        
    Returns:
        Dictionary with comprehensive portfolio analysis
    """
    total_usd = sum(positions.values()) + stable_usd
    
    concentration = compute_concentration(positions)
    rebalance = compute_rebalance_advice(total_usd, stable_usd, target_stable_pct)
    
    # Calculate additional metrics
    num_assets = len(positions)
    avg_position = total_usd / num_assets if num_assets > 0 else 0
    
    # Herfindahl-Hirschman Index (HHI) for concentration
    hhi = sum(((value / total_usd) * 100) ** 2 for value in positions.values()) if total_usd > 0 else 0
    
    # Concentration interpretation
    if hhi > 2500:
        concentration_level = "Very High"
    elif hhi > 1500:
        concentration_level = "High"
    elif hhi > 1000:
        concentration_level = "Moderate"
    else:
        concentration_level = "Low"
    
    return {
        "total_usd": round(total_usd, 2),
        "num_assets": num_assets,
        "avg_position": round(avg_position, 2),
        "concentration": concentration,
        "rebalance": rebalance,
        "hhi": round(hhi, 2),
        "concentration_level": concentration_level,
        "stable_allocation": {
            "current_usd": stable_usd,
            "current_pct": round((stable_usd / total_usd) * 100, 2) if total_usd > 0 else 0,
            "target_pct": target_stable_pct
        }
    }

def format_portfolio_report(metrics: Dict) -> str:
    """
    Format portfolio metrics into a human-readable report.
    
    Args:
        metrics: Output from compute_portfolio_metrics()
        
    Returns:
        Formatted string report
    """
    report = f"📊 **Portfolio Analysis**\n\n"
    report += f"💰 **Total Value**: ${metrics['total_usd']:,.2f}\n"
    report += f"📈 **Assets**: {metrics['num_assets']} positions\n"
    report += f"📊 **Concentration**: {metrics['concentration_level']} (HHI: {metrics['hhi']})\n"
    report += f"🎯 **Top Asset**: {metrics['concentration']['top_asset']} ({metrics['concentration']['top_pct']}%)\n\n"
    
    # Rebalancing advice
    rebalance = metrics['rebalance']
    if abs(rebalance['delta_usd']) > 0:
        report += f"⚖️ **Rebalancing**: {rebalance['suggestion']}\n"
        report += f"📊 **Stable Allocation**: {rebalance['current_pct']}% → {rebalance['target_pct']}%\n\n"
    
    # Warnings
    if metrics['concentration']['warnings']:
        report += "⚠️ **Warnings**:\n"
        for warning in metrics['concentration']['warnings']:
            report += f"• {warning}\n"
    
    return report
