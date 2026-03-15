#!/usr/bin/env python3
"""
川普密碼 分析 #4 — 人物與國家點名分析
他提到誰、什麼國家、頻率變化 = 風向球
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).parent

with open(BASE / "clean_president.json", 'r') as f:
    posts = json.load(f)

originals = [p for p in posts if p['has_text'] and not p['is_retweet']]

print("=" * 70)
print("🌍 分析 #4: 人物與國家點名分析")
print(f"   分析對象: 就任後原創貼文 {len(originals)} 篇")
print("=" * 70)

# --- 1. 國家/地區提及頻率 ---
countries = {
    'China': ['China', 'Chinese', 'Beijing', 'Xi', 'Jinping', 'CCP'],
    'Japan': ['Japan', 'Japanese', 'Tokyo', 'Kishida', 'Ishiba'],
    'Russia': ['Russia', 'Russian', 'Putin', 'Moscow', 'Kremlin'],
    'Ukraine': ['Ukraine', 'Ukrainian', 'Zelensky', 'Zelenskyy', 'Kiev', 'Kyiv'],
    'Iran': ['Iran', 'Iranian', 'Tehran', 'Khamenei'],
    'North Korea': ['North Korea', 'DPRK', 'Kim Jong', 'Pyongyang'],
    'Israel': ['Israel', 'Israeli', 'Netanyahu', 'Bibi', 'Gaza', 'Hamas', 'Hezbollah'],
    'Mexico': ['Mexico', 'Mexican', 'Cartels', 'Border'],
    'Canada': ['Canada', 'Canadian', 'Trudeau', 'Ottawa'],
    'Europe/EU': ['Europe', 'European', 'EU ', 'NATO', 'Brussels'],
    'UK': ['Britain', 'British', 'England', 'London', 'Starmer'],
    'India': ['India', 'Indian', 'Modi', 'Delhi'],
    'Taiwan': ['Taiwan', 'Taiwanese', 'Taipei'],
    'Saudi Arabia': ['Saudi', 'Arabia', 'Riyadh', 'MBS'],
    'South Korea': ['South Korea', 'Korean', 'Seoul'],
}

country_counts = {}
country_monthly = defaultdict(lambda: defaultdict(int))

for country, keywords in countries.items():
    count = 0
    for p in originals:
        content = p['content']
        if any(kw.lower() in content.lower() for kw in keywords):
            count += 1
            month = p['created_at'][:7]
            country_monthly[country][month] += 1
    country_counts[country] = count

print(f"\n🌐 國家/地區提及次數:")
print("-" * 60)
for country, count in sorted(country_counts.items(), key=lambda x: -x[1]):
    bar = '█' * (count // 3)
    print(f"  {country:15s} | {count:4d}篇 {bar}")

# 國家提及的月度趨勢（Top 5 國家）
top_countries = sorted(country_counts.items(), key=lambda x: -x[1])[:6]
print(f"\n📈 Top 6 國家月度趨勢:")
print("-" * 60)
all_months = sorted(set(p['created_at'][:7] for p in originals))
header = f"  {'月份':10s}"
for c, _ in top_countries:
    header += f" {c[:6]:>7s}"
print(header)

for month in all_months:
    row = f"  {month:10s}"
    for c, _ in top_countries:
        val = country_monthly[c].get(month, 0)
        row += f" {val:7d}"
    print(row)

# --- 2. 人物點名 ---
people = {
    'Biden': ['Biden', 'Joe Biden', 'Sleepy Joe'],
    'Obama': ['Obama', 'Barack'],
    'Pelosi': ['Pelosi', 'Nancy'],
    'Schumer': ['Schumer', 'Chuck Schumer'],
    'DeSantis': ['DeSantis', 'Ron DeSantis', 'DeSanctimonious'],
    'Elon Musk': ['Elon', 'Musk', 'Tesla', 'DOGE'],
    'Vivek': ['Vivek', 'Ramaswamy'],
    'Kamala': ['Kamala', 'Harris'],
    'Pence': ['Pence', 'Mike Pence'],
    'McConnell': ['McConnell', 'Mitch'],
    'RFK Jr': ['Kennedy', 'RFK'],
    'Vance': ['Vance', 'J.D.', 'JD Vance'],
    'Jack Smith': ['Jack Smith', 'Special Counsel'],
    'Putin': ['Putin', 'Vladimir'],
    'Xi Jinping': ['Xi Jinping', 'Xi '],
    'Zelensky': ['Zelensky', 'Zelenskyy'],
    'Kim Jong Un': ['Kim Jong'],
    'Netanyahu': ['Netanyahu', 'Bibi'],
}

people_counts = {}
people_monthly = defaultdict(lambda: defaultdict(int))

for person, keywords in people.items():
    count = 0
    for p in originals:
        content = p['content']
        if any(kw.lower() in content.lower() for kw in keywords):
            count += 1
            month = p['created_at'][:7]
            people_monthly[person][month] += 1
    people_counts[person] = count

print(f"\n👤 人物提及次數:")
print("-" * 60)
for person, count in sorted(people_counts.items(), key=lambda x: -x[1]):
    if count > 0:
        bar = '█' * min(count // 2, 40)
        print(f"  {person:15s} | {count:4d}篇 {bar}")

# --- 3. 暱稱/外號追蹤 ---
print(f"\n🏷️ 川普專用外號追蹤:")
print("-" * 60)

nicknames = [
    'Sleepy Joe', 'Crooked', 'Crazy', 'Radical Left', 'Fake News',
    'RINO', 'Deep State', 'Witch Hunt', 'Enemy of the People',
    'Do Nothing', 'Low Energy', 'Lyin\'', 'Shifty', 'Nervous',
    'Deranged', 'Failing', 'Phony', 'Corrupt', 'Lunatic',
    'Incompetent', 'Stupid', 'DeSanctimonious', 'Comrade',
    'Laughing', 'Loco', 'Wacko', 'Liddle', 'Mini', 'Sloppy',
]

nickname_counts = {}
for nick in nicknames:
    count = sum(1 for p in originals if nick.lower() in p['content'].lower())
    if count > 0:
        nickname_counts[nick] = count

for nick, count in sorted(nickname_counts.items(), key=lambda x: -x[1]):
    bar = '█' * min(count, 30)
    print(f"  {nick:25s} | {count:4d} {bar}")

# --- 4. 主題關鍵字 ---
print(f"\n📋 政策關鍵字頻率:")
print("-" * 60)

topics = {
    'Tariff/關稅': ['tariff', 'tariffs', 'duty', 'duties'],
    'Border/邊境': ['border', 'wall', 'immigration', 'migrant', 'deportation', 'deport'],
    'Economy/經濟': ['economy', 'economic', 'inflation', 'gdp', 'recession', 'growth'],
    'Trade/貿易': ['trade', 'trade deal', 'trade deficit', 'export', 'import'],
    'Military/軍事': ['military', 'army', 'navy', 'troops', 'defense', 'defence'],
    'Energy/能源': ['energy', 'oil', 'gas', 'drill', 'pipeline', 'opec'],
    'Tech/科技': ['technology', 'tech', 'artificial intelligence', ' ai ', 'chips', 'semiconductor'],
    'Crime/犯罪': ['crime', 'criminal', 'gang', 'ms-13', 'fentanyl', 'drugs'],
    'Election/選舉': ['election', 'vote', 'voter', 'ballot', 'poll'],
    'Tax/稅': ['tax', 'taxes', 'irs', 'tax cut'],
    'Jobs/就業': ['jobs', 'employment', 'unemployment', 'workers', 'hiring'],
    'Stock Market/股市': ['stock market', 'dow', 'nasdaq', 'wall street', 's&p'],
}

topic_counts = {}
topic_monthly = defaultdict(lambda: defaultdict(int))

for topic, keywords in topics.items():
    count = 0
    for p in originals:
        cl = p['content'].lower()
        if any(kw in cl for kw in keywords):
            count += 1
            month = p['created_at'][:7]
            topic_monthly[topic][month] += 1
    topic_counts[topic] = count

for topic, count in sorted(topic_counts.items(), key=lambda x: -x[1]):
    bar = '█' * (count // 3)
    print(f"  {topic:20s} | {count:4d}篇 {bar}")

# 主題月度趨勢
print(f"\n📈 主題月度趨勢 (Top 6):")
print("-" * 60)
top_topics = sorted(topic_counts.items(), key=lambda x: -x[1])[:6]
header = f"  {'月份':10s}"
for t, _ in top_topics:
    header += f" {t[:8]:>9s}"
print(header)

for month in all_months:
    row = f"  {month:10s}"
    for t, _ in top_topics:
        val = topic_monthly[t].get(month, 0)
        row += f" {val:9d}"
    print(row)

# 存結果
results = {
    'country_counts': country_counts,
    'country_monthly': {k: dict(v) for k, v in country_monthly.items()},
    'people_counts': people_counts,
    'people_monthly': {k: dict(v) for k, v in people_monthly.items()},
    'nickname_counts': nickname_counts,
    'topic_counts': topic_counts,
    'topic_monthly': {k: dict(v) for k, v in topic_monthly.items()},
}
with open(BASE / 'results_04_entities.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n💾 詳細結果存入 results_04_entities.json")
