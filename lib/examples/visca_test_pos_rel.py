import sys
sys.path.append('..')  # assuming running from lib/examples directory (cd lib/examples from base directory).
from avkans_visca_utils import AvkansControl

cam1=AvkansControl("192.168.35.37")

print("Going home")
cam1.send_raw(cam1.cmd.ptz_home)
cam1.wait_complete()

print("inquiring as to my position: ")
pos=cam1.send_raw(cam1.cmd.q_ptz_pos)
print("Pos: ",pos)

print("Relative move +20 pan")
cam1.send_raw(cam1.cmd.ptz_to_rel_position(20,0,0.5,0.5))
cam1.wait_complete()

print("Relative move to -20 pan")
cam1.send_raw(cam1.cmd.ptz_to_rel_position(-20,0,0.5,0.5))
cam1.wait_complete()


print("Relative move to +10 tilt")
cam1.send_raw(cam1.cmd.ptz_to_rel_position(0,10,0.5,0.5))
cam1.wait_complete()

print("Relative move to -10 tilt")
cam1.send_raw(cam1.cmd.ptz_to_rel_position(0,-10,0.5,0.5))
cam1.wait_complete()


print("inquiring to position...")
pos=cam1.send_raw(cam1.cmd.q_ptz_position)
print("Pos: ",pos)

exit()