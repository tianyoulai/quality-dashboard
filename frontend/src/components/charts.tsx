'use client';

import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

// 主题色
const COLORS = {
  primary: '#8b5cf6',
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  info: '#3b82f6',
};

const CHART_COLORS = [
  COLORS.primary,
  COLORS.success,
  COLORS.info,
  COLORS.warning,
  COLORS.danger,
];

// 自定义 Tooltip 样式
const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div style={{
        background: 'var(--card-bg)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        padding: 'var(--spacing-sm)',
        boxShadow: 'var(--shadow-lg)',
      }}>
        <p style={{ margin: 0, fontWeight: 600, marginBottom: '4px' }}>{label}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} style={{ margin: 0, color: entry.color, fontSize: '0.875em' }}>
            {entry.name}: {entry.value}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

// 性能趋势折线图
export function PerformanceTrendChart({ data }: { data: any[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="name" stroke="var(--text-muted)" />
        <YAxis stroke="var(--text-muted)" />
        <Tooltip content={<CustomTooltip />} />
        <Legend />
        <Line
          type="monotone"
          dataKey="响应时间"
          stroke={COLORS.primary}
          strokeWidth={2}
          dot={{ fill: COLORS.primary, r: 4 }}
          activeDot={{ r: 6 }}
        />
        <Line
          type="monotone"
          dataKey="目标值"
          stroke={COLORS.success}
          strokeWidth={2}
          strokeDasharray="5 5"
          dot={{ fill: COLORS.success, r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

// 接口性能对比柱状图
export function ApiPerformanceBarChart({ data }: { data: any[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="name" stroke="var(--text-muted)" />
        <YAxis stroke="var(--text-muted)" />
        <Tooltip content={<CustomTooltip />} />
        <Legend />
        <Bar dataKey="优化前" fill={COLORS.danger} radius={[8, 8, 0, 0]} />
        <Bar dataKey="优化后" fill={COLORS.success} radius={[8, 8, 0, 0]} />
        <Bar dataKey="目标值" fill={COLORS.info} radius={[8, 8, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// 性能提升面积图
export function PerformanceImprovementAreaChart({ data }: { data: any[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="name" stroke="var(--text-muted)" />
        <YAxis stroke="var(--text-muted)" />
        <Tooltip content={<CustomTooltip />} />
        <Legend />
        <Area
          type="monotone"
          dataKey="提升幅度"
          stroke={COLORS.primary}
          fill={COLORS.primary}
          fillOpacity={0.6}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// 性能分布饼图
export function PerformanceDistributionPieChart({ data }: { data: any[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          labelLine={false}
          label={({ name, percent }: any) => `${name}: ${((percent || 0) * 100).toFixed(0)}%`}
          outerRadius={100}
          fill="#8884d8"
          dataKey="value"
        >
          {data.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={CHART_COLORS[index % CHART_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip content={<CustomTooltip />} />
      </PieChart>
    </ResponsiveContainer>
  );
}

// 错误率趋势图
export function ErrorRateTrendChart({ data }: { data: any[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="name" stroke="var(--text-muted)" />
        <YAxis stroke="var(--text-muted)" />
        <Tooltip content={<CustomTooltip />} />
        <Legend />
        <Area
          type="monotone"
          dataKey="错误率"
          stroke={COLORS.danger}
          fill={COLORS.danger}
          fillOpacity={0.3}
        />
        <Area
          type="monotone"
          dataKey="警戒线"
          stroke={COLORS.warning}
          fill="none"
          strokeDasharray="5 5"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// 数据库查询性能柱状图
export function DatabaseQueryBarChart({ data }: { data: any[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} layout="horizontal">
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis type="number" stroke="var(--text-muted)" />
        <YAxis type="category" dataKey="name" stroke="var(--text-muted)" width={100} />
        <Tooltip content={<CustomTooltip />} />
        <Legend />
        <Bar dataKey="查询时间" fill={COLORS.primary} radius={[0, 8, 8, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
