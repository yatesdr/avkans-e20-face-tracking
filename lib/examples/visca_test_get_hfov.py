import sys
sys.path.append('..')  # assuming running from lib/examples directory (cd lib/examples from base directory).
from avkans_visca_utils import AvkansControl

cam1=AvkansControl("192.168.35.37")

was_flushed=cam1.socket_flush()
print("Dumped data from socket: ",was_flushed)

print("Going home")
cam1.send_raw(cam1.cmd.ptz_home)
cam1.wait_complete()
print("Done.\n\n")

print("Setting zoom full wide...")
cam1.send_raw(cam1.cmd.ptz_zoom(0))
cam1.wait_complete()
print("Done.\n\n")

print("inquiring as to angular field of view: ")
fov = cam1.ptz_get_hfov()
print("Position: ",fov)
print("Done.\n\n")

print("Setting zoom full tele...")
cam1.send_raw(cam1.cmd.ptz_zoom(20))
cam1.wait_complete()
print("Done.\n\n")

print("inquiring as to angular field of view: ")
fov = cam1.ptz_get_hfov()
print("Position: ",fov)
print("Done.\n\n")

print("Going home...")
cam1.send_raw(cam1.cmd.ptz_home)

exit()
