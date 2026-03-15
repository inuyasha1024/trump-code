"""
套利引擎

整合 polymarket_client 與 signal_market_mapper，
計算信號強度 x 市場低估程度 → 套利機會分數。
支援 demo 模式（假數據）與 live 模式（真實 API）。
"""

from __future__ import annotations

import random
from typing import Any

from polymarket_client import (
    PolymarketAPIError,
    fetch_trump_markets,
    get_market_price,
    search_markets,
)
from signal_market_mapper import match_signals_to_markets


# =====================================================================
# 核心計算
# =====================================================================


def _calc_undervaluation(
    current_price: float,
    direction: str,
) -> float:
    """
    計算市場低估程度。

    在預測市場中，價格 = 機率（0.0 ~ 1.0）。
    - LONG 方向（看漲）：價格越低 → 低估越嚴重 → 套利機會越大
    - SHORT 方向（看跌）：價格越高 → 低估越嚴重 → 套利機會越大

    Args:
        current_price: 當前市場價格（0.0 ~ 1.0）。
        direction: 操作方向，"LONG" 或 "SHORT"。

    Returns:
        低估程度分數（0.0 ~ 1.0），越高表示越被低估。
    """
    # 確保價格在合理範圍
    price = max(0.01, min(0.99, current_price))

    if direction == "LONG":
        # 價格低 = 被低估 = 機會大
        return 1.0 - price
    elif direction == "SHORT":
        # 價格高 = 被高估 = 做空機會大
        return price
    else:
        # NEUTRAL 或其他 → 無方向性判斷
        return 0.5


def _calc_opportunity_score(
    signal_confidence: float,
    undervaluation: float,
    signal_count: int = 1,
) -> float:
    """
    計算套利機會分數。

    公式：score = 信心度 x 低估程度 x 信號加成
    信號加成：多個信號指向同一方向時，分數微幅提升。

    Args:
        signal_confidence: 信號信心度（0.0 ~ 1.0）。
        undervaluation: 市場低估程度（0.0 ~ 1.0）。
        signal_count: 指向同一方向的信號數量。

    Returns:
        套利機會分數（0.0 ~ 1.0）。
    """
    # 多信號加成（對數遞減：2個=+10%, 3個=+15%, ...）
    count_bonus = 1.0 + min(0.2, 0.1 * (signal_count - 1) ** 0.5) if signal_count > 1 else 1.0
    raw = signal_confidence * undervaluation * count_bonus
    return min(1.0, round(raw, 4))


def analyze_opportunity(
    signals: list[str],
    market_prices: dict[str, float],
    market_names: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """
    分析套利機會。

    步驟：
      1. 將信號映射到市場搜尋指令
      2. 對每個市場代幣，計算低估程度
      3. 結合信號強度產出套利分數
      4. 按分數排序回傳

    Args:
        signals: 信號字串列表（如 ["TARIFF", "deal"]）。
        market_prices: {token_id: price} 的價格字典，price 介於 0.0 ~ 1.0。
        market_names: {token_id: 市場名稱} 的可選字典。

    Returns:
        套利機會列表，按 opportunity_score 降序排列。
        每個元素為：
        {
            "market_name": str,
            "token_id": str,
            "current_price": float,
            "expected_direction": str,
            "signal_strength": float,
            "undervaluation": float,
            "opportunity_score": float,
            "matched_signals": list[str],
        }
    """
    if market_names is None:
        market_names = {}

    # 第一步：映射信號
    mappings = match_signals_to_markets(signals)
    valid_mappings = [m for m in mappings if m["signal_type"] != "UNKNOWN"]

    if not valid_mappings:
        return []

    # 彙整：同一方向的信號數量與信心度
    # （簡化模型：所有有效信號都套用到所有市場）
    direction_votes: dict[str, list[dict[str, Any]]] = {"LONG": [], "SHORT": [], "NEUTRAL": []}
    for m in valid_mappings:
        direction_votes[m["direction"]].append(m)

    # 決定主方向：票數多的贏
    primary_direction = max(direction_votes, key=lambda d: len(direction_votes[d]))
    primary_signals = direction_votes[primary_direction]

    if not primary_signals:
        return []

    # 信號強度 = 所有同方向信號的平均信心度
    avg_confidence = sum(s["confidence"] for s in primary_signals) / len(primary_signals)
    signal_count = len(primary_signals)
    matched_signal_types = [s["signal_type"] for s in primary_signals]

    # 第二步：對每個市場計算套利分數
    opportunities: list[dict[str, Any]] = []

    for token_id, price in market_prices.items():
        underval = _calc_undervaluation(price, primary_direction)
        score = _calc_opportunity_score(avg_confidence, underval, signal_count)

        opportunities.append({
            "market_name": market_names.get(token_id, token_id),
            "token_id": token_id,
            "current_price": round(price, 4),
            "expected_direction": primary_direction,
            "signal_strength": round(avg_confidence, 4),
            "undervaluation": round(underval, 4),
            "opportunity_score": score,
            "matched_signals": matched_signal_types,
        })

    # 按分數降序排列
    opportunities.sort(key=lambda x: x["opportunity_score"], reverse=True)
    return opportunities


# =====================================================================
# Demo 模式
# =====================================================================


def _generate_demo_data() -> tuple[
    dict[str, float],
    dict[str, str],
]:
    """
    產生假的市場數據供 demo 使用。

    Returns:
        (prices, names) 兩個字典。
    """
    demo_markets = [
        ("token_tariff_china_001", "Will Trump impose 60% tariff on China by Q3 2026?", 0.35),
        ("token_tariff_eu_002", "Will Trump impose auto tariffs on EU by July 2026?", 0.42),
        ("token_deal_china_003", "Will US-China trade deal be reached by Dec 2026?", 0.22),
        ("token_deal_mexico_004", "Will USMCA be renegotiated by 2027?", 0.58),
        ("token_action_eo_005", "Will Trump sign executive order on crypto by June 2026?", 0.71),
        ("token_threat_iran_006", "Will Trump impose new sanctions on Iran by Q2 2026?", 0.63),
        ("token_relief_auto_007", "Will auto tariff exemptions be extended?", 0.81),
        ("token_tariff_steel_008", "Will steel tariffs exceed 30% by 2026?", 0.28),
    ]

    # 加一點隨機浮動讓每次 demo 略有不同
    prices: dict[str, float] = {}
    names: dict[str, str] = {}
    for tid, name, base_price in demo_markets:
        noise = random.uniform(-0.05, 0.05)
        prices[tid] = max(0.05, min(0.95, base_price + noise))
        names[tid] = name

    return prices, names


def run_demo() -> None:
    """以假數據執行完整的套利分析流程。"""
    print("=== 套利引擎 Demo 模式 ===\n")

    # 產生假數據
    prices, names = _generate_demo_data()

    print("[市場價格（模擬）]")
    for tid, price in prices.items():
        print(f"  {names[tid]:<60s} | 價格: {price:.2%}")

    # 測試不同信號組合
    test_cases: list[tuple[str, list[str]]] = [
        ("單一 TARIFF 信號", ["TARIFF"]),
        ("TARIFF + ACTION 雙信號", ["TARIFF", "ACTION"]),
        ("DEAL 信號", ["DEAL"]),
        ("RELIEF 信號（反向）", ["RELIEF"]),
        ("混合信號（含未知）", ["TARIFF", "deal", "unknown_xyz"]),
    ]

    for label, signals in test_cases:
        print(f"\n{'=' * 70}")
        print(f"[場景] {label}")
        print(f"[信號] {signals}")
        print(f"{'=' * 70}")

        results = analyze_opportunity(signals, prices, names)

        if not results:
            print("  （無有效套利機會）")
            continue

        # 表格輸出
        print(f"\n  {'市場':<55s} | {'價格':>6s} | {'方向':>5s} | {'信號':>6s} | {'低估':>6s} | {'分數':>6s}")
        print(f"  {'-' * 55}-+--------+-------+--------+--------+--------")

        for r in results:
            name_short = r["market_name"][:55]
            print(
                f"  {name_short:<55s} | {r['current_price']:6.2%} | "
                f"{r['expected_direction']:>5s} | {r['signal_strength']:6.2%} | "
                f"{r['undervaluation']:6.2%} | {r['opportunity_score']:6.4f}"
            )

        # 標示最佳機會
        best = results[0]
        print(f"\n  最佳機會: {best['market_name']}")
        print(f"  → 分數 {best['opportunity_score']:.4f} | "
              f"價格 {best['current_price']:.2%} | 方向 {best['expected_direction']}")


def run_live(signals: list[str]) -> list[dict[str, Any]]:
    """
    以真實 API 數據執行套利分析。

    步驟：
      1. 搜尋川普相關市場
      2. 取得各市場價格
      3. 執行套利分析

    Args:
        signals: 信號字串列表。

    Returns:
        套利機會列表。
    """
    print("[Live] 搜尋川普相關市場...")

    try:
        raw = fetch_trump_markets(limit=10)
    except PolymarketAPIError as e:
        print(f"  API 錯誤: {e}")
        return []

    market_list = raw.get("data", [])
    if not market_list:
        print("  找不到市場數據")
        return []

    # 收集 token_id 與名稱
    prices: dict[str, float] = {}
    names: dict[str, str] = {}

    for market in market_list:
        # Gamma API 回傳的市場結構中，tokens 是代幣列表
        tokens = market.get("tokens", [])
        question = market.get("question", "(無標題)")

        for token in tokens:
            tid = token.get("token_id", "")
            if not tid:
                continue

            # 嘗試從 API 取得即時價格
            try:
                price_resp = get_market_price(tid)
                price_val = float(price_resp.get("price", 0.5))
            except (PolymarketAPIError, ValueError, TypeError):
                # 如果 API 失敗，使用 token 本身可能帶的價格
                price_val = float(token.get("price", 0.5))

            prices[tid] = price_val
            outcome = token.get("outcome", "")
            names[tid] = f"{question} [{outcome}]" if outcome else question

    print(f"  找到 {len(prices)} 個代幣")

    # 執行分析
    results = analyze_opportunity(signals, prices, names)
    return results


# =====================================================================
# 入口
# =====================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--live":
        # Live 模式：python arbitrage_engine.py --live TARIFF DEAL
        live_signals = sys.argv[2:] if len(sys.argv) > 2 else ["TARIFF"]
        print(f"以信號 {live_signals} 執行 live 分析...\n")
        results = run_live(live_signals)

        if results:
            print(f"\n[Live 結果] 共 {len(results)} 個機會：")
            for r in results:
                print(f"  {r['market_name'][:60]:<60s} | "
                      f"分數: {r['opportunity_score']:.4f} | "
                      f"方向: {r['expected_direction']}")
        else:
            print("\n（無結果，可能 API 暫時不可用）")
    else:
        # Demo 模式
        run_demo()

    print("\n=== 結束 ===")
