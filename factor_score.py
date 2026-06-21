# -*- coding: utf-8 -*-
"""
因子打分选股系统
================
用 pywencai 获取数据，对股票池做多因子打分排序。

用法：
  python factor_score.py                    # 默认沪深300，输出Top10
  python factor_score.py --pool 中证500     # 换股票池
  python factor_score.py --top 5            # 输出Top5
  python factor_score.py --add              # 自动把Top5加入模拟交易系统

依赖：pywencai, pandas
"""

import argparse
import datetime
import json
import os
import sys
import pandas as pd
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, 'data.json')

# ── 因子权重配置 ──
# 权重总和 = 1.0
# 正数 = 越大越好（如 ROE）
# 负数 = 越小越好（如 PE，取负数后越大越好）
FACTOR_WEIGHTS = {
    'PE':       -0.20,  # 市盈率，越低越好
    'PB':       -0.10,  # 市净率，越低越好
    'ROE':       0.30,  # 净资产收益率，越高越好
    'momentum':  0.15,  # 近期涨幅，越高越好（动量效应）
    'turnover':  0.10,  # 换手率，适中最好（后面会处理）
    'mcap':     -0.15,  # 总市值，偏小盘（A股小盘效应）
}


def fetch_pool(pool_name='沪深300'):
    """从问财获取股票池数据"""
    import pywencai

    query = f'{pool_name}成分股 市盈率 市净率 ROE 换手率 涨跌幅 总市值'
    print(f'正在查询: {query}')

    df = pywencai.get(query=query, query_type='stock')

    if df is None or not hasattr(df, 'columns'):
        print('[ERROR] 问财查询失败')
        return None

    print(f'获取到 {len(df)} 只股票')
    return df


def clean_columns(df):
    """清洗列名，提取需要的因子"""
    # 找到包含关键字段的列
    col_map = {}
    for c in df.columns:
        if c.startswith('市盈率(pe)'):
            col_map['PE'] = c
        elif c.startswith('市净率(pb)'):
            col_map['PB'] = c
        elif '净资产收益率roe' in c and '预测' not in c:
            col_map['ROE'] = c
        elif c.startswith('换手率'):
            col_map['turnover_raw'] = c
        elif c.startswith('涨跌幅') or c.startswith('最新涨跌幅'):
            col_map['momentum'] = c
        elif c.startswith('总市值'):
            col_map['mcap'] = c

    result = pd.DataFrame()
    result['code'] = df['股票代码'].astype(str).str.replace(r'\.\w+$', '', regex=True)
    result['name'] = df['股票简称']

    for factor, col in col_map.items():
        result[factor] = pd.to_numeric(df[col], errors='coerce')

    # 换手率特殊处理：取绝对值
    if 'turnover_raw' in col_map:
        result['turnover'] = pd.to_numeric(df[col_map['turnover_raw']], errors='coerce')

    return result.dropna(subset=['PE', 'ROE'])


def score_factors(df):
    """对每个因子做排名打分（百分位）"""
    scored = df.copy()

    for factor in FACTOR_WEIGHTS:
        if factor not in scored.columns:
            continue

        values = scored[factor].copy()

        # 换手率特殊处理：适中最好，用高斯打分
        if factor == 'turnover':
            median_val = values.median()
            std_val = values.std()
            if std_val > 0:
                # 距离中位数越近，分数越高
                scored[f'{factor}_score'] = np.exp(-0.5 * ((values - median_val) / std_val) ** 2)
            else:
                scored[f'{factor}_score'] = 0.5
        else:
            # 其他因子：百分位排名（0~1）
            scored[f'{factor}_score'] = values.rank(pct=True)

    return scored


def compute_total_score(df):
    """加权求和"""
    scored = df.copy()
    total = pd.Series(0.0, index=scored.index)
    details = []

    for factor, weight in FACTOR_WEIGHTS.items():
        score_col = f'{factor}_score'
        if score_col in scored.columns:
            contribution = scored[score_col] * weight
            total += contribution
            details.append(f'{factor}({weight:+.2f})')

    scored['total_score'] = total
    return scored, details


def run(pool='沪深300', top_n=10, add_to_system=False):
    """主流程"""
    print(f'\n{"="*55}')
    print(f'  因子打分选股 — {pool}')
    print(f'{"="*55}\n')

    # 1. 获取数据
    raw = fetch_pool(pool)
    if raw is None:
        return

    # 2. 清洗
    df = clean_columns(raw)
    print(f'有效股票: {len(df)} 只\n')

    # 3. 因子打分
    scored = score_factors(df)

    # 4. 加权排序
    result, details = compute_total_score(scored)
    result = result.sort_values('total_score', ascending=False).reset_index(drop=True)

    # 5. 输出
    print(f'因子权重: {" + ".join(details)}\n')
    print(f'{"排名":>4}  {"代码":>8}  {"名称":>8}  {"总分":>6}  {"PE":>7}  {"PB":>6}  {"ROE":>7}  {"涨幅":>7}  {"换手":>6}  {"市值(亿)":>8}')
    print('-' * 85)

    top = result.head(top_n)
    for i, row in top.iterrows():
        mcap_yi = row.get('mcap', 0) / 1e8 if row.get('mcap', 0) > 0 else 0
        print(f'  {i+1:>2}   {row["code"]:>8}  {row["name"]:>8}  '
              f'{row["total_score"]:>6.3f}  '
              f'{row.get("PE",0):>7.1f}  {row.get("PB",0):>6.2f}  '
              f'{row.get("ROE",0):>7.2f}  {row.get("momentum",0):>6.2f}%  '
              f'{row.get("turnover",0):>5.2f}%  {mcap_yi:>8.0f}')

    # 6. 可选：加入模拟交易系统
    if add_to_system:
        codes = top['code'].tolist()
        names = dict(zip(top['code'], top['name']))
        today = datetime.date.today().strftime('%Y-%m-%d')
        print(f'\n准备把 Top{top_n} 加入模拟交易系统...')
        print(f'股票: {", ".join(codes)}')

        # 调用 update.py --add
        code_str = ','.join(codes)
        os.system(f'python "{os.path.join(SCRIPT_DIR, "update.py")}" --add {code_str}')

    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='因子打分选股')
    parser.add_argument('--pool', default='沪深300', help='股票池（沪深300/中证500/创业板 等）')
    parser.add_argument('--top', type=int, default=10, help='输出前N只')
    parser.add_argument('--add', action='store_true', help='把Top5加入模拟交易系统')
    args = parser.parse_args()

    run(pool=args.pool, top_n=args.top, add_to_system=args.add)
