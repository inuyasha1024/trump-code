#!/usr/bin/env python3
"""
川普密碼 分析 #11 — 暴力搜索
把所有特徵的 2 條件、3 條件、4 條件組合全部跑一遍
前 10 個月找規則 → 最後 3 個月驗證 → 兩段都對的才是真密碼
"""

import json
import re
from itertools import combinations
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent

with open(BASE / "clean_president.json") as f:
    posts = json.load(f)

with open(BASE / "market_SP500.json") as f:
    sp500 = json.load(f)

sp_by_date = {r['date']: r for r in sp500}

originals = sorted(
    [p for p in posts if p['has_text'] and not p['is_retweet']],
    key=lambda p: p['created_at']
)

# === 每天算 20+ 個二元特徵 ===

daily_posts = defaultdict(list)
for p in originals:
    daily_posts[p['created_at'][:10]].append(p)

sorted_dates = sorted(daily_posts.keys())

def est_hour(utc_str):
    dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
    return (dt.hour - 5) % 24, dt.minute

def compute_features(date, idx):
    """計算某一天的所有二元特徵"""
    day_p = daily_posts.get(date, [])
    if not day_p:
        return None

    f = {}
    post_count = len(day_p)
    f['posts_high'] = post_count >= 20      # 高發文量
    f['posts_low'] = post_count <= 5        # 低發文量
    f['posts_very_high'] = post_count >= 35 # 極高

    tariff = 0; deal = 0; relief = 0; action = 0
    attack = 0; positive = 0; market_brag = 0
    china = 0; iran = 0; russia = 0
    pre_tariff = 0; pre_deal = 0; pre_relief = 0; pre_action = 0
    open_tariff = 0; open_deal = 0
    night_post = 0; sig_djt = 0; sig_potus = 0; sig_tyfa = 0
    total_excl = 0; total_caps = 0; total_alpha = 0
    total_len = 0

    for p in day_p:
        cl = p['content'].lower()
        c = p['content']
        h, m_val = est_hour(p['created_at'])
        is_pre = h < 9 or (h == 9 and m_val < 30)
        is_open = not is_pre and h < 16
        is_night = h < 5 or h >= 23

        if any(w in cl for w in ['tariff', 'tariffs', 'duty']): tariff += 1
        if any(w in cl for w in ['deal', 'agreement', 'signed', 'negotiate']): deal += 1
        if any(w in cl for w in ['pause', 'exempt', 'suspend', 'delay']): relief += 1
        if any(w in cl for w in ['immediately', 'hereby', 'executive order', 'just signed']): action += 1
        if any(w in cl for w in ['fake news', 'corrupt', 'fraud', 'witch hunt']): attack += 1
        if any(w in cl for w in ['great', 'tremendous', 'incredible', 'historic', 'beautiful']): positive += 1
        if any(w in cl for w in ['stock market', 'all time high', 'record high', 'dow']): market_brag += 1
        if any(w in cl for w in ['china', 'chinese', 'beijing']): china += 1
        if any(w in cl for w in ['iran', 'iranian']): iran += 1
        if any(w in cl for w in ['russia', 'putin', 'ukraine']): russia += 1

        if is_pre and tariff: pre_tariff += 1
        if is_pre and deal: pre_deal += 1
        if is_pre and relief: pre_relief += 1
        if is_pre and action: pre_action += 1
        if is_open and tariff: open_tariff += 1
        if is_open and deal: open_deal += 1
        if is_night: night_post += 1

        if 'President DJT' in c: sig_djt += 1
        if 'PRESIDENT OF THE UNITED STATES' in c: sig_potus += 1
        if 'Thank you for your attention' in c: sig_tyfa += 1

        total_excl += c.count('!')
        total_caps += sum(1 for ch in c if ch.isupper())
        total_alpha += sum(1 for ch in c if ch.isalpha())
        total_len += len(c)

    # 二元特徵
    f['has_tariff'] = tariff >= 1
    f['tariff_heavy'] = tariff >= 3
    f['has_deal'] = deal >= 1
    f['deal_heavy'] = deal >= 2
    f['has_relief'] = relief >= 1
    f['has_action'] = action >= 1
    f['has_attack'] = attack >= 1
    f['attack_heavy'] = attack >= 3
    f['has_positive'] = positive >= 1
    f['positive_heavy'] = positive >= 3
    f['has_market_brag'] = market_brag >= 1
    f['brag_heavy'] = market_brag >= 2
    f['has_china'] = china >= 1
    f['has_iran'] = iran >= 1
    f['has_russia'] = russia >= 1
    f['pre_tariff'] = pre_tariff >= 1
    f['pre_deal'] = pre_deal >= 1
    f['pre_relief'] = pre_relief >= 1
    f['pre_action'] = pre_action >= 1
    f['open_tariff'] = open_tariff >= 1
    f['open_tariff_heavy'] = open_tariff >= 2
    f['open_deal'] = open_deal >= 1
    f['has_night_post'] = night_post >= 1
    f['sig_djt'] = sig_djt >= 1
    f['sig_potus'] = sig_potus >= 1
    f['sig_tyfa'] = sig_tyfa >= 1
    f['high_emotion'] = (total_caps / max(total_alpha, 1)) > 0.2
    f['lots_of_excl'] = total_excl >= 5
    f['long_posts'] = (total_len / max(post_count, 1)) > 400
    f['short_posts'] = (total_len / max(post_count, 1)) < 150

    # 多天趨勢特徵
    if idx >= 3:
        prev_tariff = sum(1 for j in range(max(0,idx-3), idx)
                         if any('tariff' in p['content'].lower() for p in daily_posts.get(sorted_dates[j], [])))
        f['tariff_streak_3d'] = prev_tariff >= 3
        f['tariff_rising'] = prev_tariff >= 2 and tariff >= 1
    else:
        f['tariff_streak_3d'] = False
        f['tariff_rising'] = False

    # Deal 和 Tariff 的相對比例
    f['deal_over_tariff'] = deal > tariff and deal >= 1
    f['tariff_only'] = tariff >= 1 and deal == 0
    f['deal_only'] = deal >= 1 and tariff == 0

    # 前 7 天發文量比較
    if idx >= 7:
        prev_avg = sum(len(daily_posts.get(sorted_dates[j], []))
                      for j in range(idx-7, idx)) / 7
        f['volume_spike'] = post_count > prev_avg * 2 if prev_avg > 0 else False
        f['volume_drop'] = post_count < prev_avg * 0.4 if prev_avg > 0 else False
    else:
        f['volume_spike'] = False
        f['volume_drop'] = False

    return f


def next_trading_day(date_str):
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    for i in range(1, 6):
        d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
        if d in sp_by_date:
            return d
    return None


# === 計算所有天的特徵 ===
print("📊 計算每日特徵中...")
all_features = {}
for idx, date in enumerate(sorted_dates):
    feat = compute_features(date, idx)
    if feat:
        all_features[date] = feat

# 取得所有特徵名
feature_names = sorted(list(all_features[sorted_dates[10]].keys()))
print(f"   特徵數: {len(feature_names)} 個")
print(f"   天數: {len(all_features)} 天")

# === 分割：訓練 vs 驗證 ===
# 前 10 個月 = 訓練，最後 3 個月 = 驗證
cutoff = "2025-12-01"
train_dates = [d for d in sorted_dates if d < cutoff and d in all_features and d in sp_by_date]
test_dates = [d for d in sorted_dates if d >= cutoff and d in all_features and d in sp_by_date]

print(f"   訓練期: {train_dates[0]} ~ {train_dates[-1]} ({len(train_dates)} 天)")
print(f"   驗證期: {test_dates[0]} ~ {test_dates[-1]} ({len(test_dates)} 天)")

# === 暴力搜索 ===
print(f"\n{'='*90}")
print(f"🔨 暴力搜索 — 所有 2/3/4 條件組合 × 2 方向 × 3 持有天數")
print(f"{'='*90}")

hold_options = [1, 2, 3]
direction_options = ['LONG', 'SHORT']

# 計算組合數
n_features = len(feature_names)
n2 = len(list(combinations(range(n_features), 2)))
n3 = len(list(combinations(range(n_features), 3)))
n4 = len(list(combinations(range(n_features), 4)))
total_combos = (n2 + n3 + n4) * len(hold_options) * len(direction_options)
print(f"   2 條件: {n2} 組")
print(f"   3 條件: {n3} 組")
print(f"   4 條件: {n4} 組")
print(f"   × {len(hold_options)} 持有天數 × {len(direction_options)} 方向")
print(f"   總計: {total_combos:,} 組合")

# 回測單個組合
def backtest_combo(feature_combo, direction, hold, dates):
    """回測一個特定的條件組合"""
    trades = []

    for date in dates:
        feat = all_features.get(date)
        if not feat:
            continue

        # 檢查所有條件是否同時滿足
        triggered = all(feat.get(f, False) for f in feature_combo)
        if not triggered:
            continue

        # 找入場/出場
        entry_day = next_trading_day(date)
        if not entry_day:
            continue

        exit_day = entry_day
        for _ in range(hold):
            nd = next_trading_day(exit_day)
            if nd:
                exit_day = nd

        if entry_day not in sp_by_date or exit_day not in sp_by_date:
            continue

        entry_p = sp_by_date[entry_day]['open']
        exit_p = sp_by_date[exit_day]['close']

        if direction == 'LONG':
            ret = (exit_p - entry_p) / entry_p * 100
        else:
            ret = (entry_p - exit_p) / entry_p * 100

        trades.append({'date': date, 'return': ret})

    if len(trades) < 3:  # 至少 3 筆才有統計意義
        return None

    wins = sum(1 for t in trades if t['return'] > 0)
    total_ret = sum(t['return'] for t in trades)
    avg_ret = total_ret / len(trades)
    win_rate = wins / len(trades) * 100

    return {
        'trades': len(trades),
        'wins': wins,
        'win_rate': win_rate,
        'avg_return': avg_ret,
        'total_return': total_ret,
        'details': trades,
    }


# === 跑所有組合 ===
winners_train = []  # 訓練期勝率 > 60% 的
total_tested = 0
progress_interval = 5000

print(f"\n🔄 開跑...\n")

for n_conditions in [2, 3, 4]:
    for combo in combinations(range(n_features), n_conditions):
        feature_combo = [feature_names[i] for i in combo]

        for hold in hold_options:
            for direction in direction_options:
                total_tested += 1

                if total_tested % progress_interval == 0:
                    print(f"   已跑 {total_tested:,} / {total_combos:,} ({total_tested/total_combos*100:.1f}%) | 候選: {len(winners_train)}", flush=True)

                # 訓練期回測
                result = backtest_combo(feature_combo, direction, hold, train_dates)
                if result and result['win_rate'] >= 60 and result['avg_return'] > 0.1:
                    winners_train.append({
                        'features': feature_combo,
                        'direction': direction,
                        'hold': hold,
                        'n_conditions': n_conditions,
                        'train': result,
                    })

print(f"\n✅ 全部跑完！")
print(f"   總組合: {total_tested:,}")
print(f"   訓練期過關: {len(winners_train)} 組 (勝率>60% & 平均報酬>0.1%)")

# === 用驗證期檢驗 ===
print(f"\n{'='*90}")
print(f"🧪 驗證期檢驗 — 只有兩段都對的才是真密碼")
print(f"{'='*90}")

final_winners = []

for w in winners_train:
    test_result = backtest_combo(w['features'], w['direction'], w['hold'], test_dates)
    if test_result and test_result['win_rate'] >= 55 and test_result['avg_return'] > 0:
        w['test'] = test_result
        w['combined_win_rate'] = (w['train']['win_rate'] + test_result['win_rate']) / 2
        w['combined_avg_return'] = (w['train']['avg_return'] + test_result['avg_return']) / 2
        final_winners.append(w)

# 按綜合表現排序
final_winners.sort(key=lambda w: (-w['combined_win_rate'], -w['combined_avg_return']))

print(f"\n   訓練期過關: {len(winners_train)} 組")
print(f"   驗證期也過關: {len(final_winners)} 組 ← 真密碼候選")
print(f"   淘汰率: {(1 - len(final_winners)/max(len(winners_train),1))*100:.1f}%")

# === 打印 Top 30 ===
print(f"\n{'='*90}")
print(f"🏆 川普密碼 — 最終排行榜 Top 30（訓練+驗證都過關）")
print(f"{'='*90}")
print(f"  {'排名':>4s} | {'方向':>4s} | {'持有':>2s} | {'訓練勝率':>8s} | {'驗證勝率':>8s} | {'訓練報酬':>8s} | {'驗證報酬':>8s} | 條件組合")
print(f"  {'-'*4}-+-{'-'*4}-+-{'-'*2}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*30}")

for rank, w in enumerate(final_winners[:30], 1):
    dir_icon = "📈" if w['direction'] == 'LONG' else "📉"
    features_str = ' + '.join(w['features'])

    print(f"  {rank:4d} | {dir_icon}{w['direction']:>3s} | {w['hold']:2d}天 | "
          f"{w['train']['win_rate']:6.1f}% | {w['test']['win_rate']:6.1f}% | "
          f"{w['train']['avg_return']:+.3f}% | {w['test']['avg_return']:+.3f}% | "
          f"{features_str}")

# === 按條件數分組統計 ===
print(f"\n{'='*90}")
print(f"📊 幾個條件最好？")
print(f"{'='*90}")
for n in [2, 3, 4]:
    group = [w for w in final_winners if w['n_conditions'] == n]
    if group:
        avg_wr = sum(w['combined_win_rate'] for w in group) / len(group)
        avg_ret = sum(w['combined_avg_return'] for w in group) / len(group)
        best = group[0]
        print(f"  {n} 條件: {len(group)} 組過關 | 平均勝率 {avg_wr:.1f}% | 平均報酬 {avg_ret:+.3f}%")
        print(f"    最佳: {' + '.join(best['features'])} ({best['direction']}, {best['hold']}天)")

# === 找最常出現的特徵 ===
print(f"\n{'='*90}")
print(f"📊 哪些特徵最常出現在贏家組合？（真密碼的 DNA）")
print(f"{'='*90}")
feature_freq = defaultdict(int)
for w in final_winners:
    for f_name in w['features']:
        feature_freq[f_name] += 1

for fname, count in sorted(feature_freq.items(), key=lambda x: -x[1])[:20]:
    bar = '█' * min(count, 40)
    pct = count / max(len(final_winners), 1) * 100
    print(f"  {fname:25s} | {count:4d}次 ({pct:5.1f}%) {bar}")

# 存結果
output = {
    'total_tested': total_tested,
    'train_passed': len(winners_train),
    'final_passed': len(final_winners),
    'top_30': [{
        'rank': i+1,
        'features': w['features'],
        'direction': w['direction'],
        'hold': w['hold'],
        'train_win_rate': round(w['train']['win_rate'], 1),
        'test_win_rate': round(w['test']['win_rate'], 1),
        'train_avg_return': round(w['train']['avg_return'], 3),
        'test_avg_return': round(w['test']['avg_return'], 3),
    } for i, w in enumerate(final_winners[:30])],
    'feature_frequency': dict(sorted(feature_freq.items(), key=lambda x: -x[1])[:20]),
}

with open(BASE / 'results_11_bruteforce.json', 'w') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n💾 結果存入 results_11_bruteforce.json")
