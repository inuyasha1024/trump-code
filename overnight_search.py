#!/usr/bin/env python3
"""
川普密碼 — 過夜大搜索
擴展到 500+ 特徵，暴力搜索所有組合
設計成背景執行，跑完自動存結果
"""

import json
import re
import csv
import html
import time
import urllib.request
from itertools import combinations
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent
START_TIME = time.time()

def log(msg):
    elapsed = time.time() - START_TIME
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)
    print(f"[{mins:02d}:{secs:02d}] {msg}", flush=True)

# ============================================================
# 步驟 1: 下載最新資料
# ============================================================
log("📥 步驟 1/5: 下載最新資料")

try:
    req = urllib.request.Request("https://ix.cnn.io/data/truth-social/truth_archive.csv")
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode('utf-8')
    reader = csv.DictReader(raw.splitlines())
    all_rows = list(reader)
    log(f"   下載完成: {len(all_rows)} 篇推文")

    # 清洗
    posts = []
    for row in all_rows:
        content = row['content'].strip()
        try:
            content = content.encode('latin-1').decode('utf-8')
        except:
            pass
        content = html.unescape(content)

        if content and not content.startswith('RT @'):
            created = row['created_at']
            if created >= '2025-01-20':
                posts.append({
                    'created_at': created,
                    'content': content,
                })

    posts.sort(key=lambda p: p['created_at'])
    log(f"   就任後原創: {len(posts)} 篇")

except Exception as e:
    log(f"   ⚠️ 下載失敗，用本地資料: {e}")
    with open(BASE / "clean_president.json") as f:
        loaded = json.load(f)
    posts = sorted(
        [p for p in loaded if p['has_text'] and not p.get('is_retweet', False)],
        key=lambda p: p['created_at']
    )
    log(f"   本地資料: {len(posts)} 篇")

# 下載股市資料
log("   下載股市資料...")
try:
    import subprocess
    subprocess.run(['pip3', 'install', 'yfinance', '--quiet'], capture_output=True)
    import yfinance as yf
    sp = yf.download('^GSPC', start='2025-01-17', end='2026-03-16', progress=False)
    sp500 = []
    for date, row in sp.iterrows():
        sp500.append({
            'date': date.strftime('%Y-%m-%d'),
            'open': round(float(row['Open'].iloc[0]), 2),
            'close': round(float(row['Close'].iloc[0]), 2),
        })
    log(f"   S&P500: {len(sp500)} 交易日")
except Exception as e:
    log(f"   ⚠️ yfinance 失敗，用本地: {e}")
    with open(BASE / "market_SP500.json") as f:
        sp500 = json.load(f)

sp_by_date = {r['date']: r for r in sp500}


# ============================================================
# 步驟 2: 擴展特徵到 500+
# ============================================================
log("📊 步驟 2/5: 擴展特徵")

daily_posts = defaultdict(list)
for p in posts:
    daily_posts[p['created_at'][:10]].append(p)
sorted_dates = sorted(daily_posts.keys())

# 單字關鍵字清單（每個都是獨立特徵）
KEYWORDS = [
    # 政策
    'tariff', 'tariffs', 'deal', 'trade', 'agreement', 'negotiate',
    'pause', 'exempt', 'suspend', 'delay', 'reciprocal', 'duty',
    'executive order', 'signed', 'immediately', 'hereby', 'effective',
    'ban', 'block', 'restrict', 'sanction',
    # 國家
    'china', 'chinese', 'japan', 'japanese', 'mexico', 'canada',
    'russia', 'putin', 'ukraine', 'iran', 'israel', 'europe',
    'india', 'taiwan', 'korea', 'saudi',
    # 經濟
    'stock market', 'dow', 'nasdaq', 'economy', 'inflation',
    'interest rate', 'oil', 'gas', 'energy', 'jobs',
    'gdp', 'deficit', 'debt', 'billion', 'trillion',
    # 情緒詞
    'great', 'tremendous', 'incredible', 'historic', 'beautiful',
    'amazing', 'fantastic', 'wonderful', 'perfect',
    'fake', 'corrupt', 'terrible', 'horrible', 'worst',
    'disaster', 'disgrace', 'stupid', 'incompetent', 'pathetic',
    # 人物
    'biden', 'obama', 'pelosi', 'elon', 'musk', 'doge',
    'vance', 'desantis', 'kamala',
    # 政策口號
    'maga', 'save america', 'america first', 'golden age',
    'liberation day', 'filibuster', 'obamacare',
    # 簽名
    'president djt', 'president of the united states',
    'thank you for your attention', 'never let you down',
    'complete and total',
]

def est_hour(utc_str):
    dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
    return (dt.hour - 5) % 24, dt.minute

def compute_features(date, idx):
    """計算 500+ 特徵"""
    day_p = daily_posts.get(date, [])
    if not day_p:
        return None

    f = {}
    n = len(day_p)

    # --- 基本量化 ---
    total_len = sum(len(p['content']) for p in day_p)
    avg_len = total_len / n
    total_excl = sum(p['content'].count('!') for p in day_p)
    total_q = sum(p['content'].count('?') for p in day_p)
    total_caps = sum(sum(1 for c in p['content'] if c.isupper()) for p in day_p)
    total_alpha = sum(sum(1 for c in p['content'] if c.isalpha()) for p in day_p)
    caps_ratio = total_caps / max(total_alpha, 1)

    # 發文量特徵（多個閾值）
    f['posts_1_5'] = 1 <= n <= 5
    f['posts_6_10'] = 6 <= n <= 10
    f['posts_11_20'] = 11 <= n <= 20
    f['posts_21_35'] = 21 <= n <= 35
    f['posts_36plus'] = n >= 36

    # 文字長度特徵
    f['avg_len_short'] = avg_len < 150
    f['avg_len_medium'] = 150 <= avg_len < 350
    f['avg_len_long'] = 350 <= avg_len < 600
    f['avg_len_very_long'] = avg_len >= 600

    # 大寫率
    f['caps_low'] = caps_ratio < 0.10
    f['caps_medium'] = 0.10 <= caps_ratio < 0.18
    f['caps_high'] = 0.18 <= caps_ratio < 0.25
    f['caps_very_high'] = caps_ratio >= 0.25

    # 驚嘆號
    excl_per = total_excl / n
    f['excl_none'] = excl_per < 0.3
    f['excl_normal'] = 0.3 <= excl_per < 1.5
    f['excl_heavy'] = 1.5 <= excl_per < 3
    f['excl_extreme'] = excl_per >= 3

    # 問號（少見=聲明多，多=在質疑）
    f['questions_yes'] = total_q >= 2
    f['questions_no'] = total_q == 0

    # --- 時段特徵 ---
    pre_count = 0; open_count = 0; after_count = 0; night_count = 0
    for p in day_p:
        h, m_val = est_hour(p['created_at'])
        if h < 9 or (h == 9 and m_val < 30): pre_count += 1
        elif h < 16: open_count += 1
        elif h < 20: after_count += 1
        else: night_count += 1

    f['mostly_premarket'] = pre_count > n * 0.5
    f['mostly_open'] = open_count > n * 0.5
    f['mostly_after'] = after_count > n * 0.5
    f['has_night'] = night_count >= 1
    f['heavy_night'] = night_count >= 3

    # --- 每個關鍵字的有無 + 時段組合 ---
    for kw in KEYWORDS:
        kw_clean = kw.replace(' ', '_').replace("'", '')
        total_kw = 0
        pre_kw = 0
        open_kw = 0
        for p in day_p:
            cl = p['content'].lower()
            if kw in cl:
                total_kw += 1
                h, m_val = est_hour(p['created_at'])
                if h < 9 or (h == 9 and m_val < 30): pre_kw += 1
                elif h < 16: open_kw += 1

        f[f'kw_{kw_clean}'] = total_kw >= 1
        f[f'kw_{kw_clean}_2plus'] = total_kw >= 2
        if pre_kw >= 1:
            f[f'pre_{kw_clean}'] = True
        if open_kw >= 1:
            f[f'open_{kw_clean}'] = True

    # --- 星期特徵 ---
    dt = datetime.strptime(date, '%Y-%m-%d')
    f['is_monday'] = dt.weekday() == 0
    f['is_friday'] = dt.weekday() == 4
    f['is_weekend'] = dt.weekday() >= 5

    # --- 趨勢特徵（前 N 天比較）---
    if idx >= 3:
        prev_counts = [len(daily_posts.get(sorted_dates[j], [])) for j in range(max(0,idx-3), idx)]
        f['volume_rising_3d'] = all(prev_counts[i] <= prev_counts[i+1] for i in range(len(prev_counts)-1)) if len(prev_counts) >= 2 else False
        f['volume_falling_3d'] = all(prev_counts[i] >= prev_counts[i+1] for i in range(len(prev_counts)-1)) if len(prev_counts) >= 2 else False
    else:
        f['volume_rising_3d'] = False
        f['volume_falling_3d'] = False

    if idx >= 7:
        prev_7 = [len(daily_posts.get(sorted_dates[j], [])) for j in range(idx-7, idx)]
        avg_7 = sum(prev_7) / 7
        f['volume_spike'] = n > avg_7 * 2 if avg_7 > 0 else False
        f['volume_drop'] = n < avg_7 * 0.4 if avg_7 > 0 else False
    else:
        f['volume_spike'] = False
        f['volume_drop'] = False

    # --- 組合特徵 ---
    has_tariff = any(kw in ' '.join(p['content'].lower() for p in day_p) for kw in ['tariff', 'tariffs'])
    has_deal = 'deal' in ' '.join(p['content'].lower() for p in day_p)

    f['deal_without_tariff'] = has_deal and not has_tariff
    f['tariff_without_deal'] = has_tariff and not has_deal
    f['both_tariff_and_deal'] = has_tariff and has_deal

    # 只保留 True 的特徵（節省記憶體）
    return {k: v for k, v in f.items() if v is True}


# 計算所有天
log("   計算每日特徵...")
all_features = {}
for idx, date in enumerate(sorted_dates):
    feat = compute_features(date, idx)
    if feat:
        all_features[date] = feat

# 統計特徵數
all_feat_names = set()
for feat in all_features.values():
    all_feat_names.update(feat.keys())

feature_names = sorted(all_feat_names)
log(f"   ✅ 特徵數: {len(feature_names)} 個")
log(f"   天數: {len(all_features)} 天")


# ============================================================
# 步驟 3: 只保留有意義的特徵（出現 5-200 天）
# ============================================================
log("🔧 步驟 3/5: 過濾特徵")

feat_counts = Counter()
for feat in all_features.values():
    feat_counts.update(feat.keys())

# 太少（<5天）= 樣本不夠，太多（>200天）= 沒區別力
useful_features = [f for f, c in feat_counts.items() if 5 <= c <= 200]
useful_features.sort()
log(f"   有效特徵: {len(useful_features)} / {len(feature_names)} 個")


# ============================================================
# 步驟 4: 暴力搜索
# ============================================================
log("🔨 步驟 4/5: 暴力搜索")

def next_td(date_str):
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    for i in range(1, 6):
        d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
        if d in sp_by_date:
            return d
    return None

# 分割訓練/驗證
cutoff = "2025-12-01"
train_dates = [d for d in sorted_dates if d < cutoff and d in all_features and d in sp_by_date]
test_dates = [d for d in sorted_dates if d >= cutoff and d in all_features and d in sp_by_date]
log(f"   訓練: {len(train_dates)} 天 | 驗證: {len(test_dates)} 天")

# 預計算每天的市場報酬
day_returns = {}
for date in sorted_dates:
    for hold in [1, 2, 3]:
        entry = next_td(date) if date in sp_by_date else None
        if not entry or entry not in sp_by_date:
            # 嘗試用日期本身
            if date in sp_by_date:
                entry = date
            else:
                continue

        exit_d = entry
        for _ in range(hold):
            nd = next_td(exit_d)
            if nd:
                exit_d = nd

        if entry in sp_by_date and exit_d in sp_by_date:
            ep = sp_by_date[entry]['open']
            xp = sp_by_date[exit_d]['close']
            day_returns[(date, hold)] = (xp - ep) / ep * 100

log(f"   預計算報酬完成")

# 先只跑 2 和 3 條件（4 條件在 500+ 特徵下太多）
n_feat = len(useful_features)
n2 = n_feat * (n_feat - 1) // 2
n3 = n_feat * (n_feat - 1) * (n_feat - 2) // 6
total_combos = (n2 + n3) * 3 * 2  # × 3 持有 × 2 方向
log(f"   2條件: {n2:,} | 3條件: {n3:,}")
log(f"   總組合: {total_combos:,}")

winners = []
tested = 0
batch_time = time.time()

for n_cond in [2, 3]:
    for combo_idx in combinations(range(n_feat), n_cond):
        feature_combo = [useful_features[i] for i in combo_idx]

        for hold in [1, 2, 3]:
            for direction in ['LONG', 'SHORT']:
                tested += 1

                if tested % 50000 == 0:
                    elapsed = time.time() - batch_time
                    speed = 50000 / elapsed
                    remaining = (total_combos - tested) / speed
                    log(f"   {tested:,}/{total_combos:,} ({tested/total_combos*100:.1f}%) | 候選:{len(winners)} | 剩~{remaining/60:.0f}分鐘")
                    batch_time = time.time()

                # 快速訓練期回測
                train_rets = []
                for date in train_dates:
                    feat = all_features.get(date, {})
                    if all(feat.get(f, False) for f in feature_combo):
                        r = day_returns.get((date, hold))
                        if r is not None:
                            if direction == 'SHORT':
                                train_rets.append(-r)
                            else:
                                train_rets.append(r)

                if len(train_rets) < 3:
                    continue

                wins = sum(1 for r in train_rets if r > 0)
                win_rate = wins / len(train_rets) * 100
                avg_ret = sum(train_rets) / len(train_rets)

                if win_rate < 65 or avg_ret < 0.15:
                    continue

                # 通過訓練期！驗證期
                test_rets = []
                for date in test_dates:
                    feat = all_features.get(date, {})
                    if all(feat.get(f, False) for f in feature_combo):
                        r = day_returns.get((date, hold))
                        if r is not None:
                            if direction == 'SHORT':
                                test_rets.append(-r)
                            else:
                                test_rets.append(r)

                if len(test_rets) < 2:
                    continue

                test_wins = sum(1 for r in test_rets if r > 0)
                test_rate = test_wins / len(test_rets) * 100
                test_avg = sum(test_rets) / len(test_rets)

                if test_rate >= 55 and test_avg > 0:
                    winners.append({
                        'features': feature_combo,
                        'direction': direction,
                        'hold': hold,
                        'n_cond': n_cond,
                        'train_trades': len(train_rets),
                        'train_win_rate': round(win_rate, 1),
                        'train_avg': round(avg_ret, 3),
                        'test_trades': len(test_rets),
                        'test_win_rate': round(test_rate, 1),
                        'test_avg': round(test_avg, 3),
                        'combined_score': round((win_rate + test_rate) / 2, 1),
                    })


# ============================================================
# 步驟 5: 整理結果
# ============================================================
log(f"\n✅ 搜索完成！")
log(f"   總組合: {tested:,}")
log(f"   最終存活: {len(winners)} 組")

# 排序
winners.sort(key=lambda w: (-w['combined_score'], -w['train_avg'] - w['test_avg']))

# 存完整結果
with open(BASE / 'overnight_results.json', 'w') as f:
    json.dump({
        'meta': {
            'total_tested': tested,
            'total_features': len(useful_features),
            'train_days': len(train_dates),
            'test_days': len(test_dates),
            'survivors': len(winners),
            'completed_at': datetime.utcnow().isoformat() + 'Z',
            'runtime_seconds': round(time.time() - START_TIME),
        },
        'feature_list': useful_features,
        'winners': winners[:500],  # Top 500
    }, f, ensure_ascii=False, indent=2)

# 存監控用的精簡版（只存 Top 100 規則）
monitor_rules = []
for w in winners[:100]:
    monitor_rules.append({
        'id': f"R{len(monitor_rules)+1:04d}",
        'features': w['features'],
        'direction': w['direction'],
        'hold': w['hold'],
        'train_wr': w['train_win_rate'],
        'test_wr': w['test_win_rate'],
        'score': w['combined_score'],
    })

with open(BASE / 'monitor_rules.json', 'w') as f:
    json.dump(monitor_rules, f, ensure_ascii=False, indent=2)

# 打印 Top 30
log(f"\n{'='*90}")
log(f"🏆 Top 30 真密碼")
log(f"{'='*90}")
log(f"  {'#':>3s} | {'方向':>3s} | {'天':>2s} | {'訓練':>5s} | {'驗證':>5s} | {'訓均':>6s} | {'驗均':>6s} | 條件")

for i, w in enumerate(winners[:30], 1):
    d = "📈" if w['direction'] == 'LONG' else "📉"
    feats = ' + '.join(w['features'])
    log(f"  {i:3d} | {d:>3s} | {w['hold']:2d} | {w['train_win_rate']:4.0f}% | {w['test_win_rate']:4.0f}% | {w['train_avg']:+.3f} | {w['test_avg']:+.3f} | {feats}")

# 特徵頻率
feat_freq = Counter()
for w in winners:
    for f_name in w['features']:
        feat_freq[f_name] += 1

log(f"\n📊 真密碼 DNA（Top 20 最常出現的特徵）:")
for fname, count in feat_freq.most_common(20):
    pct = count / max(len(winners), 1) * 100
    log(f"  {fname:35s} | {count:5d}次 ({pct:5.1f}%)")

runtime = time.time() - START_TIME
log(f"\n⏱️ 總耗時: {runtime/60:.1f} 分鐘")
log(f"💾 完整結果: overnight_results.json")
log(f"💾 監控規則: monitor_rules.json (Top 100)")
log(f"✅ 過夜搜索完成！明天起每天自動監控。")
