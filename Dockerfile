from python:3.10-bullseye
RUN apt update && apt install -y avahi-daemon
RUN apt install -y python3-opencv
RUN service avahi-daemon start
RUN pip install flask opencv-python lmdb ndi-python face-detection-tflite 
RUN ldconfig
COPY . app/
WORKDIR app
ENTRYPOINT ["python3","app.py"]
