# week7 Step 10: multi-stage build so `docker compose up` covers the
# frontend too — build stage has the full node_modules/toolchain, the
# runtime stage only ships Next's standalone server output (next.config.js
# `output: "standalone"`).
FROM node:20-slim AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["node", "server.js"]
