FROM python:3.9.4
MAINTAINER ppotatoo

WORKDIR /code
ADD requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]