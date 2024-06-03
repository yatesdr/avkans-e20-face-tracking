import sys
sys.path.append('..')  # assuming running from lib/examples directory (cd lib/examples from base directory).
from avkans_visca_utils import AvkansControl
import time

print("White balance setting over Visca/TCP does not work, this is a bug from AVKans and a report has been submitted.")
exit()

cam1=AvkansControl("192.168.35.37")
print(cam1.socket_flush())

print("Going home...")
cam1.send_raw(cam1.cmd.ptz_home)
cam1.wait_complete()

print("Setting WB Manual mode")
cam1.send_raw(cam1.cmd.wb_mode_manual)
resp=cam1.recv_raw()
print(resp)
time.sleep(3)
print("Setting WB indoor mode")
cam1.send_raw(cam1.cmd.wb_mode_indoor)
resp=cam1.recv_raw()
print(resp)

time.sleep(3)

print("Setting WB outdoor mode")
cam1.send_raw(cam1.cmd.wb_mode_outdoor)
resp=cam1.recv_raw()
print(resp)
time.sleep(3)
print("Querying WB mode...")
cam1.send_raw(cam1.cmd.q_wb_mode)
resp=cam1.recv_raw()
print(resp)
time.sleep(3)
print("Setting mode auto")
cam1.send_raw(cam1.cmd.wb_mode_auto)
time.sleep(3)