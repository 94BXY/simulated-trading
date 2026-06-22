# -*- coding: utf-8 -*-
"""
AI量化每日更新脚本
==================
1. 获取股票池
2. 训练/更新模型
3. 预测评分
4. 执行交易信号
5. 生成复盘
6. 更新HTML页面
"""
import sys
import os
import datetime
import json

# 添加路径
sys.path.insert(0, os.path.dirname(__file__))

from ai_quant.predictor import AIPredictor
from ai_quant.backtester import Backtester

def run_daily_update():
    """执行每日更新"""
    print("=" * 60)
    print(f"  AI量化系统 - 每日更新")
    print(f"  时间: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 60)
    
    # 初始化预测器
    predictor = AIPredictor(data_dir=r'E:\素材\模拟交易')
    
    # 1. 获取股票池
    print("\n[1/6] 获取股票池...")
    stock_pool = predictor.get_stock_pool()
    print(f"  股票池: {len(stock_pool)} 只")
    
    # 2. 训练模型（首次或每周更新）
    model_path = os.path.join(os.path.dirname(__file__), 'ai_quant', 'models', 'factor_model.pt')
    need_train = not os.path.exists(model_path)
    
    # 检查是否需要重新训练（每周一次）
    if os.path.exists(model_path):
        mtime = os.path.getmtime(model_path)
        days_since_train = (datetime.datetime.now().timestamp() - mtime) / 86400
        if days_since_train > 7:
            need_train = True
    
    if need_train:
        print("\n[2/6] 训练模型...")
        predictor.train_model(stock_pool)
    else:
        print("\n[2/6] 模型已存在，跳过训练")
    
    # 3. 预测评分
    print("\n[3/6] 预测评分...")
    predictions = predictor.predict_stocks(stock_pool)
    print(f"  预测完成: {len(predictions)} 只")
    
    if predictions:
        print("\n  Top 5 推荐:")
        for i, p in enumerate(predictions[:5]):
            print(f"    {i+1}. {p['code']} {p['name']} 评分:{p['score']:.4f} 价格:{p['close']:.2f}")
    
    # 4. 生成交易信号
    print("\n[4/6] 生成交易信号...")
    today = datetime.date.today()
    signals = predictor.generate_signals(predictions, today)
    
    print(f"  买入信号: {len(signals['buy'])} 只")
    print(f"  卖出信号: {len(signals['sell'])} 只")
    print(f"  持仓: {len(signals['hold'])} 只")
    
    # 5. 执行交易
    print("\n[5/6] 执行交易...")
    trade_results = predictor.execute_signals(signals, today)
    
    for result in trade_results:
        status = "✓" if result['success'] else "✗"
        print(f"    {status} {result['message']}")
    
    # 6. 记录每日净值
    prices = {p['code']: p['close'] for p in predictions}
    predictor.backtester.record_daily(today, prices)
    
    # 7. 生成复盘
    print("\n[6/6] 生成复盘...")
    review = predictor.generate_review(today, predictions, trade_results)
    
    # 保存复盘日志
    log_dir = os.path.join(os.path.dirname(__file__), 'ai_quant', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"review_{today}.json")
    
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(review, f, ensure_ascii=False, indent=2)
    print(f"  复盘已保存: {log_path}")
    
    # 8. 保存数据
    predictor.save_data()
    
    # 9. 生成HTML数据
    generate_html_data(predictor, predictions, signals, review)
    
    # 10. 更新HTML
    update_html()
    
    print("\n" + "=" * 60)
    print("  更新完成！")
    print("=" * 60)
    
    return predictor, predictions, review


def generate_html_data(predictor, predictions, signals, review):
    """生成HTML数据文件"""
    data = {
        'updateTime': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        'predictions': predictions[:50],  # 前50只
        'signals': {
            'buy': [{'code': s['code'], 'name': s['name'], 'close': s['close'], 'score': s['score']} 
                   for s in signals['buy']],
            'sell': [{'code': s['code'], 'name': s['name'], 'close': s['close'], 'score': s['score']} 
                    for s in signals['sell']],
        },
        'portfolio': {
            'capital': predictor.backtester.capital,
            'positions': predictor.backtester.positions,
            'total_value': predictor.backtester.get_total_value(
                {p['code']: p['close'] for p in predictions}
            )
        },
        'performance': predictor.backtester.get_performance(),
        'review': review
    }
    
    data_path = os.path.join(r'E:\素材\模拟交易', 'ai_quant_data.json')
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"  数据文件已生成: {data_path}")


def update_html():
    """更新HTML文件"""
    html_path = os.path.join(r'E:\素材\模拟交易', 'ai_quant.html')
    data_path = os.path.join(r'E:\素材\模拟交易', 'ai_quant_data.json')
    
    # 读取数据
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 生成HTML
    html_content = generate_html_template(data)
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"  HTML已更新: {html_path}")


def generate_html_template(data):
    """生成HTML模板"""
    predictions = data.get('predictions', [])
    signals = data.get('signals', {})
    portfolio = data.get('portfolio', {})
    performance = data.get('performance', {})
    review = data.get('review', {})
    
    # 持仓HTML
    positions_html = ''
    for code, pos in portfolio.get('positions', {}).items():
        stock = next((p for p in predictions if p['code'] == code), None)
        current_price = stock['close'] if stock else pos['buy_price']
        profit = (current_price - pos['buy_price']) / pos['buy_price'] * 100
        profit_class = 'positive' if profit >= 0 else 'negative'
        
        # T+1判断
        buy_date = datetime.datetime.strptime(pos['buy_date'], '%Y-%m-%d').date()
        can_sell = datetime.date.today() > buy_date
        sell_status = '✅' if can_sell else '❌'
        
        positions_html += f'''
        <tr>
            <td>{code}</td>
            <td>{pos['name']}</td>
            <td>{pos['qty']}</td>
            <td>{pos['buy_price']:.2f}</td>
            <td>{current_price:.2f}</td>
            <td class="{profit_class}">{profit:+.2f}%</td>
            <td>{sell_status}</td>
        </tr>'''
    
    # 推荐HTML
    buy_html = ''
    for stock in signals.get('buy', []):
        buy_html += f'''
        <tr>
            <td>{stock['code']}</td>
            <td>{stock['name']}</td>
            <td>{stock['close']:.2f}</td>
            <td>{stock['score']:.4f}</td>
            <td><span class="badge badge-buy">买入</span></td>
        </tr>'''
    
    # 绩效HTML
    perf = performance
    
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI 量化预测系统</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
:root {{
    --bg: #0f0f23; --card: #1a1a3e; --border: #2a2a5e;
    --text: #e0e0ff; --text-dim: #8888aa;
    --green: #00ff88; --red: #ff4444; --blue: #4488ff; --amber: #ffaa00;
    --radius: 8px;
}}
body {{ font-family: system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text); padding: 20px; max-width: 1200px; margin: 0 auto; }}
h1 {{ font-size: 24px; margin-bottom: 24px; display: flex; align-items: center; gap: 10px; }}
h2 {{ font-size: 18px; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }}
.btn {{ padding: 10px 20px; background: var(--blue); color: #fff; border: none; border-radius: var(--radius); cursor: pointer; text-decoration: none; font-size: 14px; }}
.btn:hover {{ opacity: 0.85; }}
.card {{ background: var(--card); border-radius: var(--radius); padding: 20px; margin-bottom: 16px; border: 1px solid var(--border); }}
table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); }}
th {{ color: var(--text-dim); font-weight: 600; }}
.positive {{ color: var(--green); }}
.negative {{ color: var(--red); }}
.badge {{ padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 700; }}
.badge-buy {{ background: rgba(0,255,136,0.2); color: var(--green); }}
.badge-sell {{ background: rgba(255,68,68,0.2); color: var(--red); }}
.perf-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; }}
.perf-item {{ text-align: center; }}
.perf-value {{ font-size: 24px; font-weight: 700; }}
.perf-label {{ font-size: 12px; color: var(--text-dim); }}
.chart-container {{ height: 300px; margin-top: 16px; }}
</style>
</head>
<body>

<h1>🤖 AI 量化预测系统</h1>
<div style="display:flex;gap:12px;margin-bottom:24px;">
    <a href="index.html" class="btn">← 追踪系统</a>
    <a href="cta.html" class="btn" style="background:#00c853;">📊 CTA信号</a>
</div>

<div class="card">
    <h2>📈 今日AI推荐</h2>
    <table>
        <thead>
            <tr><th>代码</th><th>名称</th><th>价格</th><th>评分</th><th>信号</th></tr>
        </thead>
        <tbody>{buy_html}</tbody>
    </table>
</div>

<div class="card">
    <h2>💼 当前持仓</h2>
    <p style="color:var(--text-dim);margin-bottom:12px;">可用资金: ¥{portfolio.get('capital', 0):,.2f} | 总资产: ¥{portfolio.get('total_value', 0):,.2f}</p>
    <table>
        <thead>
            <tr><th>代码</th><th>名称</th><th>持仓</th><th>成本</th><th>现价</th><th>盈亏</th><th>可卖</th></tr>
        </thead>
        <tbody>{positions_html if positions_html else '<tr><td colspan="7" style="text-align:center;color:var(--text-dim);">暂无持仓</td></tr>'}</tbody>
    </table>
</div>

<div class="card">
    <h2>📊 绩效统计</h2>
    <div class="perf-grid">
        <div class="perf-item">
            <div class="perf-value {'positive' if perf.get('total_return', 0) >= 0 else 'negative'}">{perf.get('total_return', 0):+.2f}%</div>
            <div class="perf-label">总收益</div>
        </div>
        <div class="perf-item">
            <div class="perf-value {'positive' if perf.get('annual_return', 0) >= 0 else 'negative'}">{perf.get('annual_return', 0):+.2f}%</div>
            <div class="perf-label">年化收益</div>
        </div>
        <div class="perf-item">
            <div class="perf-value">{perf.get('sharpe_ratio', 0):.2f}</div>
            <div class="perf-label">夏普比率</div>
        </div>
        <div class="perf-item">
            <div class="perf-value negative">{perf.get('max_drawdown', 0):.2f}%</div>
            <div class="perf-label">最大回撤</div>
        </div>
        <div class="perf-item">
            <div class="perf-value">{perf.get('win_rate', 0):.1f}%</div>
            <div class="perf-label">胜率</div>
        </div>
        <div class="perf-item">
            <div class="perf-value">{perf.get('total_trades', 0)}</div>
            <div class="perf-label">总交易次数</div>
        </div>
    </div>
</div>

<div class="card">
    <h2>📝 今日复盘</h2>
    <div style="color:var(--text-dim);">
        <p>分析股票: {review.get('market_summary', {}).get('total_stocks_analyzed', 0)} 只</p>
        <p>今日交易: {len(review.get('trades', []))} 笔</p>
        <h3 style="margin-top:12px;color:var(--text);">学习心得:</h3>
        <ul style="margin-left:20px;">
            {''.join(f'<li>{lesson}</li>' for lesson in review.get('lessons', []))}
        </ul>
    </div>
</div>

<div class="card">
    <h2>🔬 因子评分分布</h2>
    <div class="chart-container">
        <canvas id="scoreChart"></canvas>
    </div>
</div>

<script>
// 评分分布图
const ctx = document.getElementById('scoreChart').getContext('2d');
const scores = {json.dumps([p['score'] for p in predictions[:30]])};
const labels = {json.dumps([p['name'] for p in predictions[:30]])};

new Chart(ctx, {{
    type: 'bar',
    data: {{
        labels: labels,
        datasets: [{{
            label: 'AI评分',
            data: scores,
            backgroundColor: scores.map(s => s >= 0 ? 'rgba(0,255,136,0.6)' : 'rgba(255,68,68,0.6)'),
            borderColor: scores.map(s => s >= 0 ? '#00ff88' : '#ff4444'),
            borderWidth: 1
        }}]
    }},
    options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
            legend: {{ display: false }}
        }},
        scales: {{
            x: {{ 
                ticks: {{ color: '#8888aa', maxRotation: 45 }},
                grid: {{ color: 'rgba(255,255,255,0.05)' }}
            }},
            y: {{ 
                ticks: {{ color: '#8888aa' }},
                grid: {{ color: 'rgba(255,255,255,0.05)' }}
            }}
        }}
    }}
}});
</script>

</body>
</html>'''


if __name__ == '__main__':
    run_daily_update()
