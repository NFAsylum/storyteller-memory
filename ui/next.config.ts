import path from "node:path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Repo root also has a package-lock.json (unrelated tooling); pin Turbopack's
  // workspace root to this app so it stops warning about multiple lockfiles.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
