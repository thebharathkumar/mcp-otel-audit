FROM python:3.12-slim
WORKDIR /app

# --trusted-host lets the build succeed behind TLS-intercepting proxies
# (e.g. corporate egress, sandboxed CI). Package integrity is enforced by
# wheel hashes from PyPI's index, not by the TLS chain to pypi.org.
ENV PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org pypi.python.org"

COPY _shared /app/_shared
COPY traceloop/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY traceloop/server.py /app/server.py

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "/app/server.py"]
