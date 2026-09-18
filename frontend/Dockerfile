# Development image: installs dependencies fresh into the image (never reuses
# the host's node_modules) and runs the Next.js dev server against a
# bind-mounted copy of the source, so host edits hot-reload inside the container.
FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
