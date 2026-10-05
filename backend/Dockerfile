FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --system lain \
    && useradd --system --gid lain --home-dir /app --no-create-home lain

COPY --chown=lain:lain model.py server.py *.txt ./
USER lain
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)" || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-proxy-headers"]
