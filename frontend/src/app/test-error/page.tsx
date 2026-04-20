"""ErrorBoundary 测试页面 - 验证错误边界是否生效。

访问路径：http://localhost:3000/test-error

功能：
1. 触发同步错误（点击按钮）
2. 触发异步错误（API 请求失败）
3. 触发子组件错误
"""

'use client';

import { useState } from 'react';

function BrokenComponent() {
  // 故意抛出错误
  throw new Error('这是一个测试错误！');
  return <div>这段代码永远不会执行</div>;
}

function AsyncErrorComponent() {
  const [showError, setShowError] = useState(false);

  if (showError) {
    throw new Error('这是一个异步触发的错误！');
  }

  return (
    <button
      onClick={() => setShowError(true)}
      className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
    >
      触发异步错误
    </button>
  );
}

export default function TestErrorPage() {
  const [showBrokenComponent, setShowBrokenComponent] = useState(false);

  return (
    <div className="container mx-auto p-8">
      <h1 className="text-3xl font-bold mb-8">ErrorBoundary 测试页面</h1>

      <div className="space-y-6">
        {/* 测试1：同步错误 */}
        <div className="border p-4 rounded">
          <h2 className="text-xl font-semibold mb-4">测试1: 同步错误</h2>
          <p className="text-gray-600 mb-4">
            点击按钮会立即抛出错误，ErrorBoundary 应该捕获并显示降级 UI
          </p>
          {!showBrokenComponent ? (
            <button
              onClick={() => setShowBrokenComponent(true)}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              触发同步错误
            </button>
          ) : (
            <BrokenComponent />
          )}
        </div>

        {/* 测试2：异步错误 */}
        <div className="border p-4 rounded">
          <h2 className="text-xl font-semibold mb-4">测试2: 异步错误</h2>
          <p className="text-gray-600 mb-4">
            点击按钮会在下次渲染时抛出错误
          </p>
          <AsyncErrorComponent />
        </div>

        {/* 测试3：API 错误（不会被 ErrorBoundary 捕获，需要在代码中处理） */}
        <div className="border p-4 rounded">
          <h2 className="text-xl font-semibold mb-4">测试3: API 错误</h2>
          <p className="text-gray-600 mb-4">
            API 错误需要在代码中用 try-catch 处理，ErrorBoundary 不会捕获
          </p>
          <button
            onClick={async () => {
              try {
                await fetch('http://localhost:8000/api/v1/nonexistent');
              } catch (error) {
                alert('API 错误已被 catch 捕获（不会触发 ErrorBoundary）');
              }
            }}
            className="px-4 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600"
          >
            触发 API 错误
          </button>
        </div>

        {/* 说明 */}
        <div className="bg-blue-50 border border-blue-200 p-4 rounded">
          <h3 className="font-semibold text-blue-900 mb-2">💡 注意事项</h3>
          <ul className="list-disc list-inside text-blue-800 space-y-1">
            <li>ErrorBoundary 只能捕获子组件树中的渲染错误</li>
            <li>事件处理器中的错误需要用 try-catch 手动处理</li>
            <li>异步代码（Promise）中的错误不会被捕获</li>
            <li>服务端渲染（SSR）的错误需要单独处理</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
