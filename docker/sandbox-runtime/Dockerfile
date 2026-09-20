ARG SANDBOX_BASE_IMAGE=enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox:1.11.0
FROM ${SANDBOX_BASE_IMAGE}

ARG DOTNET_SDK_VERSION=8.0.425

USER root

ENV DEBIAN_FRONTEND=noninteractive \
    DOTNET_ROOT=/usr/local/dotnet \
    PATH=/usr/local/dotnet:${PATH}

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        tesseract-ocr \
        tesseract-ocr-chi-sim \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/yuxi-sandbox-requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/yuxi-sandbox-requirements.txt \
    && rm /tmp/yuxi-sandbox-requirements.txt

RUN curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh \
    && bash /tmp/dotnet-install.sh --version "$DOTNET_SDK_VERSION" --install-dir "$DOTNET_ROOT" --no-path \
    && rm /tmp/dotnet-install.sh \
    && dotnet --info >/dev/null
