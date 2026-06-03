#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模拟交易追踪系统 — 每日更新脚本

用法：
  python3 update.py                 # 更新所有股票的收盘价
  python3 update.py --buy           # 9:35 时段执行，获取买入价
  python3 update.py --add 002463    # 添加新推荐（今日）
  python3 update.py --add 002463,600519,300033  # 批量添加

依赖：thsdk, pandas
"""

import argparse
import datetime
import json
import os
import sys
import time

# ── 配置 ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, 'data.json')


def load_data():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'[OK] 已保存 {DATA_FILE}')


def get_ths():
    from thsdk import THS
    ths = THS()
    ths.connect()
    return ths


def resolve_thscode(ths, code):
    """股票代码 → THSCODE (SZ: USZA, SH: USHA)"""
    if code.startswith(('6', '5')):
        return f'USHA{code}'
    elif code.startswith(('0', '3', '2')):
        return f'USZA{code}'
    else:
        result = ths.search_symbols(code)
        if result.data:
            return result.data[0].get('THSCODE', f'USZA{code}')
        return f'USZA{code}'


def search_stock(ths, query):
    """搜索股票，返回 (code, name, thscode)"""
    result = ths.search_symbols(query)
    if result.data:
        r = result.data[0]
        return r['Code'], r['Name'], r['THSCODE']
    return None, None, None


def is_limit_up_locked(ths, thscode):
    """
    一字板判定：
    1. 开盘价 ≈ 涨停价（昨收 * 1.10 或 1.20）
    2. 卖一档无挂单 或 买一封单远大于卖一
    """
    try:
        quote = ths.market_data_cn(thscode)
        if not quote.data:
            return False
        q = quote.data[0]

        prev_close = q.get('昨收价', 0)
        open_price = q.get('开盘价', 0)
        if not prev_close or not open_price:
            return False

        code = thscode[-6:]
        limit_pct = 0.20 if code.startswith(('3', '68')) else 0.10
        limit_up_price = round(prev_close * (1 + limit_pct), 2)

        if open_price < limit_up_price * 0.999:
            return False

        depth = ths.depth(thscode)
        if not depth.data:
            return True

        d = depth.data[0]
        ask_vol = d.get('卖1量', 0) or 0
        bid_vol = d.get('买1量', 0) or 0

        if ask_vol == 0:
            return True
        if bid_vol > ask_vol * 5:
            return True

        return False
    except Exception as e:
        print(f'  [WARN] 一字板判定异常: {e}')
        return False


def get_price_at_935(ths, thscode):
    """获取 9:35 时刻的成交价"""
    try:
        data = ths.intraday_data(thscode)
        if data.data:
            for bar in data.data:
                t = bar.get('时间')
                if t and hasattr(t, 'hour') and t.hour == 9 and t.minute == 35:
                    return bar.get('收盘价') or bar.get('价格')
            for bar in data.data:
                t = bar.get('时间')
                if t and hasattr(t, 'hour') and (t.hour == 9 and t.minute >= 30) or (t.hour == 10):
                    return bar.get('收盘价') or bar.get('价格')
        quote = ths.market_data_cn(thscode)
        if quote.data:
            return quote.data[0].get('价格')
    except Exception as e:
        print(f'  [WARN] 获取9:35价格异常: {e}')
    return None


def get_latest_close(ths, thscode, count=1):
    """获取最新收盘价"""
    try:
        k = ths.klines(thscode, interval='day', count=count)
        if k.data:
            latest = k.data[-1]
            date_str = latest['时间'].strftime('%Y-%m-%d') if hasattr(latest['时间'], 'strftime') else str(latest['时间'])[:10]
            return date_str, latest['收盘价']
    except Exception as e:
        print(f'  [WARN] 获取收盘价异常: {e}')
    return None, None


def compute_repeat_stats(groups):
    stat_map = {}
    for g in groups:
        for s in g['stocks']:
            if s['code'] not in stat_map:
                stat_map[s['code']] = {
                    'code': s['code'], 'name': s['name'],
                    'recommend_count': 0, 'first_date': '', 'last_date': ''
                }
            st = stat_map[s['code']]
            st['recommend_count'] = max(st['recommend_count'], s['recommend_count'])
            dates = sorted(s['recommend_dates'])
            st['first_date'] = dates[0]
            st['last_date'] = dates[-1]
    return sorted(
        [v for v in stat_map.values() if v['recommend_count'] >= 2],
        key=lambda x: x['recommend_count'], reverse=True
    )


# ── 主流程 ──

def cmd_update_close():
    """更新所有持仓股的最新收盘价"""
    data = load_data()
    ths = get_ths()
    updated = 0

    for group in data['groups']:
        for stock in group['stocks']:
            if stock['buy_status'] != 'success' or not stock['buy_price']:
                continue

            code = stock['code']
            thscode = resolve_thscode(ths, code)
            date_str, close = get_latest_close(ths, thscode)

            if close and date_str:
                existing = [p for p in stock['daily_prices'] if p['date'] == date_str]
                if existing:
                    existing[0]['close'] = close
                else:
                    stock['daily_prices'].append({'date': date_str, 'close': close})
                    stock['daily_prices'].sort(key=lambda p: p['date'])

                pnl = ((close - stock['buy_price']) / stock['buy_price'] * 100)
                sign = '+' if pnl >= 0 else ''
                print(f'  {stock["name"]}({code}): {close}  收益 {sign}{pnl:.2f}%')
                updated += 1

            time.sleep(0.3)

    data['repeat_stats'] = compute_repeat_stats(data['groups'])
    save_data(data)
    ths.disconnect()
    print(f'\n[完成] 更新了 {updated} 只股票的收盘价')


def cmd_buy():
    """9:35 获取买入价"""
    data = load_data()
    ths = get_ths()
    today = datetime.date.today().strftime('%Y-%m-%d')

    for group in data['groups']:
        for stock in group['stocks']:
            if stock['first_recommend_date'] != today:
                continue
            if stock['buy_price'] is not None:
                continue

            code = stock['code']
            thscode = resolve_thscode(ths, code)
            print(f'  处理 {stock["name"]}({code})...')

            if is_limit_up_locked(ths, thscode):
                stock['buy_status'] = 'failed_limit_up'
                stock['buy_price'] = None
                print(f'    → 一字板，买入失败')
                continue

            price = get_price_at_935(ths, thscode)
            if price:
                stock['buy_status'] = 'success'
                stock['buy_price'] = round(float(price), 2)
                date_str, close = get_latest_close(ths, thscode)
                if close:
                    stock['daily_prices'].append({'date': date_str, 'close': close})
                print(f'    → 买入成功 @ {stock["buy_price"]}')
            else:
                print(f'    → 无法获取价格')

            time.sleep(0.3)

    data['repeat_stats'] = compute_repeat_stats(data['groups'])
    save_data(data)
    ths.disconnect()
    print('\n[完成] 买入处理完毕')


def cmd_add(codes_str):
    """添加新推荐股票"""
    data = load_data()
    ths = get_ths()

    today = datetime.date.today()
    date_str = today.strftime('%Y-%m-%d')
    group_id = 'group_' + date_str.replace('-', '')

    group = None
    for g in data['groups']:
        if g['id'] == group_id:
            group = g
            break
    if not group:
        group = {
            'id': group_id,
            'label': f'{today.month}月{today.day}日 推荐组',
            'date': date_str,
            'stocks': []
        }
        data['groups'].insert(0, group)

    codes = [c.strip() for c in codes_str.split(',') if c.strip()]

    for code in codes:
        code = code.replace(' ', '')[:6]
        if not code.isdigit():
            print(f'  [跳过] 无效代码: {code}')
            continue

        found_code, name, thscode = search_stock(ths, code)
        if not found_code:
            print(f'  [跳过] 未找到: {code}')
            continue

        all_stocks = [s for g in data['groups'] for s in g['stocks']]
        existing = next((s for s in all_stocks if s['code'] == found_code), None)

        if existing:
            if date_str not in existing['recommend_dates']:
                existing['recommend_dates'].append(date_str)
                existing['recommend_count'] += 1
            if not any(s['code'] == found_code for s in group['stocks']):
                group['stocks'].append(existing)
            print(f'  [重复] {name}({found_code}) 第{existing["recommend_count"]}次推荐')
        else:
            new_stock = {
                'code': found_code, 'name': name,
                'first_recommend_date': date_str,
                'recommend_dates': [date_str],
                'recommend_count': 1,
                'buy_status': 'success',
                'buy_price': None,
                'daily_prices': []
            }
            group['stocks'].insert(0, new_stock)
            print(f'  [新增] {name}({found_code})')

        time.sleep(0.3)

    data['repeat_stats'] = compute_repeat_stats(data['groups'])
    save_data(data)
    ths.disconnect()
    print(f'\n[完成] 添加了 {len(codes)} 只股票到 {group["label"]}')
    print('提示: 在 9:35 运行 python3 update.py --buy 获取买入价')


def main():
    parser = argparse.ArgumentParser(description='模拟交易更新脚本')
    parser.add_argument('--buy', action='store_true', help='获取 9:35 买入价')
    parser.add_argument('--add', type=str, help='添加新推荐: --add 002463,600519')
    args = parser.parse_args()

    if args.add:
        cmd_add(args.add)
    elif args.buy:
        cmd_buy()
    else:
        cmd_update_close()


if __name__ == '__main__':
    main()
