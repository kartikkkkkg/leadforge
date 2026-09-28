FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
# Guarantee world-readable static assets regardless of the build host's umask:
# nginx workers run as the unprivileged `nginx` user and must be able to read
# these files (a restrictive umask would otherwise cause 403s on every page).
RUN chmod -R a=rX /usr/share/nginx/html
EXPOSE 80
