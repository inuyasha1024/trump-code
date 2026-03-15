<div align="center">

# 🔐 TRUMP CODE
### 川普密碼 ・ トランプ・コード

**Brute-force cryptanalysis of presidential communications × stock market.**

[![Models Tested](https://img.shields.io/badge/Models_Tested-31.5M-FF0000?style=for-the-badge&logo=pytorch&logoColor=white)](data/surviving_rules.json)
[![Surviving Rules](https://img.shields.io/badge/Survivors-50%2C872-00C853?style=for-the-badge&logo=checkmarx&logoColor=white)](data/surviving_rules.json)
[![Features](https://img.shields.io/badge/Features-316-2962FF?style=for-the-badge&logo=databricks&logoColor=white)](analysis_11_brute_force.py)
[![Data](https://img.shields.io/badge/Data-Open-FF6F00?style=for-the-badge&logo=openaccessbutton&logoColor=white)](data/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

---

*Can you decode the President's posts before the market moves?*

*川普發文裡藏著股市密碼。你能比市場更早解讀嗎？*

*大統領の投稿に隠された株式市場のシグナル。市場より先に解読できるか？*

[English](#the-hypothesis) · [中文](#核心假設) · [日本語](#仮説)

</div>

---

## 📊 At a Glance

```
Data:     32,069 Truth Social posts (updated every 5 min)
          7,411 post-inauguration originals
          289 S&P 500 / NASDAQ / VIX trading days

Engine:   316 binary features per day
          31,554,180 prediction models tested
          50,872 survived two-stage validation (0.16%)

Live:     Daily automated pipeline
          Fetch → Analyze → Predict → Verify → Report → GitHub Sync
```

---

## The Hypothesis

> Trump is the only person on Earth who can move global markets with a single post. If there are patterns in his posting behavior — timing, word choice, emotional intensity, keyword combinations — knowing them before the market reacts is pure alpha.

## 核心假設

> 川普是地球上唯一一個「發一段文字就能撼動全球股市」的人。如果他的發文存在規律——時機、用詞、情緒強度、關鍵字組合——比市場更早解讀就是獲利先機。

## 仮説

> トランプは、たった一つの投稿で世界市場を動かせる地球上唯一の人物。投稿のタイミング、言葉選び、感情の強度、キーワードの組み合わせにパターンがあるなら、市場より先に解読することは純粋なアルファになる。

---

## 🔑 Key Discoveries | 核心發現 | 主要発見

### 1. The Tariff-Deal Seesaw | 關稅-Deal 蹺蹺板 | 関税・ディールのシーソー

|  | Signal | S&P 500 Next Day | Interpretation |
|--|--------|-----------------|----------------|
| 🔴 | Tariff during market hours | **-0.113%** | Bearish: sell pressure |
| 🟢 | Pre-market RELIEF | **+1.122%** | **Strongest buy signal found** |
| 🟡 | TARIFF + DEAL + RELIEF same day | **69% win rate** | Reversal: bottom signal |
| ⚪ | He brags about stock market | Next day **flat/down** | Contrarian: short-term top |

> **盤前出現 RELIEF（暫緩/豁免），當天 S&P 平均漲 +1.12%。這是最強的買入信號。**
>
> **市場時間中に RELIEF（一時停止/免除）が出れば、当日のS&Pは平均+1.12%。最強の買いシグナル。**

### 2. The 17-Hour Window | 17 小時操作窗口 | 17時間ウィンドウ

```
TARIFF threat  ───[ 17.4 hours median ]───▶  DEAL confirmation  ───▶  Market rally
關稅威脅        ───[   中位數 17.4 小時   ]───▶  Deal 確認信號        ───▶  股市反彈
関税の脅し      ───[   中央値 17.4 時間   ]───▶  ディール確認          ───▶  市場反発
```

### 3. The Crash Predictor | 大跌預測器 | 暴落予測

The day before S&P drops >1% vs rallies >1%:

| Feature | Before 📈 Rally | Before 📉 Crash | Signal |
|---------|:---:|:---:|--------|
| Deal mention ratio | **43.2%** | 27.7% | More Deals → Rally |
| Tariff mentions | 1.1 | **1.6** | More Tariffs → Crash |
| CAPS ratio | 12.4% | **14.4%** | More emotional → Crash |
| Sentiment score | 1.8 | **2.3** | ⚠️ *More positive before crashes* |

> **最反直覺的發現：大跌前一天他反而語氣更正面。像是在安撫。**
>
> **最も反直感的な発見：暴落の前日、彼はむしろポジティブ。まるで市場をなだめるように。**

### 4. Code Changes Detected | 密碼換碼 | コード変更検出

He changes his patterns. We track it.

| When | What Changed | Mutation Score |
|------|-------------|---------------|
| 2025-08 | New signature "President DJT" (0 → 38/month) | 5.3 |
| 2025-11 | CAPS ratio surged +3.3% (election mode) | **9.5** |
| 2025-12 | Post length dropped 122 chars, CAPS fell 5.5% | **14.1** 🚨 |
| 2026-02 | "Save America Act" — brand new phrase | New cycle |
| 2026-03 | Iran entered top-5 keywords for first time | Geopolitical shift |

---

## ⚙️ Methodology | 方法論 | 方法論

### Phase 1 — Data Collection | 資料收集 | データ収集
- **Source:** Truth Social public archive (updated every 5 minutes)
- **Market:** S&P 500, NASDAQ, DOW, VIX via Yahoo Finance
- **Period:** 2025-01-20 (Inauguration) → Present

### Phase 2 — Feature Engineering (316 Features) | 特徵工程 | 特徴量エンジニアリング

Every trading day gets **316 binary features** from Trump's posts:

| Category | # | Examples |
|----------|---|---------|
| 🔤 Keyword presence | 92 | `kw_tariff`, `kw_deal`, `kw_china`, `kw_iran` |
| 🔥 Keyword intensity | 46 | `kw_tariffs_2plus`, `kw_great_heavy` |
| ⏰ Time-of-day × keyword | 58 | `pre_tariff`, `open_deal`, `night_post` |
| 📝 Style metrics | 25 | `caps_high`, `excl_extreme`, `long_posts` |
| 📊 Behavioral patterns | 35 | `volume_spike`, `tariff_streak`, `deal_no_tariff` |
| ✍️ Signature tracking | 12 | `sig_djt`, `sig_potus`, `sig_tyfa` |
| 📅 Calendar | 8 | `is_monday`, `is_friday` |
| 📈 Trend | 40 | `volume_rising_3d`, `tariff_rising` |

### Phase 3 — Brute-Force Search (31.5M Models) | 暴力搜索 | 総当たり探索

```
316 features  ×  C(316,2) + C(316,3) combinations
              ×  3 holding periods (1, 2, 3 days)
              ×  2 directions (LONG, SHORT)
              = 31,554,180 models tested
```

### Phase 4 — Two-Stage Validation | 雙段驗證 | 二段階検証

```
Training:   Jan 2025 — Nov 2025  (216 trading days)
Testing:    Dec 2025 — Mar 2026  ( 70 trading days)
Pass both → Survive
Survival rate: 0.16%  (50,872 / 31,554,180)
```

### Phase 5 — Live Monitoring | 即時監控 | ライブモニタリング

Daily automated pipeline on our VPS:

```
Fetch latest posts  →  Extract 316 features  →  Run 50,872 models
       ↓                                               ↓
Fetch S&P 500       →  Verify yesterday's predictions  →  Update scoreboard
       ↓                                               ↓
Generate trilingual report  →  git push  →  This repo auto-updates
```

---

## 📁 Open Data | 公開資料 | オープンデータ

**Everything is open. Fork it. Improve it. Prove us wrong.**

**全部公開。拿去用、拿去改、拿去打臉我們。**

**全て公開。フォークして、改善して、間違いを証明してほしい。**

### Files

| File | Description | 說明 | 説明 |
|------|-------------|------|------|
| [`data/daily_report.json`](data/daily_report.json) | Today's signals (trilingual) | 今日信號（三語） | 本日のシグナル（3カ国語） |
| [`data/surviving_rules.json`](data/surviving_rules.json) | All 50,872 model rules | 全部存活規則 | 全生存ルール |
| [`data/big_moves.json`](data/big_moves.json) | >1% move analysis | 大波動分析 | 大幅変動分析 |
| [`data/report_history.json`](data/report_history.json) | Historical daily reports | 歷史報告 | 過去のレポート |
| [`data/scoreboard.json`](data/scoreboard.json) | Model hit rates | 模型命中率 | モデル的中率 |
| [`data/results_*.json`](data/) | All 12 analysis results | 12 項分析結果 | 12分析の結果 |

### Fetch Directly | 直接拉資料 | 直接取得

```bash
# Today's report (trilingual)
curl -s https://raw.githubusercontent.com/sstklen/trump-code/main/data/daily_report.json | python3 -m json.tool

# All surviving rules
curl -s https://raw.githubusercontent.com/sstklen/trump-code/main/data/surviving_rules.json

# In Python
import json, urllib.request
url = "https://raw.githubusercontent.com/sstklen/trump-code/main/data/daily_report.json"
report = json.loads(urllib.request.urlopen(url).read())
print(report['summary']['zh'])  # Chinese
print(report['summary']['ja'])  # Japanese
print(report['summary']['en'])  # English
```

---

## 🚀 Run It Yourself | 自己跑 | 自分で実行

```bash
git clone https://github.com/sstklen/trump-code.git
cd trump-code

# Step 1: Download & clean data
python3 clean_data.py

# Step 2: Run any analysis (12 available)
python3 analysis_01_caps.py         # CAPS code analysis        | 大寫密碼    | 大文字コード
python3 analysis_02_timing.py       # Posting time patterns      | 時間規律    | 投稿時間パターン
python3 analysis_03_hidden.py       # Hidden messages (acrostic) | 藏頭詩搜索  | 隠しメッセージ
python3 analysis_04_entities.py     # Country & people mentions  | 國家人物    | 国・人物分析
python3 analysis_05_anomaly.py      # Anomaly detection          | 異常偵測    | 異常検出
python3 analysis_06_market.py       # Posts vs S&P 500           | 推文vs股市  | 投稿vs株式市場
python3 analysis_07_signal_sequence.py  # Signal sequences       | 信號序列    | シグナルシーケンス
python3 analysis_08_backtest.py     # Strategy backtesting       | 策略回測    | バックテスト
python3 analysis_10_code_change.py  # Code change detection      | 換碼偵測    | コード変更検出
python3 analysis_12_big_moves.py    # Big move prediction        | 大波動預測  | 大幅変動予測

# Step 3: Run brute-force search (takes ~25 min)
python3 overnight_search.py

# Step 4: Check today's signals
python3 trump_monitor.py --once
```

---

## 📈 Daily Report Sample | 每日報告範例 | 日次レポートサンプル

```
川普密碼每日報告 — 2026-03-15
今日推文: 11 篇 | 觸發模型: 0 組
偵測信號: Deal, 中國, 伊朗, 只有Deal沒有關稅✅
共識方向: 0 組看多 vs 0 組看空

トランプ・コード日次レポート — 2026-03-15
本日の投稿: 11件 | トリガーモデル: 0組
検出シグナル: ディール, 中国, イラン, Dealのみ（関税無し）✅

Trump Code Daily Report — 2026-03-15
Posts today: 11 | Models triggered: 0
Signals: DEAL, CHINA, IRAN, DEAL_ONLY
```

---

## 🤝 How to Contribute | 怎麼參與 | 参加方法

**We need the world's eyes on this. One team can't decode Trump alone.**

**光靠我們解不完。需要全世界的眼睛一起看。**

**一つのチームだけでは解読できない。世界中の目が必要。**

### 3 Ways to Help | 三種參與方式 | 3つの参加方法

#### 🔍 1. Propose a New Feature | 提出新特徵 | 新特徴量の提案

Think of something we're not tracking. Open an issue with:

```
Title: [FEATURE] Description
Body:
- What to track: (e.g., "count how many times he uses ALL CAPS for country names")
- Why it might matter: (e.g., "he capitalizes countries he's about to sanction")
- How to detect it: (e.g., regex pattern or keyword list)
```

**你覺得我們漏看了什麼？** 比如：「他全大寫寫國家名的時候，是不是要制裁那個國家了？」像這樣的猜測就是新特徵。開一個 issue 告訴我們。

**見逃していることはないか？** 例えば：「国名を全て大文字で書く時、その国に制裁を加えようとしているのでは？」このような仮説が新しい特徴量になる。issueを開いて教えてほしい。

#### 📊 2. Run Your Own Analysis | 跑你自己的分析 | 独自の分析を実行

```bash
git clone https://github.com/sstklen/trump-code.git
cd trump-code
python3 clean_data.py  # Get the data
# Now write your own analysis and submit a PR!
```

Ideas we haven't tried yet:

| Idea | Difficulty | Impact |
|------|-----------|--------|
| Correlate with Bitcoin/Gold/Oil prices | ⭐ Easy | High |
| Analyze image/video posts (not just text) | ⭐⭐ Medium | High |
| Track which accounts he retweets before big moves | ⭐ Easy | Medium |
| NLP sentiment in languages other than English | ⭐⭐ Medium | Medium |
| Compare 1st term tweets vs 2nd term posts | ⭐ Easy | Fun |
| Cross-reference with his public schedule | ⭐⭐ Medium | High |
| Detect if posts are written by him vs staff | ⭐⭐⭐ Hard | Very High |

**下載資料，跑你自己的分析，發現新規律就發 PR。** 上面那些是我們還沒試過的方向。

**データをダウンロードして、自分の分析を実行。新しいパターンを発見したらPRを送ってほしい。**

#### ✅ 3. Verify Our Predictions | 驗證我們的預測 | 予測の検証

Every day we publish predictions in `data/daily_report.json`. You can:

1. **Check if yesterday's prediction was correct** — compare with actual market close
2. **Find patterns in our failures** — when do we fail? Is there a meta-pattern?
3. **Track model decay** — which rules are dying? Which are getting stronger?

**每天看我們的預測對不對。如果發現「我們在某種情況下特別容易錯」，那本身就是一個新發現。**

**毎日の予測が正しいか確認してほしい。「特定の状況で特に間違いやすい」ことを発見すれば、それ自体が新しい発見。**

---

## ⚠️ Disclaimer | 免責聲明 | 免責事項

> **This project is for research and educational purposes only.**
> Past patterns do not guarantee future results. This is NOT financial advice. Trump can change his patterns at any time — and we track that too.
>
> **本專案僅供研究與教育用途。** 歷史規律不代表未來表現。這不是投資建議。川普隨時可能換密碼——我們也在追蹤這件事。
>
> **本プロジェクトは研究・教育目的のみ。** 過去のパターンは将来の結果を保証しない。投資助言ではない。トランプはいつでもパターンを変える可能性がある——それも追跡している。

---

<div align="center">

Built by **[Washin Mura (和心村)](https://washinmura.jp)** — Boso Peninsula, Japan.

Powered by brute-force computation, not gut feeling.

暴力運算驅動，不靠直覺。 | 直感ではなく、力任せの計算で。

---

*If you find patterns we missed, open an issue. Let's decode this together.*

*如果你發現了我們沒看到的規律，歡迎開 issue。一起來解碼。*

*見逃したパターンがあれば issue を。一緒に解読しよう。*

⭐ Star this repo to follow the live decoding.

</div>
