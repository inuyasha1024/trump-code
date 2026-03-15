"""
信號→市場映射器

將川普密碼信號（TARIFF, DEAL, RELIEF, ACTION, THREAT）
映射到 Polymarket 上對應的預測市場。
支援模糊匹配與信心度評估。
"""

from __future__ import annotations

from typing import Any


# =====================================================================
# 信號類型定義
# =====================================================================

# 每個信號類型包含：
#   - keywords: 用來搜尋 Polymarket 市場的關鍵字列表
#   - default_direction: 信號出現時的預設操作方向
#   - base_confidence: 基礎信心度（0.0 ~ 1.0）
#   - description: 信號說明

SIGNAL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "TARIFF": {
        "keywords": ["tariff", "trade", "import", "duty", "customs"],
        "default_direction": "LONG",
        "base_confidence": 0.7,
        "description": "關稅/貿易相關信號 — 川普傾向加徵關稅時觸發",
    },
    "DEAL": {
        "keywords": ["deal", "agreement", "negotiate", "trade deal", "summit"],
        "default_direction": "LONG",
        "base_confidence": 0.65,
        "description": "交易/協議信號 — 暗示即將達成某種協議",
    },
    "RELIEF": {
        "keywords": ["relief", "exemption", "waiver", "reduce", "cut"],
        "default_direction": "SHORT",
        "base_confidence": 0.6,
        "description": "寬減信號 — 減免關稅或放寬限制",
    },
    "ACTION": {
        "keywords": ["executive order", "action", "sign", "announce", "decree"],
        "default_direction": "LONG",
        "base_confidence": 0.75,
        "description": "行政行動信號 — 即將簽署行政命令或採取具體措施",
    },
    "THREAT": {
        "keywords": ["threat", "warn", "sanction", "punish", "retaliate", "ban"],
        "default_direction": "LONG",
        "base_confidence": 0.55,
        "description": "威脅信號 — 口頭威脅但未必落實，信心度較低",
    },
}

# 同義詞/模糊匹配表：當輸入的信號文字不完全匹配時使用
SIGNAL_ALIASES: dict[str, str] = {
    # TARIFF 系列
    "tariff": "TARIFF",
    "trade_war": "TARIFF",
    "import_tax": "TARIFF",
    "customs": "TARIFF",
    "duty": "TARIFF",
    # DEAL 系列
    "deal": "DEAL",
    "agreement": "DEAL",
    "negotiate": "DEAL",
    "summit": "DEAL",
    "handshake": "DEAL",
    # RELIEF 系列
    "relief": "RELIEF",
    "exemption": "RELIEF",
    "waiver": "RELIEF",
    "reduce": "RELIEF",
    "cut": "RELIEF",
    # ACTION 系列
    "action": "ACTION",
    "executive_order": "ACTION",
    "eo": "ACTION",
    "sign": "ACTION",
    "decree": "ACTION",
    # THREAT 系列
    "threat": "THREAT",
    "warn": "THREAT",
    "sanction": "THREAT",
    "ban": "THREAT",
    "retaliate": "THREAT",
}


def _normalize_signal(signal: str) -> str | None:
    """
    正規化信號名稱：先嘗試精確匹配，再嘗試模糊匹配。

    Args:
        signal: 原始信號字串。

    Returns:
        正規化後的信號類型（大寫），或 None 表示無法辨識。
    """
    upper = signal.strip().upper()

    # 精確匹配
    if upper in SIGNAL_DEFINITIONS:
        return upper

    # 模糊匹配（透過別名表）
    lower = signal.strip().lower().replace(" ", "_").replace("-", "_")
    if lower in SIGNAL_ALIASES:
        return SIGNAL_ALIASES[lower]

    # 子字串匹配：檢查信號文字是否包含任何已知關鍵字
    for alias_key, signal_type in SIGNAL_ALIASES.items():
        if alias_key in lower or lower in alias_key:
            return signal_type

    return None


def _build_market_queries(signal_type: str) -> list[str]:
    """
    根據信號類型產生用於搜尋 Polymarket 的查詢字串列表。

    Args:
        signal_type: 正規化後的信號類型。

    Returns:
        搜尋關鍵字列表。
    """
    definition = SIGNAL_DEFINITIONS.get(signal_type)
    if not definition:
        return []
    return list(definition["keywords"])


def match_signals_to_markets(signals: list[str]) -> list[dict[str, Any]]:
    """
    將一組信號映射到可能的 Polymarket 市場搜尋指令。

    對每個輸入信號：
      1. 正規化信號名稱（支援模糊匹配）
      2. 查找對應的市場搜尋關鍵字
      3. 產出映射結果，包含方向與信心度

    Args:
        signals: 信號字串列表，例如 ["TARIFF", "deal", "executive_order"]。

    Returns:
        映射結果列表，每個元素為 dict：
        {
            "signal_type": "TARIFF",
            "original_input": "tariff",
            "market_queries": ["tariff", "trade", ...],
            "direction": "LONG",
            "confidence": 0.7,
            "description": "...",
        }
        無法辨識的信號會標記 signal_type 為 "UNKNOWN"。
    """
    results: list[dict[str, Any]] = []

    for raw_signal in signals:
        signal_type = _normalize_signal(raw_signal)

        if signal_type is None:
            # 無法辨識 → 回傳 UNKNOWN 讓呼叫方知道
            results.append({
                "signal_type": "UNKNOWN",
                "original_input": raw_signal,
                "market_queries": [],
                "direction": "NEUTRAL",
                "confidence": 0.0,
                "description": f"無法辨識的信號: {raw_signal}",
            })
            continue

        definition = SIGNAL_DEFINITIONS[signal_type]
        queries = _build_market_queries(signal_type)

        results.append({
            "signal_type": signal_type,
            "original_input": raw_signal,
            "market_queries": queries,
            "direction": definition["default_direction"],
            "confidence": definition["base_confidence"],
            "description": definition["description"],
        })

    return results


def get_supported_signals() -> list[dict[str, Any]]:
    """
    列出所有支援的信號類型及其定義。

    Returns:
        信號定義列表。
    """
    return [
        {
            "signal_type": sig_type,
            "keywords": defn["keywords"],
            "direction": defn["default_direction"],
            "confidence": defn["base_confidence"],
            "description": defn["description"],
        }
        for sig_type, defn in SIGNAL_DEFINITIONS.items()
    ]


# =====================================================================
# Demo
# =====================================================================

if __name__ == "__main__":
    print("=== 信號→市場映射器 Demo ===\n")

    # 列出所有支援的信號
    print("[支援的信號類型]")
    for sig in get_supported_signals():
        print(f"  {sig['signal_type']:10s} | 方向: {sig['direction']:5s} | "
              f"信心度: {sig['confidence']:.0%} | {sig['description']}")

    print()

    # 測試映射
    test_signals = ["TARIFF", "deal", "executive_order", "ban", "some_random_thing"]
    print(f"[測試信號] {test_signals}\n")

    mappings = match_signals_to_markets(test_signals)
    for m in mappings:
        print(f"  輸入: {m['original_input']!r}")
        print(f"    → 信號類型: {m['signal_type']}")
        print(f"    → 方向: {m['direction']}")
        print(f"    → 信心度: {m['confidence']:.0%}")
        print(f"    → 搜尋關鍵字: {m['market_queries']}")
        print(f"    → 說明: {m['description']}")
        print()

    print("=== Demo 結束 ===")
