<p align="center">
  <img src="https://img.shields.io/badge/Models_Tested-31%2C554%2C180-red?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Surviving_Rules-50%2C872-brightgreen?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Signal_Features-316-blue?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Live_Monitoring-24%2F7-orange?style=for-the-badge" />
</p>

# TRUMP CODE | 川普密碼 | トランプ・コード

**Can you decode the President's posts before the market moves?**

We ran **31.5 million prediction models** against every Trump Truth Social post since inauguration, cross-referenced with S&P 500 / NASDAQ / VIX data, and found **50,872 statistically validated signal combinations** that survived both training AND out-of-sample verification.

This is not sentiment analysis. This is brute-force cryptanalysis of presidential communications.

---

## The Hypothesis | 核心假設 | 仮説

> Trump is the only person on Earth who can move global markets with a single post.
> If there are patterns in his posting behavior, knowing them is alpha.
>
> 川普是地球上唯一一個「發一段文字就能撼動全球股市」的人。
> 如果他的發文存在規律，看懂的人就佔了先機。
>
> トランプは、たった一つの投稿で世界市場を動かせる地球上唯一の人物。
> その投稿パターンを解読できれば、それは純粋なアルファ（超過収益）になる。

---

## Key Discoveries | 核心發現 | 主要発見

### 1. The Tariff-Deal Seesaw | 關稅-Deal 蹺蹺板

| Signal | Next-Day S&P 500 | Win Rate |
|--------|-----------------|----------|
| Tariff mentioned during market hours | **-0.113%** | Bearish |
| Deal mentioned, no Tariff | **+0.028%** | Neutral-Bullish |
| Pre-market RELIEF signal | **+1.122%** | **Strong Buy** |
| TARIFF + DEAL + RELIEF same day | **69% win rate** | **Reversal Buy** |

The single most profitable signal: **Pre-market RELIEF (pause/exempt/suspend) averages +1.12% same-day return.**

### 2. The 17-Hour Window | 17 小時操作窗口 | 17時間の取引ウィンドウ

From TARIFF signal to DEAL signal: **median 17.4 hours**.

```
Signal 1 (TARIFF threat)  →  Operation Window (~17h)  →  Signal 2 (DEAL confirmation)
信號1（關稅威脅）            →  操作窗口（約17小時）        →  信號2（Deal確認）
シグナル1（関税の脅し）       →  取引ウィンドウ（約17時間）   →  シグナル2（ディール確認）
```

### 3. Code Changes Detected | 密碼換碼偵測 | コード変更の検出

Trump changes his communication patterns. We track it.

| Date | Change | Impact |
|------|--------|--------|
| 2025-08 | New signature "President DJT" appeared (0 → 38/month) | Formality shift |
| 2025-10 | "filibuster" entered vocabulary | Legislative push signal |
| 2025-12 | Style mutation score **14.1** (highest ever) | Post-election reset |
| 2026-02 | "Save America Act" — brand new phrase | New policy cycle |

### 4. Big Moves Are Predictable | 大漲大跌可預測 | 大きな値動きは予測可能

The day before a **>1% S&P crash**, compared to a **>1% rally**:

| Feature | Before Rally | Before Crash | Delta |
|---------|-------------|-------------|-------|
| Deal mention ratio | **43.2%** | 27.7% | +15.5% |
| Tariff mentions | 1.1 | **1.6** | -0.5 |
| CAPS ratio | 12.4% | **14.4%** | -2.0% |
| Avg post length | **343 chars** | 301 chars | +42 |
| Sentiment (positive - negative) | 1.8 | **2.3** | Counterintuitive: more positive before crashes |

**The most dangerous signal: Trump sounds unusually positive → crash incoming.**

---

## Methodology | 方法論 | 方法論

### Phase 1: Data Collection
- Source: Truth Social public archive (updated every 5 minutes)
- Posts: **32,069 total** / **7,411 post-inauguration** / **5,306 original with text**
- Market: S&P 500, NASDAQ, DOW, VIX (daily OHLCV)

### Phase 2: Feature Engineering (316 Features)
Every day gets **316 binary features** extracted from Trump's posts:

| Category | Count | Examples |
|----------|-------|---------|
| Keyword presence | 92 | `kw_tariff`, `kw_deal`, `kw_china` |
| Keyword intensity | 46 | `kw_tariffs_2plus`, `kw_great_heavy` |
| Time-of-day signals | 58 | `pre_tariff`, `open_deal`, `night_post` |
| Style metrics | 25 | `caps_high`, `excl_extreme`, `long_posts` |
| Behavioral patterns | 35 | `volume_spike`, `tariff_streak`, `deal_no_tariff` |
| Signature tracking | 12 | `sig_djt`, `sig_potus`, `sig_tyfa` |
| Calendar features | 8 | `is_monday`, `is_friday` |
| Trend features | 40 | `volume_rising_3d`, `tariff_rising` |

### Phase 3: Brute-Force Search (31.5 Million Models)
- All **2-condition and 3-condition combinations** of 316 features
- × 3 holding periods (1, 2, 3 days)
- × 2 directions (LONG, SHORT)
- **Total: 31,554,180 models tested**

### Phase 4: Two-Stage Validation
- **Training period**: Jan 2025 — Nov 2025 (216 trading days)
- **Test period**: Dec 2025 — Mar 2026 (70 trading days)
- Only models passing BOTH stages survive
- **Survival rate: 0.16%** (50,872 / 31,554,180)

### Phase 5: Live Monitoring (Daily)
- Auto-fetch latest posts every 24 hours
- Run all surviving models against new data
- Track hit rate, retire failing models, discover new patterns

---

## Live Scoreboard | 即時成績板 | ライブスコアボード

*Updated daily by automated pipeline.*

> Coming soon: daily prediction logs with verified outcomes.

---

## Architecture | 系統架構 | システム構成

```
Truth Social (public) ──→ Data Pipeline ──→ Feature Extraction (316 dims)
                                                      ↓
S&P 500 / NASDAQ / VIX ──→ Market Data ──→ Brute-Force Search Engine
                                                      ↓
                                              50,872 Surviving Models
                                                      ↓
                                           Daily Live Predictions ──→ GitHub Scoreboard
```

---

## Open Data & API | 全部公開 | 全データ公開

**Everything is open. Models, rules, predictions, raw data.** Fork it, improve it, prove us wrong.

全部公開。模型、規則、預測、原始資料。你能用就拿去用，你能改進就發 PR。

全て公開。モデル、ルール、予測、生データ。フォークして改善してほしい。

### Files in This Repo

| File | Description |
|------|-------------|
| `data/daily_signals.json` | Daily signal scores for every trading day |
| `data/surviving_rules.json` | All 50,872 surviving model rules |
| `data/predictions_log.json` | Every prediction made, with outcome |
| `data/big_moves.json` | Feature profile of every >1% market day |
| `data/scoreboard.json` | Live hit-rate scoreboard (auto-updated) |
| `analysis_*.py` | All 12 analysis scripts (run them yourself) |

### Fetch Data Directly from GitHub | 直接從 GitHub 拉資料

No API needed. Just fetch the raw JSON:

```bash
# 今日信號 / Today's signals
curl https://raw.githubusercontent.com/washinmura/trump-code/main/data/daily_signals.json

# 存活規則 / All surviving rules
curl https://raw.githubusercontent.com/washinmura/trump-code/main/data/surviving_rules.json

# 成績板 / Scoreboard
curl https://raw.githubusercontent.com/washinmura/trump-code/main/data/scoreboard.json

# 大波動分析 / Big move analysis
curl https://raw.githubusercontent.com/washinmura/trump-code/main/data/big_moves.json
```

Or in Python:
```python
import json, urllib.request
url = "https://raw.githubusercontent.com/washinmura/trump-code/main/data/surviving_rules.json"
rules = json.loads(urllib.request.urlopen(url).read())
print(f"Loaded {len(rules['rules'])} rules")
```

Data is auto-synced daily from our analysis server. Everyone gets the same data we use.

資料每天自動從分析伺服器同步。你拿到的跟我們用的一模一樣。

データは毎日分析サーバーから自動同期。あなたが取得するデータは私たちと同じもの。

---

## Quick Start | 快速開始

```bash
# Clone
git clone https://github.com/washinmura/trump-code.git
cd trump-code

# Download latest data & clean
python3 clean_data.py

# Run any analysis
python3 analysis_01_caps.py        # CAPS pattern analysis
python3 analysis_02_timing.py      # Posting time patterns
python3 analysis_06_market.py      # Posts vs S&P 500
python3 analysis_12_big_moves.py   # Big move prediction

# Single scan (today's signals)
python3 trump_monitor.py --once
```

---

## Disclaimer | 免責聲明 | 免責事項

This project is for **research and educational purposes only**.

- Past patterns do not guarantee future results
- This is NOT financial advice. Do NOT trade based solely on this analysis
- Trump can change his patterns at any time (we track this too)

本專案僅供研究與教育用途。歷史規律不代表未來表現。這不是投資建議。

本プロジェクトは研究・教育目的のみ。過去のパターンは将来の結果を保証しない。投資助言ではない。

---

## Credits

Built by **Washin Mura (和心村)** — a digital village in the Boso Peninsula, Japan.

Powered by brute-force computation, not gut feeling.

<p align="center">
  <sub>If you find patterns we missed, open an issue. Let's decode this together.</sub><br/>
  <sub>如果你發現了我們沒看到的規律，歡迎開 issue。一起來解碼。</sub><br/>
  <sub>見逃したパターンがあればissueを。一緒に解読しよう。</sub>
</p>
