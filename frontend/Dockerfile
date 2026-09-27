# ─── Frontend (Vite + React + TypeScript) ──────────────────────────
FROM node:20-alpine

WORKDIR /app

# Install dependencies first for better Docker layer caching
COPY package.json package-lock.json* ./
RUN npm install

# Copy source code
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
