# The Executor — Railway cron image.
# Each scheduled run boots this container, runs one pulse, and exits.
FROM node:22-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 ca-certificates util-linux \
 && rm -rf /var/lib/apt/lists/* \
 && npm install -g @anthropic-ai/claude-code

WORKDIR /app
COPY . .
RUN chmod +x scripts/*.sh

# Claude Code config (incl. Robinhood MCP OAuth) lives on the mounted volume so it
# survives redeploys. See README → Railway for the one-time OAuth step.
ENV CLAUDE_CONFIG_DIR=/data/claude

CMD ["./scripts/railway_pulse.sh"]
