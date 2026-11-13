# Frontend image (sprint 3, task 3: React skeleton and routing).
#
# docker-compose mounts ./frontend into /app and keeps node_modules in an anonymous
# volume, so the image only has to provide a working toolchain: the dependencies are
# installed from the lockfile at build time and reused until the lockfile changes.
FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-fund --no-audit

COPY . .

EXPOSE 3000

# 0.0.0.0 is required inside a container; 3000 is the origin CORS_ORIGINS expects.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
