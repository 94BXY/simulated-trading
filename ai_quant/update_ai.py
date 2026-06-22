# -*- coding: utf-8 -*-
"""
AI量化预测 - 每日更新脚本
=========================
1. 获取股票数据
2. 训练/加载模型
3. 预测评分
4. 更新持仓
5. 生成HTML
"""

import sys
import os
import json
import argparse
from datetime import datetime

# 添加路径
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, r'E:\素材\pytorch-quant')

from factor_engine import compute_factors, get_factor_columns, prepare_training_data
from model_trainer import train_model, save_model, load_model
from predictor import predict_stock_pool, get_stock_pool, fetch_stock_data
from backtester import Backtester


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_FILE = os.path.join(PROJECT_DIR, 'ai_trading.json')
HTML_FILE = os.path.join(PROJECT_DIR, 'ai_quant.html')
MODEL_PATH = os.path.join(SCRIPT_DIR, 'models', 'factor_model.pt')


def train_new_model():
    """训练新模型"""
    print("\n[1/4] 获取训练数据...")
    from data_utils import get_multi_stocks_data
    
    # 使用更多股票训练
    symbols = get_stock_pool()[:50]  # 用前50只训练
    stock_dict = get_multi_stocks_data(symbols)
    print(f"  获取了 {len(stock_dict)} 只股票数据")
    
    print("\n[2/4] 计算因子...")
    X, y, scaler = prepare_training_data(stock_dict)
    if X is None:
        print("  数据不足，无法训练")
        return None, None
    
    print(f"  训练样本: {len(X)}")
    
    print("\n[3/4] 训练模型...")
    model, losses = train_model(X, y, n_factors=len(get_factor_columns()))
    
    print("\n[4/4] 保存模型...")
    save_model(model, scaler)
    
    return model, scaler


def run_prediction():
    """运行预测"""
    print("\n[预测] 对股票池进行评分...")
    predictions = predict_stock_pool(top_n=20)
    return predictions


def update_positions(bt, prices, date):
    """更新持仓状态"""
    print("\n[持仓] 更新持仓价格...")
    
    for code in list(bt.positions.keys()):
        if code in prices:
            old_price = bt.positions[code]['buy_price']
            new_price = prices[code]
            profit = (new_price - old_price) / old_price * 100
            name = bt.positions[code]['name']
            print(f"  {name}({code}): {old_price:.2f} -> {new_price:.2f} ({profit:+.1f}%)")
    
    bt.record_daily(date, prices)


def generate_html(bt, predictions):
    """生成HTML页面"""
    print("\n[HTML] 生成展示页面...")
    
    summary = bt.get_summary()
    
    # 持仓数据
    positions_data = []
    for code, pos in bt.positions.items():
        positions_data.append({
            'code': code,
            'name': pos['name'],
            'qty': pos['qty'],
            'buy_price': pos['buy_price'],
            'buy_date': pos['buy_date'],
            'cost': pos['cost']
        })
    
    # 预测数据
    predictions_data = predictions[:10]  # Top 10
    
    # 交易记录
    trades_data = bt.trades[-20:]  # 最近20笔
    
    # 净值曲线
    daily_data = bt.daily_values[-60:]  # 最近60天
    
    # 生成JSON
    ai_data = {
        'updateTime': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'summary': summary,
        'positions': positions_data,
        'predictions': predictions_data,
        'trades': trades_data,
        'dailyValues': daily_data
    }
    
    # 读取HTML模板
    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # 替换数据
    import re
    json_str = json.dumps(ai_data, ensure_ascii=False, indent=2)
    pattern = r'const AI_DATA = .*?;'
    replacement = f'const AI_DATA = {json_str};'
    html = re.sub(pattern, replacement, html, count=1, flags=re.DOTALL)
    
    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"  已更新 {HTML_FILE}")


def main():
    parser = argparse.ArgumentParser(description='AI量化预测系统')
    parser.add_argument('--train', action='store_true', help='重新训练模型')
    parser.add_argument('--predict', action='store_true', help='运行预测')
    parser.add_argument('--buy', action='store_true', help='执行买入')
    parser.add_argument('--sell', type=str, help='卖出股票代码')
    parser.add_argument('--all', action='store_true', help='完整更新流程')
    args = parser.parse_args()
    
    bt = Backtester.load(DATA_FILE)
    
    if args.train or args.all:
        model, scaler = train_new_model()
    
    if args.predict or args.all:
        predictions = run_prediction()
        
        # 更新持仓价格
        prices = {p['code']: p['price'] for p in predictions}
        update_positions(bt, prices, datetime.now().strftime('%Y-%m-%d'))
        
        # 保存
        bt.save(DATA_FILE)
        
        # 生成HTML
        generate_html(bt, predictions)
        
        # 打印预测结果
        print("\n===== AI预测Top 10 =====")
        for i, p in enumerate(predictions[:10]):
            print(f"  {i+1}. {p['code']}  Score: {p['score']:.4f}  Price: {p['price']:.2f}")
    
    if args.buy:
        # 自动买入Top预测股票
        predictions = run_prediction()
        target_count = bt.target_positions - len(bt.positions)
        if target_count <= 0:
            print("\n[买入] 持仓已满，无需买入")
        else:
            print(f"\n[买入] 目标买入 {target_count} 只...")
            bought = 0
            for p in predictions:
                if bought >= target_count:
                    break
                if p['code'] in bt.positions:
                    continue
                ok, msg = bt.buy(p['code'], p['name'], p['price'], datetime.now().strftime('%Y-%m-%d'))
                if ok:
                    print(f"  {msg}")
                    bought += 1
            bt.save(DATA_FILE)
    
    if args.sell:
        # 卖出指定股票
        predictions = run_prediction()
        prices = {p['code']: p['price'] for p in predictions}
        if args.sell in prices:
            ok, msg = bt.sell(args.sell, prices[args.sell], datetime.now().strftime('%Y-%m-%d'))
            print(f"\n[卖出] {msg}")
            bt.save(DATA_FILE)
        else:
            print(f"\n[卖出] 未找到 {args.sell} 的价格数据")
    
    print("\n完成！")


if __name__ == '__main__':
    main()
