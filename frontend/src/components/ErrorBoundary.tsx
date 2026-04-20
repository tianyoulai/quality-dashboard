/**
 * ErrorBoundary - React 错误边界组件
 * 
 * 功能：
 * 1. 捕获子组件树中的 JavaScript 错误
 * 2. 显示友好的降级 UI
 * 3. 上报错误到后端日志
 * 4. 支持错误恢复（刷新页面）
 * 
 * 使用方式：
 * ```tsx
 * <ErrorBoundary fallback={<CustomErrorPage />}>
 *   <YourComponent />
 * </ErrorBoundary>
 * ```
 */

'use client';

import { Component, ReactNode } from 'react';

type ErrorBoundaryProps = {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
};

type ErrorBoundaryState = {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
};

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    // 更新 state，下次渲染时显示降级 UI
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    // 记录错误信息
    console.error('ErrorBoundary caught:', error, errorInfo);

    this.setState({
      error,
      errorInfo,
    });

    // 调用外部错误处理器
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    // 上报错误到后端
    this.reportError(error, errorInfo);
  }

  /**
   * 上报错误到后端日志接口
   */
  private async reportError(error: Error, errorInfo: React.ErrorInfo): Promise<void> {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
      
      await fetch(`${apiBase}/api/v1/log-error`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          error_type: 'frontend_error',
          error_message: error.message,
          error_stack: error.stack,
          component_stack: errorInfo.componentStack,
          user_agent: navigator.userAgent,
          url: window.location.href,
          timestamp: new Date().toISOString(),
        }),
      });
    } catch (e) {
      // 上报失败，静默忽略（避免二次错误）
      console.warn('Failed to report error:', e);
    }
  }

  /**
   * 重置错误状态（用户点击"重试"）
   */
  private handleReset = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      // 使用自定义降级 UI
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // 默认降级 UI
      return (
        <div className="error-boundary-container">
          <div className="error-boundary-content">
            <h2 className="error-boundary-title">😵 页面出错了</h2>
            <p className="error-boundary-message">
              {this.state.error?.message || '未知错误'}
            </p>
            
            <div className="error-boundary-actions">
              <button
                onClick={() => window.location.reload()}
                className="error-boundary-button-primary"
              >
                刷新页面
              </button>
              <button
                onClick={this.handleReset}
                className="error-boundary-button-secondary"
              >
                重试
              </button>
            </div>

            {/* 开发环境显示详细错误信息 */}
            {process.env.NODE_ENV === 'development' && this.state.error && (
              <details className="error-boundary-details">
                <summary>错误详情（仅开发环境可见）</summary>
                <pre className="error-boundary-stack">
                  {this.state.error.stack}
                </pre>
                {this.state.errorInfo && (
                  <pre className="error-boundary-component-stack">
                    {this.state.errorInfo.componentStack}
                  </pre>
                )}
              </details>
            )}
          </div>

          <style jsx>{`
            .error-boundary-container {
              display: flex;
              justify-content: center;
              align-items: center;
              min-height: 100vh;
              padding: 20px;
              background-color: #f9fafb;
            }

            .error-boundary-content {
              max-width: 600px;
              width: 100%;
              padding: 40px;
              background: white;
              border-radius: 8px;
              box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
              text-align: center;
            }

            .error-boundary-title {
              font-size: 24px;
              font-weight: 600;
              color: #1f2937;
              margin-bottom: 16px;
            }

            .error-boundary-message {
              font-size: 16px;
              color: #6b7280;
              margin-bottom: 32px;
            }

            .error-boundary-actions {
              display: flex;
              gap: 12px;
              justify-content: center;
              margin-bottom: 24px;
            }

            .error-boundary-button-primary {
              padding: 12px 24px;
              font-size: 16px;
              font-weight: 500;
              color: white;
              background-color: #3b82f6;
              border: none;
              border-radius: 6px;
              cursor: pointer;
              transition: background-color 0.2s;
            }

            .error-boundary-button-primary:hover {
              background-color: #2563eb;
            }

            .error-boundary-button-secondary {
              padding: 12px 24px;
              font-size: 16px;
              font-weight: 500;
              color: #374151;
              background-color: #e5e7eb;
              border: none;
              border-radius: 6px;
              cursor: pointer;
              transition: background-color 0.2s;
            }

            .error-boundary-button-secondary:hover {
              background-color: #d1d5db;
            }

            .error-boundary-details {
              text-align: left;
              margin-top: 24px;
              padding: 16px;
              background-color: #f3f4f6;
              border-radius: 6px;
            }

            .error-boundary-details summary {
              cursor: pointer;
              font-weight: 500;
              color: #374151;
            }

            .error-boundary-stack,
            .error-boundary-component-stack {
              margin-top: 12px;
              padding: 12px;
              background-color: #1f2937;
              color: #f9fafb;
              font-size: 12px;
              font-family: monospace;
              overflow-x: auto;
              border-radius: 4px;
            }
          `}</style>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * 错误边界 Hook（用于函数组件内部捕获错误）
 * 注意：这个 Hook 不能捕获子组件的错误，只能捕获当前组件的异步错误
 */
export function useErrorHandler(): (error: Error) => void {
  return (error: Error) => {
    // 手动触发错误边界
    throw error;
  };
}
