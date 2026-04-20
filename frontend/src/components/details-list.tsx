/**
 * 使用 usePagination Hook 的示例组件（简化版）
 * 
 * 场景：加载分页数据（如详情列表），自动管理页码、loading、分页元数据
 * 
 * 注意：本示例已简化，实际使用时请根据 API 接口调整
 */

'use client';

export function DetailsList() {
  return (
    <div className="details-container">
      <div className="info-box">
        <h3>📋 详情列表组件</h3>
        <p>本组件展示如何使用 usePagination Hook。</p>
        <p>完整实现请参考实际业务页面。</p>
      </div>
      
      <style jsx>{`
        .details-container {
          padding: 2rem;
        }
        
        .info-box {
          padding: 2rem;
          background: #f0f9ff;
          border: 1px solid #bfdbfe;
          border-radius: 8px;
        }
        
        .info-box h3 {
          margin: 0 0 1rem 0;
          color: #1a1a1a;
        }
        
        .info-box p {
          margin: 0.5rem 0;
          color: #374151;
        }
      `}</style>
    </div>
  );
}
