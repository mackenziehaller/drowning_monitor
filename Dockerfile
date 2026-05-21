FROM python:3.11-slim

# ── System dependencies ───────────────────────────────────────────
# curl/gnupg to add Microsoft repo; unixodbc-dev for pyodbc build
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg2 unixodbc-dev gcc g++ \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/12/prod.list \
        -o /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── App code ──────────────────────────────────────────────────────
COPY . .

# ── Streamlit config ──────────────────────────────────────────────
# Disable the "Is this okay?" prompt and set the server to listen on all interfaces.
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true

# ── Ollama host ───────────────────────────────────────────────────
# Ollama runs on the HOST machine, not inside the container.
# On Docker Desktop (Mac/Windows) host.docker.internal resolves to the host.
# On Linux pass --add-host=host.docker.internal:host-gateway at runtime,
# or override with: -e OLLAMA_HOST=http://<host-ip>:11434
ENV OLLAMA_HOST=http://host.docker.internal:11434

# DB_PATH in config.py is "../drowning_cases.db" which resolves to /drowning_cases.db
# Mount your database file there at runtime:
#   -v /absolute/path/to/drowning_cases.db:/drowning_cases.db
# Mount chroma_db for RAG persistence:
#   -v /absolute/path/to/chroma_db:/app/chroma_db
VOLUME ["/drowning_cases.db", "/app/chroma_db", "/app/pdf_cache"]

EXPOSE 8501

CMD ["streamlit", "run", "app.py"]
