import type { NextConfig } from "next";

// Deploy sob subpath (ex.: https://wiki.ioi.ia.br/prisma) via env PRISMA_BASE_PATH.
// Em dev/local fica vazio (raiz). output standalone => imagem Docker enxuta.
const basePath = process.env.PRISMA_BASE_PATH || "";

const nextConfig: NextConfig = {
  output: "standalone",
  basePath: basePath || undefined,
  assetPrefix: basePath || undefined,
};

export default nextConfig;
