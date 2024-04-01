FROM python:3.10
RUN apt update && apt upgrade -y
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD [ "make" ]