import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Docker 部署必须：生成 standalone 包，体积小、启动快
  output: "standalone",
};

export default nextConfig;
