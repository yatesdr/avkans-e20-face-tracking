import sys
sys.path.append('..')  # assuming running from lib/examples directory (cd lib/examples from base directory).
from avkans_visca_utils import AvkansControl

cam1=AvkansControl("192.168.35.37")

print("Going home")
cam1.send_raw(cam1.cmd.ptz_home)
cam1.wait_complete()

print("inquiring as to my position: ")
pos = cam1.ptz_get_abs_position()
print("pan,tilt=",pos)

print("Going to 0,0")
cam1.send_raw(cam1.cmd.ptz_to_abs_position(0,0,0.5,0.5))
cam1.wait_complete()

print("tilting to -10 degrees")
cam1.send_raw(cam1.cmd.ptz_to_abs_position(0,-10,0.5,0.5))
cam1.wait_complete()

print("tilting to +10 degrees")
cam1.send_raw(cam1.cmd.ptz_to_abs_position(0,10,0.5,0.5))
cam1.wait_complete()

print("tilting to +90 degrees")
cam1.send_raw(cam1.cmd.ptz_to_abs_position(0,90,0.5,0.5))
cam1.wait_complete()

print("tilting to -28 degrees")
cam1.send_raw(cam1.cmd.ptz_to_abs_position(0,-28,0.5,0.5))
cam1.wait_complete()

print("Panning to -175 degrees (left)")
cam1.send_raw(cam1.cmd.ptz_to_abs_position(-175,0,0.5,0.5))
cam1.wait_complete()

print("Panning to 175 degrees (right)")
cam1.send_raw(cam1.cmd.ptz_to_abs_position(175,0,0.5,0.5))
cam1.wait_complete()

print("Going home at full speed")
cam1.send_raw(cam1.cmd.ptz_to_abs_position(0,0,1,1))
cam1.wait_complete()