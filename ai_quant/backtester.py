# -*- coding: utf-8 -*-
"""
回测系统
========
模拟交易，遵循T+1规则
"""
import json
import datetime
import os

class Backtester:
    """回测引擎"""
    
    def __init__(self, initial_capital=100000, max_positions=10):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.max_positions = max_positions
        self.positions = {}  # {code: {qty, buy_price, buy_date, name}}
        self.trades = []     # 交易记录
        self.daily_values = []  # 每日净值
        self.daily_returns = []  # 每日收益率
    
    def can_sell(self, code, current_date):
        """T+1规则：买入当天不能卖出"""
        if code not in self.positions:
            return False
        buy_date = self.positions[code]['buy_date']
        if isinstance(buy_date, str):
            buy_date = datetime.datetime.strptime(buy_date, '%Y-%m-%d').date()
        if isinstance(current_date, str):
            current_date = datetime.datetime.strptime(current_date, '%Y-%m-%d').date()
        return current_date > buy_date
    
    def can_buy(self):
        """检查是否还能买入（持仓数量限制）"""
        return len(self.positions) < self.max_positions
    
    def get_position_value(self, prices):
        """计算持仓市值"""
        value = 0
        for code, pos in self.positions.items():
            if code in prices:
                value += pos['qty'] * prices[code]
        return value
    
    def get_total_value(self, prices):
        """计算总资产"""
        return self.capital + self.get_position_value(prices)
    
    def buy(self, code, name, price, date, amount=None):
        """
        买入股票
        amount: 买入金额，默认使用10%仓位
        """
        if not self.can_buy():
            return False, "持仓已满"
        
        if code in self.positions:
            return False, "已持有该股票"
        
        if amount is None:
            amount = self.capital * 0.1  # 默认10%仓位
        
        # 计算可买数量（整手）
        qty = int(amount / price / 100) * 100
        if qty <= 0:
            return False, "资金不足"
        
        cost = qty * price
        if cost > self.capital:
            return False, "资金不足"
        
        # 执行买入
        self.capital -= cost
        self.positions[code] = {
            'qty': qty,
            'buy_price': price,
            'buy_date': str(date),
            'name': name
        }
        
        self.trades.append({
            'code': code,
            'name': name,
            'action': 'BUY',
            'price': price,
            'qty': qty,
            'amount': cost,
            'date': str(date),
            'capital_after': self.capital
        })
        
        return True, f"买入 {name}({code}) {qty}股 @ {price}"
    
    def sell(self, code, price, date):
        """
        卖出股票（需满足T+1）
        """
        if code not in self.positions:
            return False, "未持有该股票"
        
        if not self.can_sell(code, date):
            return False, "T+1限制，今日买入不能卖出"
        
        pos = self.positions.pop(code)
        amount = pos['qty'] * price
        profit = (price - pos['buy_price']) / pos['buy_price'] * 100
        
        self.capital += amount
        
        self.trades.append({
            'code': code,
            'name': pos['name'],
            'action': 'SELL',
            'price': price,
            'qty': pos['qty'],
            'amount': amount,
            'date': str(date),
            'profit_pct': profit,
            'buy_price': pos['buy_price'],
            'capital_after': self.capital
        })
        
        return True, f"卖出 {pos['name']}({code}) {pos['qty']}股 @ {price} ({profit:+.2f}%)"
    
    def record_daily(self, date, prices):
        """记录每日净值"""
        total = self.get_total_value(prices)
        daily_return = 0
        if self.daily_values:
            prev = self.daily_values[-1]['total']
            daily_return = (total - prev) / prev * 100
        
        self.daily_values.append({
            'date': str(date),
            'total': total,
            'capital': self.capital,
            'position': self.get_position_value(prices),
            'return_pct': daily_return
        })
        self.daily_returns.append(daily_return)
    
    def get_performance(self):
        """计算绩效指标"""
        if not self.daily_values:
            return {}
        
        total_value = self.daily_values[-1]['total']
        total_return = (total_value - self.initial_capital) / self.initial_capital * 100
        
        # 年化收益
        days = len(self.daily_values)
        annual_return = total_return * 252 / days if days > 0 else 0
        
        # 夏普比率
        if self.daily_returns and len(self.daily_returns) > 1:
            returns_array = np.array(self.daily_returns[1:])  # 去掉第一天
            sharpe = np.sqrt(252) * returns_array.mean() / returns_array.std() if returns_array.std() > 0 else 0
        else:
            sharpe = 0
        
        # 最大回撤
        max_drawdown = 0
        peak = self.initial_capital
        for dv in self.daily_values:
            if dv['total'] > peak:
                peak = dv['total']
            drawdown = (peak - dv['total']) / peak * 100
            max_drawdown = max(max_drawdown, drawdown)
        
        # 胜率
        wins = sum(1 for t in self.trades if t['action'] == 'SELL' and t.get('profit_pct', 0) > 0)
        total_sells = sum(1 for t in self.trades if t['action'] == 'SELL')
        win_rate = wins / total_sells * 100 if total_sells > 0 else 0
        
        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'total_trades': len(self.trades),
            'current_positions': len(self.positions)
        }
    
    def to_dict(self):
        """导出为字典"""
        return {
            'initial_capital': self.initial_capital,
            'capital': self.capital,
            'positions': self.positions,
            'trades': self.trades,
            'daily_values': self.daily_values,
            'performance': self.get_performance()
        }
    
    def save(self, filepath):
        """保存到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load(cls, filepath):
        """从文件加载"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        bt = cls(initial_capital=data['initial_capital'])
        bt.capital = data['capital']
        bt.positions = data['positions']
        bt.trades = data['trades']
        bt.daily_values = data['daily_values']
        return bt


import numpy as np
