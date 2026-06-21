# -*- coding: utf-8 -*-
"""
CTA 自动刷新脚本
================
扫描全市场股票池，生成 CTA 趋势信号，更新 cta_data.json 和 cta.html。

用法：
  python cta_refresh.py                  # 立即执行一次扫描
  python cta_refresh.py --schedule       # 定时模式：10:00 和 14:30 自动刷新
  python cta_refresh.py --pool hs300     # 只扫描沪深300
  python cta_refresh.py --dry-run        # 测试模式，不实际连接数据源

依赖：thsdk, pandas, pywencai, numpy
"""

import argparse
import datetime
import json
import os
import re
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, 'cta_data.json')
CTA_HTML = os.path.join(SCRIPT_DIR, 'cta.html')

# ── 定时配置 ──
SCHEDULE_TIMES = [(10, 0), (14, 30)]  # 每天 10:00 和 14:30


def is_trading_day():
    """判断今天是否为交易日（周一至周五，不含节假日）"""
    today = datetime.date.today()
    if today.weekday() >= 5:
        return False
    # TODO: 可扩展节假日判断
    return True


def next_schedule_time():
    """返回下一次调度时间"""
    now = datetime.datetime.now()
    today = now.date()
    for hour, minute in SCHEDULE_TIMES:
        target = datetime.datetime.combine(today, datetime.time(hour, minute))
        if now < target:
            return target
    tomorrow = today + datetime.timedelta(days=1)
    return datetime.datetime.combine(
        tomorrow, datetime.time(SCHEDULE_TIMES[0][0], SCHEDULE_TIMES[0][1])
    )


def wait_until(target_time):
    """等待到指定时间"""
    while True:
        now = datetime.datetime.now()
        diff = (target_time - now).total_seconds()
        if diff <= 0:
            return
        if diff > 120:
            print(f'  ⏳ 等待 {int(diff // 60)} 分钟...')
            time.sleep(60)
        else:
            time.sleep(max(diff, 0.1))


def run_scan(pools=None):
    """执行一次 CTA 全量扫描"""
    if pools is None:
        pools = ['hs300', 'zz500', 'cyb']

    print('=' * 60)
    print(f'  CTA 趋势信号刷新 - {datetime.datetime.now():%Y-%m-%d %H:%M:%S}')
    print(f'  扫描池: {", ".join(pools).upper()}')
    print('=' * 60)

    # 导入 cta_signal 模块
    sys.path.insert(0, SCRIPT_DIR)
    import cta_signal

    # 执行扫描
    print('\n[1/4] 连接数据源...')
    results = cta_signal.scan_all(pools)
    print(f'  ✅ 扫描完成，共 {len(results)} 只股票')

    # 分类统计
    buys = sorted(
        [r for r in results if r['signal'] == 'BUY'],
        key=lambda x: x['rsi']
    )
    watches = sorted(
        [r for r in results if r['signal'] == 'WATCH'],
        key=lambda x: x['rsi']
    )
    sells = sorted(
        [r for r in results if r['signal'] == 'SELL'],
        key=lambda x: -x['rsi']
    )

    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

    print(f'\n  📊 信号统计:')
    print(f'     🔴 BUY   = {len(buys)}')
    print(f'     🟡 WATCH = {len(watches)}')
    print(f'     🟢 SELL  = {len(sells)}')

    # 打印 BUY 信号
    if buys:
        print(f'\n  ── BUY 信号 ({len(buys)}) ──')
        for r in buys[:10]:
            print(f'    {r["code"]} {r["name"]:>8} | {r["close"]:.2f} | '
                  f'RSI={r["rsi"]:.1f} | MACD={r["macd"]:.3f}')
        if len(buys) > 10:
            print(f'    ... 还有 {len(buys) - 10} 只')

    # 保存 cta_data.json
    print('\n[2/4] 保存 cta_data.json...')
    cta_data = {
        'buys': buys,
        'watches': watches,
        'sells': sells,
        'updateTime': now_str,
        'scanPools': pools,
        'totalCount': len(results),
    }
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(cta_data, f, ensure_ascii=False, indent=2)
    print(f'  ✅ 已保存 {DATA_FILE}')

    # 更新 cta.html
    print('\n[3/4] 更新 cta.html...')
    update_cta_html(cta_data)

    # 完成
    print(f'\n[4/4] 刷新完成 ✅')
    print(f'  时间: {now_str}')
    print(f'  数据: {DATA_FILE}')
    print(f'  页面: {CTA_HTML}')
    print('=' * 60)

    return cta_data


def update_cta_html(cta_data):
    """更新 cta.html 中嵌入的 CTA_DATA"""
    if not os.path.exists(CTA_HTML):
        print(f'  ⚠️  cta.html 不存在，将生成新文件')
        generate_cta_html(cta_data)
        return

    with open(CTA_HTML, 'r', encoding='utf-8') as f:
        html = f.read()

    new_json = json.dumps(cta_data, ensure_ascii=False, indent=2)
    html = re.sub(
        r'const CTA_DATA = .*?;',
        f'const CTA_DATA = {new_json};',
        html,
        flags=re.DOTALL
    )

    with open(CTA_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'  ✅ 已更新 {CTA_HTML}')


def generate_cta_html(cta_data):
    """从头生成 cta.html（如果文件不存在）"""
    new_json = json.dumps(cta_data, ensure_ascii=False, indent=2)

    html_template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CTA 趋势信号</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0a0e17; color: #e0e6f0; font-family: -apple-system, 'Segoe UI', sans-serif; min-height: 100vh; }
.header { background: linear-gradient(135deg, #1a237e 0%, #0d47a1 100%); padding: 20px 24px; display: flex; align-items: center; justify-content: space-between; }
.header h1 { font-size: 22px; color: #fff; }
.header .nav { display: flex; gap: 12px; }
.header .nav a { color: #90caf9; text-decoration: none; font-size: 14px; padding: 6px 12px; border-radius: 6px; background: rgba(255,255,255,0.1); }
.header .nav a:hover { background: rgba(255,255,255,0.2); }
.header .nav a.active { background: #448aff; color: #fff; }
.container { max-width: 1200px; margin: 0 auto; padding: 20px; }
.stats-bar { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
.stat-card { flex: 1; min-width: 120px; background: #131a2e; border-radius: 12px; padding: 16px; text-align: center; border: 1px solid #1e2a45; }
.stat-card .num { font-size: 32px; font-weight: 700; }
.stat-card .label { font-size: 12px; color: #78849e; margin-top: 4px; }
.stat-card.buy .num { color: #ff5252; }
.stat-card.watch .num { color: #ffd740; }
.stat-card.sell .num { color: #69f0ae; }
.section { background: #131a2e; border-radius: 12px; margin-bottom: 20px; border: 1px solid #1e2a45; overflow: hidden; }
.section-header { padding: 16px 20px; display: flex; align-items: center; justify-content: space-between; cursor: pointer; }
.section-header h2 { font-size: 16px; display: flex; align-items: center; gap: 8px; }
.section-header .count { background: #1e2a45; padding: 2px 10px; border-radius: 10px; font-size: 13px; color: #78849e; }
.section-body { padding: 0 20px 20px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { text-align: left; padding: 10px 12px; color: #78849e; font-weight: 500; border-bottom: 1px solid #1e2a45; font-size: 12px; }
td { padding: 10px 12px; border-bottom: 1px solid #0f1525; }
tr:hover td { background: rgba(68,138,255,0.05); }
.signal-buy { color: #ff5252; font-weight: 600; }
.signal-watch { color: #ffd740; font-weight: 600; }
.signal-sell { color: #69f0ae; font-weight: 600; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.tag-buy { background: rgba(255,82,82,0.15); color: #ff5252; }
.tag-watch { background: rgba(255,215,64,0.15); color: #ffd740; }
.tag-sell { background: rgba(105,240,174,0.15); color: #69f0ae; }
.tag-pool { background: rgba(68,138,255,0.15); color: #448aff; }
.bar { height: 6px; border-radius: 3px; background: #1e2a45; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.bar-buy { background: linear-gradient(90deg, #ff5252, #ff1744); }
.bar-watch { background: linear-gradient(90deg, #ffd740, #ff9100); }
.bar-sell { background: linear-gradient(90deg, #69f0ae, #00c853); }
.update-time { text-align: center; color: #78849e; font-size: 12px; margin-top: 20px; }
.empty { text-align: center; padding: 40px; color: #78849e; }
.badge { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
.badge-buy { background: #ff5252; }
.badge-watch { background: #ffd740; }
.badge-sell { background: #69f0ae; }
</style>
</head>
<body>
<div class="header">
  <h1>📈 CTA 趋势信号</h1>
  <div class="nav">
    <a href="index.html">📊 模拟交易</a>
    <a href="cta.html" class="active">📈 CTA信号</a>
  </div>
</div>
<div class="container">
  <div class="stats-bar">
    <div class="stat-card buy">
      <div class="num" id="buyCount">-</div>
      <div class="label"><span class="badge badge-buy"></span>买入信号</div>
    </div>
    <div class="stat-card watch">
      <div class="num" id="watchCount">-</div>
      <div class="label"><span class="badge badge-watch"></span>观望</div>
    </div>
    <div class="stat-card sell">
      <div class="num" id="sellCount">-</div>
      <div class="label"><span class="badge badge-sell"></span>卖出信号</div>
    </div>
  </div>
  <div class="section" id="buySection">
    <div class="section-header" onclick="toggle('buyBody')">
      <h2>🔴 买入信号 <span class="count" id="buyTag">0</span></h2>
    </div>
    <div class="section-body" id="buyBody">
      <table>
        <thead><tr>
          <th>代码</th><th>名称</th><th>池</th><th>收盘</th><th>涨幅</th>
          <th>MA5</th><th>MA20</th><th>RSI</th><th>MACD</th><th>强度</th>
        </tr></thead>
        <tbody id="buyTable"></tbody>
      </table>
    </div>
  </div>
  <div class="section" id="watchSection">
    <div class="section-header" onclick="toggle('watchBody')">
      <h2>🟡 观望信号 <span class="count" id="watchTag">0</span></h2>
    </div>
    <div class="section-body" id="watchBody">
      <table>
        <thead><tr>
          <th>代码</th><th>名称</th><th>池</th><th>收盘</th>
          <th>MA5</th><th>MA20</th><th>RSI</th><th>MACD</th>
        </tr></thead>
        <tbody id="watchTable"></tbody>
      </table>
    </div>
  </div>
  <div class="section" id="sellSection">
    <div class="section-header" onclick="toggle('sellBody')">
      <h2>🟢 卖出信号 <span class="count" id="sellTag">0</span></h2>
    </div>
    <div class="section-body" id="sellBody" style="display:none">
      <table>
        <thead><tr>
          <th>代码</th><th>名称</th><th>池</th><th>收盘</th>
          <th>RSI</th><th>原因</th>
        </tr></thead>
        <tbody id="sellTable"></tbody>
      </table>
    </div>
  </div>
  <div class="update-time">更新时间: <span id="updateTime">-</span></div>
</div>
<script>
const CTA_DATA = """ + new_json + """;

function toggle(id) {
  const el = document.getElementById(id);
  el.style.display = el.style.display === 'none' ? '' : 'none';
}

function renderBar(val, max, cls) {
  const pct = Math.min(Math.abs(val) / max * 100, 100);
  return '<div class="bar"><div class="bar-fill ' + cls + '" style="width:' + pct + '%"></div></div>';
}

function render() {
  if (!CTA_DATA) {
    document.getElementById('buyTable').innerHTML = '<tr><td colspan="10" class="empty">暂无数据，请运行 cta_refresh.py 生成</td></tr>';
    return;
  }
  var buys = CTA_DATA.buys || [];
  var watches = CTA_DATA.watches || [];
  var sells = CTA_DATA.sells || [];
  var updateTime = CTA_DATA.updateTime || '-';

  document.getElementById('buyCount').textContent = buys.length;
  document.getElementById('watchCount').textContent = watches.length;
  document.getElementById('sellCount').textContent = sells.length;
  document.getElementById('buyTag').textContent = buys.length;
  document.getElementById('watchTag').textContent = watches.length;
  document.getElementById('sellTag').textContent = sells.length;
  document.getElementById('updateTime').textContent = updateTime;

  var buyHtml = buys.map(function(r) {
    var strength = Math.min((r.rsi / 70 * 0.5 + Math.abs(r.macd) / 10 * 0.5) * 100, 100);
    return '<tr>'
      + '<td><strong>' + r.code + '</strong></td>'
      + '<td>' + r.name + '</td>'
      + '<td><span class="tag tag-pool">' + (r.pool||'-') + '</span></td>'
      + '<td>' + r.close.toFixed(2) + '</td>'
      + '<td class="' + (r.pct>=0?'signal-buy':'signal-sell') + '">' + (r.pct>=0?'+':'') + r.pct.toFixed(2) + '%</td>'
      + '<td>' + r.ma5.toFixed(2) + '</td>'
      + '<td>' + r.ma20.toFixed(2) + '</td>'
      + '<td>' + r.rsi.toFixed(1) + '</td>'
      + '<td>' + r.macd.toFixed(3) + '</td>'
      + '<td style="min-width:80px">' + renderBar(strength, 100, 'bar-buy') + '</td>'
      + '</tr>';
  }).join('');
  document.getElementById('buyTable').innerHTML = buyHtml || '<tr><td colspan="10" class="empty">今日无买入信号</td></tr>';

  var watchHtml = watches.slice(0, 30).map(function(r) {
    return '<tr>'
      + '<td><strong>' + r.code + '</strong></td>'
      + '<td>' + r.name + '</td>'
      + '<td><span class="tag tag-pool">' + (r.pool||'-') + '</span></td>'
      + '<td>' + r.close.toFixed(2) + '</td>'
      + '<td>' + r.ma5.toFixed(2) + '</td>'
      + '<td>' + r.ma20.toFixed(2) + '</td>'
      + '<td>' + r.rsi.toFixed(1) + '</td>'
      + '<td>' + r.macd.toFixed(3) + '</td>'
      + '</tr>';
  }).join('');
  document.getElementById('watchTable').innerHTML = watchHtml || '<tr><td colspan="8" class="empty">无观望信号</td></tr>';

  var sellHtml = sells.slice(0, 20).map(function(r) {
    return '<tr>'
      + '<td><strong>' + r.code + '</strong></td>'
      + '<td>' + r.name + '</td>'
      + '<td><span class="tag tag-pool">' + (r.pool||'-') + '</span></td>'
      + '<td>' + r.close.toFixed(2) + '</td>'
      + '<td>' + r.rsi.toFixed(1) + '</td>'
      + '<td style="font-size:12px;color:#78849e">' + (r.reason||'') + '</td>'
      + '</tr>';
  }).join('');
  document.getElementById('sellTable').innerHTML = sellHtml || '<tr><td colspan="6" class="empty">无卖出信号</td></tr>';
}

render();
</script>
</body>
</html>"""

    with open(CTA_HTML, 'w', encoding='utf-8') as f:
        f.write(html_template)
    print(f'  ✅ 已生成 {CTA_HTML}')


def schedule_mode(pools=None):
    """定时模式：在 10:00 和 14:30 自动执行"""
    print('=' * 60)
    print('  CTA 定时刷新模式')
    print(f'  调度时间: {", ".join(f"{h:02d}:{m:02d}" for h, m in SCHEDULE_TIMES)}')
    print('  按 Ctrl+C 退出')
    print('=' * 60)

    while True:
        now = datetime.datetime.now()
        today = now.date()

        if not is_trading_day():
            print(f'\n⏭️  {today} 非交易日，跳过')
            tomorrow_950 = datetime.datetime.combine(
                today + datetime.timedelta(days=1),
                datetime.time(9, 50)
            )
            wait_until(tomorrow_950)
            continue

        target = None
        for hour, minute in SCHEDULE_TIMES:
            t = datetime.datetime.combine(today, datetime.time(hour, minute))
            if now < t:
                target = t
                break

        if target is None:
            target = datetime.datetime.combine(
                today + datetime.timedelta(days=1),
                datetime.time(SCHEDULE_TIMES[0][0], SCHEDULE_TIMES[0][1])
            )
            print(f'\n📅 今日调度已结束，下次: {target:%Y-%m-%d %H:%M}')
        else:
            print(f'\n📅 下次扫描: {target:%Y-%m-%d %H:%M}')

        wait_until(target)

        if not is_trading_day():
            print(f'⏭️  {target.date()} 非交易日，跳过')
            continue

        try:
            run_scan(pools)
        except Exception as e:
            print(f'\n❌ 扫描失败: {e}')
            import traceback
            traceback.print_exc()

        time.sleep(60)


def main():
    parser = argparse.ArgumentParser(description='CTA 趋势信号自动刷新')
    parser.add_argument('--schedule', action='store_true',
                        help='定时模式：10:00 和 14:30 自动刷新')
    parser.add_argument('--pool', default='all',
                        help='扫描池: hs300/zz500/cyb/all (默认 all)')
    parser.add_argument('--dry-run', action='store_true',
                        help='测试模式，不连接数据源')
    args = parser.parse_args()

    pools = ['hs300', 'zz500', 'cyb'] if args.pool == 'all' else [args.pool]

    if args.dry_run:
        print('🧪 测试模式')
        print(f'  扫描池: {pools}')
        print(f'  数据文件: {DATA_FILE}')
        print(f'  HTML文件: {CTA_HTML}')
        print(f'  交易日: {is_trading_day()}')
        print(f'  下次调度: {next_schedule_time()}')
        empty_data = {
            'buys': [],
            'watches': [],
            'sells': [],
            'updateTime': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
            'scanPools': pools,
            'totalCount': 0,
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(empty_data, f, ensure_ascii=False, indent=2)
        print(f'  ✅ 已生成空 {DATA_FILE}')
        generate_cta_html(empty_data)
        return

    if args.schedule:
        schedule_mode(pools)
    else:
        run_scan(pools)


if __name__ == '__main__':
    main()
