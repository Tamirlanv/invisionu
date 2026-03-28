import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: path.join(__dirname, "../.."),
  async rewrites() {
    const dest = process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";
    return [{ source: "/api/v1/:path*", destination: `${dest}/api/v1/:path*` }];
  },
};

export default nextConfig;
