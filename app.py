
from flask import Flask, redirect, request
#from flask.response import text, json, html, redirect
from lib.avkans_ndi_utils import AvkansCamera
from lib.avkans_visca_utils import AvkansControl
import json as jsonlib
import os, cv2, time, threading, lmdb, pickle, base64, operator
from queue import Queue
from ultralytics import YOLO
import numpy as np

# Mediapipe models via python's face-detection-tflite models
from fdlite import FaceDetection, FaceDetectionModel

# Instantiate Sanic app
app = Flask("ptzTracker")
db_env=lmdb.open("ptzTracker.db")

tqueues=list()

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

# A tracking thread using google mediapipe.
def mediapipe_tracker(cam_ip, zoom=False):
    print("MediaPipe tracker thread started on ",cam_ip)

    detect_faces = FaceDetection(model_type=FaceDetectionModel.FULL)

    ndi = AvkansCamera()
    ndi.connect_by_ip(cam_ip)
    frame = ndi.get_cv2_frame()  # First frame takes a second or two, pull it at inits.
    ptz = AvkansControl(cam_ip) # Visca controller.

    # For debugging it's useful to start at home.   Disable for prod.
    ptz.send(ptz.cmd.ptz_zero_zero)
    ptz.wait_complete()

    hafov = ptz.ptz_get_hfov() # horizontal angular field of view.
    print("hafov 1: ",hafov)

    error_vector=(None,None) # error is stored in this vector after successful detection.
    target_position=(0.5,0.5) # width,height in range 0 to 1.  Where do you want the center of the target in the frame?
    allowed_error=(0.1,0.1) # width,height in range 0 to 1.   FHD 1920x1080, 0.1 corresponds to 192,108 pixel allowed error vectors.
    
    hafov = ptz.ptz_get_hfov() # horizontal angular field of view.
    vafov = 9./16.*hafov # vertical angular field of view, assumes 16:9 aspect ratio and rectilinear lens.

    # Where we want the target in the frame
    target_loc = np.array((frame.shape[1]*target_position[0],frame.shape[0]*target_position[1]))

    loop_rate=10 # starting value   
    while(True):
        tstart=time.time()
        if haltTrackingThread(cam_ip):
            return(0)

        # To most closely sync the current position with the frame, it's best to get position first
        # position getting has the most latency.
        cam_abs_pos,frame_ts = ptz.ptz_get_position(return_ts=True) # About 50ms or so usually.
        if cam_abs_pos==None: # Sometimes the socket flakes.
            print("[ Warning ] - Cam abs position was none: ",cam_abs_pos)
            continue

        # Grab a matching frame right away - NDI frame grabbing is usually pretty quick, 5ms or so.
        frame = ndi.get_cv2_frame()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame.setflags(write=1)

        # Do inference.
        actual_loc = detect_faces_mp(frame,detect_faces)
        if actual_loc:
            actual_loc=np.array(actual_loc)
        else:
            print("\r No face detected, passing",end=" ")
            loop_rate = 1/(time.time()-tstart)
            print("Loop rate: 2",loop_rate, end=" ")
            continue

        hafov = ptz.ptz_get_hfov() # horizontal angular field of view.
        vafov = 9./16.*hafov # vertical angular field of view, assumes 16:9 aspect ratio and rectilinear lens.

        error_vector = actual_loc-target_loc # Compute error vector.
        permitted_error = allowed_error * np.array((frame.shape[1],frame.shape[0]))
        dx = float(hafov*error_vector[0])/float(frame.shape[1]) # pan error in degrees
        dy = -float(vafov*error_vector[1])/float(frame.shape[0]) # tilt error in degrees
        cam_abs_pos = np.array(cam_abs_pos)
        cam_correct_pos = cam_abs_pos + np.array((dx,dy))

        # If we are outside the allowable error, command a correction.
        if (abs(error_vector[0]) > permitted_error[0] or abs(error_vector[1]) > permitted_error[1]):
            # we want our correction to take about 3x the loop time.
            # Loop at 10hz means we want 0.3s in our movement command.
            # To accomplish, compute angular movement and convert to cam speeds for pan and tilt.
            pan_angular_error = abs(error_vector[0])/frame.shape[1]*hafov # degrees
            tilt_angular_error = abs(error_vector[1])/frame.shape[0]*vafov # degrees
            pan_speed = ptz.pan_deg_per_sec_to_speed(pan_angular_error*loop_rate/6.)
            tilt_speed = ptz.tilt_deg_per_sec_to_speed(tilt_angular_error*loop_rate/6.)

            ptz.send(ptz.cmd.ptz_to_abs_position(cam_correct_pos[0],cam_correct_pos[1],pan_speed,tilt_speed))

        loop_rate=1/(time.time()-tstart)
        print("\rLoop rate: ",loop_rate," Hz", end="")

        

def clip(value, min_val, max_val):
    return min(max(value, min_val), max_val)

def detect_faces_mp(frame,detect_faces):
    faces = detect_faces(frame)
    if not len(faces):
        return None
    else:
        points=[]
        for f in faces:
            if f.score>0.75:
                bbox = f.bbox
                bbox_center_xy_n = ((bbox.xmin+bbox.xmax)/2., (bbox.ymin+bbox.ymax)/2.)
                bbox_center = (int(bbox_center_xy_n[0]*frame.shape[1]),int(bbox_center_xy_n[1]*frame.shape[0]))
                points.append(bbox_center)

        if len(points):
            px=0; py=0
            for p in points:
                px+=p[0]
                py+=p[1]
            px = px/len(points)
            py = py/len(points)
            centroid=(px,py)
            return centroid
    return None


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

def load_sources_from_db():
    with db_env.begin(write=False) as txn:
        sourcepickle = txn.get("sources".encode('utf-8'))
    
    if sourcepickle:
        sources=pickle.loads(sourcepickle)
    else:
        sources=None
        
    if not sources:
        print("[ Warning ] - Sources invalid or None, creating empty source list...")
        sources=list()
        store_sources_to_db(sources)

    return sources


def store_sources_to_db(sources):
    # persist sources in db as pickle
    p = pickle.dumps(sources)
    
    with db_env.begin(write=True) as txn:
        txn.put("sources".encode('utf-8'),p)
        return True
    return False


# Evaluate db for thread stop conditions
def haltTrackingThread(cam_ip):
    sources = load_sources_from_db()
    halt=False

    # See if an explicit halt is called by clicking the button.
    # If cam_ip is not found in the current state, it's a zombie thread so kill it.
    cam_ip_found=False
    for item in sources:
        if item['ip']==cam_ip:
            cam_ip_found=True
            halt = item.get('haltTrackingThread')
        
    #print("Halt: ",halt)
    #print("Cam_IP_found: ",cam_ip_found)

    if halt==True or cam_ip_found==False:
        print(" [ Notice ] - Exiting tracking thread.")
        return True
    #print("Continuing")
    return False


# Render the main user interface.
@app.get("/")
def main():
    template=None

    sources=load_sources_from_db()
    
    with open("html/index.html",'r') as f:
          template=f.read()

    scripts=""

    stable=""
    for idx,source in enumerate(sources):
        if source.get("haltTrackingThread")==False:
            trackcommand=f"<button style='background-color: rgb(0,255,0); color: red;' onclick='location.href=\"/stopTracking?idx={idx}\"'>Track Stop</button>"
        else:
            trackcommand=f"<button onclick='location.href=\"/startTracking?idx={idx}\"'>Track Start</button>"


        # Make the HTML table elements for gui.
        stable+=f"""
        <tr><td colspan=100% height=10px style="background-color: black;"> </td></tr>
        <tr>
        <td>{source['name']}</td>
        <td>{source['ip']}</td>
        <td>{trackcommand}</td>
        <td><a href='/removesource?idx={idx}'>X</td>
        </tr>

        <tr><td colspan=100%><img width=300 height=169 style="background-color: gray;" id="preview{idx}" src="#">
        <br>
        <button onclick="load_image_preview({idx})">Refresh Preview</button></td></tr>
        """

        scripts+=f"await load_image_preview({idx});"

    scripts="<script>async function ldprev(){"+scripts+"} ldprev();</script>"

    template=template.replace("%SOURCES%",stable)
    template=template.replace("%SCRIPTS%",scripts)

    return template

@app.get("/addcambyip")
def addcambyip():
     
     # Get the args
     camip = request.args.get("camip")
     camname = request.args.get("camname")

     sources = load_sources_from_db()

     # Don't accept invalid or incomplete args.
     if (camip is not None and camname is not None):
        sources.append({"name": camname, "ip": camip})

        # Don't allow duplicates
        scopy = list()
        for item in sources:
            if item not in scopy:
                scopy.append(item.copy())
        sources=scopy

        # Persist changes to database
        store_sources_to_db(sources)

     return f"{camip} {camname}"


@app.get("/camlist")
def camlist():
    sources=load_sources_from_db()
    return sources

@app.get("/removesource")
def removesource():
    sources=load_sources_from_db()
    idx=int(request.args.get("idx"))
    del sources[idx]

    # persist sources to lightning.
    store_sources_to_db(sources)
    return redirect("/")

@app.get("/preview-b64")
def getPreview():
    idx = request.args.get("idx")
    idx = int(idx)
    print("idx: ",idx)
    sources = load_sources_from_db()
    source=sources[idx]
    print("Source: ",source)

    # open the image source and try to pull an image.
    try:
        cam = AvkansCamera()
        cam.connect_by_ip(source['ip'])
        img=cam.get_cv2_frame()
        img=cv2.resize(img,(300,169))
        img=cv2.cvtColor(img,cv2.COLOR_BGR2RGB,img)
        r, buffer = cv2.imencode(".jpg",img)
        b64_image = base64.b64encode(buffer).decode()

    except Exception as e:
        print("failed to load preview!!!!!!")
        print('e: ',e)
        b64_image=None
        pass

    print("Returning for idx ",idx,": ",bool(b64_image))
    html_src_tag = f"""data:image/jpg;base64,{b64_image}"""

    return html_src_tag




@app.get("/startTracking")
def startTracking():

    cam_ip=None
    idx=None
    sources=load_sources_from_db()

    # Handles by index, name, or camera ip
    idx = request.args.get("idx")
    if (idx):
        idx = int(idx)
        cam_ip = sources[idx]['ip']
    
    name = request.args.get("name")
    if (name):
        for i,source in enumerate(sources):
            if source['name']==name:
                cam_ip=sources[i]['ip']
                idx=i
    
    req_ip = request.args.get("ip")
    if (req_ip):
        for i,source in enumerate(sources):
            if source['ip']==req_ip:
                cam_ip=sources[i]['ip']
                idx=i
            
    
    if cam_ip is None or idx is None:
        return f"Failure - No cameras found by that identifier: idx={idx} cam_ip={cam_ip}"
    
    # Spawn separate thread for tracking code
    sources[idx]['haltTrackingThread']=False

    T = threading.Thread(target=mediapipe_tracker,args=(cam_ip,), daemon=True)
    T.start()

    store_sources_to_db(sources)
    return redirect("/")

@app.get("/stopTracking")
def stopTracking():

    cam_ip=None
    idx=None
    sources=load_sources_from_db()

    # Handles by index, name, or camera ip
    idx = request.args.get("idx")
    if (idx):
        idx = int(idx)
        cam_ip = sources[idx]['ip']
    
    name = request.args.get("name")
    if (name):
        for i,source in enumerate(sources):
            if source['name']==name:
                cam_ip=sources[i]['ip']
                idx=i
    
    req_ip = request.args.get("ip")
    if (req_ip):
        for i,source in enumerate(sources):
            if source['ip']==req_ip:
                cam_ip=sources[i]['ip']
                idx=i


    sources[idx]['haltTrackingThread']=True
    store_sources_to_db(sources)
    return redirect("/")

@app.get("/searchndi")
def searchndi():
    cam=AvkansCamera()
    found=cam.get_sources_as_dict()
    return jsonlib.dumps(found,indent=2)

if __name__ == "__main__":

    # Use lightning db for inter-worker communication
    print("Opening database!!! ")
    app.run(host="0.0.0.0",port=8091,debug=True)
