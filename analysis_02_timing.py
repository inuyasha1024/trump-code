#!/usr/bin/env python3
"""
川普密碼 分析 #2 — 發文時間規律
什麼時候發？頻率突變前後發生了什麼？
"""

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent

with open(BASE / "clean_president.json", 'r') as f:
    posts = json.load(f)

originals = [p for p in posts if p['has_text'] and not p['is_retweet']]

print("=" * 70)
print("⏰ 分析 #2: 發文時間規律")
print(f"   分析對象: 就任後原創貼文 {len(originals)} 篇")
print("=" * 70)

# --- 1. 每小時分布（UTC → EST 轉換，Trump 在東岸） ---
hour_dist = Counter()
hour_by_month = defaultdict(Counter)

for p in originals:
    dt = datetime.fromisoformat(p['created_at'].replace('Z', '+00:00'))
    est_hour = (dt.hour - 5) % 24  # UTC → EST (簡易)
    hour_dist[est_hour] += 1
    month = p['created_at'][:7]
    hour_by_month[month][est_hour] += 1

print(f"\n🕐 發文時段分布 (美東時間 EST):")
print("-" * 60)
max_count = max(hour_dist.values())
for h in range(24):
    count = hour_dist.get(h, 0)
    bar = '█' * int(count / max_count * 40) if max_count > 0 else ''
    period = "🌙" if h < 6 else ("☀️" if h < 12 else ("🌅" if h < 18 else "🌙"))
    print(f"  {h:02d}:00 {period} {count:4d} {bar}")

# 深夜推文 (12am-5am EST)
night_posts = [p for p in originals
               if (datetime.fromisoformat(p['created_at'].replace('Z', '+00:00')).hour - 5) % 24 < 5]
print(f"\n🌙 深夜推文 (12am-5am EST): {len(night_posts)} 篇 ({len(night_posts)/len(originals)*100:.1f}%)")
if night_posts:
    print("   最近 5 篇深夜推文:")
    for p in night_posts[:5]:
        dt = datetime.fromisoformat(p['created_at'].replace('Z', '+00:00'))
        est_h = (dt.hour - 5) % 24
        print(f"   {p['created_at'][:16]} (EST {est_h}:{dt.minute:02d}) | {p['content'][:80]}...")

# --- 2. 每日發文量 ---
print(f"\n📅 每日發文量分布:")
print("-" * 60)
daily = Counter()
for p in originals:
    daily[p['created_at'][:10]] += 1

counts = sorted(daily.values())
avg_daily = sum(counts) / len(counts)
print(f"  平均每天: {avg_daily:.1f} 篇")
print(f"  最少: {counts[0]} 篇")
print(f"  最多: {counts[-1]} 篇")
print(f"  中位數: {counts[len(counts)//2]} 篇")

# Top 10 最多發文的日子
print(f"\n🔥 Top 10 發文最多的日子:")
for date, count in daily.most_common(10):
    # 那天的第一篇看看主題
    day_posts = [p for p in originals if p['created_at'][:10] == date]
    topic = day_posts[0]['content'][:60] if day_posts else ''
    bar = '█' * count
    print(f"  {date} | {count:3d}篇 | {bar} | {topic}...")

# 沉默日（0 篇或極少篇）
print(f"\n🤫 沉默日（≤2 篇）:")
all_dates = sorted(daily.keys())
quiet_days = [(d, daily[d]) for d in all_dates if daily[d] <= 2]
print(f"  總計 {len(quiet_days)} 天")
for d, c in quiet_days[-10:]:
    print(f"  {d} | {c} 篇")

# --- 3. 星期分布 ---
print(f"\n📊 星期分布:")
print("-" * 60)
weekday_dist = Counter()
weekday_names = ['一', '二', '三', '四', '五', '六', '日']
for p in originals:
    dt = datetime.fromisoformat(p['created_at'].replace('Z', '+00:00'))
    weekday_dist[dt.weekday()] += 1

for wd in range(7):
    count = weekday_dist.get(wd, 0)
    bar = '█' * int(count / max(weekday_dist.values()) * 30)
    print(f"  週{weekday_names[wd]} | {count:4d} {bar}")

# --- 4. 發文間隔分析 ---
print(f"\n⏱️ 發文間隔分析:")
print("-" * 60)
intervals = []
sorted_posts = sorted(originals, key=lambda p: p['created_at'])
for i in range(1, len(sorted_posts)):
    dt1 = datetime.fromisoformat(sorted_posts[i-1]['created_at'].replace('Z', '+00:00'))
    dt2 = datetime.fromisoformat(sorted_posts[i]['created_at'].replace('Z', '+00:00'))
    diff_minutes = (dt2 - dt1).total_seconds() / 60
    intervals.append({
        'minutes': diff_minutes,
        'date': sorted_posts[i]['created_at'][:16],
        'content': sorted_posts[i]['content'][:60]
    })

intervals_min = sorted([i['minutes'] for i in intervals])
print(f"  最短間隔: {intervals_min[0]:.0f} 分鐘")
print(f"  最長間隔: {intervals_min[-1]:.0f} 分鐘 ({intervals_min[-1]/60:.1f} 小時)")
print(f"  平均間隔: {sum(intervals_min)/len(intervals_min):.0f} 分鐘")
print(f"  中位數間隔: {intervals_min[len(intervals_min)//2]:.0f} 分鐘")

# 連續轟炸（5分鐘內連發多篇）
bursts = [i for i in intervals if i['minutes'] < 5]
print(f"\n🔥 連續轟炸（5分鐘內連發）: {len(bursts)} 次")

# 長沉默後的第一篇（沉默 > 12小時）
long_silence = [i for i in intervals if i['minutes'] > 720]
print(f"\n😶 長時間沉默（>12小時）後的第一篇: {len(long_silence)} 次")
for item in long_silence[:10]:
    hours = item['minutes'] / 60
    print(f"  沉默 {hours:.1f}h → {item['date']} | {item['content']}...")

# --- 5. 發文量趨勢（每週） ---
print(f"\n📈 每週發文量趨勢:")
print("-" * 60)
weekly = defaultdict(int)
for p in originals:
    dt = datetime.fromisoformat(p['created_at'].replace('Z', '+00:00'))
    # ISO week
    year, week, _ = dt.isocalendar()
    key = f"{year}-W{week:02d}"
    weekly[key] += 1

weeks = sorted(weekly.keys())
for w in weeks[-16:]:  # 最近 16 週
    count = weekly[w]
    bar = '█' * (count // 2)
    print(f"  {w} | {count:3d} {bar}")

# 存結果
results = {
    'hourly_distribution_est': dict(hour_dist),
    'daily_counts': dict(daily.most_common()),
    'weekday_distribution': {weekday_names[k]: v for k, v in weekday_dist.items()},
    'night_posts_count': len(night_posts),
    'burst_count': len(bursts),
    'long_silence_count': len(long_silence),
    'avg_daily': round(avg_daily, 1),
    'avg_interval_minutes': round(sum(intervals_min)/len(intervals_min), 0),
}
with open(BASE / 'results_02_timing.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n💾 詳細結果存入 results_02_timing.json")
