#!/usr/bin/env python3
"""
川普密碼 分析 #9 — 多信號組合評分模型
不再靠單一規則，而是同時算多個維度的分數，加總後回測
像「信用評分」一樣，每天給股市一個「川普信號分數」
"""

import json
import re
import math
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

def est_hour(utc_str):
    dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
    return (dt.hour - 5) % 24, dt.minute

def next_td(date_str, market=sp_by_date):
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    for i in range(1, 6):
        d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
        if d in market:
            return d
    return None

print("=" * 90)
print("🧮 分析 #9: 多信號組合評分模型")
print("=" * 90)

# === 每天算分 ===

daily_scores = {}

# 預計算每日特徵
daily_posts = defaultdict(list)
for p in originals:
    daily_posts[p['created_at'][:10]].append(p)

sorted_dates = sorted(daily_posts.keys())

for idx, date in enumerate(sorted_dates):
    day_p = daily_posts[date]
    score = 0  # -100（極度看空）到 +100（極度看多）
    components = {}

    # --- 維度 1: 關稅 vs Deal 比例 (-20 ~ +20) ---
    tariff_count = 0
    deal_count = 0
    relief_count = 0
    for p in day_p:
        cl = p['content'].lower()
        if any(w in cl for w in ['tariff', 'tariffs', 'duty', 'duties']):
            tariff_count += 1
        if any(w in cl for w in ['deal', 'agreement', 'negotiate', 'signed']):
            deal_count += 1
        if any(w in cl for w in ['pause', 'delay', 'exempt', 'exception', 'suspend']):
            relief_count += 1

    if tariff_count + deal_count + relief_count > 0:
        deal_ratio = (deal_count + relief_count * 2) / (tariff_count + deal_count + relief_count)
        dim1 = (deal_ratio - 0.5) * 40  # -20 ~ +20
    else:
        dim1 = 0
    components['deal_vs_tariff'] = round(dim1, 1)
    score += dim1

    # --- 維度 2: 情緒方向 (-15 ~ +15) ---
    positive_words = ['great', 'tremendous', 'incredible', 'beautiful', 'amazing',
                      'wonderful', 'historic', 'best', 'winning', 'victory', 'love', 'proud']
    negative_words = ['fake', 'corrupt', 'terrible', 'horrible', 'worst', 'disgrace',
                      'incompetent', 'pathetic', 'stupid', 'disaster', 'fraud', 'enemy']
    pos_count = 0
    neg_count = 0
    for p in day_p:
        cl = p['content'].lower()
        pos_count += sum(1 for w in positive_words if w in cl)
        neg_count += sum(1 for w in negative_words if w in cl)

    if pos_count + neg_count > 0:
        sentiment = (pos_count - neg_count) / (pos_count + neg_count)
        dim2 = sentiment * 15
    else:
        dim2 = 0
    components['sentiment'] = round(dim2, 1)
    score += dim2

    # --- 維度 3: 發文量異常 (-10 ~ +10) ---
    # 前 7 天平均
    prev_counts = []
    for j in range(max(0, idx-7), idx):
        prev_counts.append(len(daily_posts.get(sorted_dates[j], [])))
    avg_prev = sum(prev_counts) / max(len(prev_counts), 1)
    today_count = len(day_p)

    if avg_prev > 0:
        volume_ratio = today_count / avg_prev
        if volume_ratio > 2:
            dim3 = -10  # 爆量 = 可能恐慌
        elif volume_ratio > 1.5:
            dim3 = -5
        elif volume_ratio < 0.5:
            dim3 = -5  # 極度沉默也不好
        else:
            dim3 = 5   # 正常偏多 = 穩定
    else:
        dim3 = 0
    components['volume'] = round(dim3, 1)
    score += dim3

    # --- 維度 4: 盤前信號 (-15 ~ +15) ---
    pre_tariff = 0
    pre_deal = 0
    pre_relief = 0
    pre_action = 0
    for p in day_p:
        h, m = est_hour(p['created_at'])
        if h < 9 or (h == 9 and m < 30):
            cl = p['content'].lower()
            if any(w in cl for w in ['tariff', 'tariffs']): pre_tariff += 1
            if any(w in cl for w in ['deal', 'agreement', 'signed']): pre_deal += 1
            if any(w in cl for w in ['pause', 'exempt', 'suspend', 'delay']): pre_relief += 1
            if any(w in cl for w in ['immediately', 'hereby', 'executive order', 'just signed']): pre_action += 1

    dim4 = (pre_deal * 5 + pre_relief * 10 + pre_action * 3 - pre_tariff * 2)
    dim4 = max(-15, min(15, dim4))
    components['pre_market'] = round(dim4, 1)
    score += dim4

    # --- 維度 5: 趨勢變化（和前3天比）(-15 ~ +15) ---
    prev_tariff_3 = 0
    prev_deal_3 = 0
    for j in range(max(0, idx-3), idx):
        for p in daily_posts.get(sorted_dates[j], []):
            cl = p['content'].lower()
            if any(w in cl for w in ['tariff', 'tariffs']): prev_tariff_3 += 1
            if any(w in cl for w in ['deal', 'agreement']): prev_deal_3 += 1

    # 今天 deal 增加 + tariff 減少 = 轉折
    tariff_change = tariff_count - (prev_tariff_3 / 3 if prev_tariff_3 else 0)
    deal_change = deal_count - (prev_deal_3 / 3 if prev_deal_3 else 0)
    dim5 = (deal_change - tariff_change) * 5
    dim5 = max(-15, min(15, dim5))
    components['trend_shift'] = round(dim5, 1)
    score += dim5

    # --- 維度 6: 結尾簽名等級 (-5 ~ +10) ---
    formal = 0
    for p in day_p:
        c = p['content']
        if 'PRESIDENT OF THE UNITED STATES' in c: formal += 3
        elif 'President DJT' in c: formal += 2
        elif 'Thank you for your attention' in c: formal += 1
    dim6 = min(formal, 10)
    components['formality'] = dim6
    score += dim6

    # --- 維度 7: 「炫耀股市」反指標 (-10 ~ 0) ---
    brag = 0
    for p in day_p:
        cl = p['content'].lower()
        if any(w in cl for w in ['stock market', 'all time high', 'record high', 'market up', 'markets up']):
            brag += 1
    dim7 = -min(brag * 3, 10)
    components['brag_penalty'] = dim7
    score += dim7

    # --- 維度 8: 大寫強度 (-5 ~ +5) ---
    caps_total = 0
    alpha_total = 0
    for p in day_p:
        caps_total += sum(1 for c in p['content'] if c.isupper())
        alpha_total += sum(1 for c in p['content'] if c.isalpha())
    caps_ratio = caps_total / max(alpha_total, 1)
    # 高大寫 = 情緒化 = 可能到頂
    if caps_ratio > 0.3:
        dim8 = -5
    elif caps_ratio > 0.2:
        dim8 = -2
    else:
        dim8 = 3
    components['caps_intensity'] = dim8
    score += dim8

    daily_scores[date] = {
        'score': round(score, 1),
        'components': components,
        'post_count': today_count,
        'tariff': tariff_count,
        'deal': deal_count,
        'relief': relief_count,
    }

# === 回測：按分數分組 ===
print(f"\n📊 每日信號分數分布:")
scores_list = [(d, s['score']) for d, s in daily_scores.items()]
scores_values = [s for _, s in scores_list]
print(f"   最低: {min(scores_values):.1f}")
print(f"   最高: {max(scores_values):.1f}")
print(f"   平均: {sum(scores_values)/len(scores_values):.1f}")
print(f"   中位: {sorted(scores_values)[len(scores_values)//2]:.1f}")

# 按分數分 5 等份
print(f"\n📊 分數區間 vs 隔日 S&P500 報酬:")
print(f"   {'區間':20s} | {'天數':>4s} | {'隔日報酬':>10s} | {'勝率':>6s} | {'S&P vs NQ'}")
print(f"   {'-'*20}-+-{'-'*4}-+-{'-'*10}-+-{'-'*6}-+-{'-'*20}")

# 5 分位數
buckets = [
    ('🔴 很看空 (<-10)', lambda s: s < -10),
    ('🟠 偏看空 (-10~0)', lambda s: -10 <= s < 0),
    ('🟡 中性 (0~10)', lambda s: 0 <= s < 10),
    ('🟢 偏看多 (10~20)', lambda s: 10 <= s < 20),
    ('🔵 很看多 (≥20)', lambda s: s >= 20),
]

for bucket_name, bucket_fn in buckets:
    days = [(d, s) for d, s in scores_list if bucket_fn(s['score']) and d in sp_by_date]
    if not days:
        continue

    sp_returns = []
    nq_returns = []
    for d, s in days:
        ntd = next_td(d)
        if ntd and ntd in sp_by_date:
            nsp = sp_by_date[ntd]
            sp_ret = (nsp['close'] - nsp['open']) / nsp['open'] * 100
            sp_returns.append(sp_ret)
        if ntd and ntd in nq_by_date:
            nnq = nq_by_date[ntd]
            nq_ret = (nnq['close'] - nnq['open']) / nnq['open'] * 100
            nq_returns.append(nq_ret)

    if sp_returns:
        avg_sp = sum(sp_returns) / len(sp_returns)
        avg_nq = sum(nq_returns) / len(nq_returns) if nq_returns else 0
        win = sum(1 for r in sp_returns if r > 0)
        win_rate = win / len(sp_returns) * 100
        sp_nq = f"SP:{avg_sp:+.3f}% NQ:{avg_nq:+.3f}%"
        print(f"   {bucket_name:20s} | {len(days):4d} | {avg_sp:+.3f}%     | {win_rate:5.1f}% | {sp_nq}")


# === 用分數做交易策略 ===
print(f"\n{'='*90}")
print("📊 組合評分策略回測")
print("=" * 90)

# 策略 A：分數 > 15 做多 1 天
# 策略 B：分數 < -5 做空 1 天
# 策略 C：分數從 <0 翻到 >10（轉折買入 2 天）

strategies = {
    'A: 高分(>15)做多1天': {'trigger': lambda d, s, ps: s['score'] > 15, 'direction': 'LONG', 'hold': 1},
    'B: 低分(<-5)做空1天': {'trigger': lambda d, s, ps: s['score'] < -5, 'direction': 'SHORT', 'hold': 1},
    'C: 翻正(前天<0今天>10)做多2天': {
        'trigger': lambda d, s, ps: s['score'] > 10 and ps and ps['score'] < 0,
        'direction': 'LONG', 'hold': 2
    },
    'D: 高分(>20)做多2天': {'trigger': lambda d, s, ps: s['score'] > 20, 'direction': 'LONG', 'hold': 2},
    'E: 盤前Relief+分數>5做多1天': {
        'trigger': lambda d, s, ps: s['components'].get('pre_market', 0) > 5 and s['score'] > 5,
        'direction': 'LONG', 'hold': 1
    },
    'F: 轉折+ACTION做多2天': {
        'trigger': lambda d, s, ps: s['components'].get('trend_shift', 0) > 5 and s['components'].get('pre_market', 0) > 0 and s['score'] > 8,
        'direction': 'LONG', 'hold': 2
    },
}

for strat_name, strat in strategies.items():
    trades = []
    capital = 10000

    prev_score = None
    for date in sorted_dates:
        if date not in daily_scores:
            continue
        s = daily_scores[date]

        if strat['trigger'](date, s, prev_score):
            entry_day = next_td(date)
            if not entry_day or entry_day not in sp_by_date:
                prev_score = s
                continue

            exit_day = entry_day
            for _ in range(strat['hold']):
                nd = next_td(exit_day)
                if nd:
                    exit_day = nd

            if exit_day not in sp_by_date:
                prev_score = s
                continue

            entry_p = sp_by_date[entry_day]['open']
            exit_p = sp_by_date[exit_day]['close']

            if strat['direction'] == 'LONG':
                ret = (exit_p - entry_p) / entry_p * 100
            else:
                ret = (entry_p - exit_p) / entry_p * 100

            trades.append({
                'entry': entry_day,
                'exit': exit_day,
                'return': ret,
                'score': s['score'],
            })

        prev_score = s

    if trades:
        wins = sum(1 for t in trades if t['return'] > 0)
        avg_ret = sum(t['return'] for t in trades) / len(trades)
        total_ret = sum(t['return'] for t in trades)

        cum = 10000
        peak = 10000
        max_dd = 0
        for t in trades:
            cum *= (1 + t['return'] / 100)
            peak = max(peak, cum)
            dd = (peak - cum) / peak * 100
            max_dd = max(max_dd, dd)

        print(f"\n  📋 {strat_name}")
        print(f"     交易: {len(trades)} | 勝率: {wins/len(trades)*100:.1f}% | 平均: {avg_ret:+.3f}% | 累積: {total_ret:+.2f}% | $10K→${cum:,.0f} | 最大回撤: {max_dd:.1f}%")

        # 顯示每筆交易
        if len(trades) <= 30:
            for t in trades:
                arrow = "✅" if t['return'] > 0 else "❌"
                print(f"        {t['entry']} → {t['exit']} | 分數{t['score']:+.1f} | {t['return']:+.2f}% {arrow}")


# === 最近 30 天分數 ===
print(f"\n{'='*90}")
print("📊 最近 30 天川普信號分數:")
print("=" * 90)
print(f"  {'日期':12s} | {'分數':>6s} | {'柱狀圖':40s} | {'主要成分'}")
for date in sorted_dates[-30:]:
    s = daily_scores[date]
    score = s['score']
    # 柱狀圖
    if score > 0:
        bar = ' ' * 20 + '█' * min(int(score), 20)
    else:
        width = min(abs(int(score)), 20)
        bar = ' ' * (20 - width) + '▓' * width + '|'

    # 主要影響因子
    top_comp = sorted(s['components'].items(), key=lambda x: abs(x[1]), reverse=True)[:2]
    comp_str = ', '.join(f"{k}:{v:+.0f}" for k, v in top_comp)

    sp = sp_by_date.get(date)
    sp_ret = ""
    if sp:
        ret = (sp['close'] - sp['open']) / sp['open'] * 100
        sp_ret = f"S&P{ret:+.2f}%"

    print(f"  {date:12s} | {score:+6.1f} | {bar:40s} | {comp_str:25s} {sp_ret}")


# 存結果
results = {
    'daily_scores': {d: {'score': s['score'], 'components': s['components']}
                     for d, s in daily_scores.items()},
}
with open(BASE / 'results_09_combo.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n💾 結果存入 results_09_combo.json")
