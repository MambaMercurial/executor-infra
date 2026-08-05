# The Executor — Railway always-on worker image.
# The container runs the engine daemon continuously; the daemon invokes headless
# Claude runs (pre/post-market, weekly, execution bridge) itself.
FROM node:22-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-pip ca-certificates util-linux \
 && rm -rf /var/lib/apt/lists/* \
 && npm install -g @anthropic-ai/claude-code

WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY . .
RUN chmod +x scripts/*.sh

# Claude config (incl. Robinhood MCP OAuth) + mutable book live on the /data volume.
ENV CLAUDE_CONFIG_DIR=/data/claude

CMD ["./scripts/run_daemon.sh"]
