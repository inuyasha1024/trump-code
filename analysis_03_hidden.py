#!/usr/bin/env python3
"""
川普密碼 分析 #3 — 隱藏訊息搜索
藏頭詩、首字母、重複模式、數字密碼
"""

import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).parent

with open(BASE / "clean_president.json", 'r') as f:
    posts = json.load(f)

originals = [p for p in posts if p['has_text'] and not p['is_retweet'] and p['content_length'] > 50]

print("=" * 70)
print("🕵️ 分析 #3: 隱藏訊息搜索")
print(f"   分析對象: 就任後原創貼文（>50字）{len(originals)} 篇")
print("=" * 70)

# --- 1. 藏頭詩分析：每篇貼文每句話第一個字母 ---
print(f"\n📜 藏頭詩分析（每句第一個字母）:")
print("-" * 60)

acrostics = []
for p in originals:
    content = p['content']
    # 用句號、驚嘆號、問號分句
    sentences = re.split(r'[.!?]+', content)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 3]

    if len(sentences) >= 3:  # 至少 3 句才有意義
        first_letters = ''.join([s[0].upper() for s in sentences if s])
        acrostics.append({
            'date': p['created_at'][:10],
            'letters': first_letters,
            'sentence_count': len(sentences),
            'content_preview': content[:100],
            'url': p['url']
        })

print(f"  分析了 {len(acrostics)} 篇（≥3 句）")

# 找看起來像英文單字的
import string
# 常見英文字典（簡易）
interesting_words = {'MAGA', 'TRUMP', 'WIN', 'USA', 'WAR', 'DEAL', 'HELP', 'FIRE',
                     'VOTE', 'LOVE', 'HATE', 'KILL', 'STOP', 'SAVE', 'PLAN', 'CODE',
                     'FAKE', 'TRUE', 'GOLD', 'SELL', 'BUY', 'RUN', 'FLY', 'SPY',
                     'SOS', 'FBI', 'CIA', 'GOD', 'OIL', 'GAS', 'TAX', 'PAY',
                     'END', 'NEW', 'OLD', 'BIG', 'TOP', 'RED', 'BLUE', 'FREE',
                     'RICH', 'POOR', 'FAST', 'SLOW', 'GOOD', 'EVIL', 'FEAR',
                     'HOPE', 'DOOM', 'BOOM', 'BUST', 'CASH', 'DEBT', 'BOND',
                     'WALL', 'GATE', 'DARK', 'DEEP', 'HIGH', 'LOW', 'FALL',
                     'RISE', 'LOOK', 'HIDE', 'FIND', 'LOST', 'SAFE', 'RISK',
                     'NUKE', 'BOMB', 'IRAN', 'NATO', 'ASIA', 'EURO'}

found_words = []
for a in acrostics:
    letters = a['letters']
    # 滑動窗口找子字串
    for wlen in range(3, min(len(letters) + 1, 8)):
        for i in range(len(letters) - wlen + 1):
            sub = letters[i:i + wlen]
            if sub in interesting_words:
                found_words.append({
                    'word': sub,
                    'full_letters': letters,
                    'date': a['date'],
                    'url': a['url'],
                    'preview': a['content_preview']
                })

print(f"\n🎯 藏頭詩中找到已知英文字:")
if found_words:
    for fw in found_words[:20]:
        print(f"  {fw['date']} | 藏頭: {fw['full_letters']} | 找到: [{fw['word']}] | {fw['preview'][:60]}...")
else:
    print("  （未找到明顯英文單字）")

# 顯示所有藏頭（最近 30 篇）
print(f"\n📋 最近 30 篇藏頭字母:")
for a in acrostics[:30]:
    print(f"  {a['date']} | {a['letters']:20s} ({a['sentence_count']}句)")

# --- 2. 數字密碼 ---
print(f"\n🔢 數字密碼分析:")
print("-" * 60)

all_numbers = Counter()
number_posts = []

for p in originals:
    numbers = re.findall(r'\b(\d[\d,.]*)\b', p['content'])
    cleaned_nums = []
    for n in numbers:
        clean = n.replace(',', '').replace('.', '')
        if clean.isdigit() and len(clean) >= 1:
            cleaned_nums.append(int(clean))
            all_numbers[n] += 1  # 保留原始格式

    if cleaned_nums:
        number_posts.append({
            'date': p['created_at'][:10],
            'numbers': cleaned_nums,
            'raw': numbers,
            'content': p['content'][:100]
        })

print(f"  含數字的貼文: {len(number_posts)} 篇")
print(f"  不同數字: {len(all_numbers)} 種")

print(f"\n🏆 Top 30 最常出現的數字:")
for num, count in all_numbers.most_common(30):
    print(f"  {num:>15s} → {count:3d} 次")

# 特殊數字分析
print(f"\n🔮 特殊數字模式:")
all_ints = []
for np_item in number_posts:
    all_ints.extend(np_item['numbers'])

# 重複出現的具體數字
int_counts = Counter(all_ints)
repeated = [(n, c) for n, c in int_counts.most_common(30) if c >= 3 and n > 10]
print(f"  重複 3 次以上的數字（>10）:")
for n, c in repeated[:15]:
    print(f"    {n:>12,} → {c} 次")

# --- 3. 重複短語（n-gram）分析 ---
print(f"\n🔄 重複短語分析:")
print("-" * 60)

# 3-gram
trigrams = Counter()
bigrams = Counter()

for p in originals:
    words = re.findall(r'[A-Za-z\']+', p['content'])
    words_lower = [w.lower() for w in words]

    for i in range(len(words_lower) - 2):
        tri = ' '.join(words_lower[i:i+3])
        trigrams[tri] += 1

    for i in range(len(words_lower) - 1):
        bi = ' '.join(words_lower[i:i+2])
        bigrams[bi] += 1

# 過濾掉太普通的（the of a 等）
stop_starts = {'the', 'of', 'a', 'an', 'in', 'to', 'and', 'is', 'it', 'for',
               'on', 'at', 'by', 'with', 'from', 'as', 'that', 'this', 'was',
               'are', 'be', 'has', 'have', 'had', 'will', 'would', 'which'}

interesting_tri = [(t, c) for t, c in trigrams.most_common(500)
                   if c >= 5 and t.split()[0] not in stop_starts]

print(f"  Top 25 川普口頭禪（3 詞組合，出現 ≥5 次）:")
for phrase, count in interesting_tri[:25]:
    bar = '█' * min(count, 30)
    print(f"  {phrase:35s} {count:4d} {bar}")

# --- 4. 標點符號密碼 ---
print(f"\n❗ 標點符號分析:")
print("-" * 60)

excl_counts = []  # 每篇的驚嘆號數
for p in originals:
    excl = p['content'].count('!')
    excl_counts.append({
        'date': p['created_at'][:10],
        'exclamation': excl,
        'question': p['content'].count('?'),
        'ellipsis': p['content'].count('...'),
        'dash': p['content'].count('—') + p['content'].count('-'),
        'length': p['content_length']
    })

total_excl = sum(e['exclamation'] for e in excl_counts)
total_quest = sum(e['question'] for e in excl_counts)
total_ellip = sum(e['ellipsis'] for e in excl_counts)

print(f"  驚嘆號 ! 總計: {total_excl} 個 (平均每篇 {total_excl/len(originals):.1f})")
print(f"  問號 ? 總計: {total_quest} 個")
print(f"  省略號 ... 總計: {total_ellip} 個")

# 驚嘆號最多的貼文
top_excl = sorted(excl_counts, key=lambda x: x['exclamation'], reverse=True)
print(f"\n  驚嘆號最多的 5 篇:")
for e in top_excl[:5]:
    # 找到對應的貼文
    post = next(p for p in originals if p['created_at'][:10] == e['date'])
    print(f"    {e['date']} | !×{e['exclamation']} | {post['content'][:80]}...")

# --- 5. 結尾簽名模式 ---
print(f"\n✍️ 結尾簽名模式:")
print("-" * 60)

endings = Counter()
for p in originals:
    content = p['content'].strip()
    # 取最後一句
    last_sentence = re.split(r'[.!?]', content)
    last = last_sentence[-1].strip() if last_sentence else ''
    if len(last) > 10 and len(last) < 80:
        endings[last] += 1

print("  重複出現的結尾:")
for ending, count in endings.most_common(15):
    if count >= 3:
        print(f"    [{count:3d}次] \"{ending}\"")

# 存結果
results = {
    'acrostics_sample': acrostics[:50],
    'acrostic_words_found': found_words,
    'top_numbers': dict(all_numbers.most_common(50)),
    'top_trigrams': dict(interesting_tri[:50]),
    'punctuation': {
        'total_exclamation': total_excl,
        'total_question': total_quest,
        'avg_exclamation': round(total_excl/len(originals), 1),
    },
    'top_endings': dict(endings.most_common(20)),
}
with open(BASE / 'results_03_hidden.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n💾 詳細結果存入 results_03_hidden.json")
