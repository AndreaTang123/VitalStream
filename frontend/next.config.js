/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // week7 Step 10: standalone output is what makes the Dockerfile's final
  // stage a small `node server.js` image instead of shipping node_modules.
  output: "standalone",
};

module.exports = nextConfig;
