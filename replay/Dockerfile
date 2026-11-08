# Replay sandbox for Tier A. Same base as bench/Dockerfile, plus SQLite, PostgreSQL and Node.
# Network is only used at build time. Every case runs with --network none and no host mounts.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates libicu-dev less rsync \
      sqlite3 postgresql nodejs npm make procps file unzip zip xz-utils \
 && rm -rf /var/lib/apt/lists/*
ARG PWSH=7.5.2
RUN curl -fsSL -o /tmp/pwsh.tgz https://github.com/PowerShell/PowerShell/releases/download/v${PWSH}/powershell-${PWSH}-linux-arm64.tar.gz \
 && mkdir -p /opt/microsoft/powershell && tar -xzf /tmp/pwsh.tgz -C /opt/microsoft/powershell \
 && chmod +x /opt/microsoft/powershell/pwsh && ln -s /opt/microsoft/powershell/pwsh /usr/local/bin/pwsh && rm /tmp/pwsh.tgz
# Fake ssh: the remote command runs in this same container, after the local shell has already expanded it.
RUN printf '#!/bin/sh\n# usage: ssh [opts] host "remote command"\nfor last; do :; done\nexec sh -c "$last"\n' > /usr/local/bin/ssh && chmod +x /usr/local/bin/ssh
# PostgreSQL helpers for cases that need a database. Data lives in /home/dev/pgdata, owned by dev.
RUN ln -s /usr/lib/postgresql/*/bin/initdb /usr/local/bin/initdb && ln -s /usr/lib/postgresql/*/bin/pg_ctl /usr/local/bin/pg_ctl \
 && printf '#!/bin/sh\n[ -d /home/dev/pgdata ] || exit 0\npg_ctl -D /home/dev/pgdata -l /home/dev/pg.log -o "-k /tmp -c listen_addresses=" -w start >/dev/null\n' > /usr/local/bin/start-postgres \
 && chmod +x /usr/local/bin/start-postgres
RUN useradd -m -s /bin/bash dev && mkdir -p /opt/app /srv/sites && chown -R dev:dev /opt/app /srv/sites
ENV PGHOST=/tmp
USER dev
WORKDIR /home/dev
