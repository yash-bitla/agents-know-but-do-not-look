# Sandbox for replaying agent commands. Network is only used at build time.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates libicu-dev less rsync \
 && rm -rf /var/lib/apt/lists/*
ARG PWSH=7.5.2
RUN curl -fsSL -o /tmp/pwsh.tgz https://github.com/PowerShell/PowerShell/releases/download/v${PWSH}/powershell-${PWSH}-linux-arm64.tar.gz \
 && mkdir -p /opt/microsoft/powershell && tar -xzf /tmp/pwsh.tgz -C /opt/microsoft/powershell \
 && chmod +x /opt/microsoft/powershell/pwsh && ln -s /opt/microsoft/powershell/pwsh /usr/local/bin/pwsh && rm /tmp/pwsh.tgz
# Fake ssh: the remote command runs in this same container, after the local shell has already expanded it.
RUN printf '#!/bin/sh\n# usage: ssh [opts] host "remote command"\nfor last; do :; done\nexec sh -c "$last"\n' > /usr/local/bin/ssh && chmod +x /usr/local/bin/ssh
RUN useradd -m -s /bin/bash dev && mkdir -p /opt/app /srv/sites && chown -R dev:dev /opt/app /srv/sites
USER dev
WORKDIR /home/dev
