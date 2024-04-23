FROM python:3.10
RUN apt update && apt upgrade -y
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD [ "bash" ]
LABEL org.opencontainers.image.source=https://github.com/pikxels/pikxels