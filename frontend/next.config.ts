import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Lean, self-contained server bundle for the Docker image (see
  // frontend/Dockerfile) - copies only the traced production deps instead
  // of the full node_modules tree.
  output: "standalone",
};

export default nextConfig;
