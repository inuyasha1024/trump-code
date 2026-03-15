"""
Polymarket API 客戶端

封裝 Gamma API 與 CLOB API，提供川普相關預測市場的查詢功能。
僅使用 stdlib（urllib.request），不引入額外依賴。
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Any


# === 基礎設定 ===

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
CLOB_BASE_URL = "https://clob.polymarket.com"

DEFAULT_TIMEOUT = 15  # 秒
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # 秒，每次重試間隔（指數退避基數）

USER_AGENT = "TrumpCode-PolymarketClient/1.0"


class PolymarketAPIError(Exception):
    """Polymarket API 呼叫失敗時拋出的例外。"""

    def __init__(self, message: str, status_code: int | None = None, url: str = ""):
        self.status_code = status_code
        self.url = url
        super().__init__(message)


def _request(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    發送 HTTP GET 請求，附帶重試與錯誤處理。

    Args:
        url: 完整的請求 URL。
        timeout: 請求逾時秒數。
        max_retries: 最大重試次數。
        headers: 額外的 HTTP 標頭。

    Returns:
        解析後的 JSON dict（若 API 回傳 list，會包裝成 {"data": [...]}）。

    Raises:
        PolymarketAPIError: 所有重試都失敗時拋出。
    """
    req_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, headers=req_headers, method="GET")
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                parsed = json.loads(raw)
                # 統一回傳 dict：若 API 回傳 list，包裝一層
                if isinstance(parsed, list):
                    return {"data": parsed}
                return parsed
        except urllib.error.HTTPError as e:
            last_error = PolymarketAPIError(
                f"HTTP {e.code}: {e.reason}", status_code=e.code, url=url
            )
            # 4xx 不重試（除了 429 Too Many Requests）
            if 400 <= e.code < 500 and e.code != 429:
                raise last_error
        except urllib.error.URLError as e:
            last_error = PolymarketAPIError(
                f"連線失敗: {e.reason}", url=url
            )
        except json.JSONDecodeError as e:
            last_error = PolymarketAPIError(
                f"JSON 解析失敗: {e}", url=url
            )
        except TimeoutError:
            last_error = PolymarketAPIError(
                f"請求逾時（{timeout}s）", url=url
            )

        if attempt < max_retries:
            # 指數退避：1s, 2s, 4s...
            delay = RETRY_DELAY * (2 ** (attempt - 1))
            time.sleep(delay)

    raise last_error  # type: ignore[misc]


# =====================================================================
# Gamma API — 市場搜尋、詳情
# =====================================================================


def fetch_trump_markets(
    limit: int = 50,
    active: bool = True,
) -> dict[str, Any]:
    """
    搜尋所有川普相關的預測市場。

    用多個關鍵字搜尋 slug（slug_contains 是 Gamma API 唯一有效的文字搜尋）。
    合併去重後回傳。

    Args:
        limit: 每個關鍵字回傳數量上限。
        active: 是否只回傳進行中的市場。

    Returns:
        {"data": [market_dict, ...]}
    """
    # 多關鍵字搜尋（slug 用連字號）
    search_slugs = [
        'trump', 'tariff', 'trade-deal', 'china-trade',
        'executive-order', 'approval-rating', 'congress',
    ]

    all_markets: dict[str, dict] = {}

    for slug_kw in search_slugs:
        params = urllib.parse.urlencode({
            "limit": min(limit, 30),
            "active": str(active).lower(),
            "closed": "false" if active else "true",
            "slug_contains": slug_kw,
        })
        url = f"{GAMMA_BASE_URL}/markets?{params}"
        try:
            result = _request(url)
            markets = result.get('data', result) if isinstance(result, dict) else result
            if isinstance(markets, list):
                for m in markets:
                    mid = m.get('id', m.get('conditionId', ''))
                    if mid:
                        all_markets[mid] = m
        except PolymarketAPIError:
            continue

    # 按流動性排序
    sorted_markets = sorted(
        all_markets.values(),
        key=lambda m: float(m.get('liquidityNum', 0) or 0),
        reverse=True,
    )

    return {"data": sorted_markets}


def search_markets(query: str, limit: int = 20) -> dict[str, Any]:
    """
    以自訂關鍵字搜尋 Polymarket 市場。

    Args:
        query: 搜尋字串（例如 'tariff', 'china-trade'）。
        limit: 回傳數量上限。

    Returns:
        {"data": [market_dict, ...]}
    """
    # slug_contains 是唯一有效的文字搜尋方式
    slug_query = query.lower().replace(' ', '-')
    params = urllib.parse.urlencode({
        "limit": limit,
        "active": "true",
        "closed": "false",
        "slug_contains": slug_query,
    })
    url = f"{GAMMA_BASE_URL}/markets?{params}"
    return _request(url)


def get_market_detail(condition_id: str) -> dict[str, Any]:
    """
    取得單一市場的完整詳情。

    Args:
        condition_id: 市場的 condition ID。

    Returns:
        市場詳情 dict，包含 question、outcomes、volume 等。
    """
    url = f"{GAMMA_BASE_URL}/markets/{condition_id}"
    return _request(url)


# =====================================================================
# CLOB API — 價格、訂單簿
# =====================================================================


def get_market_price(token_id: str) -> dict[str, Any]:
    """
    取得單一市場的即時價格。

    Args:
        token_id: 市場代幣 ID。

    Returns:
        {"price": float, "token_id": str} 或 API 回傳的原始結構。
    """
    url = f"{CLOB_BASE_URL}/price?token_id={urllib.parse.quote(token_id)}&side=buy"
    return _request(url)


def get_prices_batch(token_ids: list[str]) -> dict[str, Any]:
    """
    批量取得多個市場的即時價格。

    逐一呼叫 get_market_price 後彙整回傳。
    （CLOB API 未提供原生批量端點，故此處逐筆查詢。）

    Args:
        token_ids: 代幣 ID 列表。

    Returns:
        {"prices": {token_id: price_dict, ...}, "errors": {token_id: error_msg, ...}}
    """
    results: dict[str, Any] = {}
    errors: dict[str, str] = {}

    for tid in token_ids:
        try:
            results[tid] = get_market_price(tid)
        except PolymarketAPIError as e:
            errors[tid] = str(e)

    return {"prices": results, "errors": errors}


def get_price_history(
    token_id: str,
    interval: str = "1d",
    fidelity: int = 60,
) -> dict[str, Any]:
    """
    取得市場的歷史價格走勢。

    Args:
        token_id: 代幣 ID。
        interval: 時間區間，如 '1d'、'1w'、'1m'。
        fidelity: 資料點精度（分鐘），預設 60。

    Returns:
        {"history": [{"t": timestamp, "p": price}, ...]}
    """
    params = urllib.parse.urlencode({
        "market": token_id,
        "interval": interval,
        "fidelity": fidelity,
    })
    url = f"{CLOB_BASE_URL}/prices-history?{params}"
    return _request(url)


def get_orderbook(token_id: str) -> dict[str, Any]:
    """
    取得市場的訂單簿（買賣掛單）。

    Args:
        token_id: 代幣 ID。

    Returns:
        {"bids": [...], "asks": [...]} 結構的訂單簿。
    """
    url = f"{CLOB_BASE_URL}/book?token_id={urllib.parse.quote(token_id)}"
    return _request(url)


# =====================================================================
# Demo
# =====================================================================

if __name__ == "__main__":
    print("=== Polymarket 川普市場查詢 Demo ===\n")

    # 1. 搜尋川普相關市場
    print("[1] 搜尋川普相關市場...")
    try:
        markets = fetch_trump_markets(limit=5)
        market_list = markets.get("data", [])
        if market_list:
            for i, m in enumerate(market_list, 1):
                question = m.get("question", "(無標題)")
                mid = m.get("id", "N/A")
                print(f"  {i}. {question}")
                print(f"     ID: {mid}")
        else:
            print("  (沒有找到市場，API 可能格式不同)")
            print(f"  原始回傳 keys: {list(markets.keys())}")
    except PolymarketAPIError as e:
        print(f"  API 錯誤: {e}")

    # 2. 搜尋 tariff 市場
    print("\n[2] 搜尋 'tariff' 市場...")
    try:
        tariff = search_markets("tariff", limit=3)
        for m in tariff.get("data", []):
            print(f"  - {m.get('question', '?')}")
    except PolymarketAPIError as e:
        print(f"  API 錯誤: {e}")

    print("\n（價格/訂單簿查詢需要有效的 token_id，跳過 demo。）")
    print("=== Demo 結束 ===")
