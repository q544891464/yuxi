ARG SANDBOX_RUNTIME_IMAGE
FROM ${SANDBOX_RUNTIME_IMAGE}

USER root

ENV DEBIAN_FRONTEND=noninteractive \
    DOTNET_ROOT=/usr/local/dotnet \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 \
    DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE=true \
    NUGET_PACKAGES=/opt/yuxi-nuget \
    NODE_PATH=/opt/yuxi-node/node_modules \
    PATH=/usr/local/dotnet:/opt/yuxi-node/node_modules/.bin:${PATH}

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        fonts-noto-cjk \
        libreoffice-calc \
        libreoffice-impress \
        libreoffice-writer \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY docker/offline/sandbox-requirements.txt /tmp/yuxi-sandbox-requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/yuxi-sandbox-requirements.txt \
    && rm /tmp/yuxi-sandbox-requirements.txt

COPY docker/offline/sandbox-package.json /opt/yuxi-node/package.json
COPY docker/offline/sandbox-package-lock.json /opt/yuxi-node/package-lock.json
RUN npm ci --prefix /opt/yuxi-node --omit=dev --no-audit --no-fund

COPY docker/offline/sandbox-nuget.csproj /tmp/yuxi-openxml-cache/yuxi-openxml-cache.csproj
RUN dotnet restore /tmp/yuxi-openxml-cache/yuxi-openxml-cache.csproj \
        --packages "$NUGET_PACKAGES" \
        --ignore-failed-sources

COPY docker/offline/sandbox-smoke.py /opt/yuxi-sandbox-smoke.py
COPY docker/offline/runtime-README.md /opt/yuxi-runtime-README.md

USER 1000:1000
