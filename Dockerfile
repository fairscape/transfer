FROM ubuntu:latest
RUN apt-get update -y
RUN apt-get upgrade -y
RUN apt-get install curl -y
RUN apt-get update -y
RUN apt-get install -y python3 python3-pip build-essential


RUN export PATH=/sbin:/bin:/usr/bin:/usr/sbin:/usr/local/sbin:/usr/local/bin
RUN apt-get install vim -y

COPY requirements.txt .
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt

COPY ./app .
COPY . .


ENTRYPOINT [ "python3","transfer.py"]
