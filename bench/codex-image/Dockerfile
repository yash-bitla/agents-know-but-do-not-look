# Codex CLI in a throwaway container. No host folders are mounted. Only the login file is copied in at run time.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/*
ARG V=0.166.0
RUN curl -fsSL -o /tmp/c.tgz https://github.com/openai/codex/releases/download/rust-v${V}/codex-aarch64-unknown-linux-musl.tar.gz \
 && tar -xzf /tmp/c.tgz -C /usr/local/bin && mv /usr/local/bin/codex-aarch64-unknown-linux-musl /usr/local/bin/codex && chmod +x /usr/local/bin/codex && rm /tmp/c.tgz
RUN useradd -m reviewer && mkdir -p /home/reviewer/.codex /home/reviewer/work && chown -R reviewer:reviewer /home/reviewer
USER reviewer
WORKDIR /home/reviewer/work
