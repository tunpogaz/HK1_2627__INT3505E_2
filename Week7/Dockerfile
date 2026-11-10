# ─── Stage 1: Builder (Slide 40) ───
FROM python:3.12-slim AS builder
WORKDIR /build

COPY requirements.txt ./
RUN pip install --no-cache-dir uv \
 && uv venv /opt/venv

ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

RUN uv pip install --no-cache -r requirements.txt

# ─── Stage 2: Runtime (Slide 40) ───
FROM python:3.12-slim
WORKDIR /app

RUN groupadd -r app && \
    useradd -r -g app -d /app app

# Copy virtualenv từ builder
COPY --from=builder --chown=app:app /opt/venv /opt/venv
COPY --chown=app:app . /app

ENV VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

USER app
EXPOSE 5000

# Chạy WSGI server với Gunicorn (Slide 39, 40)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "wsgi:app"]
