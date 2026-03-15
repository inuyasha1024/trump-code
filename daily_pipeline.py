#!/usr/bin/env python3
"""
川普密碼 — 每日管線（VPS 上執行）
1. 抓最新推文
2. 抓最新股市
3. 驗證昨天的預測
4. 對今天跑所有存活規則
5. 產出三語報告
6. 同步到 GitHub
"""

import json
import csv
import html
import re
import os
import subprocess
import urllib.request
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)

TODAY = datetime.utcnow().strftime('%Y-%m-%d')
NOW = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

def log(msg):
    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] {msg}", flush=True)


# ============================================================
# 步驟 1: 抓最新推文
# ============================================================
def fetch_posts():
    log("📥 1/6 抓取最新推文...")
    try:
        req = urllib.request.Request("https://ix.cnn.io/data/truth-social/truth_archive.csv")
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode('utf-8')

        reader = csv.DictReader(raw.splitlines())
        all_rows = list(reader)

        posts = []
        for row in all_rows:
            if not row.get('content') or not row.get('created_at'):
                continue
            content = row['content'].strip()
            try:
                content = content.encode('latin-1').decode('utf-8')
            except:
                pass
            content = html.unescape(content)

            created = row.get('created_at', '')
            if not created or not created.startswith('20'):
                continue
            if content and created and not content.startswith('RT @') and created >= '2025-01-20':
                posts.append({
                    'created_at': created,
                    'content': content,
                    'url': row.get('url', ''),
                })

        posts.sort(key=lambda p: p['created_at'])
        log(f"   ✅ {len(posts)} 篇原創推文")
        return posts

    except Exception as e:
        log(f"   ⚠️ 失敗: {e}")
        return []


# ============================================================
# 步驟 2: 抓最新股市
# ============================================================
def fetch_market():
    log("📈 2/6 抓取股市資料...")
    try:
        import yfinance as yf
        sp = yf.download('^GSPC', start='2025-01-17', period='max', progress=False)
        records = []
        for date, row in sp.iterrows():
            records.append({
                'date': date.strftime('%Y-%m-%d'),
                'open': round(float(row['Open'].iloc[0]), 2),
                'close': round(float(row['Close'].iloc[0]), 2),
                'high': round(float(row['High'].iloc[0]), 2),
                'low': round(float(row['Low'].iloc[0]), 2),
            })

        # 存檔
        with open(BASE / 'market_SP500.json', 'w') as f:
            json.dump(records, f, indent=2)

        log(f"   ✅ S&P500: {len(records)} 交易日，最新 {records[-1]['date']}")
        return {r['date']: r for r in records}

    except Exception as e:
        log(f"   ⚠️ yfinance 失敗，用本地: {e}")
        with open(BASE / 'market_SP500.json') as f:
            records = json.load(f)
        return {r['date']: r for r in records}


# ============================================================
# 步驟 3: 計算今日信號
# ============================================================
KEYWORDS = [
    'tariff', 'tariffs', 'deal', 'agreement', 'negotiate', 'signed',
    'pause', 'exempt', 'suspend', 'delay', 'reciprocal',
    'china', 'chinese', 'japan', 'mexico', 'iran', 'russia', 'europe', 'india',
    'great', 'tremendous', 'incredible', 'historic', 'beautiful',
    'fake', 'corrupt', 'terrible', 'disaster', 'disgrace',
    'stock market', 'all time high', 'record high', 'dow', 'nasdaq',
    'immediately', 'executive order', 'just signed', 'hereby',
    'oil', 'energy', 'border', 'military', 'nuclear',
    'save america', 'filibuster', 'maga',
    'president djt', 'thank you for your attention', 'never let you down',
]

def est_hour(utc_str):
    dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
    return (dt.hour - 5) % 24, dt.minute

def compute_day_features(day_posts):
    """計算一天的所有特徵"""
    f = {}
    if not day_posts:
        return f

    n = len(day_posts)
    all_text = ' '.join(p['content'].lower() for p in day_posts)
    all_content = ' '.join(p['content'] for p in day_posts)

    f['posts_1_5'] = 1 <= n <= 5
    f['posts_6_10'] = 6 <= n <= 10
    f['posts_11_20'] = 11 <= n <= 20
    f['posts_21_35'] = 21 <= n <= 35
    f['posts_36plus'] = n >= 36

    caps = sum(1 for c in all_content if c.isupper())
    alpha = sum(1 for c in all_content if c.isalpha())
    cr = caps / max(alpha, 1)
    f['caps_high'] = cr > 0.18
    f['caps_very_high'] = cr > 0.25

    excl = all_content.count('!')
    f['excl_heavy'] = excl >= 5
    f['excl_extreme'] = excl >= 10

    avg_len = sum(len(p['content']) for p in day_posts) / n
    f['avg_len_short'] = avg_len < 150
    f['avg_len_medium'] = 150 <= avg_len < 350
    f['avg_len_long'] = avg_len > 400

    for kw in KEYWORDS:
        kw_clean = kw.replace(' ', '_')
        count = all_text.count(kw)
        if count >= 1:
            f[f'kw_{kw_clean}'] = True
        if count >= 2:
            f[f'kw_{kw_clean}_2plus'] = True

        # 盤前/盤中
        for p in day_posts:
            h, m_val = est_hour(p['created_at'])
            if kw in p['content'].lower():
                if h < 9 or (h == 9 and m_val < 30):
                    f[f'pre_{kw_clean}'] = True
                elif h < 16:
                    f[f'open_{kw_clean}'] = True

    has_t = any(w in all_text for w in ['tariff', 'tariffs'])
    has_d = 'deal' in all_text
    f['tariff_no_deal'] = has_t and not has_d
    f['deal_no_tariff'] = has_d and not has_t
    f['both_tariff_and_deal'] = has_t and has_d

    dt = datetime.strptime(day_posts[0]['created_at'][:10], '%Y-%m-%d')
    f['is_monday'] = dt.weekday() == 0
    f['is_friday'] = dt.weekday() == 4

    night = sum(1 for p in day_posts if est_hour(p['created_at'])[0] < 5 or est_hour(p['created_at'])[0] >= 23)
    f['has_night'] = night >= 1

    f['questions_yes'] = all_content.count('?') >= 2

    return {k: v for k, v in f.items() if v is True}


def run_predictions(today_features, rules):
    """用所有存活規則跑今天的預測"""
    triggered = []
    for rule in rules:
        if all(today_features.get(feat, False) for feat in rule['features']):
            triggered.append(rule)
    return triggered


# ============================================================
# 步驟 4: 驗證過去的預測
# ============================================================
def verify_past_predictions(sp_by_date):
    log("✅ 4/6 驗證過去的預測...")
    history_file = DATA / "prediction_history.json"
    if not history_file.exists():
        return []

    with open(history_file) as f:
        history = json.load(f)

    updated = 0
    for pred in history:
        if pred.get('status') == 'PENDING':
            exit_date = pred.get('exit_date')
            if exit_date and exit_date in sp_by_date:
                entry_date = pred.get('entry_date')
                if entry_date in sp_by_date:
                    entry_p = sp_by_date[entry_date]['open']
                    exit_p = sp_by_date[exit_date]['close']
                    ret = (exit_p - entry_p) / entry_p * 100

                    if pred['direction'] == 'SHORT':
                        ret = -ret

                    pred['actual_return'] = round(ret, 3)
                    pred['correct'] = ret > 0
                    pred['status'] = 'VERIFIED'
                    updated += 1

    with open(history_file, 'w') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    log(f"   ✅ 驗證了 {updated} 筆預測")
    return history


# ============================================================
# 步驟 5: 三語報告
# ============================================================
def generate_report(today_posts, today_features, triggered_rules, history, sp_by_date):
    log("📊 5/6 產出三語報告...")

    n_posts = len(today_posts)
    n_triggered = len(triggered_rules)

    # 統計
    long_rules = [r for r in triggered_rules if r.get('direction') == 'LONG']
    short_rules = [r for r in triggered_rules if r.get('direction') == 'SHORT']

    # 歷史命中率
    verified = [p for p in history if p.get('status') == 'VERIFIED']
    correct = [p for p in verified if p.get('correct')]
    hit_rate = len(correct) / max(len(verified), 1) * 100

    # 今天的關鍵信號
    key_signals = []
    if today_features.get('kw_tariff') or today_features.get('kw_tariffs'):
        key_signals.append(('TARIFF', '關稅', '関税'))
    if today_features.get('kw_deal'):
        key_signals.append(('DEAL', 'Deal', 'ディール'))
    if today_features.get('kw_china') or today_features.get('kw_chinese'):
        key_signals.append(('CHINA', '中國', '中国'))
    if today_features.get('kw_iran'):
        key_signals.append(('IRAN', '伊朗', 'イラン'))
    if today_features.get('tariff_no_deal'):
        key_signals.append(('TARIFF_ONLY', '只有關稅沒有Deal⚠️', '関税のみ（Deal無し）⚠️'))
    if today_features.get('deal_no_tariff'):
        key_signals.append(('DEAL_ONLY', '只有Deal沒有關稅✅', 'Dealのみ（関税無し）✅'))

    # 最新一篇
    latest = today_posts[-1] if today_posts else None
    latest_content = latest['content'][:100] if latest else 'N/A'
    latest_time = latest['created_at'][:16] if latest else 'N/A'

    # S&P 最新
    latest_sp = list(sp_by_date.values())[-1] if sp_by_date else {}
    sp_close = latest_sp.get('close', 0)
    sp_date = latest_sp.get('date', 'N/A')

    report = {
        'date': TODAY,
        'generated_at': NOW,
        'posts_today': n_posts,
        'latest_post': {
            'time': latest_time,
            'content_preview': latest_content,
        },
        'signals_detected': [s[0] for s in key_signals],
        'models_triggered': n_triggered,
        'direction_summary': {
            'LONG': len(long_rules),
            'SHORT': len(short_rules),
            'consensus': 'BULLISH' if len(long_rules) > len(short_rules) * 1.5
                         else ('BEARISH' if len(short_rules) > len(long_rules) * 1.5
                               else 'NEUTRAL'),
        },
        'historical_hit_rate': {
            'verified': len(verified),
            'correct': len(correct),
            'rate': round(hit_rate, 1),
        },
        'sp500_latest': {
            'date': sp_date,
            'close': sp_close,
        },

        # 三語摘要
        'summary': {
            'en': f"Trump Code Daily Report — {TODAY}\n"
                  f"Posts today: {n_posts} | Models triggered: {n_triggered}\n"
                  f"Signals: {', '.join(s[0] for s in key_signals) or 'None'}\n"
                  f"Consensus: {len(long_rules)} LONG vs {len(short_rules)} SHORT\n"
                  f"Historical hit rate: {hit_rate:.1f}% ({len(correct)}/{len(verified)})\n"
                  f"Latest post: {latest_content}",

            'zh': f"川普密碼每日報告 — {TODAY}\n"
                  f"今日推文: {n_posts} 篇 | 觸發模型: {n_triggered} 組\n"
                  f"偵測信號: {', '.join(s[1] for s in key_signals) or '無'}\n"
                  f"共識方向: {len(long_rules)} 組看多 vs {len(short_rules)} 組看空\n"
                  f"歷史命中率: {hit_rate:.1f}% ({len(correct)}/{len(verified)})\n"
                  f"最新推文: {latest_content}",

            'ja': f"トランプ・コード日次レポート — {TODAY}\n"
                  f"本日の投稿: {n_posts}件 | トリガーモデル: {n_triggered}組\n"
                  f"検出シグナル: {', '.join(s[2] for s in key_signals) or 'なし'}\n"
                  f"コンセンサス: {len(long_rules)}組ロング vs {len(short_rules)}組ショート\n"
                  f"過去の的中率: {hit_rate:.1f}% ({len(correct)}/{len(verified)})\n"
                  f"最新投稿: {latest_content}",
        },

        'triggered_rules_sample': [
            {
                'features': r['features'],
                'direction': r.get('direction', 'LONG'),
                'hold': r.get('hold', 1),
                'train_wr': r.get('train_wr', 0),
                'test_wr': r.get('test_wr', 0),
            }
            for r in triggered_rules[:20]
        ],
    }

    # 存報告
    with open(DATA / 'daily_report.json', 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 歷史累積
    reports_file = DATA / 'report_history.json'
    reports = []
    if reports_file.exists():
        with open(reports_file) as f:
            reports = json.load(f)
    reports.append({
        'date': TODAY,
        'posts': n_posts,
        'triggered': n_triggered,
        'long': len(long_rules),
        'short': len(short_rules),
        'signals': [s[0] for s in key_signals],
        'consensus': report['direction_summary']['consensus'],
    })
    with open(reports_file, 'w') as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)

    log(f"   ✅ 報告完成")
    return report


# ============================================================
# 步驟 6: 同步到 GitHub
# ============================================================
def sync_to_github():
    log("🔄 6/6 同步到 GitHub...")
    try:
        os.chdir(BASE)
        subprocess.run(['git', 'add', 'data/'], capture_output=True)
        subprocess.run(['git', 'add', 'market_SP500.json'], capture_output=True)

        result = subprocess.run(
            ['git', 'commit', '-m', f'Daily update: {TODAY} | Auto-synced from VPS'],
            capture_output=True, text=True
        )

        if 'nothing to commit' in result.stdout + result.stderr:
            log("   ℹ️ 沒有新資料需要同步")
            return

        push = subprocess.run(
            ['git', 'push', 'origin', 'main'],
            capture_output=True, text=True, timeout=60
        )

        if push.returncode == 0:
            log("   ✅ GitHub 同步完成")
        else:
            log(f"   ⚠️ Push 失敗: {push.stderr[:100]}")

    except Exception as e:
        log(f"   ⚠️ 同步失敗: {e}")


# ============================================================
# 主程式
# ============================================================
def main():
    log(f"{'='*70}")
    log(f"🔴 川普密碼 每日管線 — {TODAY}")
    log(f"{'='*70}")

    # 1. 抓推文
    posts = fetch_posts()
    if not posts:
        log("❌ 無法取得推文，中止")
        return

    # 2. 抓股市
    sp_by_date = fetch_market()

    # 3. 計算今日信號
    log("🧮 3/6 計算今日信號...")
    daily = defaultdict(list)
    for p in posts:
        daily[p['created_at'][:10]].append(p)

    today_key = sorted(daily.keys())[-1]  # 最新一天
    today_posts = daily[today_key]
    today_features = compute_day_features(today_posts)

    log(f"   最新日期: {today_key} | {len(today_posts)} 篇")
    log(f"   觸發特徵: {len(today_features)} 個")

    # 關鍵信號
    key = []
    if today_features.get('kw_tariff'): key.append('TARIFF')
    if today_features.get('kw_deal'): key.append('DEAL')
    if today_features.get('kw_china'): key.append('CHINA')
    if today_features.get('kw_iran'): key.append('IRAN')
    if today_features.get('tariff_no_deal'): key.append('⚠️TARIFF_ONLY')
    if today_features.get('deal_no_tariff'): key.append('✅DEAL_ONLY')
    log(f"   關鍵信號: {', '.join(key) or '無'}")

    # 4. 載入存活規則，跑預測
    rules_file = BASE / 'monitor_rules.json'
    if rules_file.exists():
        with open(rules_file) as f:
            rules = json.load(f)
    else:
        rules = []

    triggered = run_predictions(today_features, rules)
    long_t = [r for r in triggered if r.get('direction') == 'LONG']
    short_t = [r for r in triggered if r.get('direction') == 'SHORT']
    log(f"   觸發規則: {len(triggered)} / {len(rules)}")
    log(f"   看多: {len(long_t)} | 看空: {len(short_t)}")

    # 5. 驗證過去預測
    history = verify_past_predictions(sp_by_date)

    # 6. 產出報告
    report = generate_report(today_posts, today_features, triggered, history, sp_by_date)

    # 打印三語摘要
    log(f"\n{'='*70}")
    log("📋 DAILY REPORT")
    log(f"{'='*70}")
    print(report['summary']['en'])
    log(f"\n{'='*70}")
    log("📋 每日報告")
    log(f"{'='*70}")
    print(report['summary']['zh'])
    log(f"\n{'='*70}")
    log("📋 日次レポート")
    log(f"{'='*70}")
    print(report['summary']['ja'])

    # 7. 同步
    sync_to_github()

    log(f"\n{'='*70}")
    log(f"✅ 管線完成！")
    log(f"{'='*70}")


if __name__ == '__main__':
    main()
