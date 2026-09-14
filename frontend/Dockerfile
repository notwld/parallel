FROM node:24-slim
WORKDIR /app
COPY package.json package-lock.json ./
# npm ci alone can skip the platform's native rolldown binding (npm/cli#4828),
# so refetch optional deps without rewriting the lockfile.
RUN npm ci && npm install --include=optional --no-save
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
