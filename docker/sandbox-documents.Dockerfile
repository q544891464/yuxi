FROM enterprise-public-cn-beijing.cr.volces.com/vefaas-public/all-in-one-sandbox@sha256:6328d7fd2f0ff0b4c147c3d05b3df1ce331f4a482eb6e550ecd64ed1fcf906e7

USER root
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
RUN sed -i 's|http://archive.ubuntu.com/ubuntu/|https://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g; s|http://security.ubuntu.com/ubuntu/|https://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libreoffice-writer libreoffice-calc libreoffice-impress fonts-noto-cjk poppler-utils \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install --no-cache-dir --index-url "$PIP_INDEX_URL" \
    python-docx==1.2.0 docxtpl==0.20.2 pypdf==6.0.0 reportlab==4.4.3
COPY docker/sandbox-documents-smoke.py /opt/yuxi-documents-smoke.py
RUN python3 /opt/yuxi-documents-smoke.py
