import sys, time
import numpy as np
sys.path.append('..')  # assuming running from lib/examples directory (cd lib/examples from base directory).
from avkans_visca_utils import AvkansControl

cam1=AvkansControl("192.168.35.37")
cam1.socket_flush()

times = []
speeds=[0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0]
for speed in speeds:

    print("Going home at normal speed.")
    print("Sending: ",cam1.cmd.ptz_zero_zero)
    cam1.send_raw(cam1.cmd.ptz_zero_zero)
    cam1.wait_complete()
    print("Done.\n\n")

    print(f"Panning to 175 left at speed {speed}")
    c = cam1.cmd.ptz_to_abs_position(-175,0,speed,0)
    print("Sending command: ",c)
    cam1.send_raw(cam1.cmd.ptz_to_abs_position(-175,0,speed,0))
    t_pan0 = time.time()
    cam1.wait_complete()

    t_pan0 = time.time()-t_pan0
    print(f"Speed {speed}:  175 degrees in {t_pan0} seconds.")
    times.append(t_pan0)


print("Going home")
cam1.send_raw(cam1.cmd.ptz_home)
cam1.wait_complete()
print("Done.\n\n")

print("Speeds: ",speeds)
print("Times: ",times)
t = np.array(times)
s = np.array(speeds)
d = 175 / t
print("Degrees/sec: ",d)



