# -*- coding: utf-8 -*-
"""
CTA 刷新 + 部署脚本
====================
扫描数据 → 更新 cta_data.json → 更新 cta.html → 部署到 Cloudflare Pages

用法：
  python cta_refresh_deploy.py              # 刷新 + 部署
  python cta_refresh_deploy.py --no-deploy  # 只刷新，不部署
"""
import argparse
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def refresh():
    print('[1/2] 刷新 CTA 数据...')
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, 'cta_refresh.py')],
        cwd=SCRIPT_DIR, capture_output=False
    )
    return result.returncode == 0

def deploy():
    print('\n[2/2] 部署到 Cloudflare Pages...')
    result = subprocess.run(
        ['npx', 'wrangler', 'pages', 'deploy', '.', '--project-name', 'cta-signals', '--branch', 'main'],
        cwd=SCRIPT_DIR, capture_output=False, timeout=120
    )
    if result.returncode == 0:
        print('\n✅ 部署完成!')
        print('   URL: https://cta-signals.pages.dev/cta.html')
    else:
        print('\n❌ 部署失败')
    return result.returncode == 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-deploy', action='store_true', help='只刷新，不部署')
    args = parser.parse_args()

    if refresh():
        if not args.no_deploy:
            deploy()
    else:
        print('❌ 刷新失败')
