# Production image: build the static Vite bundle, then serve it with nginx.
# Not used by local dev (that's `npm run dev`, see vite.config.ts's proxy) —
# this is for a real deployment where the frontend is its own service.

FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Baked in at build time — see src/lib/apiClient.ts. Vite only inlines
# import.meta.env.VITE_* values that exist in the process environment
# during `vite build`, so this has to be an ENV, not just an ARG.
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 8080
