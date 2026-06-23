# -*- coding: utf-8 -*-
"""
AI 预测器
=========
获取数据、计算因子、运行模型、生成推荐
"""
import sys
import os
import datetime
import json
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

# 添加pytorch-quant路径
sys.path.insert(0, r'E:\素材\pytorch-quant')
from data_utils import get_stock_data

from .factor_engine import FactorEngine
from .model_trainer import ModelTrainer
from .backtester import Backtester

class NumpyEncoder(json.JSONEncoder):
    """处理numpy类型的JSON编码器"""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

class AIPredictor:
    """AI选股预测器"""
    
    def __init__(self, data_dir=None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)))
        self.data_dir = data_dir
        self.ai_data_path = os.path.join(data_dir, 'ai_trading.json')
        
        # 初始化组件
        self.factor_engine = FactorEngine()
        self.model_trainer = ModelTrainer()
        self.backtester = Backtester(initial_capital=100000, max_positions=10)
        
        # 加载已有数据
        if os.path.exists(self.ai_data_path):
            self.load_data()
    
    def get_stock_pool(self):
        """
        获取股票池
        使用pywencai获取沪深主板股票（排除创业板和ST）
        """
        try:
            import pywencai
            query = "沪深A股，非ST，非创业板，流通市值大于50亿，近20日日均成交额大于1亿"
            result = pywencai.get(query=query, query_type='stock')
            
            if result is not None and len(result) > 0:
                stocks = []
                for _, row in result.iterrows():
                    code = str(row.get('股票代码', ''))
                    name = str(row.get('股票简称', ''))
                    
                    # 过滤创业板和ST
                    if FactorEngine.is_chinext(code) or FactorEngine.is_st(name):
                        continue
                    
                    stocks.append({
                        'code': code,
                        'name': name,
                        'close': float(row.get('最新价', 0)),
                        'pct_chg': float(row.get('涨跌幅', 0)),
                        'volume': float(row.get('成交量', 0)),
                        'turnover_rate': float(row.get('换手率', 0))
                    })
                
                print(f"  获取到 {len(stocks)} 只股票")
                return stocks[:100]  # 限制数量
        except Exception as e:
            print(f"  pywencai获取失败: {e}")
        
        # 备用：使用默认股票池
        return self._get_default_pool()
    
    def _get_default_pool(self):
        """默认股票池（沪深300成分股部分）"""
        default_stocks = [
            {'code': '600519', 'name': '贵州茅台'},
            {'code': '601318', 'name': '中国平安'},
            {'code': '600036', 'name': '招商银行'},
            {'code': '000858', 'name': '五粮液'},
            {'code': '601166', 'name': '兴业银行'},
            {'code': '600276', 'name': '恒瑞医药'},
            {'code': '601398', 'name': '工商银行'},
            {'code': '600900', 'name': '长江电力'},
            {'code': '601012', 'name': '隆基绿能'},
            {'code': '600030', 'name': '中信证券'},
            {'code': '601888', 'name': '中国中免'},
            {'code': '600887', 'name': '伊利股份'},
            {'code': '000333', 'name': '美的集团'},
            {'code': '000651', 'name': '格力电器'},
            {'code': '601899', 'name': '紫金矿业'},
            {'code': '600050', 'name': '中国联通'},
            {'code': '601668', 'name': '中国建筑'},
            {'code': '600585', 'name': '海螺水泥'},
            {'code': '000001', 'name': '平安银行'},
            {'code': '600000', 'name': '浦发银行'},
        ]
        return default_stocks
    
    def fetch_stock_data(self, code, days=120):
        """获取单只股票历史数据"""
        end = datetime.datetime.now().strftime('%Y%m%d')
        start = (datetime.datetime.now() - datetime.timedelta(days=days*2)).strftime('%Y%m%d')
        return get_stock_data(code, start, end)
    
    def compute_factors_for_pool(self, stock_pool):
        """为股票池计算因子"""
        all_data = []
        
        for stock in stock_pool:
            code = stock['code']
            name = stock['name']
            
            try:
                df = self.fetch_stock_data(code)
                if df is None or len(df) < 60:
                    continue
                
                # 计算因子
                df = self.factor_engine.compute_all_factors(df)
                df['code'] = code
                df['name'] = name
                
                # 取最新一行
                latest = df.iloc[-1]
                factor_cols = self.factor_engine.get_factor_columns()
                
                # 检查因子是否有NaN
                factor_values = [latest.get(f, np.nan) for f in factor_cols]
                if any(np.isnan(v) for v in factor_values):
                    continue
                
                all_data.append({
                    'code': code,
                    'name': name,
                    'close': float(latest['close']),
                    'pct_chg': float(latest.get('pct_chg', 0)),
                    'factors': [float(v) for v in factor_values],
                    'latest_date': str(latest['date'].date()) if hasattr(latest['date'], 'date') else str(latest['date'])
                })
                
            except Exception as e:
                print(f"  {code} {name} 计算因子失败: {e}")
                continue
        
        return all_data
    
    def train_model(self, stock_pool):
        """训练模型"""
        print("\n[训练模型] 获取训练数据...")
        
        all_train_data = []
        for stock in stock_pool[:30]:  # 用30只股票训练
            code = stock['code']
            try:
                df = self.fetch_stock_data(code)
                if df is None or len(df) < 80:
                    continue
                
                df = self.factor_engine.compute_all_factors(df)
                df = df.dropna()
                
                factor_cols = self.factor_engine.get_factor_columns()
                X = df[factor_cols].values
                y = df['future_return_5d'].values
                
                all_train_data.append((X, y))
            except:
                continue
        
        if not all_train_data:
            print("  训练数据不足")
            return None
        
        # 合并数据
        X_all = np.vstack([x for x, y in all_train_data])
        y_all = np.concatenate([y for x, y in all_train_data])
        
        # 标准化
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_all)
        
        # 训练
        print(f"  训练样本: {len(X_scaled)}")
        losses = self.model_trainer.train(X_scaled, y_all, epochs=200)
        
        # 保存scaler参数
        self.scaler_mean = scaler.mean_.tolist()
        self.scaler_scale = scaler.scale_.tolist()
        
        return losses
    
    def predict_stocks(self, stock_pool):
        """预测股票评分"""
        print("\n[预测] 计算因子...")
        pool_data = self.compute_factors_for_pool(stock_pool)
        
        if not pool_data:
            print("  无有效数据")
            return []
        
        # 标准化
        factor_cols = self.factor_engine.get_factor_columns()
        X = np.array([d['factors'] for d in pool_data])
        
        if hasattr(self, 'scaler_mean') and hasattr(self, 'scaler_scale'):
            X_scaled = (X - np.array(self.scaler_mean)) / np.array(self.scaler_scale)
        else:
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
        
        # 预测
        scores = self.model_trainer.predict(X_scaled)
        
        # 组装结果
        results = []
        for i, data in enumerate(pool_data):
            results.append({
                'code': data['code'],
                'name': data['name'],
                'close': data['close'],
                'score': float(scores[i]),
                'pct_chg': data['pct_chg'],
                'factors': dict(zip(factor_cols, data['factors'])),
                'latest_date': data['latest_date']
            })
        
        # 按评分排序
        results.sort(key=lambda x: x['score'], reverse=True)
        
        return results
    
    def generate_signals(self, predictions, current_date):
        """
        生成交易信号
        基于评分和置信度决定买入/卖出
        """
        signals = {
            'buy': [],
            'sell': [],
            'hold': []
        }
        
        # 买入信号：评分前10且评分>0
        for pred in predictions[:10]:
            if pred['score'] > 0 and self.backtester.can_buy():
                signals['buy'].append(pred)
        
        # 卖出信号：持仓中评分下降的
        for code, pos in self.backtester.positions.items():
            # 找到对应股票的评分
            stock_pred = next((p for p in predictions if p['code'] == code), None)
            if stock_pred:
                # 评分低于-0.5或亏损超过5%触发卖出
                current_price = stock_pred['close']
                profit = (current_price - pos['buy_price']) / pos['buy_price']
                
                if stock_pred['score'] < -0.5 or profit < -0.05:
                    if self.backtester.can_sell(code, current_date):
                        signals['sell'].append(stock_pred)
                else:
                    signals['hold'].append(stock_pred)
        
        return signals
    
    def execute_signals(self, signals, current_date):
        """执行交易信号"""
        results = []
        
        # 先执行卖出
        for stock in signals['sell']:
            success, msg = self.backtester.sell(stock['code'], stock['close'], current_date)
            results.append({
                'action': 'SELL',
                'success': success,
                'message': msg,
                'stock': stock
            })
        
        # 再执行买入
        for stock in signals['buy']:
            success, msg = self.backtester.buy(
                stock['code'], stock['name'], stock['close'], current_date
            )
            results.append({
                'action': 'BUY',
                'success': success,
                'message': msg,
                'stock': stock
            })
        
        return results
    
    def generate_review(self, date, predictions, trade_results):
        """生成每日复盘"""
        performance = self.backtester.get_performance()
        
        review = {
            'date': str(date),
            'market_summary': {
                'total_stocks_analyzed': len(predictions),
                'top_picks': [{'code': p['code'], 'name': p['name'], 'score': float(p['score'])} 
                             for p in predictions[:5]],
                'bottom_picks': [{'code': p['code'], 'name': p['name'], 'score': float(p['score'])} 
                                for p in predictions[-5:]]
            },
            'trades': trade_results,
            'portfolio': {
                'capital': float(self.backtester.capital),
                'positions': {k: {**v, 'qty': int(v['qty']), 'buy_price': float(v['buy_price'])} 
                             for k, v in self.backtester.positions.items()},
                'total_value': float(self.backtester.get_total_value(
                    {p['code']: p['close'] for p in predictions}
                ))
            },
            'performance': {k: float(v) if isinstance(v, (int, float, np.integer, np.floating)) else v 
                           for k, v in performance.items()},
            'lessons': self._generate_lessons(predictions, trade_results, performance)
        }
        
        return review
    
    def _generate_lessons(self, predictions, trade_results, performance):
        """生成学习心得"""
        lessons = []
        
        # 分析交易结果
        buys = [t for t in trade_results if t['action'] == 'BUY' and t['success']]
        sells = [t for t in trade_results if t['action'] == 'SELL' and t['success']]
        
        if buys:
            lessons.append(f"今日买入 {len(buys)} 只股票，关注后续表现")
        
        if sells:
            lessons.append(f"今日卖出 {len(sells)} 只")
        
        # 绩效分析
        if performance.get('max_drawdown', 0) > 10:
            lessons.append("最大回撤超过10%，需要加强风控")
        
        if performance.get('win_rate', 0) < 40:
            lessons.append("胜率偏低，考虑提高选股阈值")
        
        return lessons
    
    def save_data(self):
        """保存数据"""
        data = {
            'backtester': self.backtester.to_dict(),
            'scaler_mean': getattr(self, 'scaler_mean', None),
            'scaler_scale': getattr(self, 'scaler_scale', None),
            'last_update': str(datetime.datetime.now())
        }
        
        with open(self.ai_data_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, cls=NumpyEncoder)
        
        print(f"  数据已保存到 {self.ai_data_path}")
    
    def load_data(self):
        """加载数据"""
        try:
            with open(self.ai_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if 'backtester' in data:
                bt_data = data['backtester']
                self.backtester = Backtester(
                    initial_capital=bt_data['initial_capital'],
                    max_positions=10
                )
                self.backtester.capital = bt_data['capital']
                self.backtester.positions = bt_data['positions']
                self.backtester.trades = bt_data['trades']
                self.backtester.daily_values = bt_data.get('daily_values', [])
            
            if data.get('scaler_mean'):
                self.scaler_mean = data['scaler_mean']
                self.scaler_scale = data['scaler_scale']
            
            print("  数据已加载")
        except Exception as e:
            print(f"  加载数据失败: {e}")
