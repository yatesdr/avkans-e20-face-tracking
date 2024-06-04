import sys,time
sys.path.append('..')  # assuming running from lib/examples directory (cd lib/examples from base directory).
from avkans_visca_utils import AvkansControl

cam1=AvkansControl("192.168.35.37")

zoom_ratio = cam1.ptz_get_zoom_mag()

print("Zoom ratio:  ",zoom_ratio)

print("Sending to 5x zoom...")
cam1.send(cam1.cmd.ptz_zoom(5))
cam1.wait_complete()
time.sleep(2)

print("Sending to 10x zoom...")
cam1.send(cam1.cmd.ptz_zoom(10))
cam1.wait_complete()
time.sleep(2)

print("Sending to 15x zoom...")
cam1.send(cam1.cmd.ptz_zoom(15))
cam1.wait_complete()
time.sleep(2)

print("Sending to 20x zoom...")
cam1.send(cam1.cmd.ptz_zoom(20))
cam1.wait_complete()
time.sleep(2)

for i in range(10):
    print("Checking zoom...")
    zoom_ratio = cam1.ptz_get_zoom_mag()
    print("Zoom ratio:  ",zoom_ratio)

print("Setting zoom to full wide")
cam1.send(cam1.cmd.ptz_zoom(1))
cam1.wait_complete()

print("Checking zoom...")
zoom_ratio = cam1.ptz_get_zoom_mag()
print("Zoom ratio:  ",zoom_ratio)


