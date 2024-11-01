FROM python:3.9.20-bullseye

COPY requirements.txt /requirements.txt
RUN pip install -r /requirements.txt

COPY *.whl /
RUN for wheel in $(find . -name '*.whl'); do pip install $wheel; rm $wheel; done 

CMD /usr/local/bin/python

