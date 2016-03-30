FROM docker.io/archlight/zipline:v8
MAINTAINER Ren Wei

ADD ./web /home/vmagent/app/web
#ENV GOOGLE_APPLICATION_CREDENTIALS /home/vmagent/app/web/tigris_key.json
ENV GOOGLE_APPLICATION_CREDENTIALS web/tigris_key.json

# Container configuration
EXPOSE 5000 
VOLUME [ "/var/log/app_engine", "/root/.config/gcloud" ]

ENTRYPOINT ["/usr/bin/python"]
CMD ["/app/web/engine.py"]
