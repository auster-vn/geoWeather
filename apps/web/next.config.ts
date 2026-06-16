import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  distDir: '.next-dev',
  typescript: {
    ignoreBuildErrors: true,
  },
  allowedDevOrigins: ['192.168.2.39', 'localhost'],
  turbopack: {
    root: "/home/cp/Documents/geoWeather"
  }
};

export default nextConfig;
