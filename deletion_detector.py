#!/usr/bin/env python3
"""
川普密碼 — 刪文偵測器
三源比對，找出「發了又刪」的推文
刪文可能是最強的信號——他不想讓你看到的，可能正是密碼

邏輯：
  CNN 有 + Truth Social 沒有 = 被刪了
  自建庫有 + CNN 沒有 = CNN 漏掉了
  三源都有 = 確認存在
  只有一源有 = 可疑，需要標記

用法:
  python3 deletion_detector.py              # 執行刪文偵測
  python3 deletion_detector.py --history    # 顯示歷史刪文記錄
"""

import json
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent
DATA = BASE / "data"
DELETIONS_LOG = DATA / "deletions.json"


def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)


def check_truth_social_exists(truth_social_url):
    """檢查一篇推文在 Truth Social 上是否還存在"""
    if not truth_social_url or 'truthsocial.com' not in truth_social_url:
        return 'unknown'

    try:
        req = urllib.request.Request(truth_social_url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        }, method='HEAD')
        with urllib.request.urlopen(req, timeout=10) as resp:
            # 200 = 存在（但可能返回 JS 頁面）
            return 'exists'
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return 'deleted'
        elif e.code == 403:
            return 'blocked'
        return f'http_{e.code}'
    except Exception:
        return 'error'


def detect_deletions():
    """比對三源，找出被刪的推文"""
    log("🔍 刪文偵測器啟動")

    # 載入所有來源
    sources = {}

    # CNN Archive（從 daily pipeline 的輸出或直接下載）
    cnn_file = DATA / "market_SP500.json"  # 存在代表管線跑過
    try:
        from multi_source_fetcher import fetch_cnn_archive
        cnn_result = fetch_cnn_archive()
        if cnn_result['status'] == 'ok':
            sources['cnn'] = {p['content'][:80].lower().strip(): p
                             for p in cnn_result['posts'] if p.get('content')}
            log(f"   CNN: {len(sources['cnn'])} 篇")
    except Exception as e:
        log(f"   CNN 載入失敗: {e}")

    # 自建庫
    own_file = DATA / "own_archive.json"
    if own_file.exists():
        with open(own_file, encoding='utf-8') as f:
            own_data = json.load(f)
        sources['own'] = {p['content'][:80].lower().strip(): p
                         for p in own_data.get('posts', []) if p.get('content')}
        log(f"   自建庫: {len(sources['own'])} 篇")
    else:
        log("   自建庫: 尚未建立")

    if len(sources) < 2:
        log("   ⚠️ 需要至少 2 個來源才能偵測刪文")
        return

    # 比對：找出「某源有、其他源沒有」的推文
    all_fps = set()
    for src in sources.values():
        all_fps.update(src.keys())

    log(f"   總指紋數: {len(all_fps)}")

    # 分類
    in_all = []
    in_some = []

    for fp in all_fps:
        present_in = [name for name, src in sources.items() if fp in src]
        missing_from = [name for name in sources if name not in present_in]

        if len(present_in) == len(sources):
            in_all.append(fp)
        else:
            # 取得推文資訊
            post = None
            for name in present_in:
                post = sources[name].get(fp)
                if post:
                    break

            in_some.append({
                'content_preview': post['content'][:120] if post else fp[:80],
                'created_at': post.get('created_at', '?') if post else '?',
                'url': post.get('url', '') if post else '',
                'present_in': present_in,
                'missing_from': missing_from,
            })

    log(f"\n   📊 比對結果:")
    log(f"      所有來源都有: {len(in_all)} 篇")
    log(f"      部分來源有: {len(in_some)} 篇")

    # 重點：CNN 有但自建庫沒有 → 可能是 RT 或格式差異
    # 重點：自建庫有但 CNN 沒有 → CNN 漏掉了
    # 最重要：以前有現在沒有 → 被刪了

    # 載入已知刪文記錄
    known_deletions = []
    if DELETIONS_LOG.exists():
        with open(DELETIONS_LOG, encoding='utf-8') as f:
            known_deletions = json.load(f)

    # 對「部分來源有」的推文，檢查 Truth Social 是否還存在
    new_deletions = []
    if in_some:
        log(f"\n   🔍 檢查 {min(len(in_some), 20)} 篇可疑推文...")
        for item in in_some[:20]:  # 限制檢查數量
            url = item.get('url', '')
            if 'truthsocial.com' in url:
                status = check_truth_social_exists(url)
                item['truth_social_status'] = status
                if status == 'deleted':
                    new_deletions.append(item)
                    log(f"      🚨 刪文發現! {item['created_at'][:16]} | {item['content_preview'][:60]}...")
            import time
            time.sleep(0.5)

    # 更新刪文記錄
    if new_deletions:
        for d in new_deletions:
            d['detected_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        known_deletions.extend(new_deletions)

        with open(DELETIONS_LOG, 'w', encoding='utf-8') as f:
            json.dump(known_deletions, f, ensure_ascii=False, indent=2)

        log(f"\n   🚨 新發現 {len(new_deletions)} 篇刪文！")
        log(f"   📁 歷史刪文總計: {len(known_deletions)} 篇")
    else:
        log(f"\n   ✅ 沒有發現新的刪文")

    # 存比對摘要
    summary = {
        'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'sources_used': list(sources.keys()),
        'total_unique_posts': len(all_fps),
        'in_all_sources': len(in_all),
        'partial_match': len(in_some),
        'new_deletions': len(new_deletions),
        'total_known_deletions': len(known_deletions),
        'partial_details': in_some[:50],  # 前 50 條
    }

    with open(DATA / 'deletion_report.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return summary


def show_history():
    """顯示歷史刪文記錄"""
    if not DELETIONS_LOG.exists():
        print("尚無刪文記錄")
        return

    with open(DELETIONS_LOG, encoding='utf-8') as f:
        deletions = json.load(f)

    print(f"📋 歷史刪文記錄: {len(deletions)} 篇")
    print("=" * 80)
    for d in deletions:
        print(f"  {d.get('created_at', '?')[:16]} | 偵測於 {d.get('detected_at', '?')[:16]}")
        print(f"  內容: {d.get('content_preview', '?')[:100]}")
        print(f"  來源: {', '.join(d.get('present_in', []))}")
        print()


def main():
    if '--history' in sys.argv:
        show_history()
    else:
        detect_deletions()


if __name__ == '__main__':
    main()
