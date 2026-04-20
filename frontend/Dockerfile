# ============================================================
# QC 统一看板前端 - Docker 镜像
# ============================================================
# 基础镜像：Node.js 20
# 构建：Next.js 静态导出或 standalone 模式
# ============================================================

# 阶段1：构建
FROM node:20-alpine AS builder

WORKDIR /app

# 复制依赖文件
COPY package.json package-lock.json* ./

# 安装依赖
RUN npm ci

# 复制代码
COPY . .

# 构建（Next.js standalone 模式）
RUN npm run build

# 阶段2：运行
FROM node:20-alpine AS runner

WORKDIR /app

# 创建非 root 用户
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# 复制构建产物
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

CMD ["node", "server.js"]
