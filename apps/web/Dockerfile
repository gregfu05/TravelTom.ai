FROM node:20-alpine AS build

WORKDIR /app

COPY apps/web/package*.json ./
RUN npm ci

COPY apps/web ./

ARG VITE_API_BASE_URL=/api/v1
ARG VITE_APPINSIGHTS_CONNECTION_STRING=

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_APPINSIGHTS_CONNECTION_STRING=$VITE_APPINSIGHTS_CONNECTION_STRING

RUN npm run build

FROM nginx:1.27-alpine

COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
