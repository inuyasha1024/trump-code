# Trump-Code 改進規格書 v1.0

> 2026-03-15 | 8 路審查（4 AI 外部搜尋 + 4 深度代碼審查）產出
> 執行人拿到這份文件後，依 Phase 順序逐項修，每項標 ✅ 才算完成

---

## 概覽

| 項目 | 數字 |
|------|------|
| 總問題數 | 48 |
| Phase 數 | 6 |
| 🚨 緊急（資安/法律） | 7 |
| 🔴 高（分析正確性） | 13 |
| 🟡 中（品質/維護性） | 15 |
| 🟢 低（最佳實踐） | 13 |

---

## Phase 0：緊急資安修復（預估 1 小時）

> 這些問題已經在 git 歷史裡，不修就是裸奔。先做這批再做其他。

### P0-1 🚨 移除 JWT Token 洩漏

**問題**：`results_03_hidden.json` 第 554 行附近包含 Truth Social API 的 JWT token 片段：
```
"pwapi_token=***REDACTED***": 2
```
兩份都有洩漏（根目錄 + `data/` 目錄）。

**修法**：
1. 從 `results_03_hidden.json` 和 `data/results_03_hidden.json` 中，刪除包含 `pwapi_token` 的那一條 key-value pair
2. 用 BFG Repo-Cleaner 或 `git filter-repo` 清除 git 歷史中的殘留：
   ```bash
   # 安裝 BFG
   brew install bfg

   # 清除歷史中的 token
   bfg --replace-text <(echo '***REDACTED***') .
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   git push --force
   ```
3. 如果這個 token 是有效的，**立即到 Truth Social 重新產生 token**

**驗收**：`grep -r "pwapi_token" .` 和 `git log -p --all -S "pwapi_token"` 都回零結果。

---

### P0-2 🚨 修復本機路徑洩漏

**問題**：`data_stats.json`（根目錄和 `data/` 都有）包含：
```json
"clean_all_csv": "./clean_all.csv",
"clean_all_json": "./clean_all.json",
"clean_president_csv": "./clean_president.csv",
"clean_president_json": "./clean_president.json"
```
暴露了 macOS、使用者名稱 `tkman`、專案目錄。

**修法**：

檔案 `clean_data.py` L158-163，把絕對路徑改成相對路徑：

```python
# 修改前（L158-163）
'files': {
    'clean_all_csv': str(CLEAN_CSV),
    'clean_all_json': str(CLEAN_JSON),
    'clean_president_csv': str(PRESIDENT_CSV),
    'clean_president_json': str(PRESIDENT_JSON),
}

# 修改後
'files': {
    'clean_all_csv': CLEAN_CSV.name,
    'clean_all_json': CLEAN_JSON.name,
    'clean_president_csv': PRESIDENT_CSV.name,
    'clean_president_json': PRESIDENT_JSON.name,
}
```

然後更新兩份 `data_stats.json`（根目錄 + `data/`）的內容。

同樣用 BFG 清除 git 歷史中的 `***REDACTED_PATH***/`。

**驗收**：`grep -r "***REDACTED_PATH***" .` 回零結果。

---

### P0-3 🚨 加 LICENSE 檔案

**問題**：README 掛了 MIT License 徽章 `[![License: MIT]...`，但 repo 裡沒有 LICENSE 檔案。法律上 = 無授權。

**修法**：在根目錄加 `LICENSE` 檔案，內容用標準 MIT License 文本，年份 `2025-2026`，copyright holder 用 README 裡已公開的名稱。

**驗收**：`cat LICENSE` 顯示完整 MIT License 內容。

---

### P0-4 🚨 加 `requirements.txt` + 移除 Runtime pip install

**問題**：
- 整個 repo 沒有依賴管理檔案
- `overnight_search.py` L75-76 和 `daily_pipeline.py` 裡有 `subprocess.run(['pip3', 'install', 'yfinance', '--quiet'])`，VPS 背景執行時自動裝外部套件 = 供應鏈攻擊入口

**修法**：

1. 建立 `requirements.txt`：
   ```
   yfinance>=0.2.36
   ```

2. 刪除 `overnight_search.py` L75-76：
   ```python
   # 刪除這兩行
   import subprocess
   subprocess.run(['pip3', 'install', 'yfinance', '--quiet'], capture_output=True)
   ```

3. 檢查 `daily_pipeline.py` 是否也有相同的 runtime pip install，如有一併刪除

4. 在 README 的安裝指引加上：
   ```bash
   pip install -r requirements.txt
   ```

**驗收**：`grep -rn "pip.*install" *.py` 回零結果。`cat requirements.txt` 存在。

---

### P0-5 🚨 清理重複 JSON 檔案

**問題**：以下 11 個 JSON 在根目錄和 `data/` 各有一份完全重複：
```
results_01_caps.json, results_02_timing.json, results_03_hidden.json,
results_04_entities.json, results_05_anomaly.json, results_06_market.json,
results_07_signal.json, results_08_backtest.json, results_10_codechange.json,
results_11_bruteforce.json, results_12_bigmoves.json
```

**修法**：
1. 決定 canonical 位置（建議只保留 `data/`）
2. 刪除根目錄的重複副本
3. 更新 `.gitignore` 加入：
   ```gitignore
   # 分析結果只留在 data/
   results_*.json

   # 安全防護
   .env*
   *.log
   venv/
   .venv/
   .vscode/
   .idea/
   ```
4. 更新所有 `analysis_*.py` 中的輸出路徑，確保結果寫入 `data/` 而非根目錄

**驗收**：根目錄無 `results_*.json`，`data/` 有完整的 11 個。

---

### P0-6 🚨 強化 `.gitignore`

**修法**：現有 `.gitignore` 太簡陋，改成：

```gitignore
# 大型原始檔案
raw_archive.csv
clean_all.csv
clean_all.json
clean_president.csv
clean_president.json

# 分析結果（只留在 data/）
/results_*.json
/prediction_scores.json
/predictions_log.json
/overnight_results.json
/market_*.json

# 暫存
__pycache__/
*.pyc
.DS_Store
*.bak
last_seen_post.txt
alerts_log.json
overnight_log.txt

# 安全
.env
.env.*
*.key
*.pem

# IDE
.vscode/
.idea/
*.swp
*.swo

# 虛擬環境
venv/
.venv/
```

---

### P0-7 🚨 修 `daily_pipeline.py` 自動 push 安全性

**問題**：`daily_pipeline.py` L377-404 自動 `git add data/ → commit → push origin main`，無任何安全檢查。

**修法**（L377-404）：
```python
def sync_to_github():
    log("6/6 同步到 GitHub...")
    try:
        os.chdir(BASE)

        # 安全檢查：確認不會 push 敏感檔案
        import subprocess
        status = subprocess.run(['git', 'status', '--porcelain'],
                               capture_output=True, text=True)
        for line in status.stdout.splitlines():
            fname = line.strip().split()[-1] if line.strip() else ''
            if any(s in fname for s in ['.env', '.key', '.pem', 'credential']):
                log(f"   ⛔ 偵測到敏感檔案 {fname}，中止 push")
                return

        subprocess.run(['git', 'add', 'data/'], capture_output=True)
        # 只 add data/ 目錄，不 add 其他

        result = subprocess.run(
            ['git', 'commit', '-m', f'Daily update: {TODAY} | Auto-synced from VPS'],
            capture_output=True, text=True
        )

        if 'nothing to commit' in result.stdout + result.stderr:
            log("   沒有新資料需要同步")
            return

        push = subprocess.run(
            ['git', 'push', 'origin', 'main'],
            capture_output=True, text=True, timeout=60
        )

        if push.returncode == 0:
            log("   GitHub 同步完成")
        else:
            log(f"   Push 失敗: {push.stderr[:200]}")

    except Exception as e:
        log(f"   同步失敗: {e}")
```

**驗收**：若根目錄有 `.env` 檔案，sync_to_github 不會 push。

---

## Phase 1：共用模組抽取（預估 2 小時）

> 解決三套獨立系統不一致的根本問題。所有後續 Phase 都依賴這個。

### P1-1 🔴 建立 `utils.py` 共用模組

**問題**：`est_hour()`、`market_session()`、`classify_signals()`、`emotion_score()`、`next_trading_day()` 等核心函數在 3~6 個檔案中各自定義，且**版本不一致**。

**修法**：建立 `utils.py`，統一以下函數：

#### 1.1 時區轉換（修正 DST bug）

所有檔案中的 `est_hour()` 都硬編碼 `(dt.hour - 5) % 24`，完全忽略夏令時間。

涉及檔案（至少 8 處）：
- `trump_monitor.py` L79-81
- `daily_pipeline.py` L125-127
- `overnight_search.py` L137-139
- `analysis_02_timing.py` L30
- `analysis_06_market.py` L148-149
- `analysis_07_signal_sequence.py` L77-80
- `analysis_08_backtest.py` L52-54
- `analysis_09_combo_score.py` L34-36
- `analysis_11_brute_force.py` L38-40
- `analysis_12_big_moves.py` L39-45

```python
# utils.py 中的正確實作
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

def to_eastern(utc_str: str) -> datetime:
    """UTC 字串轉美東時間（自動處理 EST/EDT）"""
    dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
    return dt.astimezone(ET)

def est_hour(utc_str: str) -> tuple[int, int]:
    """回傳美東 (hour, minute)，自動處理夏令時"""
    et = to_eastern(utc_str)
    return et.hour, et.minute

def market_session(utc_str: str) -> str:
    """判斷美股交易時段"""
    h, m = est_hour(utc_str)
    if h < 4:
        return 'OVERNIGHT'
    elif h < 9 or (h == 9 and m < 30):
        return 'PRE_MARKET'
    elif h < 16:
        return 'MARKET_OPEN'
    elif h < 20:
        return 'AFTER_HOURS'
    else:
        return 'OVERNIGHT'
```

#### 1.2 關鍵字匹配（修正子字串誤判）

涉及檔案：所有 `analysis_*.py`、`trump_monitor.py`、`daily_pipeline.py`、`overnight_search.py`

現有問題：用 `if 'tariff' in text.lower()` 做子字串匹配，`'tariff'` 和 `'tariffs'` 會雙重觸發，`'total'` 會匹配 `'totally'`，`'Mitch'` 會匹配 `'kitchen'`。

```python
# utils.py
import re
from functools import lru_cache

@lru_cache(maxsize=256)
def _make_pattern(words: tuple[str, ...]) -> re.Pattern:
    """編譯字詞邊界正規表達式（快取）"""
    escaped = [re.escape(w) for w in words]
    return re.compile(r'\b(?:' + '|'.join(escaped) + r')\b', re.IGNORECASE)

def count_keywords(text: str, keywords: list[str]) -> int:
    """用字詞邊界匹配計算關鍵字出現次數（不是子字串）"""
    pattern = _make_pattern(tuple(keywords))
    return len(pattern.findall(text))

def has_keywords(text: str, keywords: list[str]) -> bool:
    """文本中是否包含任一關鍵字（字詞邊界匹配）"""
    pattern = _make_pattern(tuple(keywords))
    return bool(pattern.search(text))
```

#### 1.3 情緒分數（統一版本）

目前 `analysis_05_anomaly.py` L32-62 和 `analysis_06_market.py` L101-119 各自有不同版本的 `emotion_score()`。

```python
# utils.py — 統一版本
STRONG_WORDS = frozenset([
    'never', 'always', 'worst', 'best', 'greatest', 'terrible',
    'incredible', 'tremendous', 'massive', 'total', 'complete',
    'absolute', 'disaster', 'perfect', 'beautiful', 'horrible',
    'amazing', 'fantastic', 'disgrace', 'pathetic', 'historic',
    'unprecedented', 'radical', 'corrupt', 'crooked', 'fake'
])

def emotion_score(content: str) -> float:
    """計算單篇貼文的情緒強度 (0-100)"""
    score = 0.0
    text = content

    # 大寫字比例（最高 30 分）
    upper = sum(1 for c in text if c.isupper())
    alpha = sum(1 for c in text if c.isalpha())
    caps_ratio = upper / max(alpha, 1)
    score += caps_ratio * 30

    # 驚嘆號密度（最高 25 分）
    excl = text.count('!')
    excl_density = excl / max(len(text), 1) * 100
    score += min(excl_density * 10, 25)

    # 強烈詞彙 — 使用字詞邊界匹配（最高 25 分）
    word_count = len(re.findall(r'\b\w+\b', text.lower()))
    strong_count = count_keywords(text, list(STRONG_WORDS))
    score += min(strong_count / max(word_count, 1) * 500, 25)

    # 全大寫連續詞（最高 20 分）
    caps_words = len(re.findall(r'\b[A-Z]{3,}\b', text))
    score += min(caps_words * 2, 20)

    return min(round(score, 1), 100)
```

#### 1.4 下一個交易日

```python
# utils.py
def next_trading_day(date_str: str, market_data: dict, max_days: int = 10) -> str | None:
    """找 date_str 之後的下一個交易日，最多往後找 max_days 天"""
    from datetime import datetime, timedelta
    d = datetime.strptime(date_str, '%Y-%m-%d')
    for i in range(1, max_days + 1):
        candidate = (d + timedelta(days=i)).strftime('%Y-%m-%d')
        if candidate in market_data:
            return candidate
    return None
```

#### 1.5 更新所有檔案的 import

每個 `analysis_*.py`、`trump_monitor.py`、`daily_pipeline.py`、`overnight_search.py` 中：
1. 刪除本地定義的 `est_hour()`、`market_session()`、`emotion_score()` 等函數
2. 加上 `from utils import est_hour, market_session, emotion_score, count_keywords, has_keywords, next_trading_day`
3. 把所有 `any(w in cl for w in [...])` 替換為 `has_keywords(cl, [...])`
4. 把所有 `sum(1 for w in [...] if w in text)` 替換為 `count_keywords(text, [...])`

**驗收**：
- `grep -rn "def est_hour" *.py` 只有 `utils.py` 有結果
- `grep -rn "def emotion_score" *.py` 只有 `utils.py` 有結果
- `grep -rn "(dt.hour - 5)" *.py` 回零結果
- `grep -rn "w in cl for w in" *.py` 回零結果

---

## Phase 2：統計方法修正（預估 4 小時）

> 這是整個專案最根本的方法論問題。不修的話，找到的「密碼」幾乎可以確定都是過擬合的巧合。

### P2-1 🔴 日報酬率計算修正

**檔案**：`analysis_06_market.py` L66-71

**問題**：
```python
# 現有（錯誤）— 算的是盤中波動，不是日報酬率
return (d['close'] - d['open']) / d['open'] * 100
```
金融上的「日報酬率」是 close-to-close，不是 open-to-close。用 open-to-close 會低估隔夜跳空（如 Trump 半夜發文導致的 gap up/down）。

**修法**：
```python
def day_return(date_str: str, market_data: dict) -> float | None:
    """計算日報酬率 (close-to-close %)"""
    if date_str not in market_data:
        return None

    # 找前一個交易日
    sorted_dates = sorted(market_data.keys())
    idx = sorted_dates.index(date_str)
    if idx == 0:
        # 第一天沒有前一天，fallback 到 open-to-close
        d = market_data[date_str]
        return (d['close'] - d['open']) / d['open'] * 100

    prev_date = sorted_dates[idx - 1]
    prev_close = market_data[prev_date]['close']
    today_close = market_data[date_str]['close']
    return (today_close - prev_close) / prev_close * 100
```

注意：修改這個函數會影響整個 `analysis_06` 的所有下游分析結果，需要重跑。

同時在 `analysis_06_market.py` 加入一個 `intraday_return` 函數保留原始的 open-to-close 計算，給需要的地方用：
```python
def intraday_return(date_str: str, market_data: dict) -> float | None:
    """計算盤中報酬率 (open-to-close %)"""
    if date_str not in market_data:
        return None
    d = market_data[date_str]
    return (d['close'] - d['open']) / d['open'] * 100
```

**驗收**：確認 `day_return()` 使用 close-to-close 計算。

---

### P2-2 🔴 Buy & Hold 基準修正

**檔案**：`analysis_08_backtest.py` L116

**問題**：
```python
# 現有（不一致）— 用 close-to-close，但回測入場用 open
bh_return = (last_day['close'] - first_day['close']) / first_day['close'] * 100
```

**修法**：
```python
# 與回測一致：第一天 open 買入 → 最後一天 close 賣出
bh_return = (last_day['close'] - first_day['open']) / first_day['open'] * 100
```

**驗收**：確認 Buy & Hold 起點用 `first_day['open']`。

---

### P2-3 🔴 暴力搜索加入統計顯著性檢驗

**檔案**：`analysis_11_brute_force.py` L267-320 和 `overnight_search.py` L346-419

**問題**：3150 萬組合 × 60% 勝率門檻，零多重檢定校正。在隨機數據中也會找到大量「假陽性」。

**修法**：

#### 2.3.1 提高最低樣本量

```python
# analysis_11_brute_force.py

# 修改前（L249）
if result and result['win_rate'] >= 60 and result['avg_return'] > 0.1:

# 修改後 — 至少 10 筆交易
if result and result['trades'] >= 10 and result['win_rate'] >= 60 and result['avg_return'] > 0.1:
```

```python
# overnight_search.py

# 修改前（L377）
if len(train_rets) < 3:
# 修改後
if len(train_rets) < 10:

# 修改前（L399）
if len(test_rets) < 2:
# 修改後
if len(test_rets) < 5:
```

#### 2.3.2 加入二項檢定 p-value

在 `analysis_11_brute_force.py` 加入統計檢驗：

```python
from math import comb as C

def binomial_pvalue(wins: int, total: int, p0: float = 0.5) -> float:
    """
    二項檢定 p-value（單尾）
    H0: 勝率 = p0（隨機）
    H1: 勝率 > p0
    """
    # P(X >= wins) under H0
    pval = sum(
        C(total, k) * (p0 ** k) * ((1 - p0) ** (total - k))
        for k in range(wins, total + 1)
    )
    return pval
```

在篩選條件中加入 p-value 門檻：

```python
# 修改前（L287-288）
if result and result['win_rate'] >= 60 and result['avg_return'] > 0.1:
    winners_train.append(...)

# 修改後
if result and result['trades'] >= 10 and result['win_rate'] >= 60 and result['avg_return'] > 0.1:
    pval = binomial_pvalue(result['wins'], result['trades'])
    if pval < 0.05:  # 個別 p < 0.05
        result['p_value'] = pval
        winners_train.append(...)
```

#### 2.3.3 加入 Bonferroni 校正

在最終結果篩選時（L305-313）：

```python
# 修改後
bonferroni_alpha = 0.05 / total_combos  # 校正後的顯著性門檻

final_winners = []
for w in winners_train:
    test_result = backtest_combo(w['features'], w['direction'], w['hold'], test_dates)
    if test_result and test_result['trades'] >= 5:
        test_pval = binomial_pvalue(test_result['wins'], test_result['trades'])
        if test_result['win_rate'] >= 55 and test_result['avg_return'] > 0:
            w['test'] = test_result
            w['test_p_value'] = test_pval
            w['bonferroni_significant'] = (w.get('p_value', 1) < bonferroni_alpha)
            w['combined_win_rate'] = (w['train']['win_rate'] + test_result['win_rate']) / 2
            w['combined_avg_return'] = (w['train']['avg_return'] + test_result['avg_return']) / 2
            final_winners.append(w)
```

#### 2.3.4 加入 Permutation Test

在暴力搜索完成後，加入隨機基準線測試：

```python
import random

def permutation_test(n_permutations: int = 100) -> int:
    """
    隨機打亂日期標籤，重跑搜索，看隨機能找到多少「存活者」
    如果真實結果不顯著高於隨機，說明全是過擬合
    """
    random_survivors = []
    for i in range(n_permutations):
        # 打亂日期 → 報酬率的對應關係
        shuffled_dates = train_dates[:]
        random.shuffle(shuffled_dates)
        # ... 用打亂後的日期跑同樣的搜索 ...
        # 記錄存活數
        random_survivors.append(count)

    avg_random = sum(random_survivors) / len(random_survivors)
    return avg_random

# 在結果輸出中加入：
print(f"   隨機基準線（permutation test）: 平均 {avg_random:.0f} 組存活")
print(f"   實際存活: {len(final_winners)} 組")
print(f"   倍數: {len(final_winners) / max(avg_random, 1):.1f}x")
```

#### 2.3.5 修正組合數計算的記憶體浪費

**檔案**：`analysis_11_brute_force.py` L200-202

```python
# 修改前 — 把所有組合實例化成 list 只為了 len()
n2 = len(list(combinations(range(n_features), 2)))
n3 = len(list(combinations(range(n_features), 3)))
n4 = len(list(combinations(range(n_features), 4)))

# 修改後 — 用數學公式
from math import comb
n2 = comb(n_features, 2)
n3 = comb(n_features, 3)
n4 = comb(n_features, 4)
```

**驗收**：
- `grep -rn "binomial_pvalue\|p_value\|bonferroni" analysis_11_brute_force.py` 有結果
- 結果 JSON 中每個 winner 都有 `p_value` 和 `bonferroni_significant` 欄位
- `len(list(combinations` 被替換為 `comb()`

---

### P2-4 🔴 修正 pre_tariff 特徵計算 bug

**檔案**：`analysis_11_brute_force.py` L82-86

**問題**：
```python
# 現有（bug）
if is_pre and tariff: pre_tariff += 1    # ← 用的是「累計的 tariff」不是「當前貼文」
if is_pre and deal: pre_deal += 1
if is_pre and relief: pre_relief += 1
if is_pre and action: pre_action += 1
```
`tariff` 是累計值——如果前一篇（非盤前）已經 +1，那第二篇盤前貼文即使沒提 tariff，`tariff` 仍為 truthy，`pre_tariff` 會錯誤 +1。

**修法**：
```python
# 在迴圈內，每篇貼文獨立判斷
this_tariff = any(w in cl for w in ['tariff', 'tariffs', 'duty'])
this_deal = any(w in cl for w in ['deal', 'agreement', 'signed', 'negotiate'])
this_relief = any(w in cl for w in ['pause', 'exempt', 'suspend', 'delay'])
this_action = any(w in cl for w in ['immediately', 'hereby', 'executive order', 'just signed'])

if this_tariff: tariff += 1
if this_deal: deal += 1
if this_relief: relief += 1
if this_action: action += 1

if is_pre and this_tariff: pre_tariff += 1
if is_pre and this_deal: pre_deal += 1
if is_pre and this_relief: pre_relief += 1
if is_pre and this_action: pre_action += 1
```

注意：如果已經用 Phase 1 的 `has_keywords()` 替換了，直接改：
```python
this_tariff = has_keywords(cl, ['tariff', 'tariffs', 'duty'])
# ... etc
if is_pre and this_tariff: pre_tariff += 1
```

**驗收**：人工檢查某個只有 1 篇盤前貼文（且不含 tariff）的日子，`pre_tariff` 應為 0。

---

### P2-5 🔴 修正回測前視偏差 (Look-ahead bias)

**檔案**：`analysis_08_backtest.py` L150-199

**問題**：回測的信號使用當天**所有**推文（包括盤後 16:00+ 發布的），但入場是「下一個交易日開盤」。問題是：如果信號靠的是盤後推文，真實世界中投資人在當天收盤時看不到那些推文，不可能在下一天開盤就做出反應。

**修法**（兩個方案，選一）：

**方案 A（推薦）**：信號只用盤前 + 盤中的推文
```python
# 在 run_rule() 中，context 只包含截至 16:00 的推文
context = {
    'date': date,
    'today': {k: v for k, v in daily_signals[date].items()},
    # 加一個 pre_close 版本的信號計算
    'today_pre_close': compute_pre_close_signals(date),
    ...
}
```

**方案 B**：改為 T+2 入場（信號隔兩天才入場）

在 `run_rule()` L174 改 `next_trading_day(td, market)` 為兩次呼叫：
```python
entry_day = next_trading_day(td, market)  # T+1
if entry_day:
    entry_day = next_trading_day(entry_day, market)  # T+2
```

**驗收**：回測報告中標明信號使用的資料截止時間。

---

### P2-6 🔴 訓練/驗證分割改為動態計算

**檔案**：
- `analysis_11_brute_force.py` L183
- `overnight_search.py`（類似位置）
- `analysis_12_big_moves.py` L323-325

**問題**：`cutoff = "2025-12-01"` 硬編碼，如果資料更新到 2026 年，訓練/驗證比例會失衡。

**修法**：
```python
# 修改前
cutoff = "2025-12-01"

# 修改後 — 最後 25% 做驗證
n_dates = len(sorted_dates)
cutoff_idx = int(n_dates * 0.75)
cutoff = sorted_dates[cutoff_idx]

train_dates = [d for d in sorted_dates[:cutoff_idx] if d in all_features and d in sp_by_date]
test_dates = [d for d in sorted_dates[cutoff_idx:] if d in all_features and d in sp_by_date]

if len(test_dates) < 10:
    print("⚠️ 驗證集不足 10 天，結果不可靠")
```

**驗收**：`grep -rn '"2025-12-01"' *.py` 回零結果。

---

### P2-7 🔴 加入統計顯著性檢驗到 analysis_06

**檔案**：`analysis_06_market.py` L160-180

**問題**：所有分析只算平均值就下結論（「關稅日跌、非關稅日漲」），沒有做任何統計檢驗。

**修法**：加入簡易 t-test（不用 scipy，純 Python 實作）：

```python
import math

def welch_ttest(group1: list[float], group2: list[float]) -> dict:
    """Welch's t-test（不假設等方差）"""
    n1, n2 = len(group1), len(group2)
    if n1 < 2 or n2 < 2:
        return {'t': None, 'significant': False, 'note': '樣本不足'}

    mean1, mean2 = sum(group1)/n1, sum(group2)/n2
    var1 = sum((x - mean1)**2 for x in group1) / (n1 - 1)
    var2 = sum((x - mean2)**2 for x in group2) / (n2 - 1)

    se = math.sqrt(var1/n1 + var2/n2)
    if se == 0:
        return {'t': None, 'significant': False, 'note': '方差為零'}

    t = (mean1 - mean2) / se

    # 粗略判斷：|t| > 2 約等於 p < 0.05（自由度 > 30 時）
    df = n1 + n2 - 2
    significant = abs(t) > 2.0 and df > 10

    return {
        't': round(t, 3),
        'df': df,
        'significant': significant,
        'mean_diff': round(mean1 - mean2, 4),
    }
```

在每個「XX 日 vs 非 XX 日」的比較中，都加上 t-test：

```python
# 範例：關稅日 vs 非關稅日
tariff_returns = [day_return(d, sp) for d in tariff_days if day_return(d, sp) is not None]
non_tariff_returns = [day_return(d, sp) for d in non_tariff_days if day_return(d, sp) is not None]

test = welch_ttest(tariff_returns, non_tariff_returns)
print(f"   t = {test['t']}, {'顯著' if test['significant'] else '不顯著'} (df={test['df']})")
```

在結果 JSON 中加入 t-test 結果和顯著性標記。

**驗收**：`results_06_market.json` 中每組比較都有 `t_value` 和 `significant` 欄位。

---

### P2-8 🟡 驗證期門檻不應比訓練期寬鬆

**檔案**：`analysis_11_brute_force.py` L309，`overnight_search.py` L406

**問題**：訓練期門檻 `win_rate >= 60, avg_return > 0.1`，驗證期門檻 `win_rate >= 55, avg_return > 0`。驗證期比訓練期寬鬆，會放入更多假陽性。

**修法**：驗證期至少與訓練期同等：
```python
# 修改後
if test_result and test_result['win_rate'] >= 60 and test_result['avg_return'] > 0.1:
```

---

### P2-9 🟡 加入對照基線

**檔案**：`analysis_06_market.py`

**問題**：只分析「有發文的交易日」，沒有「所有交易日平均報酬率」作為基線。

**修法**：
```python
# 在分析開頭加入基線
all_returns = [day_return(d, sp_by_date) for d in sp_by_date if day_return(d, sp_by_date) is not None]
baseline_mean = sum(all_returns) / len(all_returns)
baseline_std = (sum((r - baseline_mean)**2 for r in all_returns) / (len(all_returns) - 1)) ** 0.5

print(f"\n📊 基線: 所有交易日 ({len(all_returns)} 天)")
print(f"   平均日報酬: {baseline_mean:+.4f}%")
print(f"   標準差: {baseline_std:.4f}%")
```

---

## Phase 3：代碼品質修正（預估 3 小時）

### P3-1 🟡 修正裸 except

**涉及檔案 + 行號**：
- `daily_pipeline.py` L54：`except:` → `except (UnicodeDecodeError, UnicodeEncodeError):`
- `overnight_search.py` L46-48：同上
- `trump_monitor.py` L319-320：`except Exception as e: pass` → `except Exception as e: logging.exception(f"Model failed: {e}")`

---

### P3-2 🟡 修正 `datetime.utcnow()` deprecated

**涉及檔案**：
- `daily_pipeline.py` L27-28
- `clean_data.py` L140

```python
# 修改前
TODAY = datetime.utcnow().strftime('%Y-%m-%d')
NOW = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

# 修改後
from datetime import datetime, timezone
TODAY = datetime.now(timezone.utc).strftime('%Y-%m-%d')
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
```

---

### P3-3 🟡 加 `if __name__ == '__main__'` 防護

**涉及檔案**：所有 `analysis_*.py`（12 個）+ `overnight_search.py`

目前所有分析腳本的邏輯都寫在模組頂層，import 就會執行。

**修法**：每個檔案把頂層程式碼包進 `main()` 函數：
```python
def main():
    # ... 原有的頂層邏輯 ...

if __name__ == '__main__':
    main()
```

`overnight_search.py` 尤其重要——L31-70 在頂層就發網路請求、裝 pip 套件。

---

### P3-4 🟡 所有 `open()` 加 `encoding='utf-8'`

**涉及檔案**：所有 `.py` 中的 `open()` 呼叫

```python
# 修改前
with open(BASE / "clean_president.json") as f:

# 修改後
with open(BASE / "clean_president.json", encoding='utf-8') as f:
```

**驗收**：`grep -rn "open(" *.py | grep -v "encoding"` 只留下 `mode='w'` 且已經有 encoding 的。

---

### P3-5 🟡 analysis_03 數字清洗 bug

**檔案**：`analysis_03_hidden.py` L100

**問題**：`n.replace(',', '').replace('.', '')` 把小數 `3.14` 變成 `314`。

**修法**：
```python
# 修改後 — 只移除千位分隔符，保留小數點
for n in numbers:
    # 移除千位逗號（如 1,000 → 1000）
    clean = n.replace(',', '')
    # 嘗試解析為數字
    try:
        val = float(clean)
        cleaned_nums.append(val)
        all_numbers[n] += 1
    except ValueError:
        continue
```

---

### P3-6 🟡 修正 analysis_05 標準差公式

**檔案**：`analysis_05_anomaly.py` L178 附近

**問題**：用母體標準差 `/ n` 而非樣本標準差 `/ (n-1)`。

**修法**：改用 `statistics.stdev()`，或手動改成 `/ (n - 1)`。

---

### P3-7 🟡 analysis_04 實體匹配改善

**檔案**：`analysis_04_entities.py` L30-54

**問題**：
- `'EU '` 帶尾隨空格，句尾 `EU.` 會漏
- `'Korean'` 會同時匹配 South Korean 和 North Korean
- `'Border'` 列在 Mexico 但可能指加拿大邊境
- `'DOGE'` 可能指 Dogecoin 或政府效率部門

**修法**：
1. 所有關鍵字改用 `utils.has_keywords()`（字詞邊界匹配）
2. 移除 `'Border'` 從 Mexico，改成 `'Southern Border'`, `'Mexican Border'`
3. `'EU'` 去掉尾隨空格（字詞邊界匹配會自動處理）
4. `'Korean'` 改成 `'South Korea'`, `'South Korean'`（North Korea 已有獨立分類）
5. `'DOGE'` 加上上下文判斷或分開追蹤

---

### P3-8 🟡 修正中位數計算

**檔案**：`analysis_02_timing.py` L67

```python
# 修改前
median_count = counts[len(counts)//2]

# 修改後
from statistics import median
median_count = median(counts) if counts else 0
```

---

### P3-9 🟡 combo_score 評分模型標註

**檔案**：`analysis_09_combo_score.py` L63-210

**問題**：40/15/25 等權重純憑直覺硬編碼。

**修法**（最低要求）：在每個權重旁加上 docstring 說明依據來源，並在 README/結果 JSON 中明確標示「本評分模型權重為主觀設定，非統計擬合」。

更好的做法：用簡單的 OLS 回歸或邏輯回歸從訓練集擬合權重。

---

## Phase 4：錯誤處理 + 防禦性程式設計（預估 2 小時）

### P4-1 🟡 空值/除零防護

逐一檢查並修正：

| 檔案 | 行號 | 問題 | 修法 |
|------|------|------|------|
| `analysis_02_timing.py` L63 | `counts[0]` 空 list | `if not counts: return` |
| `analysis_02_timing.py` L158 | `intervals_min[0]` 空 | `if not intervals_min: return` |
| `analysis_03_hidden.py` L195 | `next()` 無 default | `next((...), None)` |
| `analysis_08_backtest.py` L247 | `avg_loss == 0` 除零 | 用 `float('inf')` |
| `clean_data.py` L144 | `clean_rows[-1]` 空 list | `if clean_rows:` |
| `clean_data.py` L97 | `int('abc')` 可能炸 | try/except |
| `daily_pipeline.py` L99 | `records[-1]` 空 list | `if records:` |
| `trump_monitor.py` L521 | `pending` 可能變負 | `max(0, pending - 1)` |

---

### P4-2 🟡 JSON 寫入改為原子操作

所有寫結果 JSON 的地方，改成先寫臨時檔再 rename：

```python
import tempfile

def safe_json_write(filepath: Path, data: dict):
    """原子寫入 JSON — 寫入中斷不會損壞原檔"""
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=filepath.parent, suffix='.tmp'
    )
    try:
        with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, filepath)
    except:
        os.unlink(tmp_path)
        raise
```

---

### P4-3 🟡 overnight_search 加入 checkpoint

**檔案**：`overnight_search.py`

**問題**：暴力搜索可能跑數小時，中途被 kill 所有結果丟失。

**修法**：每 100,000 組合存一次 checkpoint：
```python
CHECKPOINT_FILE = BASE / "data" / "overnight_checkpoint.json"

if tested % 100000 == 0 and winners:
    safe_json_write(CHECKPOINT_FILE, {
        'tested': tested,
        'total': total_combos,
        'winners_so_far': len(winners),
        'winners': winners[:100],  # 只存前 100 個
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })
    log(f"   Checkpoint saved: {tested:,} tested, {len(winners)} winners")
```

---

## Phase 5：README + 免責聲明強化（預估 1 小時）

### P5-1 🟡 強化免責聲明

**檔案**：`README.md` L318-325

**修改後**（三語都需要更新，以下是英文版範例）：

```markdown
## ⚠️ Disclaimer | 免責聲明 | 免責事項

> **FOR RESEARCH AND EDUCATIONAL PURPOSES ONLY.**
>
> This project is NOT financial advice. Do NOT make investment decisions based on these findings.
>
> **Statistical Limitations:**
> - The brute-force search tests 31.5 million model combinations. Even with train/test validation,
>   many "surviving" models may be false positives due to multiple comparisons (data snooping bias).
> - Past patterns do NOT guarantee future results. Correlation ≠ causation.
> - Trump can change his communication patterns at any time.
>
> **Legal Notice:**
> - The authors assume NO liability for any financial losses incurred from using this tool.
> - Data sourced from publicly available archives. Users are responsible for compliance
>   with applicable terms of service and local regulations.
> - This project is not affiliated with Truth Social, S&P Global, or any government entity.
>
> **Not Regulated:** This tool is not registered with any financial regulatory authority
> (SEC, FINRA, FSA, etc.) in any jurisdiction.
```

中文版和日文版同步更新。

### P5-2 🟡 README 加裝設指引

在 README 的 Quick Start 中加入：

```markdown
## Installation

```bash
git clone https://github.com/sstklen/trump-code.git
cd trump-code
pip install -r requirements.txt
```
```

### P5-3 🟡 README 加統計方法說明

在 Methodology 章節加入：

```markdown
## Statistical Notes

- **Multiple Testing**: With 31.5M combinations tested, we apply Bonferroni correction
  (α = 0.05 / 31,500,000 ≈ 1.59e-9) to identify truly significant patterns.
- **Survival Rate Context**: The 0.16% survival rate should be compared against the
  permutation test baseline (random data produces ~X% survival).
- **Sample Sizes**: Only models with ≥10 training trades and ≥5 test trades are considered.
```

---

## Phase 6：測試（預估 2 小時）

### P6-1 🟢 建立 `tests/` 目錄和基礎測試

```
tests/
  test_utils.py        # est_hour DST、has_keywords、emotion_score
  test_statistics.py   # binomial_pvalue、welch_ttest
  test_clean_data.py   # 編碼修正、數字清洗
```

#### test_utils.py 最低要求

```python
import pytest
from utils import est_hour, has_keywords, emotion_score, market_session

class TestEstHour:
    def test_est_winter(self):
        """冬令時間 (EST = UTC-5)"""
        h, m = est_hour("2025-01-15T14:30:00Z")
        assert h == 9 and m == 30  # 9:30 AM EST

    def test_edt_summer(self):
        """夏令時間 (EDT = UTC-4)"""
        h, m = est_hour("2025-07-15T14:30:00Z")
        assert h == 10 and m == 30  # 10:30 AM EDT

    def test_dst_transition(self):
        """2025-03-09 夏令時間切換日"""
        h1, _ = est_hour("2025-03-09T06:00:00Z")  # 切換前
        h2, _ = est_hour("2025-03-09T08:00:00Z")  # 切換後
        assert h1 == 1  # 1 AM EST
        assert h2 == 4  # 4 AM EDT（不是 3 AM）

class TestHasKeywords:
    def test_word_boundary(self):
        assert has_keywords("tariff policy", ['tariff']) == True
        assert has_keywords("tariffs policy", ['tariff']) == False  # 不是子字串
        assert has_keywords("tariffs policy", ['tariffs']) == True

    def test_case_insensitive(self):
        assert has_keywords("TARIFF POLICY", ['tariff']) == True

    def test_no_substring_match(self):
        assert has_keywords("totally fine", ['total']) == False
        assert has_keywords("kitchen sink", ['Mitch']) == False

class TestMarketSession:
    def test_pre_market(self):
        assert market_session("2025-01-15T13:00:00Z") == 'PRE_MARKET'  # 8 AM EST

    def test_market_open(self):
        assert market_session("2025-01-15T15:00:00Z") == 'MARKET_OPEN'  # 10 AM EST

    def test_after_hours(self):
        assert market_session("2025-01-15T22:00:00Z") == 'AFTER_HOURS'  # 5 PM EST
```

---

## 驗收 Checklist

完成全部 Phase 後，逐項打勾：

```
Phase 0 — 緊急資安
[ ] P0-1  JWT Token 清除（含 git 歷史）
[ ] P0-2  本機路徑清除（含 git 歷史）
[ ] P0-3  LICENSE 檔案存在
[ ] P0-4  requirements.txt 存在 + 零 runtime pip install
[ ] P0-5  根目錄零重複 JSON
[ ] P0-6  .gitignore 包含 .env*/venv/ 等
[ ] P0-7  git push 前有敏感檔案檢查

Phase 1 — 共用模組
[ ] P1-1  utils.py 存在
[ ] P1-1a est_hour 只在 utils.py 定義，DST 正確
[ ] P1-1b has_keywords 使用 \b 邊界匹配
[ ] P1-1c emotion_score 只在 utils.py 定義
[ ] P1-1d 所有 analysis_*.py import from utils
[ ] P1-1e grep "w in cl for w in" *.py = 零結果

Phase 2 — 統計方法
[ ] P2-1  day_return 用 close-to-close
[ ] P2-2  Buy & Hold 基準一致
[ ] P2-3  暴力搜索有 p-value + Bonferroni
[ ] P2-4  pre_tariff bug 修正
[ ] P2-5  回測無前視偏差
[ ] P2-6  cutoff 動態計算
[ ] P2-7  analysis_06 有 t-test
[ ] P2-8  驗證期門檻 ≥ 訓練期
[ ] P2-9  有基線對照

Phase 3 — 代碼品質
[ ] P3-1  零裸 except
[ ] P3-2  零 datetime.utcnow()
[ ] P3-3  所有檔案有 if __name__
[ ] P3-4  所有 open() 有 encoding
[ ] P3-5  數字清洗不吃小數點
[ ] P3-6  標準差用 n-1
[ ] P3-7  實體匹配改善
[ ] P3-8  中位數用 statistics.median
[ ] P3-9  combo_score 權重有標註

Phase 4 — 防禦性程式設計
[ ] P4-1  全部空值/除零防護
[ ] P4-2  JSON 原子寫入
[ ] P4-3  overnight_search 有 checkpoint

Phase 5 — README
[ ] P5-1  免責聲明三語強化
[ ] P5-2  安裝指引
[ ] P5-3  統計方法說明

Phase 6 — 測試
[ ] P6-1  tests/ 目錄存在
[ ] P6-1a DST 測試通過
[ ] P6-1b 關鍵字邊界測試通過
[ ] P6-1c 統計函數測試通過
```

---

## 附錄 A：四軍審查來源

| 來源 | 角色 | 關鍵發現 |
|------|------|----------|
| Gemini (Google Search) | 搜尋安全風險 + 統計方法 + 法律 | yfinance 不穩定、overfitting 風險、Truth Social TOS |
| Grok (X + Web Search) | 搜尋輿論 + 類似專案 + 法律案例 | Reddit 23K 篇分析、Stanford 研究、CNBC 警告、TOS 禁自動抓取 |
| Claude (WebSearch + 靜態分析) | 本地代碼審計 | 零 API key 洩漏、subprocess 風險、依賴問題 |
| 背景 Agent×4 | 深度逐行代碼審查 | JWT 洩漏、路徑洩漏、DST bug、前視偏差、特徵計算 bug |

## 附錄 B：參考連結

- [Stanford: Trump-based Stock Predictions](https://www.comet.com/site/blog/stanford-research-series-making-trading-great-again-trump-based-stock-predictions-via-doc2vec-embeddings)
- [CNBC: Don't invest based on Trump tweets](https://www.cnbc.com/2018/03/13/cramer-dont-invest-based-on-trump-tweets.html)
- [Oxford Law: Trump tariffs and securities law](https://blogs.law.ox.ac.uk/oblb/blog-post/2025/04/most-far-reaching-securities-fraud-history-trump-tariffs-and-securities-law)
- [Truth Social Terms of Service](https://help.truthsocial.com/legal/terms-of-service)
- [Reddit: Scraping Truth Social](https://www.reddit.com/r/webscraping/comments/1i4fsif/scraping_truth_social)
