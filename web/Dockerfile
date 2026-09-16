# Dev-oriented image: docker-compose bind-mounts ./web over /app, this layer
# just needs node_modules present in the image (kept out of the bind mount
# via the anonymous volume on /app/node_modules in docker-compose.yml).
FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 4200

CMD ["npm", "start", "--", "--host", "0.0.0.0", "--poll", "2000"]
