"""
首页性能监控脚本

用途: 测量各板块 API 的加载时间，生成性能报告

运行: python3 jobs/measure_homepage_performance.py
"""

import time
import requests
from datetime import date
from typing import List, Tuple

def measure_api_performance() -> None:
    """测量首页 API 性能"""
    
    # 获取默认日期
    resp = requests.get('http://localhost:8000/api/v1/meta/date-range')
    default_date = resp.json()['data']['default_selected_date']
    
    print(f'📅 测试日期: {default_date}')
    print('=' * 70)
    
    endpoints = [
        ('总览数据', f'/api/v1/dashboard/overview?grain=day&selected_date={default_date}'),
        ('告警列表', f'/api/v1/dashboard/alerts?selected_date={default_date}&grain=day'),
        ('组别排名', f'/api/v1/dashboard/groups?selected_date={default_date}&grain=day'),
        ('队列排名', f'/api/v1/dashboard/queues?selected_date={default_date}&grain=day'),
        ('审核人排名', f'/api/v1/dashboard/reviewers?selected_date={default_date}&grain=day'),
        ('错误类型', f'/api/v1/dashboard/error-types?selected_date={default_date}&grain=day'),
        ('健康检查', '/api/health'),
    ]
    
    # 串行测试
    print('\n🔄 串行加载（按顺序）')
    print('-' * 70)
    results = []
    for name, path in endpoints:
        start = time.time()
        try:
            r = requests.get(f'http://localhost:8000{path}', timeout=5)
            duration = (time.time() - start) * 1000
            status = '✅' if r.status_code == 200 else f'❌ ({r.status_code})'
            results.append((name, duration, status))
            print(f'{status} {name:15s} {duration:7.1f}ms')
        except Exception as e:
            print(f'❌ {name:15s} 失败: {e}')
            results.append((name, 0, '❌'))
    
    serial_total = sum(r[1] for r in results)
    print('-' * 70)
    print(f'🔢 串行总耗时: {serial_total:.1f}ms ({serial_total/1000:.2f}s)')
    
    # 并行测试
    print('\n⚡ 并行加载（Promise.all）')
    print('-' * 70)
    import concurrent.futures
    
    def fetch(args):
        name, path = args
        start = time.time()
        try:
            r = requests.get(f'http://localhost:8000{path}', timeout=5)
            duration = (time.time() - start) * 1000
            return (name, duration, '✅' if r.status_code == 200 else f'❌ ({r.status_code})')
        except Exception as e:
            return (name, 0, '❌')
    
    start_parallel = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(endpoints)) as executor:
        parallel_results = list(executor.map(fetch, endpoints))
    parallel_total = (time.time() - start_parallel) * 1000
    
    for name, duration, status in parallel_results:
        if duration > 0:
            print(f'{status} {name:15s} {duration:7.1f}ms')
        else:
            print(f'{status} {name:15s} 失败')
    
    print('-' * 70)
    print(f'⚡ 并行总耗时: {parallel_total:.1f}ms ({parallel_total/1000:.2f}s)')
    print(f'📈 并行提速: {serial_total/parallel_total:.1f}x')
    
    # 性能评估
    print('\n📊 性能评估')
    print('=' * 70)
    if parallel_total < 50:
        print('🎉 优秀！首屏加载 <50ms，用户无感知')
    elif parallel_total < 100:
        print('✅ 良好！首屏加载 <100ms，体验流畅')
    elif parallel_total < 200:
        print('⚠️  一般！首屏加载 <200ms，可优化')
    else:
        print('❌ 较慢！首屏加载 >200ms，需要优化')
    
    # 最慢接口
    slowest = max(parallel_results, key=lambda x: x[1])
    print(f'\n🐌 最慢接口: {slowest[0]} ({slowest[1]:.1f}ms)')
    if slowest[1] > 50:
        print(f'💡 建议：优化 {slowest[0]} 接口，添加索引或缓存')

if __name__ == '__main__':
    try:
        measure_api_performance()
    except KeyboardInterrupt:
        print('\n\n⚠️  测试已中断')
    except Exception as e:
        print(f'\n\n❌ 测试失败: {e}')
