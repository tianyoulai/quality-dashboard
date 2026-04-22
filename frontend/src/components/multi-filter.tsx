'use client';

import { useState } from 'react';

interface FilterOption {
  value: string;
  label: string;
  checked: boolean;
}

interface MultiFilterProps {
  queues: FilterOption[];
  reviewers: FilterOption[];
  errorTypes: FilterOption[];
  onApply: (filters: {
    queues: string[];
    reviewers: string[];
    errorTypes: string[];
  }) => void;
  onReset: () => void;
}

/**
 * 多维度筛选组件
 * 
 * 支持筛选维度：
 * 1. 队列（多选）
 * 2. 审核人（搜索+多选）
 * 3. 错误类型（多选）
 */
export function MultiFilter({
  queues,
  reviewers,
  errorTypes,
  onApply,
  onReset
}: MultiFilterProps) {
  const [localQueues, setLocalQueues] = useState(queues);
  const [localReviewers, setLocalReviewers] = useState(reviewers);
  const [localErrorTypes, setLocalErrorTypes] = useState(errorTypes);
  const [reviewerSearch, setReviewerSearch] = useState('');

  // 切换选项
  const toggleOption = (
    list: FilterOption[],
    setList: React.Dispatch<React.SetStateAction<FilterOption[]>>,
    value: string
  ) => {
    setList(list.map(item => 
      item.value === value ? { ...item, checked: !item.checked } : item
    ));
  };

  // 全选/取消全选
  const toggleAll = (
    list: FilterOption[],
    setList: React.Dispatch<React.SetStateAction<FilterOption[]>>,
    checked: boolean
  ) => {
    setList(list.map(item => ({ ...item, checked })));
  };

  // 应用筛选
  const handleApply = () => {
    onApply({
      queues: localQueues.filter(q => q.checked).map(q => q.value),
      reviewers: localReviewers.filter(r => r.checked).map(r => r.value),
      errorTypes: localErrorTypes.filter(e => e.checked).map(e => e.value)
    });
  };

  // 重置筛选
  const handleReset = () => {
    setLocalQueues(queues.map(q => ({ ...q, checked: false })));
    setLocalReviewers(reviewers.map(r => ({ ...r, checked: false })));
    setLocalErrorTypes(errorTypes.map(e => ({ ...e, checked: false })));
    setReviewerSearch('');
    onReset();
  };

  // 过滤审核人列表
  const filteredReviewers = localReviewers.filter(r =>
    r.label.toLowerCase().includes(reviewerSearch.toLowerCase())
  );

  // 统计已选数量
  const selectedCount = {
    queues: localQueues.filter(q => q.checked).length,
    reviewers: localReviewers.filter(r => r.checked).length,
    errorTypes: localErrorTypes.filter(e => e.checked).length
  };
  const totalSelected = selectedCount.queues + selectedCount.reviewers + selectedCount.errorTypes;

  return (
    <div className="multi-filter">
      <div className="filter-header">
        <h4 className="filter-title">🔍 多维度筛选</h4>
        <div className="filter-actions">
          <span className="filter-count">
            {totalSelected > 0 ? `已选 ${totalSelected} 项` : '未选择'}
          </span>
          <button onClick={handleReset} className="button-link">
            重置
          </button>
          <button onClick={handleApply} className="button button-sm button-primary">
            应用筛选
          </button>
        </div>
      </div>

      <div className="filter-sections">
        {/* 队列筛选 */}
        <div className="filter-section">
          <div className="filter-section-header">
            <label className="filter-section-title">
              队列 {selectedCount.queues > 0 && `(${selectedCount.queues})`}
            </label>
            <button 
              onClick={() => toggleAll(localQueues, setLocalQueues, localQueues.some(q => !q.checked))}
              className="button-link-sm"
            >
              {localQueues.every(q => q.checked) ? '取消全选' : '全选'}
            </button>
          </div>
          <div className="filter-options">
            {localQueues.map(queue => (
              <label key={queue.value} className="filter-option">
                <input
                  type="checkbox"
                  checked={queue.checked}
                  onChange={() => toggleOption(localQueues, setLocalQueues, queue.value)}
                />
                <span>{queue.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* 审核人筛选 */}
        <div className="filter-section">
          <div className="filter-section-header">
            <label className="filter-section-title">
              审核人 {selectedCount.reviewers > 0 && `(${selectedCount.reviewers})`}
            </label>
            <button 
              onClick={() => toggleAll(localReviewers, setLocalReviewers, localReviewers.some(r => !r.checked))}
              className="button-link-sm"
            >
              {localReviewers.every(r => r.checked) ? '取消全选' : '全选'}
            </button>
          </div>
          <div style={{ marginBottom: 'var(--spacing-sm)' }}>
            <input
              type="text"
              className="input input-sm"
              placeholder="搜索审核人姓名..."
              value={reviewerSearch}
              onChange={(e) => setReviewerSearch(e.target.value)}
              style={{ width: '100%' }}
            />
          </div>
          <div className="filter-options" style={{ maxHeight: '200px', overflowY: 'auto' }}>
            {filteredReviewers.length === 0 ? (
              <div style={{ padding: 'var(--spacing-sm)', color: 'var(--text-muted)', textAlign: 'center' }}>
                未找到匹配的审核人
              </div>
            ) : (
              filteredReviewers.map(reviewer => (
                <label key={reviewer.value} className="filter-option">
                  <input
                    type="checkbox"
                    checked={reviewer.checked}
                    onChange={() => toggleOption(localReviewers, setLocalReviewers, reviewer.value)}
                  />
                  <span>{reviewer.label}</span>
                </label>
              ))
            )}
          </div>
        </div>

        {/* 错误类型筛选 */}
        <div className="filter-section">
          <div className="filter-section-header">
            <label className="filter-section-title">
              错误类型 {selectedCount.errorTypes > 0 && `(${selectedCount.errorTypes})`}
            </label>
            <button 
              onClick={() => toggleAll(localErrorTypes, setLocalErrorTypes, localErrorTypes.some(e => !e.checked))}
              className="button-link-sm"
            >
              {localErrorTypes.every(e => e.checked) ? '取消全选' : '全选'}
            </button>
          </div>
          <div className="filter-options">
            {localErrorTypes.map(errorType => (
              <label key={errorType.value} className="filter-option">
                <input
                  type="checkbox"
                  checked={errorType.checked}
                  onChange={() => toggleOption(localErrorTypes, setLocalErrorTypes, errorType.value)}
                />
                <span>{errorType.label}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      <style jsx>{`
        .multi-filter {
          background: var(--bg-primary);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          padding: var(--spacing-md);
        }

        .filter-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: var(--spacing-md);
          padding-bottom: var(--spacing-sm);
          border-bottom: 2px solid var(--border);
        }

        .filter-title {
          margin: 0;
          font-size: 1.1em;
          font-weight: 600;
        }

        .filter-actions {
          display: flex;
          align-items: center;
          gap: var(--spacing-sm);
        }

        .filter-count {
          font-size: 0.875em;
          color: var(--text-muted);
        }

        .button-link {
          background: none;
          border: none;
          color: var(--primary);
          cursor: pointer;
          font-size: 0.875em;
          padding: 4px 8px;
        }

        .button-link:hover {
          text-decoration: underline;
        }

        .button-primary {
          background: var(--primary);
          color: white;
        }

        .filter-sections {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: var(--spacing-md);
        }

        .filter-section {
          border: 1px solid var(--border);
          border-radius: var(--radius);
          padding: var(--spacing-sm);
          background: var(--bg-secondary);
        }

        .filter-section-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: var(--spacing-sm);
          padding-bottom: var(--spacing-xs);
          border-bottom: 1px solid var(--border);
        }

        .filter-section-title {
          font-weight: 500;
          font-size: 0.9em;
          margin: 0;
        }

        .button-link-sm {
          background: none;
          border: none;
          color: var(--primary);
          cursor: pointer;
          font-size: 0.75em;
          padding: 2px 4px;
        }

        .button-link-sm:hover {
          text-decoration: underline;
        }

        .filter-options {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .filter-option {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 4px;
          cursor: pointer;
          border-radius: 4px;
          transition: background 0.2s;
        }

        .filter-option:hover {
          background: var(--bg-primary);
        }

        .filter-option input[type="checkbox"] {
          cursor: pointer;
        }

        .filter-option span {
          font-size: 0.875em;
        }
      `}</style>
    </div>
  );
}
