FROM python:3.10
RUN apt update && apt upgrade -y
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV PYTHONPATH=src
CMD [ "uvicorn", "app.api.asgi:app", "--host", "0.0.0.0", "--port", "9000" ]
EXPOSE 9000