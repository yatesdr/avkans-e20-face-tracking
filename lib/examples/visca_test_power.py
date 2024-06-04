import sys
sys.path.append('..')  # assuming running from lib/examples directory (cd lib/examples from base directory).
from avkans_visca_utils import AvkansControl
import time

cam1=AvkansControl("192.168.35.37")

print("Powering down")
cam1.send(cam1.cmd.power_off)
cam1.wait_complete()
time.sleep(5)

print("Powering up")
cam1.send(cam1.cmd.power_on)
cam1.wait_complete()
time.sleep(5)

print("Resetting")
cam1.send(cam1.cmd.ptz_reset)
time.sleep(5)
