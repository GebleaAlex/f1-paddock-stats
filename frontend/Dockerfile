FROM node:24-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:24-slim
WORKDIR /app
COPY --from=build /app/.output ./.output
ENV NODE_ENV=production PORT=3000 HOST=0.0.0.0 NUXT_API_BASE=http://api:8020
USER node
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
