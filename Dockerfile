FROM python:3.9

RUN mkdir /detective-price

WORKDIR /detective-price

COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip && \
    pip install -r requirements.txt

COPY detective-price ./

CMD ["python","main.py"]