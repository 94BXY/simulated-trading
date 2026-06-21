# -*- coding: utf-8 -*-
"""
CTA 页面部署脚本
================
部署 cta.html 和 cta_data.json 到 Cloudflare Pages

用法：
  python deploy_cta.py                  # 部署到 cta-signals 项目
  python deploy_cta.py --project xxx    # 指定项目名
"""
import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def deploy(project='cta-signals'):
    print(f'Deploying to Cloudflare Pages: {project}')
    print(f'Directory: {SCRIPT_DIR}')
    
    # Deploy using wrangler
    cmd = [
        'npx', 'wrangler', 'pages', 'deploy', '.',
        '--project-name', project,
        '--branch', 'main'
    ]
    
    print(f'Command: {" ".join(cmd)}')
    print()
    
    try:
        result = subprocess.run(cmd, cwd=SCRIPT_DIR, capture_output=False, timeout=120)
        if result.returncode == 0:
            print(f'\n✅ Deployed successfully!')
            print(f'URL: https://{project}.pages.dev/')
        else:
            print(f'\n❌ Deploy failed with exit code {result.returncode}')
    except subprocess.TimeoutExpired:
        print('\n❌ Deploy timed out (120s)')
    except Exception as e:
        print(f'\n❌ Deploy error: {e}')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', default='cta-signals', help='Cloudflare Pages project name')
    args = parser.parse_args()
    deploy(args.project)
