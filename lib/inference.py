# Thread for doing the actual camera tracking commands.
# This thread assumes a parked zoom, and tracks a single "face".
def yolo_tracker(cam_ip):
    print("Single face tracking thread started on ",cam_ip)

    model_face = YOLO('yolov8n-face.pt')
    ndi = AvkansCamera()
    ndi.connect_by_ip(cam_ip)
    frame = ndi.get_cv2_frame()  # First frame takes a second or two, pull it at inits.

    ptz = AvkansControl(cam_ip)

    # For debugging it's useful to start at home.   Disable for prod.
    ptz.send(ptz.cmd.ptz_home)
    ptz.wait_complete()

    hafov = ptz.ptz_get_hfov() # horizontal angular field of view.
    print("hafov 1: ",hafov)

    error_vector=(None,None) # error is stored in this vector after successful detection.
    target_position=(0.5,0.5) # width,height in range 0 to 1.  Where do you want the center of the target in the frame?
    allowed_error=(0.1,0.1) # width,height in range 0 to 1.   FHD 1920x1080, 0.1 corresponds to 192,108 pixel allowed error vectors.
    
    ptz.socket_flush()
    hafov = ptz.ptz_get_hfov() # horizontal angular field of view.
    vafov = 9./16.*hafov # vertical angular field of view, assumes 16:9 aspect ratio and rectilinear lens.

    # Where we want the target in the frame
    target_loc = np.array((frame.shape[1]*target_position[0],frame.shape[0]*target_position[1]))

    loop_rate=10 # starting value   
    while(True):
        tstart=time.time()

        # Flush socket messages if they accumulated.
        while (ptz.recv(blocking=False)):
            pass
    
        hafov = ptz.ptz_get_hfov() # horizontal angular field of view.
        vafov = 9./16.*hafov # vertical angular field of view, assumes 16:9 aspect ratio and rectilinear lens.
        print("Field of view: ",hafov,vafov)

        # To most closely sync the current position with the frame, it's best to get position first
        # position getting has the most latency.
        cam_abs_pos = ptz.ptz_get_position() # About 50ms or so usually.
        if cam_abs_pos==None: # Sometimes the socket flakes.
            continue
        frame_ts=time.time()

        # Grab a matching frame right away - NDI frame grabbing is usually pretty quick, 5ms or so.
        frame = ndi.get_cv2_frame()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        frame.setflags(write=1)
        actual_loc = detect_single_face_yolov8(frame,model_face)

        t_elapsed=time.time()-frame_ts # Use for estimating camera position if it was moving.
    
        error_vector = actual_loc-target_loc
        permitted_error = allowed_error * np.array((frame.shape[1],frame.shape[0]))
        dx = float(hafov*error_vector[0])/float(frame.shape[1]) # pan error in degrees
        dy = -float(vafov*error_vector[1])/float(frame.shape[0]) # tilt error in degrees
        cam_abs_pos = np.array(cam_abs_pos)
        cam_correct_pos = cam_abs_pos + np.array((dx,dy))

        if actual_loc:
            actual_loc=np.array(actual_loc)
        else:
            print("No face detected, passing")
            continue

        # If we are outside the allowable error, command a correction.
        if (abs(error_vector[0]) > permitted_error[0] or abs(error_vector[1]) > permitted_error[1]):
            # we want our correction to take about 3x the loop time.
            # Loop at 10hz means we want 0.3s in our movement command.
            # To accomplish, compute angular movement and convert to cam speeds for pan and tilt.
            pan_angular_error = abs(error_vector[0])/frame.shape[1]*hafov # degrees
            tilt_angular_error = abs(error_vector[1])/frame.shape[0]*vafov # degrees
            pan_speed = ptz.pan_deg_per_sec_to_speed(pan_angular_error*loop_rate/6.)
            tilt_speed = ptz.tilt_deg_per_sec_to_speed(tilt_angular_error*loop_rate/6.)


            # Continuous motion means some responses may get queued up, flush them.
            #ptz.socket_flush()

            ptz.send(ptz.cmd.ptz_to_abs_position(cam_correct_pos[0],cam_correct_pos[1],pan_speed,tilt_speed))
            #ptz.wait_complete()

        loop_rate=1/(time.time()-tstart)
        print("\rLoop rate: ",loop_rate," Hz",end=None)

        if haltTrackingThread(cam_ip):
            exit()

def clip(value, min_val, max_val):
    return min(max(value, min_val), max_val)


def detect_single_face_yolov8(array,model_face):
    """

    Args:
        frame (_array_): Incoming Camera Frame from PTZ 

    Returns:
        _type_: cx is x coordinate, cy is y coordinate

    """
    person_in_frame = False 
    results = model_face(array,verbose = False)  # generator of Results objects
    array = results[0].plot()  
    keypoints = results[0].keypoints
    cx = 1000 
    cy = 350
    centroid=False
    
    try: 
        for r in results:
            #boxes = r.boxes.xyxn.cpu().numpy()
            #boxes = r.boxes.xywh.cpu().numpy()

            boxes = r.boxes.xyxy.cpu().numpy()
            print("Boxes: ",boxes)      
            boxes=boxes[0]
            print("Boxes[0]: ",boxes)
            centroid = ( (boxes[0]+(boxes[2]-boxes[0])/2.), (boxes[1]+(boxes[3]-boxes[1])/2.) )
            print("Centroid: ",centroid)


            #print(boxes[0][1])
            #cx = int(boxes[0][0])
            #cy = int(boxes[0][1])
            #x_left = clip(cx - 300, 0, 1920)
            #x_right = clip(cx + 300, 0, 1920)
            #y_up = clip(cy - 250, 0, 1080)
            #y_down = clip(cy + 350, 0, 1080)
            #headshot = array[y_up : y_down, x_left : x_right]
            #cv2.imshow("Single_Person_Yolov8_Headshot",headshot)
            #array = cv2.circle(array, (cx,cy), 7, (255,0,0), cv2.FILLED)
            person_in_frame = True
 
    except Exception as e:
            #headshot = MRE_LOGO
            #cv2.imshow("Single_Person_Yolov8_Headshot",headshot)
            print("Exception occurred in detect single face: ",e)
            pass  

    return centroid