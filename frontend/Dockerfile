FROM node:20-slim AS deps
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund

FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN mkdir -p public
# Git doesn't track empty directories, so a fresh clone can be missing
# public/ entirely if it had no files in it - make sure it exists before
# the runner stage tries to copy it, so the build never breaks over this.
RUN mkdir -p public

# NEXT_PUBLIC_* vars are inlined into the client bundle at BUILD time, so
# this one must be passed as a build ARG (see docker-compose.yml), not just
# a runtime environment: variable. It's the URL the *browser* will call -
# normally the backend's published host port, e.g. http://localhost:8000.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production

# Next.js "standalone" output - a minimal, self-contained server bundle -
# copied from the builder stage. See app/next.config.js `output: "standalone"`.
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
# API_INTERNAL_BASE_URL is read at RUNTIME by server components (see
# lib/api.ts) - it's how the frontend container reaches the backend
# container over the Docker network (e.g. http://backend:8000), which is
# different from NEXT_PUBLIC_API_BASE_URL above.
CMD ["node", "server.js"]
