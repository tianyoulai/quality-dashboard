'use client';

import { AppShell } from "@/components/app-shell";
import { useEffect, useState } from "react";

export default function InternalPage() {
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    // 设置页面标题
    document.title = "内检看板 | QC统一看板";
    setLoading(false);
  }, []);
  
  if (loading) {
    return (
      <AppShell
        currentPath="/internal"
        title="内检看板"
        subtitle="加载中..."
      >
        <div>加载中...</div>
      </AppShell>
    );
  }
  
  return (
    <AppShell
      currentPath="/internal"
      title="内检看板"
      subtitle="内检数据统计与分析"
    >
      <div className="internal-page">
        <div className="hero">
          <h1 className="hero-title">🔍 内检看板</h1>
          <p className="hero-subtitle">页面正在迁移中...</p>
        </div>
        
        <div className="info-box">
          <p>内检看板功能正在从 Streamlit 迁移到 Next.js。</p>
          <p>当前可以访问原版本：<a href="https://quality-dashboard-2026.streamlit.app/" target="_blank" rel="noopener noreferrer">Streamlit 版本</a></p>
        </div>
      </div>
      
      <style jsx>{`
        .internal-page {
          max-width: 1280px;
          margin: 0 auto;
          padding: 2rem;
        }
        
        .hero {
          padding: 2rem;
          background: white;
          border-radius: 8px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
          margin-bottom: 2rem;
          border-left: 4px solid #8B5CF6;
        }
        
        .hero-title {
          margin: 0 0 0.5rem 0;
          font-size: 1.75rem;
          font-weight: 700;
          color: #1a1a1a;
        }
        
        .hero-subtitle {
          margin: 0;
          font-size: 1rem;
          color: #666;
        }
        
        .info-box {
          padding: 1.5rem;
          background: #f0f9ff;
          border: 1px solid #bfdbfe;
          border-radius: 8px;
        }
        
        .info-box p {
          margin: 0 0 0.5rem 0;
        }
        
        .info-box a {
          color: #2563eb;
          text-decoration: underline;
        }
      `}</style>
    </AppShell>
  );
}
