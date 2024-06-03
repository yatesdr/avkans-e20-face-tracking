import sys
sys.path.append('..')  # assuming running from lib/examples directory (cd lib/examples from base directory).
from avkans_visca_utils import AvkansControl
import time

cam1=AvkansControl("192.168.35.37")

print("Going home")
cam1.send_raw(cam1.cmd.ptz_home)
cam1.wait_complete()

print("Going to +30,+10 relative tilt.")
cam1.send_raw(cam1.cmd.ptz_to_rel_position(30,10,1,1))
cam1.wait_complete()

print("Saving preset 1")
cam1.send_raw(cam1.cmd.pset_store(1))
cam1.socket_flush()

print("Preset saved....")
print("Going home")
cam1.send_raw(cam1.cmd.ptz_home)
cam1.wait_complete()

print("At home position, going to preset 1")
time.sleep(3)
print("Recalling Preset 1")
cam1.send_raw(cam1.cmd.pset_recall(1))
cam1.wait_complete()

print("Going home")
cam1.send_raw(cam1.cmd.ptz_home)
cam1.wait_complete()


'''
print("Going to 0,0")
cam1.send_raw(cam1.cmd.ptz_to_abs_position(0,0,0.5,0.5))
time.sleep(5)

print("tilting to -10 degrees")
cam1.send_raw(cam1.cmd.ptz_to_abs_position(0,-10,0.5,0.5))
time.sleep(5)

print("tilting to +10 degrees")
cam1.send_raw(cam1.cmd.ptz_to_abs_position(0,10,0.5,0.5))
time.sleep(5)
'''

