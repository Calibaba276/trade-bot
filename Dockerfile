# Portable quality-check environment for Glass Box.
#
# This image intentionally excludes MT5 execution. MetaTrader 5 and the
# MetaTrader5 Python package belong on the native Windows host, where NSSM runs
# the orchestrator against the local terminal. Keeping this image offline and
# broker-free makes it safe to build on any developer machine or CI runner.
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system glassbox \
    && useradd --system --gid glassbox --create-home glassbox

# CI tooling is deliberately separate from requirements.txt, which contains
# Windows/MT5 production dependencies that cannot be run in this Linux image.
COPY requirements-ci.txt ./requirements-ci.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements-ci.txt

COPY --chown=glassbox:glassbox backend ./backend
COPY --chown=glassbox:glassbox tests ./tests
COPY --chown=glassbox:glassbox pyrightconfig.json ./pyrightconfig.json

USER glassbox

# Same offline backend gate used by GitHub Actions. It never contacts MT5,
# broker accounts, Azure Key Vault, Redis, Supabase, or Telegram.
CMD ["sh", "-c", "python -m compileall -q backend/strategies backend/services tests && python -m ruff check --select=E9,F63,F7,F82 backend/strategies backend/services tests && python -m pyright backend/strategies backend/services tests && python -m pytest -q tests"]
