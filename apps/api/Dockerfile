FROM python:3.12-slim AS base
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev libgeos-dev libproj-dev gcc g++ curl \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.cargo/bin:${PATH}"

FROM base AS deps
COPY pyproject.toml ./
# Create dummy lock if not exists, but we can just run uv sync
RUN pip install uv maturin && uv pip install --system -r pyproject.toml

FROM deps AS dev
COPY . .
RUN cd packages/core-rs && maturin build --release && uv pip install --system target/wheels/*.whl
ENV PYTHONPATH="/app"
CMD ["uvicorn", "apps.api.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS prod
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin
COPY . .
ENV PYTHONPATH="/app"
RUN adduser --disabled-password --no-create-home appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "apps.api.main:app", "--workers", "4", "--host", "0.0.0.0", "--port", "8000"]
