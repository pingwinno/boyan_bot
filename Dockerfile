FROM python:3.12

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY boyan_bot.py /usr/src/app

CMD [ "python", "./boyan_bot.py" ]