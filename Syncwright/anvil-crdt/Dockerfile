FROM node:20-alpine

WORKDIR /app

COPY engine/package*.json ./engine/
RUN cd engine && npm ci

COPY engine/ ./engine/
RUN cd engine && npm run build

COPY adapters/ ./adapters/
COPY bench/ ./bench/
COPY README.md ./

CMD ["python3", "bench/self_check.py", "--adapter", "adapters.myteam:Engine", "--fk-policy", "tombstone", "--quick"]

