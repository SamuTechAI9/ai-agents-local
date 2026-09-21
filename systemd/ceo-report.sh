#!/bin/sh
for i in $(seq 1 30); do
  curl -sf --max-time 5 -o /dev/null http://127.0.0.1:5678/healthz && \
  curl -s --max-time 5 -o /dev/null https://api.telegram.org && break
  sleep 5
done
curl -s --max-time 300 -X POST http://127.0.0.1:5678/webhook/ceo-report
