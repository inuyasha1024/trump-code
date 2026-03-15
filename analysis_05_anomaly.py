#!/usr/bin/env python3
"""
川普密碼 分析 #5 — 異常偵測
找出和平常不一樣的發文行為：突然改變語氣、用詞、節奏
"""

import json
import re
import math
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).parent

with open(BASE / "clean_president.json", 'r') as f:
    posts = json.load(f)

originals = sorted(
    [p for p in posts if p['has_text'] and not p['is_retweet']],
    key=lambda p: p['created_at']
)

print("=" * 70)
print("🚨 分析 #5: 異常偵測")
print(f"   分析對象: 就任後原創貼文 {len(originals)} 篇（按時間排序）")
print("=" * 70)

# --- 1. 情緒強度指數（每篇計算） ---
print(f"\n🌡️ 情緒強度分析:")
print("-" * 60)

def emotion_score(content):
    """計算單篇貼文的情緒強度 (0-100)"""
    score = 0
    text = content

    # 大寫字比例
    upper = sum(1 for c in text if c.isupper())
    total = sum(1 for c in text if c.isalpha())
    caps_ratio = upper / max(total, 1)
    score += caps_ratio * 30  # 大寫佔比最高 30 分

    # 驚嘆號密度
    excl = text.count('!')
    excl_density = excl / max(len(text), 1) * 100
    score += min(excl_density * 10, 25)  # 最高 25 分

    # 強烈詞彙
    strong_words = ['never', 'always', 'worst', 'best', 'greatest', 'terrible',
                    'incredible', 'tremendous', 'massive', 'total', 'complete',
                    'absolute', 'disaster', 'perfect', 'beautiful', 'horrible',
                    'amazing', 'fantastic', 'disgrace', 'pathetic', 'historic',
                    'unprecedented', 'radical', 'corrupt', 'crooked', 'fake']
    word_count = len(re.findall(r'\b\w+\b', text.lower()))
    strong_count = sum(1 for w in strong_words if w in text.lower())
    score += min(strong_count / max(word_count, 1) * 500, 25)  # 最高 25 分

    # 全大寫連續詞
    caps_words = len(re.findall(r'\b[A-Z]{3,}\b', text))
    score += min(caps_words * 2, 20)  # 最高 20 分

    return min(round(score, 1), 100)

emotions = []
for p in originals:
    score = emotion_score(p['content'])
    emotions.append({
        'date': p['created_at'][:10],
        'time': p['created_at'][11:16],
        'score': score,
        'length': p['content_length'],
        'content': p['content'][:100],
        'url': p['url']
    })

avg_emotion = sum(e['score'] for e in emotions) / len(emotions)
print(f"  平均情緒強度: {avg_emotion:.1f}/100")

# 找情緒極端值
sorted_emotions = sorted(emotions, key=lambda e: e['score'], reverse=True)
print(f"\n  🔥 情緒最激烈 Top 10:")
for e in sorted_emotions[:10]:
    print(f"    {e['date']} {e['time']} | 強度:{e['score']:5.1f} | {e['content'][:70]}...")

print(f"\n  😌 情緒最平靜 Top 10:")
for e in sorted_emotions[-10:]:
    print(f"    {e['date']} {e['time']} | 強度:{e['score']:5.1f} | {e['content'][:70]}...")

# 每日平均情緒
daily_emotion = defaultdict(list)
for e in emotions:
    daily_emotion[e['date']].append(e['score'])

daily_avg = {d: sum(scores)/len(scores) for d, scores in daily_emotion.items()}
sorted_days = sorted(daily_avg.items(), key=lambda x: x[1], reverse=True)

print(f"\n  📊 情緒最激動的 10 天:")
for day, avg in sorted_days[:10]:
    bar = '█' * int(avg)
    print(f"    {day} | 平均 {avg:.1f} | {bar}")

print(f"\n  😐 情緒最平靜的 10 天:")
for day, avg in sorted_days[-10:]:
    bar = '░' * int(avg)
    print(f"    {day} | 平均 {avg:.1f} | {bar}")

# --- 2. 用詞風格突變偵測 ---
print(f"\n📊 用詞風格週變化:")
print("-" * 60)

# 以週為單位計算平均字數、大寫率、驚嘆號率
weekly_stats = defaultdict(lambda: {'lengths': [], 'caps_ratios': [], 'excl_counts': []})

for p in originals:
    from datetime import datetime
    dt = datetime.fromisoformat(p['created_at'].replace('Z', '+00:00'))
    year, week, _ = dt.isocalendar()
    key = f"{year}-W{week:02d}"

    text = p['content']
    upper = sum(1 for c in text if c.isupper())
    total_alpha = sum(1 for c in text if c.isalpha())

    weekly_stats[key]['lengths'].append(len(text))
    weekly_stats[key]['caps_ratios'].append(upper / max(total_alpha, 1))
    weekly_stats[key]['excl_counts'].append(text.count('!'))

weeks = sorted(weekly_stats.keys())
prev_avg_len = None
print(f"  {'週':10s} | {'篇數':>4s} | {'平均字數':>8s} | {'Δ字數':>7s} | {'大寫率':>6s} | {'!平均':>5s}")
for w in weeks[-20:]:  # 最近 20 週
    s = weekly_stats[w]
    avg_len = sum(s['lengths']) / len(s['lengths'])
    avg_caps = sum(s['caps_ratios']) / len(s['caps_ratios']) * 100
    avg_excl = sum(s['excl_counts']) / len(s['excl_counts'])
    count = len(s['lengths'])

    delta = f"{avg_len - prev_avg_len:+.0f}" if prev_avg_len else "—"
    marker = " ⚡" if prev_avg_len and abs(avg_len - prev_avg_len) > 50 else ""

    print(f"  {w:10s} | {count:4d} | {avg_len:8.0f} | {delta:>7s} | {avg_caps:5.1f}% | {avg_excl:5.1f}{marker}")
    prev_avg_len = avg_len

# --- 3. 「首次使用」的新詞彙 ---
print(f"\n🆕 新詞彙偵測（首次出現的特殊詞）:")
print("-" * 60)

# 把時間切成前半和後半
mid = len(originals) // 2
first_half_words = Counter()
second_half_words = Counter()

for p in originals[:mid]:
    words = set(re.findall(r'\b[A-Za-z]{4,}\b', p['content'].lower()))
    first_half_words.update(words)

for p in originals[mid:]:
    words = set(re.findall(r'\b[A-Za-z]{4,}\b', p['content'].lower()))
    second_half_words.update(words)

# 後半才出現的新詞（出現至少 5 次才算有意義）
new_words = {w: c for w, c in second_half_words.items()
             if c >= 5 and first_half_words.get(w, 0) == 0}

new_words_sorted = sorted(new_words.items(), key=lambda x: -x[1])
mid_date = originals[mid]['created_at'][:10]
print(f"  時間切點: {mid_date}")
print(f"  後半期才出現的新詞（≥5次）: {len(new_words)} 個")
for w, c in new_words_sorted[:20]:
    print(f"    {w:20s} | {c} 次")

# --- 4. 貼文長度異常 ---
print(f"\n📏 貼文長度異常:")
print("-" * 60)

lengths = [p['content_length'] for p in originals]
mean_len = sum(lengths) / len(lengths)
std_len = math.sqrt(sum((l - mean_len) ** 2 for l in lengths) / len(lengths))

print(f"  平均長度: {mean_len:.0f} 字")
print(f"  標準差: {std_len:.0f}")

# 超過 2 個標準差的
outliers_long = [(p, p['content_length']) for p in originals
                 if p['content_length'] > mean_len + 2 * std_len]
outliers_short = [(p, p['content_length']) for p in originals
                  if 0 < p['content_length'] < mean_len - 1.5 * std_len]

print(f"  異常長 (>2σ): {len(outliers_long)} 篇")
for p, l in sorted(outliers_long, key=lambda x: -x[1])[:5]:
    print(f"    {p['created_at'][:10]} | {l}字 | {p['content'][:60]}...")

print(f"  異常短 (<-1.5σ): {len(outliers_short)} 篇")
for p, l in sorted(outliers_short, key=lambda x: x[1])[:5]:
    print(f"    {p['created_at'][:10]} | {l}字 | {p['content'][:60]}...")

# 存結果
results = {
    'avg_emotion_score': round(avg_emotion, 1),
    'top_emotional_days': dict(sorted_days[:20]),
    'calmest_days': dict(sorted_days[-20:]),
    'new_words_after': mid_date,
    'new_words': dict(new_words_sorted[:50]),
    'length_stats': {
        'mean': round(mean_len),
        'std': round(std_len),
        'outliers_long': len(outliers_long),
        'outliers_short': len(outliers_short),
    }
}
with open(BASE / 'results_05_anomaly.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n💾 詳細結果存入 results_05_anomaly.json")
