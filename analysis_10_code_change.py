#!/usr/bin/env python3
"""
川普密碼 分析 #10 — 密碼換碼偵測
追蹤他的發文風格隨時間變化：什麼時候換了說法、換了節奏
如果密碼會換，那「偵測到他換密碼」本身就是最強的信號
"""

import json
import re
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent

with open(BASE / "clean_president.json", 'r') as f:
    posts = json.load(f)

originals = sorted(
    [p for p in posts if p['has_text'] and not p['is_retweet']],
    key=lambda p: p['created_at']
)

with open(BASE / "market_SP500.json", 'r') as f:
    sp500 = json.load(f)
sp_by_date = {r['date']: r for r in sp500}

print("=" * 90)
print("🔄 分析 #10: 密碼換碼偵測")
print(f"   追蹤 {len(originals)} 篇貼文的風格演化")
print("=" * 90)


# === 1. 口頭禪演化追蹤 ===
print(f"\n{'='*90}")
print("📊 1. 口頭禪出現/消失時間線")
print("=" * 90)

catchphrases = [
    'thank you for your attention to this matter',
    'complete and total endorsement',
    'will never let you down',
    'make america great again',
    'american energy dominance',
    'president djt',
    'president of the united states of america',
    'fake news',
    'radical left',
    'save america act',
    'never let you down',
    'cut taxes and regulations',
    'always under siege second amendment',
    'made in the u.s.a',
    'sleepy joe',
]

# 每月追蹤
monthly_phrases = defaultdict(lambda: defaultdict(int))
for p in originals:
    month = p['created_at'][:7]
    cl = p['content'].lower()
    for phrase in catchphrases:
        if phrase in cl:
            monthly_phrases[phrase][month] += 1

months = sorted(set(p['created_at'][:7] for p in originals))

print(f"\n  口頭禪月度變化（✦=新出現 ✗=消失 數字=次數）:")
for phrase in catchphrases:
    counts = [monthly_phrases[phrase].get(m, 0) for m in months]
    if sum(counts) < 3:
        continue

    # 找出現和消失時間
    first_seen = next((m for m, c in zip(months, counts) if c > 0), '?')
    last_seen = next((m for m, c in reversed(list(zip(months, counts))) if c > 0), '?')

    # 趨勢
    first_half = sum(counts[:len(counts)//2])
    second_half = sum(counts[len(counts)//2:])
    trend = "📈增加" if second_half > first_half * 1.3 else ("📉減少" if second_half < first_half * 0.7 else "➡️穩定")

    bar = ''.join([f"{c:>3d}" if c > 0 else '  ·' for c in counts])
    print(f"\n  「{phrase[:40]}...」")
    print(f"     首見:{first_seen} 末見:{last_seen} 趨勢:{trend} 總計:{sum(counts)}")
    print(f"     {' '.join(m[-2:] for m in months)}")
    print(f"     {bar}")


# === 2. 新詞彙出現時間點 ===
print(f"\n{'='*90}")
print("📊 2. 新關鍵字首次出現時間（密碼換碼信號）")
print("=" * 90)

# 追蹤重要關鍵字的首次出現
keywords_to_track = [
    'tariff', 'tariffs', 'reciprocal', 'deal', 'trade deal',
    'save america act', 'filibuster', 'golden age', 'liberation day',
    'stock market', 'record high', 'all time high',
    'executive order', 'emergency', 'national security',
    'deportation', 'border', 'cartel',
    'iran', 'bombing', 'nuclear',
    'doge', 'elon', 'efficiency',
    'obamacare', 'insurance', 'healthcare',
    'midterm', 'redistricting', 'vote',
    'oil', 'drill', 'energy dominance', 'lng',
    'chip', 'semiconductor', 'artificial intelligence',
]

keyword_first_appearance = {}
keyword_monthly = defaultdict(lambda: defaultdict(int))

for p in originals:
    cl = p['content'].lower()
    month = p['created_at'][:7]
    for kw in keywords_to_track:
        if kw in cl:
            keyword_monthly[kw][month] += 1
            if kw not in keyword_first_appearance:
                keyword_first_appearance[kw] = p['created_at'][:10]

# 按首次出現時間排序
sorted_kw = sorted(keyword_first_appearance.items(), key=lambda x: x[1])

print(f"\n  {'關鍵字':25s} | {'首次出現':12s} | {'月度分布（→最近）'}")
for kw, first_date in sorted_kw:
    counts = [keyword_monthly[kw].get(m, 0) for m in months]
    # 只顯示有意義的
    if sum(counts) < 5:
        continue
    # 迷你柱狀圖
    max_c = max(counts) if max(counts) > 0 else 1
    mini_bar = ''.join(['█' if c > max_c*0.7 else ('▄' if c > max_c*0.3 else ('▁' if c > 0 else ' ')) for c in counts])
    print(f"  {kw:25s} | {first_date:12s} | {mini_bar} ({sum(counts)})")


# === 3. 發文風格 DNA 每月比對 ===
print(f"\n{'='*90}")
print("📊 3. 發文風格 DNA — 每月變化")
print("=" * 90)

monthly_dna = {}
for month in months:
    month_posts = [p for p in originals if p['created_at'][:7] == month]
    if not month_posts:
        continue

    # 風格指紋
    total_chars = sum(len(p['content']) for p in month_posts)
    total_alpha = sum(sum(1 for c in p['content'] if c.isalpha()) for p in month_posts)
    total_upper = sum(sum(1 for c in p['content'] if c.isupper()) for p in month_posts)
    total_excl = sum(p['content'].count('!') for p in month_posts)
    total_question = sum(p['content'].count('?') for p in month_posts)
    avg_length = total_chars / len(month_posts)

    # 前 20 個最常用的非停用詞
    word_counts = Counter()
    for p in month_posts:
        words = re.findall(r'[a-z]{4,}', p['content'].lower())
        stop = {'that', 'this', 'with', 'from', 'have', 'been', 'will', 'just',
                'they', 'their', 'were', 'what', 'when', 'your', 'very', 'about',
                'would', 'them', 'than', 'more', 'some', 'into', 'also', 'could',
                'only', 'over', 'many', 'such', 'which', 'other', 'after', 'https',
                'truthsocial', 'users', 'realdonaldtrump', 'statuses'}
        words = [w for w in words if w not in stop]
        word_counts.update(words)

    top_words = [w for w, _ in word_counts.most_common(15)]

    monthly_dna[month] = {
        'posts': len(month_posts),
        'avg_length': round(avg_length),
        'caps_ratio': round(total_upper / max(total_alpha, 1) * 100, 1),
        'excl_per_post': round(total_excl / len(month_posts), 2),
        'q_per_post': round(total_question / len(month_posts), 2),
        'top_words': top_words,
    }

print(f"\n  {'月份':8s} | {'篇數':>4s} | {'平均長':>6s} | {'大寫率':>5s} | {'!每篇':>5s} | {'?每篇':>5s} | Top 5 關鍵字")
print(f"  {'-'*8}-+-{'-'*4}-+-{'-'*6}-+-{'-'*5}-+-{'-'*5}-+-{'-'*5}-+-{'-'*40}")
for month in months:
    d = monthly_dna.get(month)
    if not d:
        continue
    top5 = ', '.join(d['top_words'][:5])
    print(f"  {month:8s} | {d['posts']:4d} | {d['avg_length']:6d} | {d['caps_ratio']:4.1f}% | {d['excl_per_post']:5.2f} | {d['q_per_post']:5.2f} | {top5}")

# === 4. 風格突變偵測 ===
print(f"\n{'='*90}")
print("📊 4. 風格突變偵測 — 「密碼換了」的信號")
print("=" * 90)

# 比對相鄰月份的 top words 重疊率
prev_month = None
for month in months:
    d = monthly_dna.get(month)
    if not d or not prev_month:
        prev_month = monthly_dna.get(month)
        continue

    # 詞彙重疊率
    prev_words = set(prev_month['top_words'])
    curr_words = set(d['top_words'])
    overlap = len(prev_words & curr_words) / max(len(prev_words | curr_words), 1) * 100

    # 風格差異
    len_change = d['avg_length'] - prev_month['avg_length']
    caps_change = d['caps_ratio'] - prev_month['caps_ratio']
    excl_change = d['excl_per_post'] - prev_month['excl_per_post']

    # 新出現的詞
    new_words = curr_words - prev_words
    disappeared = prev_words - curr_words

    # 總突變分數
    change_score = abs(len_change)/50 + abs(caps_change)/2 + abs(excl_change)*5 + (100 - overlap)/10

    marker = "🚨" if change_score > 8 else ("⚠️" if change_score > 5 else "  ")

    print(f"  {month} {marker} 突變分數:{change_score:.1f} | 詞重疊:{overlap:.0f}% | 長度{len_change:+.0f} | 大寫{caps_change:+.1f}% | !{excl_change:+.2f}")
    if new_words:
        print(f"         新詞: {', '.join(list(new_words)[:5])}")
    if disappeared:
        print(f"         消失: {', '.join(list(disappeared)[:5])}")

    prev_month = d


# === 5. 結尾簽名切換偵測 ===
print(f"\n{'='*90}")
print("📊 5. 結尾簽名模式切換")
print("=" * 90)

signatures = {
    'DJT': 'President DJT',
    'POTUS': 'PRESIDENT OF THE UNITED STATES',
    'TYFA': 'Thank you for your attention',
    'MAGA': 'Make America Great Again',
    'plain': '(無簽名)',
}

monthly_sigs = defaultdict(lambda: defaultdict(int))
for p in originals:
    month = p['created_at'][:7]
    c = p['content']
    found = False
    for key, pattern in signatures.items():
        if key == 'plain':
            continue
        if pattern.lower() in c.lower():
            monthly_sigs[key][month] += 1
            found = True
    if not found:
        monthly_sigs['plain'][month] += 1

print(f"\n  {'月份':8s}", end='')
for key in ['DJT', 'POTUS', 'TYFA', 'MAGA', 'plain']:
    print(f" | {key:>6s}", end='')
print()

for month in months:
    print(f"  {month:8s}", end='')
    for key in ['DJT', 'POTUS', 'TYFA', 'MAGA', 'plain']:
        count = monthly_sigs[key].get(month, 0)
        print(f" | {count:6d}", end='')
    print()


# === 6. 相鄰季度「密碼差異」 ===
print(f"\n{'='*90}")
print("📊 6. 季度密碼比對 — 規則在哪個季度有效")
print("=" * 90)

# 按季度分組
quarterly = defaultdict(list)
for p in originals:
    month = int(p['created_at'][5:7])
    year = p['created_at'][:4]
    q = f"{year}-Q{(month-1)//3+1}"
    quarterly[q].append(p)

def next_td_fn(date_str):
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    for i in range(1, 6):
        d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
        if d in sp_by_date:
            return d
    return None

for q in sorted(quarterly.keys()):
    q_posts = quarterly[q]
    print(f"\n  📅 {q}: {len(q_posts)} 篇")

    # 這個季度的關稅日 vs 非關稅日表現
    q_daily = defaultdict(lambda: {'tariff': 0, 'deal': 0, 'posts': 0})
    for p in q_posts:
        d = p['created_at'][:10]
        q_daily[d]['posts'] += 1
        cl = p['content'].lower()
        if any(w in cl for w in ['tariff', 'tariffs']): q_daily[d]['tariff'] += 1
        if any(w in cl for w in ['deal', 'agreement']): q_daily[d]['deal'] += 1

    tariff_days_ret = []
    deal_days_ret = []
    for d, features in q_daily.items():
        ntd = next_td_fn(d)
        if not ntd or ntd not in sp_by_date:
            continue
        nsp = sp_by_date[ntd]
        ret = (nsp['close'] - nsp['open']) / nsp['open'] * 100
        if features['tariff'] > 0:
            tariff_days_ret.append(ret)
        if features['deal'] > 0:
            deal_days_ret.append(ret)

    t_avg = sum(tariff_days_ret)/len(tariff_days_ret) if tariff_days_ret else 0
    d_avg = sum(deal_days_ret)/len(deal_days_ret) if deal_days_ret else 0
    t_win = sum(1 for r in tariff_days_ret if r > 0) / max(len(tariff_days_ret), 1) * 100
    d_win = sum(1 for r in deal_days_ret if r > 0) / max(len(deal_days_ret), 1) * 100

    print(f"     TARIFF日({len(tariff_days_ret)}天): 隔天{t_avg:+.3f}%, 勝率{t_win:.0f}%")
    print(f"     DEAL日({len(deal_days_ret)}天):   隔天{d_avg:+.3f}%, 勝率{d_win:.0f}%")

    # 密碼有效性
    if tariff_days_ret and deal_days_ret:
        spread = d_avg - t_avg
        if spread > 0.1:
            print(f"     → ✅ DEAL>TARIFF 密碼有效 (差距{spread:+.3f}%)")
        elif spread < -0.1:
            print(f"     → ⚠️ TARIFF>DEAL 密碼反轉！(差距{spread:+.3f}%)")
        else:
            print(f"     → 🟡 差距不明顯 ({spread:+.3f}%)")


# 存結果
with open(BASE / 'results_10_codechange.json', 'w') as f:
    json.dump({
        'monthly_dna': monthly_dna,
        'keyword_first': keyword_first_appearance,
    }, f, ensure_ascii=False, indent=2)

print(f"\n💾 結果存入 results_10_codechange.json")
