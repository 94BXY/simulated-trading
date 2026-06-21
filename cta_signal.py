# -*- coding: utf-8 -*-
"""
CTA 趋势信号系统
================
每天 10:00 和 14:30 各扫一次，有信号分析后再操作。

用法：
  python cta_signal.py                     # 扫描全部池子（沪深300+中证500+创业板）
  python cta_signal.py --pool hs300        # 只扫沪深300
  python cta_signal.py --code 000001       # 看单只股票
  python cta_signal.py --add               # 买入信号加入模拟交易
  python cta_signal.py --deploy            # 生成 cta.html 并部署
"""

import argparse, datetime, os, sys, time, json, re
import pandas as pd, numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CTA_HTML = os.path.join(SCRIPT_DIR, 'cta.html')

def get_ths():
    from thsdk import THS
    ths = THS()
    ths.connect()
    return ths

def fetch_kline(ths, code, days=80):
    thscode = f'USHA{code}' if code.startswith(('6','5')) else f'USZA{code}'
    end = datetime.datetime.now()
    start = end - datetime.timedelta(days=days+30)
    try:
        result = ths.klines(thscode, start_time=start, end_time=end, interval='day')
        if not result.data:
            return None
        df = pd.DataFrame(result.data)
        df.columns = ['date','close','volume','turnover','open','high','low']
        for col in ['close','open','high','low','volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except:
        return None

def compute_indicators(df):
    close = df['close']
    ma5 = close.rolling(5).mean()
    ma10 = close.rolling(10).mean()
    ma20 = close.rolling(20).mean()
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi = 100 - (100 / (1 + gain / (loss + 1e-10)))
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9).mean()
    macd_bar = (dif - dea) * 2
    return {'ma5':ma5,'ma10':ma10,'ma20':ma20,'rsi':rsi,'dif':dif,'dea':dea,'macd_bar':macd_bar}

def generate_signal(ind, idx=-1):
    ma5 = ind['ma5'].iloc[idx]
    ma20 = ind['ma20'].iloc[idx]
    rsi = ind['rsi'].iloc[idx]
    macd_bar = ind['macd_bar'].iloc[idx]
    macd_prev = ind['macd_bar'].iloc[idx-1]
    golden = ma5 > ma20
    death = ma5 < ma20
    if death or rsi > 80:
        return 'SELL', f'Death={death} RSI={rsi:.0f}'
    elif golden and rsi < 70 and macd_bar > 0 and macd_prev <= 0:
        return 'BUY', f'Golden+RSI={rsi:.0f}+MACD red'
    elif golden and rsi < 70:
        return 'WATCH', f'Golden+RSI={rsi:.0f}(wait MACD)'
    else:
        return 'HOLD', f'MA5={ma5:.2f} MA20={ma20:.2f}'

def scan_stock(ths, code, name=''):
    df = fetch_kline(ths, code)
    if df is None or len(df) < 25:
        return None
    ind = compute_indicators(df)
    signal, reason = generate_signal(ind)
    close = df['close'].iloc[-1]
    prev_close = df['close'].iloc[-2] if len(df) > 1 else close
    pct = (close / prev_close - 1) * 100
    return {'code':code,'name':name,'close':float(close),'pct':float(pct),
            'ma5':float(ind['ma5'].iloc[-1]),'ma20':float(ind['ma20'].iloc[-1]),
            'rsi':float(ind['rsi'].iloc[-1]),'macd':float(ind['macd_bar'].iloc[-1]),
            'signal':signal,'reason':reason}

def get_pool_codes(pool='hs300'):
    import pywencai
    pool_map = {'hs300':'沪深300','zz500':'中证500','cyb':'创业板','kc':'科创板'}
    name = pool_map.get(pool, pool)
    df = pywencai.get(query=f'{name}成分股', query_type='stock')
    if df is None: return []
    code_col = [c for c in df.columns if '代码' in c]
    name_col = [c for c in df.columns if '简称' in c]
    if not code_col: return []
    codes = df[code_col[0]].astype(str).str.replace(r'\.\w+$','',regex=True).tolist()
    names = df[name_col[0]].tolist() if name_col else ['']*len(codes)
    return list(zip(codes, names))

def scan_pool(ths, pool='hs300'):
    print(f'  Scanning {pool}...')
    stock_list = get_pool_codes(pool)
    results = []
    for i, (code, name) in enumerate(stock_list):
        r = scan_stock(ths, code, name)
        if r:
            r['pool'] = pool.upper()
            results.append(r)
        if (i+1) % 50 == 0:
            print(f'    {i+1}/{len(stock_list)}...')
    return results

def scan_all(pools=None):
    if pools is None:
        pools = ['hs300','zz500','cyb']
    ths = get_ths()
    all_results = []
    for p in pools:
        results = scan_pool(ths, p)
        all_results.extend(results)
        print(f'  {p}: {len(results)} stocks scanned')
    return all_results

def print_results(results):
    buys = [r for r in results if r['signal'] == 'BUY']
    watches = [r for r in results if r['signal'] == 'WATCH']
    sells = [r for r in results if r['signal'] == 'SELL']

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    print(f'\n{"="*70}')
    print(f'  CTA Trend Signal - {now}')
    print(f'{"="*70}')

    if buys:
        print(f'\nBUY ({len(buys)})')
        print(f'{"Code":>8} {"Name":>8} {"Pool":>6} {"Close":>7} {"Chg":>6} {"RSI":>5} {"MACD":>7}')
        print('-'*60)
        for r in sorted(buys, key=lambda x: x['rsi']):
            print(f'{r["code"]:>8} {r["name"]:>8} {r["pool"]:>6} {r["close"]:>7.2f} {r["pct"]:>+5.2f}% {r["rsi"]:>5.1f} {r["macd"]:>7.3f}')

    if watches:
        print(f'\nWATCH ({len(watches)}) - top 15')
        for r in sorted(watches, key=lambda x: x['rsi'])[:15]:
            print(f'  {r["code"]} {r["name"]:>6} {r["pool"]:>6} RSI={r["rsi"]:.0f} MACD={r["macd"]:.3f}')

    print(f'\nStats: BUY={len(buys)} WATCH={len(watches)} SELL={len(sells)}')
    return buys, watches, sells

def deploy_to_html(results):
    """Embed CTA data into cta.html"""
    buys = [r for r in results if r['signal'] == 'BUY']
    watches = [r for r in results if r['signal'] == 'WATCH']
    sells = [r for r in results if r['signal'] == 'SELL']
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

    cta_data = {
        'buys': sorted(buys, key=lambda x: x['rsi']),
        'watches': sorted(watches, key=lambda x: x['rsi']),
        'sells': sorted(sells, key=lambda x: -x['rsi']),
        'updateTime': now,
    }

    with open(CTA_HTML, 'r', encoding='utf-8') as f:
        html = f.read()

    new_data = json.dumps(cta_data, ensure_ascii=False, indent=2)
    html = re.sub(r'const CTA_DATA = .*?;', f'const CTA_DATA = {new_data};', html, flags=re.DOTALL)

    with open(CTA_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'\n[OK] Updated {CTA_HTML}')

def deploy_wrangler():
    """Deploy to Cloudflare Pages"""
    os.system(f'cd "{SCRIPT_DIR}" && npx wrangler pages deploy . --project-name=simulated-trading')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--pool', default='all', help='hs300/zz500/cyb/all')
    parser.add_argument('--code', help='Scan single stock')
    parser.add_argument('--add', action='store_true', help='Add buy signals to sim trading')
    parser.add_argument('--deploy', action='store_true', help='Update cta.html and deploy')
    args = parser.parse_args()

    if args.code:
        ths = get_ths()
        r = scan_stock(ths, args.code)
        if r:
            print(f'\n{r["code"]} {r["name"]}')
            print(f'  Close: {r["close"]:.2f}  Chg: {r["pct"]:+.2f}%')
            print(f'  MA5: {r["ma5"]:.2f}  MA20: {r["ma20"]:.2f}')
            print(f'  RSI: {r["rsi"]:.1f}  MACD: {r["macd"]:.3f}')
            print(f'  Signal: {r["signal"]}')
            print(f'  Reason: {r["reason"]}')
        else:
            print('Failed to get data')
    else:
        pools = ['hs300','zz500','cyb'] if args.pool == 'all' else [args.pool]
        results = scan_all(pools)
        buys, watches, sells = print_results(results)

        # Always update cta.html
        deploy_to_html(results)

        # Optionally add to sim trading
        if args.add and buys:
            codes = [r['code'] for r in buys[:5]]
            code_str = ','.join(codes)
            print(f'\nAdding to sim: {code_str}')
            os.system(f'python "{os.path.join(SCRIPT_DIR, "update.py")}" --add {code_str}')

        # Optionally deploy
        if args.deploy:
            deploy_wrangler()
