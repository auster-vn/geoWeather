FROM node:20-alpine AS base
WORKDIR /app

# Development stage
FROM base AS dev
COPY apps/web/package.json ./apps/web/
COPY package.json ./
RUN npm install --workspaces --legacy-peer-deps
COPY . .
ENV PORT=3000
CMD ["npm", "run", "dev", "--workspace=apps/web"]

# Production build stage
FROM base AS builder
COPY apps/web/package.json ./apps/web/
COPY package.json ./
RUN npm install --workspaces --legacy-peer-deps
COPY . .
RUN npm run build --workspace=apps/web

# Production runtime stage
FROM base AS prod
COPY --from=builder /app /app
ENV PORT=3000
CMD ["npm", "run", "start", "--workspace=apps/web"]
