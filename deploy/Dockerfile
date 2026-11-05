# syntax=docker/dockerfile:1
# GERVA Capital — immagine unica per portale, battito e scheduler di GERVA-Q.
# Codice di proprieta' di root e in sola lettura per l'utente di servizio; tutto lo stato sta nei volumi.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Europe/Rome HOME=/tmp

# niente apt: meno pacchetti, meno superficie d'attacco (tzdata arriva da pip, patch e' in Python)
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin gerva \
 && mkdir -p /data /keys /andrea && chown 10001:10001 /data /keys /andrea && chmod 700 /data /keys /andrea     # i volumi nominati ereditano proprieta' e permessi

WORKDIR /app
COPY deploy/requirements.lock /app/deploy/requirements.lock
# yfinance serve solo a GERVA-Q (download dei prezzi): fuori dal lock della societa'
# certificato facoltativo per proxy aziendali con ispezione TLS: docker build --secret id=pipca,src=<ca.crt>
RUN --mount=type=secret,id=pipca,required=false \
    if [ -f /run/secrets/pipca ]; then export PIP_CERT=/run/secrets/pipca; fi; \
    pip install -r /app/deploy/requirements.lock tzdata yfinance==0.2.66

COPY . /app
RUN chmod -R a-w /app && chmod 0555 /app/deploy/entrypoint.sh

USER 10001:10001
ENTRYPOINT ["/app/deploy/entrypoint.sh"]
CMD ["python", "firm.py", "status"]
