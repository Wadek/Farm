FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh
ENV DATABASE_URL=sqlite:////data/farm.db
EXPOSE 8080
CMD ["/app/entrypoint.sh"]
