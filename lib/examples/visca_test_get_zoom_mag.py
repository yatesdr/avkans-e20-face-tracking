import sys
sys.path.append('..')  # assuming running from lib/examples directory (cd lib/examples from base directory).
from avkans_visca_utils import AvkansControl

cam1=AvkansControl("192.168.35.37")

zoom_ratio = cam1.ptz_get_zoom_mag()

print("Zoom ratio:  ",zoom_ratio)

print("Sending to 5x zoom...")
cam1.send_raw(cam1.cmd.ptz_zoom(5))
cam1.wait_complete()

for i in range(10):
    print("Checking zoom...")
    zoom_ratio = cam1.ptz_get_zoom_mag()
    print("Zoom ratio:  ",zoom_ratio)

print("Setting zoom to full wide")
cam1.send_raw(cam1.cmd.ptz_zoom(1))
cam1.wait_complete()

print("Checking zoom...")
zoom_ratio = cam1.ptz_get_zoom_mag()
print("Zoom ratio:  ",zoom_ratio)


