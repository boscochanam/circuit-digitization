import type { NextConfig } from "next";

const apiInternal =
  process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  // Required when opening the dev UI via LAN IP (e.g. http://192.168.1.22:4200)
  allowedDevOrigins: ["192.168.1.22", "localhost", "127.0.0.1"],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiInternal}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
