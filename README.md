# avkans-e20-face-tracking
A simple web interface for Yolo-V8 or Google Mediapipe face tracking implementation for AVKans E-20 Cameras using NDI and Visca TCP.   This application depends on geometry and characteristics of the E-20 Camera specifically, but you're welcome to try it out with other cameras or fork the repo to apply it to new cameras.

This code is not endorsed or distributed by AVKans, it simply uses their hardware.

# License
MIT License

# Camera set-up
The E-20 used in development was set to 1920x1080/30P using the dip switches on the bottom.    
1) Assign the camera a static IP in the web interface or using CMS
2) Make sure TCP Visca control is enabled on port 1259 (as default).   You can choose a different port and pass this port in app.py
3) The camera must have NDI enabled, or be an NDI enabled camera.   Using other protocols won't work because it's too much latency.


# Requirements
```
pip install opencv-python, numpy, sanic, ultralytics, lmbd, ndi-python
```

# Usage
Launch the application, then open your web browser.
```
python3 app.py
```

By default it serves on http://localhost:8091

1) Add your NDI sources and give them a unique name and IP address.   You will see a preview load to confirm it's working.  
2) Click the "Start Tracking" button for your assigned source to launch a thread that will search for faces and track them.

# Security notes
This application serves on the local network and anybody on that network can access it.   It's assumed this will be on a dedicated camera control / NDI network and security was largely not considered during development.   Use at your own risk, and secure appropriately if needed.

# Integration with Stream Deck
Using HTTP Get commands, the track can be started and stopped from StreamDeck by camera name or by camera IP.

By IP Address (recommended)
```
# Start tracking
http://localhost:8091/startTracking?ip=192.168.35.37

# Stop tracking
http://localhost:8091/stopTracking?ip=192.168.35.37
```

By Camera Name
```
# Start tracking
http://localhost:8091/startTracking?name=cam1

# Stop tracking
http://localhost:8091/stopTracking?name=cam1
```
# Roadmap
This is an alpha version, and needs to be cleaned up more, but is working fairly well in testing.

1) (Complete) Add support for mediapipe inference instead
2) (Complete - Untested) Add support for mult-face tracking
3) General stability and bug-fixing
4) Create dockerized implementation
5) Enable optional GPU support for those that have it.
6) Improve StreamDeck integration functionality.
