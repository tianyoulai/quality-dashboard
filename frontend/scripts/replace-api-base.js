#!/usr/bin/env node
/**
 * 将所有页面中的 hardcode localhost:8000 替换为环境变量读取
 * 在 import 区域插入 API_BASE，替换 fetch URL
 */
const fs = require('fs');
const path = require('path');

const files = [
  'src/app/details/page.tsx',
  'src/app/error-analysis/page.tsx',
  'src/app/internal/page.tsx',
  'src/app/monitor/page.tsx',
  'src/app/newcomers/batch/page.tsx',
  'src/app/visualization/page.tsx',
];

const BASE = path.resolve(__dirname, '..');

files.forEach(rel => {
  const fp = path.join(BASE, rel);
  if (!fs.existsSync(fp)) { console.log('SKIP (not found):', rel); return; }

  let src = fs.readFileSync(fp, 'utf8');
  const before = (src.match(/http:\/\/localhost:8000/g) || []).length;

  // 替换所有 http://localhost:8000 为模板字符串形式
  src = src.replace(/http:\/\/localhost:8000/g, '${API_BASE}');

  // 在第一行 'use client'; 后插入 API_BASE 常量（如果还没有）
  if (!src.includes('const API_BASE')) {
    src = src.replace(
      "'use client';",
      "'use client';\n\nconst API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';"
    );
  }

  fs.writeFileSync(fp, src, 'utf8');
  const after = (src.match(/\$\{API_BASE\}/g) || []).length;
  console.log(`✅ ${rel}: ${before} occurrences replaced`);
});

console.log('\nDone!');
