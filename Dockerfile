FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
COPY entrypoint.sh .
COPY . .
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get purge -y gcc && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /root/.cache extra doc preview README.md LICENSE .gitignore
ENTRYPOINT ["/app/entrypoint.sh"]