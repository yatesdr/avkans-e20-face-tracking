import NDIlib
import cv2
from lib.avkans_ndi_utils import AvkansCamera

cam_ip = "192.168.35.37"
cam1 = AvkansCamera()
cam1.connect_by_ip(cam_ip)
frame = cam1.get_cv2_frame()
cv2.imshow("Hello",frame)
cv2.waitKey()

