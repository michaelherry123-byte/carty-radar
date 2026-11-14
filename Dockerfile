# Carty Radar sur le serveur Contabo (14/11/2026) — remplace le déclenchement GitHub Actions + cron-job.org.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
# tzdata : les heures affichées (Europe/Paris) sans dépendre du système
RUN pip install --no-cache-dir -r requirements.txt tzdata
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["sh", "serveur/boucle.sh"]
