# avkans-e20-face-tracking
A simple web interface for Yolo-V8 face tracking implementation for AVKans E-20 Cameras using NDI and Visca TCP.   This application depends on geometry and characteristics of the E-20 Camera specifically, but you're welcome to try it out with other cameras or fork the repo to apply it to new cameras.

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
pip install opencv-python, numpy, sanic, ultralytics, lmbd
```

# Usage
Launch the application, then open your web browser.
```
python3 app.py
```

By default it serves on http://localhost:8089

1) Add your NDI sources and give them a unique name and IP address.   You will see a preview load to confirm it's working.  
2) Click the "Start Tracking" button for your assigned source to launch a thread that will search for faces and track them.

# Roadmap
This is an alpha version, and needs to be cleaned up more, but is working fairly well in testing.

1) Add support for mediapipe inference instead
2) Add support for mult-face tracking
3) General stability and bug-fixing
4) Create dockerized implementation
5) Enable optional GPU support for those that have it.
