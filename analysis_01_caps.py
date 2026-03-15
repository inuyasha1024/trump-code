#!/usr/bin/env python3
"""
川普密碼 分析 #1 — 大寫字密碼
Trump 刻意把某些字全大寫，這些字抽出來排列看看有沒有訊息
"""

import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).parent

with open(BASE / "clean_president.json", 'r') as f:
    posts = json.load(f)

# 只看有文字、非轉發的原創貼文
originals = [p for p in posts if p['has_text'] and not p['is_retweet']]

print("=" * 70)
print("🔠 分析 #1: 大寫字密碼")
print(f"   分析對象: 就任後原創貼文 {len(originals)} 篇")
print("=" * 70)

# --- 1. 抽出所有刻意全大寫的字（排除常見的 I, A, OK 等） ---
common_caps = {'I', 'A', 'OK', 'II', 'III', 'IV', 'V', 'US', 'AM', 'PM',
               'RT', 'TV', 'DC', 'NY', 'TX', 'FL', 'CA', 'OH', 'GA',
               'GOP', 'USA', 'CEO', 'FBI', 'CIA', 'DOJ', 'DHS', 'ICE',
               'NATO', 'UN', 'EU', 'UK', 'GDP', 'GPA', 'PhD', 'MD',
               'LLC', 'INC', 'CO', 'JR', 'SR', 'DR', 'MR', 'MRS', 'MS',
               'THE', 'AND', 'FOR', 'BUT', 'NOT', 'ARE', 'HAS', 'HAD',
               'HIS', 'HER', 'OUR', 'WAS', 'DID', 'LNG', 'TN', 'AI',
               'OF', 'IN', 'TO', 'ON', 'AT', 'BY', 'AN', 'OR', 'IF',
               'IT', 'IS', 'BE', 'DO', 'NO', 'SO', 'UP', 'AS', 'WE',
               'MY', 'HE', 'ME', 'ID', 'VS', 'DJ', 'DJT', 'P'}

all_caps_words = Counter()
caps_by_post = []  # (日期, [大寫字列表])
caps_timeline = []  # 時間序列

for p in originals:
    content = p['content']
    # 找所有全大寫的詞（2字以上，排除常見的）
    words = re.findall(r'\b([A-Z]{2,})\b', content)
    deliberate = [w for w in words if w not in common_caps and len(w) >= 3]

    if deliberate:
        all_caps_words.update(deliberate)
        caps_by_post.append({
            'date': p['created_at'][:10],
            'caps': deliberate,
            'first_letters': ''.join([w[0] for w in deliberate]),
            'content_preview': content[:100]
        })
        caps_timeline.append({
            'date': p['created_at'][:10],
            'count': len(deliberate),
            'words': deliberate
        })

print(f"\n📊 總計找到 {sum(all_caps_words.values())} 個刻意大寫詞")
print(f"   不同詞彙: {len(all_caps_words)} 種")
print(f"   含大寫詞的貼文: {len(caps_by_post)} 篇 / {len(originals)} 篇")

print(f"\n🏆 Top 50 最常出現的大寫詞:")
print("-" * 50)
for word, count in all_caps_words.most_common(50):
    bar = '█' * min(count, 40)
    print(f"  {word:25s} {count:4d} {bar}")

# --- 2. 大寫字首字母串起來看看 ---
print(f"\n🔍 首字母密碼（每篇貼文的大寫詞首字母串起來）:")
print("-" * 50)
# 最近 30 篇有大寫的
for item in caps_by_post[:30]:
    print(f"  {item['date']} | 首字母: {item['first_letters']:20s} | 大寫詞: {', '.join(item['caps'][:5])}")

# --- 3. 大寫詞頻率隨時間變化 ---
print(f"\n📈 每月大寫詞使用密度:")
print("-" * 50)
monthly = {}
for item in caps_timeline:
    month = item['date'][:7]
    if month not in monthly:
        monthly[month] = {'count': 0, 'posts': 0}
    monthly[month]['count'] += item['count']
    monthly[month]['posts'] += 1

# 計算每月原創貼文數
monthly_total = {}
for p in originals:
    m = p['created_at'][:7]
    monthly_total[m] = monthly_total.get(m, 0) + 1

for month in sorted(monthly.keys()):
    total = monthly_total.get(month, 1)
    avg = monthly[month]['count'] / monthly[month]['posts']
    density = monthly[month]['posts'] / total * 100
    bar = '█' * int(avg * 2)
    print(f"  {month} | {monthly[month]['posts']:3d}篇含大寫 / {total:3d}篇總計 ({density:.0f}%) | 平均每篇 {avg:.1f} 個 {bar}")

# --- 4. 大寫詞的情緒色彩分類 ---
print(f"\n🎭 大寫詞情緒分類:")
print("-" * 50)
positive = ['GREAT', 'MASSIVE', 'TREMENDOUS', 'BEAUTIFUL', 'INCREDIBLE',
            'AMAZING', 'WONDERFUL', 'HISTORIC', 'PERFECT', 'FANTASTIC',
            'MAGNIFICENT', 'EXTRAORDINARY', 'SPECTACULAR', 'BRILLIANT',
            'WINNING', 'VICTORY', 'SUCCESS', 'LOVE', 'BEST', 'STRONG',
            'POWERFUL', 'PROUD', 'HAPPY', 'BLESSED', 'GREAT']
negative = ['FAKE', 'CORRUPT', 'RADICAL', 'TERRIBLE', 'HORRIBLE',
            'WORST', 'FAILED', 'CROOKED', 'BROKEN', 'DISASTER',
            'DISGRACE', 'INCOMPETENT', 'PATHETIC', 'WEAK', 'STUPID',
            'RIGGED', 'WITCH', 'HOAX', 'SCAM', 'FRAUD', 'ENEMY',
            'ILLEGAL', 'EVIL', 'DANGEROUS', 'DESTROY']
action = ['MAGA', 'AMERICA', 'FIRST', 'FIGHT', 'VOTE', 'WIN',
          'BUILD', 'SAVE', 'STOP', 'FIRE', 'BAN', 'TARIFF',
          'TARIFFS', 'DEAL', 'TRUMP', 'REVITALIZE']

pos_count = sum(all_caps_words.get(w, 0) for w in positive)
neg_count = sum(all_caps_words.get(w, 0) for w in negative)
act_count = sum(all_caps_words.get(w, 0) for w in action)

print(f"  正面詞 (GREAT, WINNING...):  {pos_count:4d} 次")
print(f"  負面詞 (FAKE, CORRUPT...):   {neg_count:4d} 次")
print(f"  行動詞 (MAGA, TARIFFS...):   {act_count:4d} 次")
print(f"  正負比:                       {pos_count/max(neg_count,1):.1f}:1")

# --- 5. 把所有大寫詞按時間排列，看有沒有隱藏訊息 ---
print(f"\n🕵️ 最近 7 天每天的大寫詞彙（按時間排）:")
print("-" * 50)
recent_days = sorted(set(item['date'] for item in caps_by_post))[-7:]
for day in recent_days:
    day_caps = []
    for item in caps_by_post:
        if item['date'] == day:
            day_caps.extend(item['caps'])
    print(f"  {day}: {' '.join(day_caps[:20])}")

# 存結果
results = {
    'top_caps_words': dict(all_caps_words.most_common(100)),
    'caps_by_post': caps_by_post[:100],
    'monthly_density': {m: {'caps_posts': v['posts'], 'total_posts': monthly_total.get(m, 0),
                            'total_caps': v['count']}
                       for m, v in monthly.items()},
    'sentiment': {'positive': pos_count, 'negative': neg_count, 'action': act_count},
}
with open(BASE / 'results_01_caps.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n💾 詳細結果存入 results_01_caps.json")
