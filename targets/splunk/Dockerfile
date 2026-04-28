FROM python:3.12-slim
WORKDIR /app

ENV PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org pypi.python.org"

COPY _shared /app/_shared
COPY splunk/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY splunk/server.py /app/server.py

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "/app/server.py"]
