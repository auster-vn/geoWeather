import type { NextConfig } from "next";
import path from "path";

const isCI = process.env.VERCEL === "1" || process.env.CI === "true";

const nextConfig: NextConfig = {
  distDir: isCI ? undefined : '.next-dev',
  typescript: {
    ignoreBuildErrors: true,
  },
  allowedDevOrigins: ['192.168.2.39', 'localhost'],
  turbopack: {
    root: path.resolve(__dirname, "../..")
  }
};

export default nextConfig;
