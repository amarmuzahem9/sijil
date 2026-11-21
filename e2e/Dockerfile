# Image version MUST match @playwright/test in package.json.
FROM mcr.microsoft.com/playwright:v1.65.1-noble
WORKDIR /e2e
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ENTRYPOINT ["npx", "playwright", "test"]
