import sys
sys.path.append('..')  # assuming running from lib/examples directory (cd lib/examples from base directory).
from avkans_visca_utils import AvkansControl
import time

cam1=AvkansControl("192.168.35.37")

print("Powering down")
cam1.send_raw(cam1.cmd.power_off)
time.sleep(10)

print("Powering up")
cam1.send_raw(cam1.cmd.power_on)
time.sleep(10)

print("Resetting")
cam1.send_raw(cam1.cmd.ptz_reset)
cam1.socket_flush()
time.sleep(5)

