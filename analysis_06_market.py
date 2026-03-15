#!/usr/bin/env python3
"""
川普密碼 分析 #6 — 發文 vs 美股反應
核心問題：他發完文之後，股市怎麼動？
"""

import json
import re
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent

# --- 載入資料 ---
with open(BASE / "clean_president.json", 'r') as f:
    posts = json.load(f)

with open(BASE / "market_SP500.json", 'r') as f:
    sp500 = json.load(f)

with open(BASE / "market_VIX.json", 'r') as f:
    vix = json.load(f)

with open(BASE / "market_DOW.json", 'r') as f:
    dow = json.load(f)

with open(BASE / "market_NASDAQ.json", 'r') as f:
    nasdaq = json.load(f)

# 建立日期索引
sp500_by_date = {r['date']: r for r in sp500}
vix_by_date = {r['date']: r for r in vix}
dow_by_date = {r['date']: r for r in dow}
nasdaq_by_date = {r['date']: r for r in nasdaq}

originals = [p for p in posts if p['has_text'] and not p['is_retweet']]

print("=" * 80)
print("📈 分析 #6: 川普發文 vs 美股反應")
print(f"   貼文: {len(originals)} 篇 | S&P500: {len(sp500)} 交易日")
print("=" * 80)


# === 工具函數 ===

def get_next_trading_day(date_str, market_data):
    """取得某日期後的下一個交易日"""
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    for i in range(1, 5):  # 最多看後4天（跨週末）
        next_d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
        if next_d in market_data:
            return next_d
    return None

def get_prev_trading_day(date_str, market_data):
    """取得某日期前的上一個交易日"""
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    for i in range(1, 5):
        prev_d = (dt - timedelta(days=i)).strftime('%Y-%m-%d')
        if prev_d in market_data:
            return prev_d
    return None

def day_return(date_str, market_data):
    """計算當天漲跌幅 %"""
    if date_str not in market_data:
        return None
    d = market_data[date_str]
    return (d['close'] - d['open']) / d['open'] * 100

def next_day_return(date_str, market_data):
    """計算下一個交易日的漲跌幅 %"""
    next_d = get_next_trading_day(date_str, market_data)
    if not next_d:
        return None
    return day_return(next_d, market_data)

def overnight_gap(date_str, market_data):
    """計算隔夜跳空 (下一交易日 open vs 今天 close)"""
    if date_str not in market_data:
        return None
    next_d = get_next_trading_day(date_str, market_data)
    if not next_d:
        return None
    today_close = market_data[date_str]['close']
    next_open = market_data[next_d]['open']
    return (next_open - today_close) / today_close * 100


# === 每日發文特徵 ===
daily_features = defaultdict(lambda: {
    'post_count': 0, 'total_length': 0, 'excl_count': 0,
    'caps_count': 0, 'has_tariff': False, 'has_china': False,
    'has_market': False, 'has_deal': False, 'has_fake': False,
    'has_iran': False, 'has_border': False, 'emotion_sum': 0,
    'night_posts': 0, 'contents': []
})

def emotion_score(content):
    score = 0
    text = content
    upper = sum(1 for c in text if c.isupper())
    total = sum(1 for c in text if c.isalpha())
    caps_ratio = upper / max(total, 1)
    score += caps_ratio * 30
    excl = text.count('!')
    excl_density = excl / max(len(text), 1) * 100
    score += min(excl_density * 10, 25)
    strong_words = ['never', 'always', 'worst', 'best', 'greatest', 'terrible',
                    'tremendous', 'massive', 'total', 'complete', 'disaster',
                    'incredible', 'amazing', 'fantastic', 'historic', 'beautiful']
    strong_count = sum(1 for w in strong_words if w in text.lower())
    word_count = len(re.findall(r'\b\w+\b', text.lower()))
    score += min(strong_count / max(word_count, 1) * 500, 25)
    caps_words = len(re.findall(r'\b[A-Z]{3,}\b', text))
    score += min(caps_words * 2, 20)
    return min(round(score, 1), 100)

for p in originals:
    date = p['created_at'][:10]
    content_lower = p['content'].lower()
    d = daily_features[date]
    d['post_count'] += 1
    d['total_length'] += p['content_length']
    d['excl_count'] += p['content'].count('!')
    d['caps_count'] += len(re.findall(r'\b[A-Z]{3,}\b', p['content']))
    d['emotion_sum'] += emotion_score(p['content'])
    d['contents'].append(p['content'][:80])

    if any(w in content_lower for w in ['tariff', 'tariffs', 'duty', 'duties']):
        d['has_tariff'] = True
    if any(w in content_lower for w in ['china', 'chinese', 'beijing', 'xi jinping']):
        d['has_china'] = True
    if any(w in content_lower for w in ['stock market', 'dow', 'nasdaq', 's&p', 'wall street', 'market']):
        d['has_market'] = True
    if any(w in content_lower for w in ['deal', 'trade deal', 'agreement']):
        d['has_deal'] = True
    if any(w in content_lower for w in ['fake news', 'fake media', 'corrupt']):
        d['has_fake'] = True
    if any(w in content_lower for w in ['iran', 'iranian', 'tehran']):
        d['has_iran'] = True
    if any(w in content_lower for w in ['border', 'immigration', 'deport', 'illegal']):
        d['has_border'] = True

    # 盤後/盤前推文 (美東 16:00-09:30 = UTC 21:00-14:30)
    hour_utc = int(p['created_at'][11:13])
    if hour_utc >= 21 or hour_utc < 14:
        d['night_posts'] += 1


# ============================================================
# 分析 1：發文量 vs 隔天股市
# ============================================================
print(f"\n{'='*80}")
print("📊 分析 1: 發文量 vs 隔天 S&P500")
print("=" * 80)

# 按發文量分組
buckets = {'0-5篇': (0, 5), '6-10篇': (6, 10), '11-20篇': (11, 20),
           '21-40篇': (21, 40), '40+篇': (41, 999)}

for bucket_name, (lo, hi) in buckets.items():
    days = [d for d, f in daily_features.items()
            if lo <= f['post_count'] <= hi and d in sp500_by_date]
    if not days:
        continue

    next_returns = [next_day_return(d, sp500_by_date) for d in days]
    next_returns = [r for r in next_returns if r is not None]

    same_returns = [day_return(d, sp500_by_date) for d in days]
    same_returns = [r for r in same_returns if r is not None]

    if next_returns:
        avg_next = sum(next_returns) / len(next_returns)
        avg_same = sum(same_returns) / len(same_returns) if same_returns else 0
        pos = sum(1 for r in next_returns if r > 0)
        print(f"  {bucket_name:10s} | {len(days):3d}天 | 當天平均 {avg_same:+.2f}% | 隔天平均 {avg_next:+.2f}% | 隔天漲 {pos}/{len(next_returns)} ({pos/len(next_returns)*100:.0f}%)")


# ============================================================
# 分析 2：關稅推文 vs 股市
# ============================================================
print(f"\n{'='*80}")
print("📊 分析 2: 「關稅」推文日 vs 非關稅日 S&P500")
print("=" * 80)

tariff_days = [d for d, f in daily_features.items() if f['has_tariff'] and d in sp500_by_date]
non_tariff_days = [d for d, f in daily_features.items() if not f['has_tariff'] and d in sp500_by_date]

for label, days in [('提到關稅', tariff_days), ('沒提關稅', non_tariff_days)]:
    same_ret = [day_return(d, sp500_by_date) for d in days]
    same_ret = [r for r in same_ret if r is not None]
    next_ret = [next_day_return(d, sp500_by_date) for d in days]
    next_ret = [r for r in next_ret if r is not None]

    if same_ret and next_ret:
        avg_same = sum(same_ret) / len(same_ret)
        avg_next = sum(next_ret) / len(next_ret)
        pos_same = sum(1 for r in same_ret if r > 0)
        pos_next = sum(1 for r in next_ret if r > 0)
        print(f"  {label:10s} | {len(days):3d}天 | 當天 {avg_same:+.3f}% (漲{pos_same}/{len(same_ret)}) | 隔天 {avg_next:+.3f}% (漲{pos_next}/{len(next_ret)})")


# ============================================================
# 分析 3：提到中國 vs 股市
# ============================================================
print(f"\n{'='*80}")
print("📊 分析 3: 「中國」推文日 vs 其他日 S&P500")
print("=" * 80)

china_days = [d for d, f in daily_features.items() if f['has_china'] and d in sp500_by_date]
non_china_days = [d for d, f in daily_features.items() if not f['has_china'] and d in sp500_by_date]

for label, days in [('提到中國', china_days), ('沒提中國', non_china_days)]:
    same_ret = [r for r in [day_return(d, sp500_by_date) for d in days] if r is not None]
    next_ret = [r for r in [next_day_return(d, sp500_by_date) for d in days] if r is not None]
    if same_ret and next_ret:
        print(f"  {label:10s} | {len(days):3d}天 | 當天 {sum(same_ret)/len(same_ret):+.3f}% | 隔天 {sum(next_ret)/len(next_ret):+.3f}%")


# ============================================================
# 分析 4：提到股市 vs 實際股市
# ============================================================
print(f"\n{'='*80}")
print("📊 分析 4: 他主動提「股市」的日子 vs 實際表現")
print("=" * 80)

market_days = [d for d, f in daily_features.items() if f['has_market'] and d in sp500_by_date]
non_market_days = [d for d, f in daily_features.items() if not f['has_market'] and d in sp500_by_date]

for label, days in [('提到股市', market_days), ('沒提股市', non_market_days)]:
    same_ret = [r for r in [day_return(d, sp500_by_date) for d in days] if r is not None]
    next_ret = [r for r in [next_day_return(d, sp500_by_date) for d in days] if r is not None]
    if same_ret and next_ret:
        avg_s = sum(same_ret)/len(same_ret)
        avg_n = sum(next_ret)/len(next_ret)
        print(f"  {label:10s} | {len(days):3d}天 | 當天 {avg_s:+.3f}% | 隔天 {avg_n:+.3f}%")

# 他提到股市時通常是漲還是跌的日子？
print(f"\n  他通常在股市漲的日子提股市，還是跌的日子？")
for d in sorted(market_days)[-15:]:
    ret = day_return(d, sp500_by_date)
    if ret is not None:
        arrow = "📈" if ret > 0 else "📉"
        sample = daily_features[d]['contents'][0][:60] if daily_features[d]['contents'] else ''
        print(f"    {d} | S&P {ret:+.2f}% {arrow} | {sample}...")


# ============================================================
# 分析 5：情緒強度 vs 股市
# ============================================================
print(f"\n{'='*80}")
print("📊 分析 5: 情緒強度 vs S&P500")
print("=" * 80)

# 按情緒分組
emotion_buckets = []
for date, feat in daily_features.items():
    if date in sp500_by_date and feat['post_count'] > 0:
        avg_emotion = feat['emotion_sum'] / feat['post_count']
        nr = next_day_return(date, sp500_by_date)
        sr = day_return(date, sp500_by_date)
        if nr is not None and sr is not None:
            emotion_buckets.append({
                'date': date,
                'emotion': avg_emotion,
                'same_day': sr,
                'next_day': nr,
                'post_count': feat['post_count']
            })

# 按情緒強度分 5 組
emotion_buckets.sort(key=lambda x: x['emotion'])
chunk = len(emotion_buckets) // 5

for i in range(5):
    start = i * chunk
    end = start + chunk if i < 4 else len(emotion_buckets)
    group = emotion_buckets[start:end]

    avg_emo = sum(g['emotion'] for g in group) / len(group)
    avg_same = sum(g['same_day'] for g in group) / len(group)
    avg_next = sum(g['next_day'] for g in group) / len(group)
    labels = ['😌很平靜', '🙂偏平靜', '😐中等  ', '😤偏激動', '🔥很激動']

    print(f"  {labels[i]} | 情緒{avg_emo:5.1f} | {len(group):3d}天 | 當天 {avg_same:+.3f}% | 隔天 {avg_next:+.3f}%")


# ============================================================
# 分析 6：盤後/盤前推文 vs 隔日跳空
# ============================================================
print(f"\n{'='*80}")
print("📊 分析 6: 盤後推文 vs 隔日開盤跳空")
print("=" * 80)

for date, feat in sorted(daily_features.items()):
    if feat['night_posts'] > 5 and date in sp500_by_date:
        gap = overnight_gap(date, sp500_by_date)
        if gap is not None:
            arrow = "⬆️" if gap > 0 else "⬇️"
            print(f"  {date} | 盤後{feat['night_posts']:2d}篇 | 隔日跳空 {gap:+.2f}% {arrow}")


# ============================================================
# 分析 7：VIX 恐慌指數 vs 發文行為
# ============================================================
print(f"\n{'='*80}")
print("📊 分析 7: VIX 恐慌指數 vs 發文行為")
print("=" * 80)

# VIX 高的日子（>25）他怎麼發文
high_vix_days = [d for d in vix_by_date if vix_by_date[d]['close'] > 25 and d in daily_features]
low_vix_days = [d for d in vix_by_date if vix_by_date[d]['close'] < 15 and d in daily_features]
normal_vix_days = [d for d in vix_by_date if 15 <= vix_by_date[d]['close'] <= 25 and d in daily_features]

for label, days in [('VIX>25恐慌', high_vix_days), ('VIX 15-25正常', normal_vix_days), ('VIX<15平靜', low_vix_days)]:
    if not days:
        print(f"  {label:15s} | 0 天")
        continue
    avg_posts = sum(daily_features[d]['post_count'] for d in days) / len(days)
    avg_emotion = sum(daily_features[d]['emotion_sum'] / max(daily_features[d]['post_count'], 1) for d in days) / len(days)
    tariff_pct = sum(1 for d in days if daily_features[d]['has_tariff']) / len(days) * 100
    print(f"  {label:15s} | {len(days):3d}天 | 平均{avg_posts:.1f}篇/天 | 情緒{avg_emotion:.1f} | 提關稅{tariff_pct:.0f}%")


# ============================================================
# 分析 8：最大單日漲跌 vs 他的推文
# ============================================================
print(f"\n{'='*80}")
print("📊 分析 8: S&P500 最大漲跌日 — 他那天/前天發了什麼？")
print("=" * 80)

# 計算每天漲跌幅
daily_returns = []
for d in sp500:
    ret = (d['close'] - d['open']) / d['open'] * 100
    daily_returns.append({'date': d['date'], 'return': ret, 'close': d['close']})

daily_returns.sort(key=lambda x: x['return'])

print(f"\n  📉 最大跌幅 Top 10:")
for item in daily_returns[:10]:
    d = item['date']
    prev = get_prev_trading_day(d, sp500_by_date)

    # 前一天的推文
    prev_posts = daily_features.get(prev, {})
    prev_count = prev_posts.get('post_count', 0) if prev_posts else 0
    prev_tariff = prev_posts.get('has_tariff', False) if prev_posts else False
    prev_china = prev_posts.get('has_china', False) if prev_posts else False

    # 當天推文
    today_posts = daily_features.get(d, {})
    today_count = today_posts.get('post_count', 0) if today_posts else 0

    tags = []
    if prev_tariff: tags.append('💣關稅')
    if prev_china: tags.append('🇨🇳中國')

    sample = ''
    if prev_posts and prev_posts.get('contents'):
        sample = prev_posts['contents'][0][:50]

    print(f"    {d} | S&P {item['return']:+.2f}% | 前天{prev_count}篇 當天{today_count}篇 | {' '.join(tags)} | {sample}")

print(f"\n  📈 最大漲幅 Top 10:")
for item in daily_returns[-10:][::-1]:
    d = item['date']
    prev = get_prev_trading_day(d, sp500_by_date)

    prev_posts = daily_features.get(prev, {})
    prev_count = prev_posts.get('post_count', 0) if prev_posts else 0
    prev_tariff = prev_posts.get('has_tariff', False) if prev_posts else False
    prev_deal = prev_posts.get('has_deal', False) if prev_posts else False

    today_posts = daily_features.get(d, {})
    today_count = today_posts.get('post_count', 0) if today_posts else 0

    tags = []
    if prev_tariff: tags.append('💣關稅')
    if prev_deal: tags.append('🤝Deal')

    sample = ''
    if prev_posts and prev_posts.get('contents'):
        sample = prev_posts['contents'][0][:50]

    print(f"    {d} | S&P {item['return']:+.2f}% | 前天{prev_count}篇 當天{today_count}篇 | {' '.join(tags)} | {sample}")


# ============================================================
# 分析 9：關稅推文時間線 vs S&P500
# ============================================================
print(f"\n{'='*80}")
print("📊 分析 9: 關稅推文時間線 vs S&P500 走勢")
print("=" * 80)

tariff_timeline = []
for date in sorted(daily_features.keys()):
    if daily_features[date]['has_tariff'] and date in sp500_by_date:
        sp = sp500_by_date[date]
        ret = day_return(date, sp500_by_date)
        nret = next_day_return(date, sp500_by_date)
        tariff_timeline.append({
            'date': date,
            'posts': daily_features[date]['post_count'],
            'sp500_close': sp['close'],
            'day_return': ret,
            'next_return': nret,
        })

print(f"  {'日期':12s} | {'篇數':>4s} | {'S&P500':>10s} | {'當天':>7s} | {'隔天':>7s}")
print(f"  {'-'*12}-+-{'-'*4}-+-{'-'*10}-+-{'-'*7}-+-{'-'*7}")
for t in tariff_timeline:
    nr = f"{t['next_return']:+.2f}%" if t['next_return'] is not None else "  N/A"
    dr = f"{t['day_return']:+.2f}%" if t['day_return'] is not None else "  N/A"
    print(f"  {t['date']:12s} | {t['posts']:4d} | {t['sp500_close']:>10,.2f} | {dr:>7s} | {nr:>7s}")


# ============================================================
# 存結果摘要
# ============================================================
results = {
    'tariff_vs_market': {
        'tariff_days': len(tariff_days),
        'non_tariff_days': len(non_tariff_days),
    },
    'tariff_timeline': tariff_timeline,
    'biggest_drops': [{'date': d['date'], 'return': round(d['return'], 2)} for d in daily_returns[:10]],
    'biggest_gains': [{'date': d['date'], 'return': round(d['return'], 2)} for d in daily_returns[-10:]],
}
with open(BASE / 'results_06_market.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n💾 詳細結果存入 results_06_market.json")
