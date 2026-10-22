ARG API_BASE_IMAGE
FROM ${API_BASE_IMAGE}

USER root
COPY docker/offline/ocr-smoke.py /opt/basic-ocr-smoke.py
ENV PYTHONPATH=/app/package
RUN YUXI_RUNTIME_DIR=/tmp/ocr-build-runtime python /opt/basic-ocr-smoke.py --freeze \
    && rm -rf /tmp/ocr-build-runtime \
    && chown -R 1000:1000 /home/yuxi/.cache/rapidocr
USER 1000:1000
