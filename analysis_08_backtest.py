#!/usr/bin/env python3
"""
川普密碼 分析 #8 — 回測驗證
用歷史資料跑 5 條規則，看每條賺多少、勝率多少
對照組：同期 Buy & Hold S&P500
"""

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent

with open(BASE / "clean_president.json", 'r') as f:
    posts = json.load(f)

with open(BASE / "market_SP500.json", 'r') as f:
    sp500 = json.load(f)

with open(BASE / "market_NASDAQ.json", 'r') as f:
    nasdaq = json.load(f)

sp_by_date = {r['date']: r for r in sp500}
nq_by_date = {r['date']: r for r in nasdaq}

originals = sorted(
    [p for p in posts if p['has_text'] and not p['is_retweet']],
    key=lambda p: p['created_at']
)

# === 工具函數 ===

def classify_post(content):
    cl = content.lower()
    signals = set()
    if any(w in cl for w in ['tariff', 'tariffs', 'duty', 'duties', 'reciprocal']):
        signals.add('TARIFF')
    if any(w in cl for w in ['deal', 'agreement', 'negotiate', 'talks', 'signed']):
        signals.add('DEAL')
    if any(w in cl for w in ['pause', 'delay', 'exempt', 'exception', 'reduce', 'suspend', 'postpone']):
        signals.add('RELIEF')
    if any(w in cl for w in ['stock market', 'all time high', 'record high', 'dow', 'nasdaq', 'market up']):
        signals.add('MARKET_BRAG')
    if any(w in cl for w in ['china', 'chinese', 'beijing']):
        signals.add('CHINA')
    if any(w in cl for w in ['immediately', 'effective', 'hereby', 'i have directed', 'executive order', 'just signed']):
        signals.add('ACTION')
    return signals

def est_hour(utc_str):
    dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
    return (dt.hour - 5) % 24, dt.minute

def market_session(utc_str):
    h, m = est_hour(utc_str)
    if h < 9 or (h == 9 and m < 30):
        return 'PRE_MARKET'
    elif h < 16:
        return 'MARKET_OPEN'
    elif h < 20:
        return 'AFTER_HOURS'
    else:
        return 'OVERNIGHT'

def next_trading_day(date_str, market=sp_by_date):
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    for i in range(1, 6):
        d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
        if d in market:
            return d
    return None

def trading_day_offset(date_str, offset, market=sp_by_date):
    """取得 N 個交易日後的日期"""
    d = date_str
    for _ in range(abs(offset)):
        d = next_trading_day(d, market) if offset > 0 else None
        if not d:
            return None
    return d


# === 每日信號彙整 ===

daily_signals = defaultdict(lambda: {
    'tariff': 0, 'deal': 0, 'relief': 0, 'market_brag': 0,
    'action': 0, 'china': 0, 'posts': 0,
    'pre_tariff': 0, 'pre_deal': 0, 'pre_relief': 0,
    'open_tariff': 0, 'open_deal': 0,
})

for p in originals:
    date = p['created_at'][:10]
    signals = classify_post(p['content'])
    session = market_session(p['created_at'])
    d = daily_signals[date]
    d['posts'] += 1

    for sig in signals:
        d[sig.lower()] = d.get(sig.lower(), 0) + 1
        if session == 'PRE_MARKET':
            d[f'pre_{sig.lower()}'] = d.get(f'pre_{sig.lower()}', 0) + 1
        elif session == 'MARKET_OPEN':
            d[f'open_{sig.lower()}'] = d.get(f'open_{sig.lower()}', 0) + 1


print("=" * 90)
print("📊 川普密碼回測 — 5 條規則歷史驗證")
print("=" * 90)

# === Buy & Hold 基準 ===
first_day = sp500[0]
last_day = sp500[-1]
bh_return = (last_day['close'] - first_day['close']) / first_day['close'] * 100
print(f"\n📈 基準: Buy & Hold S&P500")
print(f"   期間: {first_day['date']} ~ {last_day['date']}")
print(f"   起點: {first_day['close']:,.2f} → 終點: {last_day['close']:,.2f}")
print(f"   報酬率: {bh_return:+.2f}%")
print(f"   交易日: {len(sp500)} 天")


# === 回測框架 ===

class Trade:
    def __init__(self, rule, date, direction, entry_price, reason):
        self.rule = rule
        self.entry_date = date
        self.direction = direction  # 'LONG' or 'SHORT'
        self.entry_price = entry_price
        self.reason = reason
        self.exit_date = None
        self.exit_price = None
        self.return_pct = None
        self.hold_days = None

    def close(self, exit_date, exit_price):
        self.exit_date = exit_date
        self.exit_price = exit_price
        if self.direction == 'LONG':
            self.return_pct = (exit_price - self.entry_price) / self.entry_price * 100
        else:
            self.return_pct = (self.entry_price - exit_price) / self.entry_price * 100
        d1 = datetime.strptime(self.entry_date, '%Y-%m-%d')
        d2 = datetime.strptime(self.exit_date, '%Y-%m-%d')
        self.hold_days = (d2 - d1).days


def run_rule(rule_name, trigger_fn, direction, hold_days_target, market=sp_by_date):
    """通用回測執行器"""
    trades = []
    sorted_dates = sorted(daily_signals.keys())

    for i, date in enumerate(sorted_dates):
        if date not in market:
            # 週末/假日 → 用下一個交易日
            td = next_trading_day(date, market)
            if not td:
                continue
        else:
            td = date

        # 檢查觸發條件
        context = {
            'date': date,
            'today': daily_signals[date],
            'prev_3': [daily_signals[sorted_dates[j]] for j in range(max(0,i-3), i)],
            'prev_7': [daily_signals[sorted_dates[j]] for j in range(max(0,i-7), i)],
        }

        if trigger_fn(context):
            # 下一個交易日開盤買入
            entry_day = next_trading_day(td, market)
            if not entry_day or entry_day not in market:
                continue

            entry_price = market[entry_day]['open']

            # 持有 N 個交易日後賣出
            exit_day = entry_day
            for _ in range(hold_days_target):
                nd = next_trading_day(exit_day, market)
                if nd:
                    exit_day = nd
                else:
                    break

            if exit_day not in market:
                continue

            exit_price = market[exit_day]['close']

            trade = Trade(rule_name, entry_day, direction, entry_price,
                         f"{date} signal")
            trade.close(exit_day, exit_price)
            trades.append(trade)

    return trades


def print_rule_results(rule_name, trades, description):
    """打印單條規則的回測結果"""
    if not trades:
        print(f"\n  ❌ {rule_name}: 沒有觸發")
        return

    wins = [t for t in trades if t.return_pct > 0]
    losses = [t for t in trades if t.return_pct <= 0]
    returns = [t.return_pct for t in trades]

    total_return = sum(returns)
    avg_return = total_return / len(returns)
    win_rate = len(wins) / len(trades) * 100
    avg_win = sum(t.return_pct for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t.return_pct for t in losses) / len(losses) if losses else 0
    max_win = max(returns)
    max_loss = min(returns)
    avg_hold = sum(t.hold_days for t in trades) / len(trades)

    # 假設每次投入 $10,000
    capital = 10000
    cumulative = capital
    peak = capital
    max_drawdown = 0
    for t in trades:
        cumulative *= (1 + t.return_pct / 100)
        peak = max(peak, cumulative)
        dd = (peak - cumulative) / peak * 100
        max_drawdown = max(max_drawdown, dd)

    final_value = cumulative

    print(f"\n  {'='*85}")
    print(f"  📋 規則: {rule_name}")
    print(f"  📝 {description}")
    print(f"  {'='*85}")
    print(f"  交易次數:  {len(trades):5d}")
    print(f"  勝率:      {win_rate:5.1f}%  ({len(wins)}勝 {len(losses)}負)")
    print(f"  平均報酬:  {avg_return:+.3f}% / 次")
    print(f"  累積報酬:  {total_return:+.2f}%")
    print(f"  平均持有:  {avg_hold:.1f} 天")
    print(f"  平均勝:    {avg_win:+.3f}%")
    print(f"  平均負:    {avg_loss:+.3f}%")
    print(f"  最大單筆勝: {max_win:+.2f}%")
    print(f"  最大單筆負: {max_loss:+.2f}%")
    print(f"  盈虧比:    {abs(avg_win/avg_loss) if avg_loss != 0 else 999:.2f}")
    print(f"  最大回撤:  {max_drawdown:.2f}%")
    print(f"  $10K →     ${final_value:,.0f}  ({(final_value/capital-1)*100:+.1f}%)")

    # 顯示每筆交易
    print(f"\n  📋 交易明細:")
    print(f"  {'入場':12s} | {'出場':12s} | {'入場價':>10s} | {'出場價':>10s} | {'報酬':>8s} | {'累積':>10s}")
    cum = capital
    for t in trades:
        cum *= (1 + t.return_pct / 100)
        arrow = "✅" if t.return_pct > 0 else "❌"
        print(f"  {t.entry_date:12s} | {t.exit_date:12s} | {t.entry_price:>10,.2f} | {t.exit_price:>10,.2f} | {t.return_pct:+.2f}% {arrow} | ${cum:>9,.0f}")

    return {
        'trades': len(trades),
        'win_rate': round(win_rate, 1),
        'avg_return': round(avg_return, 3),
        'total_return': round(total_return, 2),
        'max_drawdown': round(max_drawdown, 2),
        'final_value': round(final_value, 0),
    }


# ============================================================
# 規則 1: 盤前暫緩信號 → 開盤買入，持有 1 天
# ============================================================
def rule1_trigger(ctx):
    return ctx['today'].get('pre_relief', 0) >= 1

trades_r1 = run_rule('R1', rule1_trigger, 'LONG', 1)
r1 = print_rule_results(
    "規則1: 盤前RELIEF → 買入1天",
    trades_r1,
    "他在開盤前說「暫緩/豁免/暫停」→ 下一個交易日開盤買、收盤賣"
)


# ============================================================
# 規則 2: 盤中發關稅 → 避險（做空1天）
# ============================================================
def rule2_trigger(ctx):
    return ctx['today'].get('open_tariff', 0) >= 2  # 盤中提關稅 ≥2 次

trades_r2 = run_rule('R2', rule2_trigger, 'SHORT', 1)
r2 = print_rule_results(
    "規則2: 盤中TARIFF×2 → 做空1天",
    trades_r2,
    "他在交易時間提關稅 ≥2 次 → 下一個交易日開盤做空、收盤平倉"
)


# ============================================================
# 規則 3: 連3天TARIFF → 出現DEAL → 買入2天
# ============================================================
def rule3_trigger(ctx):
    prev = ctx['prev_3']
    if len(prev) < 3:
        return False
    tariff_streak = all(d['tariff'] >= 1 for d in prev)
    deal_today = ctx['today']['deal'] >= 1
    return tariff_streak and deal_today

trades_r3 = run_rule('R3', rule3_trigger, 'LONG', 2)
r3 = print_rule_results(
    "規則3: 連3天TARIFF後DEAL出現 → 買入2天",
    trades_r3,
    "連續3天提關稅後，當天出現Deal信號 → 轉折買入，持有2個交易日"
)


# ============================================================
# 規則 4: 三信號齊發 (TARIFF+DEAL+RELIEF同天) → 買入3天
# ============================================================
def rule4_trigger(ctx):
    t = ctx['today']
    return t['tariff'] >= 1 and t['deal'] >= 1 and t['relief'] >= 1

trades_r4 = run_rule('R4', rule4_trigger, 'LONG', 3)
r4 = print_rule_results(
    "規則4: TARIFF+DEAL+RELIEF齊發 → 買入3天",
    trades_r4,
    "同一天出現關稅+Deal+暫緩三種信號 → 底部買入，持有3個交易日"
)


# ============================================================
# 規則 5: 他主動炫耀股市 → 賣出信號（做空1天）
# ============================================================
def rule5_trigger(ctx):
    return ctx['today']['market_brag'] >= 2  # 一天炫耀股市 ≥2 次

trades_r5 = run_rule('R5', rule5_trigger, 'SHORT', 1)
r5 = print_rule_results(
    "規則5: 炫耀股市×2 → 做空1天",
    trades_r5,
    "他一天內主動提股市/新高 ≥2 次 → 短期到頂，隔天做空1天"
)


# ============================================================
# 加碼規則：高發文量日 (≥30篇) + TARIFF → 買入2天
# ============================================================
def rule6_trigger(ctx):
    t = ctx['today']
    return t['posts'] >= 30 and t['tariff'] >= 3

trades_r6 = run_rule('R6', rule6_trigger, 'LONG', 2)
r6 = print_rule_results(
    "規則6: 爆量日(≥30篇)+關稅密集 → 買入2天",
    trades_r6,
    "一天狂發 ≥30 篇且關稅 ≥3 次 → 市場恐慌極值，反彈在即"
)


# ============================================================
# 加碼規則：盤前 ACTION → 買入1天
# ============================================================
def rule7_trigger(ctx):
    return ctx['today'].get('pre_action', 0) >= 1

for p in originals:
    date = p['created_at'][:10]
    signals = classify_post(p['content'])
    session = market_session(p['created_at'])
    if session == 'PRE_MARKET' and 'ACTION' in signals:
        daily_signals[date]['pre_action'] = daily_signals[date].get('pre_action', 0) + 1

trades_r7 = run_rule('R7', rule7_trigger, 'LONG', 1)
r7 = print_rule_results(
    "規則7: 盤前ACTION(簽署/命令) → 買入1天",
    trades_r7,
    "他在開盤前宣布簽署/行政命令 → 開盤買入，當天收盤賣出"
)


# ============================================================
# 組合策略：同時用規則 1+3+4
# ============================================================
print(f"\n{'='*90}")
print("🏆 組合策略回測：規則 1+3+4+6 同時運行")
print("   各規則獨立觸發，不重複入場（同一天只觸一次）")
print("=" * 90)

all_trades = []
used_dates = set()

for trades, priority in [(trades_r4, 4), (trades_r1, 1), (trades_r6, 6), (trades_r3, 3)]:
    for t in trades:
        if t.entry_date not in used_dates:
            all_trades.append(t)
            used_dates.add(t.entry_date)

all_trades.sort(key=lambda t: t.entry_date)

if all_trades:
    capital = 10000
    cumulative = capital
    peak = capital
    max_dd = 0
    wins = sum(1 for t in all_trades if t.return_pct > 0)

    for t in all_trades:
        cumulative *= (1 + t.return_pct / 100)
        peak = max(peak, cumulative)
        dd = (peak - cumulative) / peak * 100
        max_dd = max(max_dd, dd)

    total_ret = sum(t.return_pct for t in all_trades)
    avg_ret = total_ret / len(all_trades)

    print(f"  交易次數:     {len(all_trades)}")
    print(f"  勝率:         {wins/len(all_trades)*100:.1f}%")
    print(f"  平均報酬:     {avg_ret:+.3f}% / 次")
    print(f"  累積報酬:     {total_ret:+.2f}%")
    print(f"  最大回撤:     {max_dd:.2f}%")
    print(f"  $10K →        ${cumulative:,.0f}")
    print(f"  vs Buy&Hold:  {bh_return:+.2f}%")


# ============================================================
# 總結
# ============================================================
print(f"\n{'='*90}")
print("📊 川普密碼回測總結")
print("=" * 90)
print(f"  {'規則':40s} | {'次數':>4s} | {'勝率':>5s} | {'平均':>8s} | {'$10K→':>10s}")
print(f"  {'-'*40}-+-{'-'*4}-+-{'-'*5}-+-{'-'*8}-+-{'-'*10}")

all_results = [
    ('R1: 盤前RELIEF→買1天', r1),
    ('R2: 盤中TARIFF×2→空1天', r2),
    ('R3: 連3天TARIFF後DEAL→買2天', r3),
    ('R4: 三信號齊發→買3天', r4),
    ('R5: 炫耀股市×2→空1天', r5),
    ('R6: 爆量日+關稅密集→買2天', r6),
    ('R7: 盤前ACTION→買1天', r7),
]

for name, result in all_results:
    if result:
        print(f"  {name:40s} | {result['trades']:4d} | {result['win_rate']:4.1f}% | {result['avg_return']:+.3f}% | ${result['final_value']:>9,.0f}")
    else:
        print(f"  {name:40s} | {'N/A':>4s} |  {'N/A':>4s} |   {'N/A':>6s} |    {'N/A':>6s}")

print(f"  {'-'*40}-+-{'-'*4}-+-{'-'*5}-+-{'-'*8}-+-{'-'*10}")
print(f"  {'Buy & Hold S&P500 (對照組)':40s} | {len(sp500):4d} | {'N/A':>5s} | {'N/A':>8s} | ${10000*(1+bh_return/100):>9,.0f}")

# 存結果
summary = {'buy_hold_return': round(bh_return, 2)}
for name, result in all_results:
    if result:
        summary[name] = result

with open(BASE / 'results_08_backtest.json', 'w') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"\n💾 詳細結果存入 results_08_backtest.json")
