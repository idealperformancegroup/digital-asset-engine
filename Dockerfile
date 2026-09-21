FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ARC_TOOLKIT_DIR=/opt/arcads

RUN apt-get update && apt-get install -y --no-install-recommends \
    git ffmpeg jq nodejs npm curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN git clone --depth 1 https://github.com/krusemediallc/arcads-claude-code.git ${ARC_TOOLKIT_DIR} \
    && if [ -f "${ARC_TOOLKIT_DIR}/shared/skills/meta-ad-builder/scripts/requirements.txt" ]; then \
         pip install --no-cache-dir -r "${ARC_TOOLKIT_DIR}/shared/skills/meta-ad-builder/scripts/requirements.txt"; \
       fi

COPY . .

CMD ["python", "worker.py"]
