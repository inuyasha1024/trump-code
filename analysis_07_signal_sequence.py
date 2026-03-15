#!/usr/bin/env python3
"""
川普密碼 分析 #7 — 信號序列分析
核心假設：
  信號1（預告）→ 操作窗口 → 信號2（確認/行動）→ 市場反應

要找的：
  1. 他發文後幾小時內股市怎麼動
  2. 關鍵字從「攻擊」轉到「Deal」的轉折點
  3. 盤前/盤後推文 vs 開盤跳空（精確到小時）
  4. 連發 vs 沉默 的節奏和市場的關係
"""

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent

with open(BASE / "clean_president.json", 'r') as f:
    posts = json.load(f)

with open(BASE / "market_SP500.json", 'r') as f:
    sp500 = json.load(f)

sp_by_date = {r['date']: r for r in sp500}

originals = sorted(
    [p for p in posts if p['has_text'] and not p['is_retweet']],
    key=lambda p: p['created_at']
)

print("=" * 80)
print("🎯 分析 #7: 信號序列分析 — 「預告 → 操作窗口 → 確認」")
print(f"   貼文: {len(originals)} 篇 | 交易日: {len(sp500)} 天")
print("=" * 80)


# === 工具 ===

def classify_post(content):
    """分類一篇貼文的信號類型"""
    cl = content.lower()
    signals = set()

    # 攻擊/威脅信號
    if any(w in cl for w in ['tariff', 'tariffs', 'duty', 'duties', 'reciprocal']):
        signals.add('TARIFF')
    if any(w in cl for w in ['china', 'chinese', 'beijing', 'xi jinping']):
        signals.add('CHINA')
    if any(w in cl for w in ['ban', 'block', 'restrict', 'sanction', 'punish']):
        signals.add('THREAT')
    if any(w in cl for w in ['fake news', 'corrupt', 'fraud', 'witch hunt', 'disgrace']):
        signals.add('ATTACK')

    # 正面/緩和信號
    if any(w in cl for w in ['deal', 'agreement', 'negotiate', 'talks', 'signed']):
        signals.add('DEAL')
    if any(w in cl for w in ['great', 'tremendous', 'historic', 'incredible', 'best']):
        signals.add('POSITIVE')
    if any(w in cl for w in ['stock market', 'all time high', 'record', 'dow', 'nasdaq']):
        signals.add('MARKET_BRAG')
    if any(w in cl for w in ['pause', 'delay', 'exempt', 'exception', 'reduce']):
        signals.add('RELIEF')

    # 行動/命令信號
    if any(w in cl for w in ['immediately', 'effective', 'hereby', 'i have directed',
                              'executive order', 'i am signing', 'just signed']):
        signals.add('ACTION')
    if any(w in cl for w in ['announcement', 'announce', 'breaking', 'just now']):
        signals.add('ANNOUNCE')

    return signals

def est_hour(utc_str):
    """UTC 時間字串 → EST 小時"""
    dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
    return (dt.hour - 5) % 24, dt.minute

def market_session(utc_str):
    """判斷發文時間屬於哪個交易時段"""
    h, m = est_hour(utc_str)
    if 4 <= h < 9:
        return 'PRE_MARKET'     # 盤前 4:00-9:29
    elif 9 <= h < 10 and m < 30:
        return 'PRE_MARKET'
    elif (9 <= h and m >= 30 and h == 9) or (10 <= h < 16):
        return 'MARKET_OPEN'    # 盤中 9:30-16:00
    elif 16 <= h < 20:
        return 'AFTER_HOURS'    # 盤後 16:00-20:00
    else:
        return 'OVERNIGHT'      # 深夜 20:00-4:00

def get_trading_day(date_str):
    """取得某日期對應的交易日（如果是週末就找下週一）"""
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    for i in range(5):
        d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
        if d in sp_by_date:
            return d
    return None

def next_trading_day(date_str):
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    for i in range(1, 5):
        d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
        if d in sp_by_date:
            return d
    return None


# ============================================================
# 1. 盤前/盤後推文的精確影響
# ============================================================
print(f"\n{'='*80}")
print("📊 1. 發文時段 vs 市場反應（精確到盤前/盤中/盤後）")
print("=" * 80)

session_effects = defaultdict(lambda: {'same_day': [], 'next_day': [], 'posts': 0})

for p in originals:
    date = p['created_at'][:10]
    session = market_session(p['created_at'])
    signals = classify_post(p['content'])

    trading_day = get_trading_day(date)
    if not trading_day:
        continue

    sp = sp_by_date.get(trading_day)
    if not sp:
        continue

    same_ret = (sp['close'] - sp['open']) / sp['open'] * 100

    next_td = next_trading_day(trading_day)
    next_ret = None
    if next_td and next_td in sp_by_date:
        nsp = sp_by_date[next_td]
        next_ret = (nsp['close'] - nsp['open']) / nsp['open'] * 100

    # 整體時段
    session_effects[session]['same_day'].append(same_ret)
    if next_ret is not None:
        session_effects[session]['next_day'].append(next_ret)
    session_effects[session]['posts'] += 1

    # 時段 × 信號類型
    for sig in signals:
        key = f"{session}+{sig}"
        session_effects[key]['same_day'].append(same_ret)
        if next_ret is not None:
            session_effects[key]['next_day'].append(next_ret)
        session_effects[key]['posts'] += 1

print(f"\n  {'時段':<20s} | {'篇數':>5s} | {'對應交易日':>10s} | {'隔日':>10s}")
print(f"  {'-'*20}-+-{'-'*5}-+-{'-'*10}-+-{'-'*10}")

for session in ['PRE_MARKET', 'MARKET_OPEN', 'AFTER_HOURS', 'OVERNIGHT']:
    d = session_effects[session]
    if d['same_day']:
        avg_s = sum(d['same_day']) / len(d['same_day'])
        avg_n = sum(d['next_day']) / len(d['next_day']) if d['next_day'] else 0
        labels = {'PRE_MARKET': '🌅盤前', 'MARKET_OPEN': '☀️盤中', 'AFTER_HOURS': '🌆盤後', 'OVERNIGHT': '🌙深夜'}
        print(f"  {labels[session]:<18s} | {d['posts']:5d} | {avg_s:+.3f}%     | {avg_n:+.3f}%")

# 關鍵組合：盤前/盤後 + 特定信號
print(f"\n  🎯 高價值組合（時段 × 信號）：")
print(f"  {'組合':<30s} | {'篇數':>5s} | {'對應交易日':>10s} | {'隔日':>10s}")
print(f"  {'-'*30}-+-{'-'*5}-+-{'-'*10}-+-{'-'*10}")

combos = ['PRE_MARKET+TARIFF', 'PRE_MARKET+DEAL', 'PRE_MARKET+ACTION',
          'AFTER_HOURS+TARIFF', 'AFTER_HOURS+DEAL', 'AFTER_HOURS+ACTION',
          'OVERNIGHT+TARIFF', 'OVERNIGHT+DEAL',
          'MARKET_OPEN+TARIFF', 'MARKET_OPEN+DEAL', 'MARKET_OPEN+MARKET_BRAG',
          'PRE_MARKET+RELIEF', 'AFTER_HOURS+RELIEF',
          'PRE_MARKET+ANNOUNCE', 'AFTER_HOURS+ANNOUNCE']

for combo in combos:
    d = session_effects.get(combo)
    if d and d['posts'] >= 3:
        avg_s = sum(d['same_day']) / len(d['same_day'])
        avg_n = sum(d['next_day']) / len(d['next_day']) if d['next_day'] else 0

        arrow_s = "📈" if avg_s > 0.1 else ("📉" if avg_s < -0.1 else "➡️")
        arrow_n = "📈" if avg_n > 0.1 else ("📉" if avg_n < -0.1 else "➡️")

        print(f"  {combo:<30s} | {d['posts']:5d} | {avg_s:+.3f}% {arrow_s}  | {avg_n:+.3f}% {arrow_n}")


# ============================================================
# 2. 「關稅→Deal」轉折偵測
# ============================================================
print(f"\n{'='*80}")
print("📊 2. 關稅 → Deal 轉折點偵測")
print("   找出他從「攻擊」轉「緩和」的精確時刻")
print("=" * 80)

# 以天為單位追蹤信號類型
daily_signals = defaultdict(lambda: {'tariff': 0, 'deal': 0, 'relief': 0, 'action': 0,
                                      'attack': 0, 'positive': 0, 'posts': 0,
                                      'first_post': None, 'last_post': None})

for p in originals:
    date = p['created_at'][:10]
    signals = classify_post(p['content'])
    d = daily_signals[date]
    d['posts'] += 1
    if 'TARIFF' in signals: d['tariff'] += 1
    if 'DEAL' in signals: d['deal'] += 1
    if 'RELIEF' in signals: d['relief'] += 1
    if 'ACTION' in signals: d['action'] += 1
    if 'ATTACK' in signals: d['attack'] += 1
    if 'POSITIVE' in signals: d['positive'] += 1
    if not d['first_post']:
        d['first_post'] = p['created_at']
    d['last_post'] = p['created_at']

# 找轉折：前N天以 TARIFF/ATTACK 為主 → 突然出現 DEAL/RELIEF
print(f"\n  掃描「攻擊期 → 緩和信號」的轉折點：")
print(f"  {'日期':12s} | {'轉折類型':15s} | {'前3天信號':25s} | {'當天信號':25s} | {'S&P反應':>10s}")
print(f"  {'-'*12}-+-{'-'*15}-+-{'-'*25}-+-{'-'*25}-+-{'-'*10}")

sorted_dates = sorted(daily_signals.keys())

for i, date in enumerate(sorted_dates):
    if i < 3:
        continue

    # 前 3 天的攻擊密度
    prev_3 = sorted_dates[i-3:i]
    prev_tariff = sum(daily_signals[d]['tariff'] for d in prev_3)
    prev_attack = sum(daily_signals[d]['attack'] for d in prev_3)
    attack_score = prev_tariff + prev_attack

    # 當天出現緩和信號
    today = daily_signals[date]
    relief_score = today['deal'] + today['relief']

    if attack_score >= 3 and relief_score >= 1:
        # 這是轉折日！
        sp = sp_by_date.get(date)
        next_td = next_trading_day(date) if date in sp_by_date else None
        sp_ret = ""
        if sp:
            ret = (sp['close'] - sp['open']) / sp['open'] * 100
            sp_ret = f"{ret:+.2f}%"
        elif next_td:
            nsp = sp_by_date[next_td]
            ret = (nsp['close'] - nsp['open']) / nsp['open'] * 100
            sp_ret = f"→{ret:+.2f}%"

        prev_sig = f"T:{prev_tariff} A:{prev_attack}"
        today_sig = f"D:{today['deal']} R:{today['relief']} T:{today['tariff']}"
        shift_type = "DEAL出現" if today['deal'] > 0 else "RELIEF出現"

        print(f"  {date:12s} | {shift_type:15s} | {prev_sig:25s} | {today_sig:25s} | {sp_ret:>10s}")


# ============================================================
# 3. 連發轟炸 vs 沉默期 — 操作窗口
# ============================================================
print(f"\n{'='*80}")
print("📊 3. 連發轟炸 → 沉默 → 再發 的節奏（操作窗口）")
print("=" * 80)

# 計算每小時的發文密度
hourly_posts = defaultdict(list)  # key: (date, hour_est) → [posts]

for p in originals:
    dt = datetime.fromisoformat(p['created_at'].replace('Z', '+00:00'))
    est_h = (dt.hour - 5) % 24
    date = p['created_at'][:10]
    hourly_posts[(date, est_h)].append(p)

# 找「爆發→沉默→爆發」模式
# 定義：1小時內 ≥5 篇 = 爆發，之後 ≥3 小時無發文 = 沉默
print(f"\n  尋找「轟炸 → 沉默窗口 → 再轟炸」模式：")
print(f"  {'日期':12s} | {'轟炸時間':10s} | {'篇數':>4s} | {'沉默':>6s} | {'再發':>10s} | {'信號變化':20s} | {'S&P':>8s}")
print(f"  {'-'*12}-+-{'-'*10}-+-{'-'*4}-+-{'-'*6}-+-{'-'*10}-+-{'-'*20}-+-{'-'*8}")

# 用精確時間重建時間線
for p in originals:
    p['_dt'] = datetime.fromisoformat(p['created_at'].replace('Z', '+00:00'))

# 按天分組
daily_posts = defaultdict(list)
for p in originals:
    daily_posts[p['created_at'][:10]].append(p)

burst_patterns = []

for date in sorted(daily_posts.keys()):
    day_p = sorted(daily_posts[date], key=lambda x: x['_dt'])
    if len(day_p) < 5:
        continue

    # 找爆發和沉默
    i = 0
    while i < len(day_p) - 1:
        # 找爆發開始：5分鐘內連發 ≥3 篇
        burst_start = i
        burst_end = i
        while burst_end < len(day_p) - 1:
            gap = (day_p[burst_end + 1]['_dt'] - day_p[burst_end]['_dt']).total_seconds() / 60
            if gap <= 15:  # 15 分鐘內
                burst_end += 1
            else:
                break

        burst_count = burst_end - burst_start + 1
        if burst_count >= 3:
            # 找沉默（到下一篇的間隔）
            if burst_end + 1 < len(day_p):
                silence_min = (day_p[burst_end + 1]['_dt'] - day_p[burst_end]['_dt']).total_seconds() / 60
            else:
                silence_min = 999

            if silence_min >= 60:  # 至少沉默 1 小時
                burst_time_est = f"{(day_p[burst_start]['_dt'].hour - 5) % 24:02d}:{day_p[burst_start]['_dt'].minute:02d}"

                # 爆發期的信號
                burst_signals = set()
                for bp in day_p[burst_start:burst_end+1]:
                    burst_signals.update(classify_post(bp['content']))

                # 沉默後的信號
                resume_signals = set()
                if burst_end + 1 < len(day_p):
                    resume_time_est = f"{(day_p[burst_end+1]['_dt'].hour - 5) % 24:02d}:{day_p[burst_end+1]['_dt'].minute:02d}"
                    for rp in day_p[burst_end+1:min(burst_end+4, len(day_p))]:
                        resume_signals.update(classify_post(rp['content']))
                else:
                    resume_time_est = "—"

                # 信號變化
                new_signals = resume_signals - burst_signals
                signal_change = ""
                if 'DEAL' in new_signals or 'RELIEF' in new_signals:
                    signal_change = "⚡ 攻→緩"
                elif 'TARIFF' in new_signals or 'ATTACK' in new_signals:
                    signal_change = "⚡ 緩→攻"
                elif burst_signals & {'TARIFF', 'ATTACK'} and resume_signals & {'TARIFF', 'ATTACK'}:
                    signal_change = "持續攻擊"
                elif burst_signals & {'DEAL', 'POSITIVE'} and resume_signals & {'DEAL', 'POSITIVE'}:
                    signal_change = "持續正面"
                else:
                    signal_change = f"{'→'.join(sorted(new_signals)[:2])}" if new_signals else "主題不變"

                sp = sp_by_date.get(date)
                sp_ret = ""
                if sp:
                    ret = (sp['close'] - sp['open']) / sp['open'] * 100
                    sp_ret = f"{ret:+.2f}%"

                burst_patterns.append({
                    'date': date,
                    'burst_time': burst_time_est,
                    'burst_count': burst_count,
                    'silence_min': round(silence_min),
                    'resume_time': resume_time_est,
                    'burst_signals': sorted(burst_signals),
                    'resume_signals': sorted(resume_signals),
                    'signal_change': signal_change,
                    'sp_return': sp_ret
                })

                if len(burst_patterns) <= 50 and silence_min >= 120:
                    print(f"  {date:12s} | EST {burst_time_est:5s} | {burst_count:4d} | {silence_min:4.0f}分 | EST {resume_time_est:5s} | {signal_change:20s} | {sp_ret:>8s}")

        i = burst_end + 1


# ============================================================
# 4. 盤前「關稅轟炸」→ 開盤反應（精確到分鐘）
# ============================================================
print(f"\n{'='*80}")
print("📊 4. 盤前關稅推文 → 開盤第一個小時反應")
print("=" * 80)

premarket_tariff_days = []

for date, day_p in daily_posts.items():
    # 找盤前 (EST 5:00-9:30) 的關稅推文
    premarket_tariff = []
    for p in day_p:
        h, m = est_hour(p['created_at'])
        if 4 <= h < 10:  # 盤前時段
            sigs = classify_post(p['content'])
            if 'TARIFF' in sigs:
                premarket_tariff.append(p)

    if premarket_tariff and date in sp_by_date:
        sp = sp_by_date[date]
        # 開盤 gap: (open - 前一天 close)
        prev_dates = sorted([d for d in sp_by_date if d < date])
        if prev_dates:
            prev_close = sp_by_date[prev_dates[-1]]['close']
            open_gap = (sp['open'] - prev_close) / prev_close * 100
            day_ret = (sp['close'] - sp['open']) / sp['open'] * 100
            first_hour = (sp['high'] - sp['open']) / sp['open'] * 100  # 近似
            first_time = premarket_tariff[0]['created_at'][11:16]

            premarket_tariff_days.append({
                'date': date,
                'tariff_count': len(premarket_tariff),
                'first_post_utc': first_time,
                'open_gap': open_gap,
                'day_return': day_ret,
                'content': premarket_tariff[0]['content'][:60]
            })

print(f"\n  找到 {len(premarket_tariff_days)} 天盤前有關稅推文")
print(f"\n  {'日期':12s} | {'篇數':>4s} | {'首篇UTC':>8s} | {'開盤跳空':>8s} | {'當天漲跌':>8s} | {'內容'}")
print(f"  {'-'*12}-+-{'-'*4}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*40}")

for d in premarket_tariff_days:
    gap_arrow = "⬆️" if d['open_gap'] > 0.1 else ("⬇️" if d['open_gap'] < -0.1 else "➡️")
    ret_arrow = "📈" if d['day_return'] > 0.5 else ("📉" if d['day_return'] < -0.5 else "➡️")
    print(f"  {d['date']:12s} | {d['tariff_count']:4d} | {d['first_post_utc']:>8s} | {d['open_gap']:+.2f}% {gap_arrow} | {d['day_return']:+.2f}% {ret_arrow} | {d['content'][:40]}")

# 統計
if premarket_tariff_days:
    avg_gap = sum(d['open_gap'] for d in premarket_tariff_days) / len(premarket_tariff_days)
    avg_ret = sum(d['day_return'] for d in premarket_tariff_days) / len(premarket_tariff_days)
    neg_gap = sum(1 for d in premarket_tariff_days if d['open_gap'] < 0)
    neg_ret = sum(1 for d in premarket_tariff_days if d['day_return'] < 0)
    print(f"\n  📊 統計摘要:")
    print(f"     盤前發關稅文 → 平均開盤跳空: {avg_gap:+.3f}%")
    print(f"     盤前發關稅文 → 平均當天收盤: {avg_ret:+.3f}%")
    print(f"     開盤跳空為負: {neg_gap}/{len(premarket_tariff_days)} ({neg_gap/len(premarket_tariff_days)*100:.0f}%)")
    print(f"     當天收跌: {neg_ret}/{len(premarket_tariff_days)} ({neg_ret/len(premarket_tariff_days)*100:.0f}%)")


# ============================================================
# 5. 「信號1 → 信號2」配對：精確時間差
# ============================================================
print(f"\n{'='*80}")
print("📊 5. 信號配對分析 — 「第一個信號」到「第二個信號」要多久")
print("=" * 80)

# 找 TARIFF → DEAL 的配對
tariff_posts = [(p, p['_dt']) for p in originals if 'TARIFF' in classify_post(p['content'])]
deal_posts = [(p, p['_dt']) for p in originals if 'DEAL' in classify_post(p['content'])]
relief_posts = [(p, p['_dt']) for p in originals if 'RELIEF' in classify_post(p['content'])]
action_posts = [(p, p['_dt']) for p in originals if 'ACTION' in classify_post(p['content'])]

print(f"\n  信號統計: TARIFF={len(tariff_posts)} | DEAL={len(deal_posts)} | RELIEF={len(relief_posts)} | ACTION={len(action_posts)}")

# TARIFF 之後最近的 DEAL 出現要多久？
print(f"\n  🔴→🟢 TARIFF 之後多久出現 DEAL:")
pairs = []
for tp, t_dt in tariff_posts:
    # 找最近的 DEAL（之後的）
    nearest_deal = None
    for dp, d_dt in deal_posts:
        if d_dt > t_dt:
            hours_diff = (d_dt - t_dt).total_seconds() / 3600
            if hours_diff <= 72:  # 3 天內
                nearest_deal = (dp, d_dt, hours_diff)
            break  # deal_posts 已排序

    if nearest_deal:
        dp, d_dt, hours = nearest_deal
        # 這段期間的市場反應
        t_date = tp['created_at'][:10]
        d_date = dp['created_at'][:10]

        sp_t = sp_by_date.get(t_date)
        sp_d = sp_by_date.get(d_date)

        market_move = ""
        if sp_t and sp_d and t_date != d_date:
            move = (sp_d['close'] - sp_t['open']) / sp_t['open'] * 100
            market_move = f"S&P {move:+.2f}%"

        pairs.append({
            'tariff_time': tp['created_at'][:16],
            'deal_time': dp['created_at'][:16],
            'hours': hours,
            'market': market_move,
            'tariff_content': tp['content'][:40],
            'deal_content': dp['content'][:40],
        })

# 統計時間差
if pairs:
    hours_list = [p['hours'] for p in pairs]
    print(f"     配對數: {len(pairs)}")
    print(f"     平均間隔: {sum(hours_list)/len(hours_list):.1f} 小時")
    print(f"     中位數: {sorted(hours_list)[len(hours_list)//2]:.1f} 小時")
    print(f"     最短: {min(hours_list):.1f} 小時")
    print(f"     最長: {max(hours_list):.1f} 小時")

    print(f"\n  最近 20 組 TARIFF→DEAL 配對:")
    print(f"  {'TARIFF時間':18s} | {'DEAL時間':18s} | {'間隔':>6s} | {'市場':>12s} | {'TARIFF內容':20s} → {'DEAL內容'}")
    for p in pairs[-20:]:
        print(f"  {p['tariff_time']:18s} | {p['deal_time']:18s} | {p['hours']:5.1f}h | {p['market']:>12s} | {p['tariff_content'][:20]} → {p['deal_content'][:20]}")


# ============================================================
# 6. 「ACTION」信號的市場衝擊
# ============================================================
print(f"\n{'='*80}")
print("📊 6. ACTION 信號（簽署/命令/生效）的市場衝擊")
print("=" * 80)

for ap, a_dt in action_posts[-30:]:
    date = ap['created_at'][:10]
    session = market_session(ap['created_at'])
    h, m = est_hour(ap['created_at'])
    signals = classify_post(ap['content'])

    sp = sp_by_date.get(date)
    next_td = next_trading_day(date)

    sp_ret = ""
    if sp:
        ret = (sp['close'] - sp['open']) / sp['open'] * 100
        sp_ret = f"當天{ret:+.2f}%"

    next_ret = ""
    if next_td and next_td in sp_by_date:
        nsp = sp_by_date[next_td]
        nret = (nsp['close'] - nsp['open']) / nsp['open'] * 100
        next_ret = f"隔天{nret:+.2f}%"

    other_sigs = signals - {'ACTION'}
    sig_str = '+'.join(sorted(other_sigs)) if other_sigs else '—'

    print(f"  {ap['created_at'][:16]} EST{h:02d}:{m:02d} | {session:12s} | {sig_str:20s} | {sp_ret:>12s} {next_ret:>12s} | {ap['content'][:50]}")


# 存結果
results = {
    'burst_patterns_count': len(burst_patterns),
    'premarket_tariff_days': len(premarket_tariff_days),
    'tariff_to_deal_pairs': len(pairs),
    'avg_tariff_to_deal_hours': round(sum(hours_list)/len(hours_list), 1) if pairs else None,
}
with open(BASE / 'results_07_signal.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n💾 詳細結果存入 results_07_signal.json")
