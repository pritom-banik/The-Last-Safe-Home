# The Last Safe Home — web image: static build served by nginx (SPEC §12). Build from the repo root
# (the Method page imports docs/METHOD*.md):
#   docker build -f web/Dockerfile --build-arg VITE_API_URL=/api/v1 -t last-safe-home-web .
# With VITE_API_URL=/api/v1 nginx proxies /api/ to the `api` service (docker compose).
FROM node:20-alpine AS build
WORKDIR /src
COPY docs/ docs/
COPY web/package.json web/package-lock.json web/
RUN cd web && npm ci --no-audit --no-fund --ignore-scripts
COPY web/ web/
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=$VITE_API_URL
RUN cd web && npm run build

FROM nginx:1.27-alpine
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/web/dist /usr/share/nginx/html
EXPOSE 80
