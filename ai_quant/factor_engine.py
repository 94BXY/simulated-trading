# -*- coding: utf-8 -*-
"""
因子计算引擎
============
计算12个量化因子用于选股
"""
import pandas as pd
import numpy as np

class FactorEngine:
    """因子计算引擎"""
    
    @staticmethod
    def compute_all_factors(df):
        """
        计算所有因子
        输入: DataFrame with columns [date, open, close, high, low, volume, turnover_rate, pct_chg]
        输出: DataFrame with factor columns added
        """
        df = df.copy()
        
        # 动量因子
        df['mom_5'] = df['close'].pct_change(5)
        df['mom_20'] = df['close'].pct_change(20)
        df['mom_60'] = df['close'].pct_change(60)
        
        # 波动因子
        df['vol_5'] = df['pct_chg'].rolling(5).std()
        df['vol_20'] = df['pct_chg'].rolling(20).std()
        
        # 量价因子
        df['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        df['turnover_avg'] = df['turnover_rate'].rolling(5).mean()
        
        # RSI(14)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))
        
        # MACD
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        
        # 布林带位置
        sma20 = df['close'].rolling(20).mean()
        std20 = df['close'].rolling(20).std()
        upper = sma20 + 2 * std20
        lower = sma20 - 2 * std20
        df['boll_position'] = (df['close'] - lower) / (upper - lower)
        
        # 趋势因子
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma20'] = df['close'].rolling(20).mean()
        df['ma_cross'] = (df['ma5'] > df['ma20']).astype(int)
        df['ma_deviation'] = df['close'] / df['ma20'] - 1
        
        # 目标变量：未来5日收益率
        df['future_return_5d'] = df['close'].shift(-5) / df['close'] - 1
        
        return df
    
    @staticmethod
    def get_factor_columns():
        """返回因子列名"""
        return [
            'mom_5', 'mom_20', 'mom_60',
            'vol_5', 'vol_20',
            'volume_ratio', 'turnover_avg',
            'rsi_14',
            'macd', 'macd_signal', 'macd_hist',
            'boll_position',
            'ma_cross', 'ma_deviation'
        ]
    
    @staticmethod
    def is_st(name):
        """判断是否ST股"""
        if name is None:
            return False
        return 'ST' in name or 'st' in name or '*ST' in name
    
    @staticmethod
    def is_chinext(code):
        """判断是否创业板(300开头)"""
        return code.startswith('300') or code.startswith('301')
    
    @staticmethod
    def filter_stock_pool(stocks_info):
        """
        过滤股票池
        排除: 创业板、ST
        """
        filtered = []
        for stock in stocks_info:
            code = stock.get('code', '')
            name = stock.get('name', '')
            
            # 排除创业板
            if FactorEngine.is_chinext(code):
                continue
            
            # 排除ST
            if FactorEngine.is_st(name):
                continue
            
            filtered.append(stock)
        
        return filtered
