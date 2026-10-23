import type { NextConfig } from "next";

// FastAPI backend. The browser calls /api/... on this app, and Next.js forwards it,
// so the login cookie stays on one origin and no CORS setup is needed.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  devIndicators: false, // hides the Next.js "N" badge in development
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/:path*` }];
  },
};

export default nextConfig;
