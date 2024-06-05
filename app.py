
from flask import Flask, redirect, request
from lib.avkans_ndi_utils import AvkansCamera
from lib.avkans_visca_utils import AvkansControl
import json as jsonlib
import cv2, time, threading, lmdb, pickle, base64
from queue import Queue
#from ultralytics import YOLO
import numpy as np

debug=True

#### APP SETTINGS ####
TARGET_POSITION_N = [0.5,0.5]   # Where do you want the center of the face? Normalized in 0,1
ALLOWED_ERROR_N = 0.1   # How far away can it be before issuing a correction? Normalized in 0,1

## Set the face detector model
from lib.inference_fdlite import fdlite_inference
DETECTOR = fdlite_inference()

# Instantiate Flask app
app = Flask("ptzTracker")
db_env=lmdb.open("ptzTracker.db")

tqueues=list()


# A tracking thread using google mediapipe.
def tracker(cam_ip, zoom=False, debug=False, detector=None):

    if detector is None:
        print("No detector found... using my own")
        from lib.inference_fdlite import fdlite_inference
        detector = fdlite_inference()
    else:
        detector=detector
    

    print("Tracker thread started on ",cam_ip, flush=True)

    # Get NDI source.
    ndi = AvkansCamera()
    ndi.connect_by_ip(cam_ip)
    frame = ndi.get_cv2_frame()  # First frame takes a second or two, pull it at inits.

    # Get PTZ controller.
    # We are using servo style control, so do not need ACK packets.  The TCP loop can handle them.
    ptz = AvkansControl(cam_ip, debug=debug, discard_packets=['ACK','COMPLETE']) # Visca controller.

    # For debugging it's useful to start at home.   Disable for prod.
    if (debug):
        ptz.send(ptz.cmd.ptz_zero_zero)

    target_position=TARGET_POSITION_N

    hafov = ptz.ptz_get_hfov() # horizontal angular field of view.
    vafov = 9./16.*hafov # vertical angular field of view, assumes 16:9 aspect ratio and rectilinear lens.

    if (debug): 
        print("hafov 1: ",hafov)
        print("vafov 1: ",vafov)
    
    # Where we want the target in the frame
    target_loc = np.array((frame.shape[1]*target_position[0],frame.shape[0]*target_position[1]))
    loop_time=0.1 # Starting value in seconds.
    tstart=time.time()

    class pid_params:
        p=0.85
        i=0
        d=0
    
    pid = pid_params

    while(True):
        try:
            loop_time=time.time()-tstart
            if loop_time<=0: loop_time=0.1

            print("\r"+" "*50+f"\rLoop completed in: {loop_time*1000:.2f}ms", end="")
            tstart=time.time()

            # Check for halt messages in the queue by cam_ip.
            if haltTrackingThread(cam_ip):
                return(0)

            # Position responses have the most latency, so do it first.            
            resp = ptz.ptz_get_position(return_ts=True) # About 50ms or so usually.
            if resp and len(resp)==2:
                cam_abs_pos,position_ts = resp[0],resp[1]
            else:
                print("[ ERROR ] - Received invalid response in app from ptz_get_position(); ",resp)
                print("[ > > > ] - Valid response should contain point coordinates and a timestamp:  (xxx,yyy), ts")
                print("[ > > > ] - A False response usually indicates a blocking socket problem.")
                continue

            # Grab a matching frame right away - NDI frame grabbing is usually pretty quick, 5ms or so.
            frame = ndi.get_cv2_frame()
            frame_ts=time.time()
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame.setflags(write=1)

            # See where we should point the camera for this frame.
            face_loc = detector.get_pixel_target(frame)
            if face_loc:
                face_loc=np.array(face_loc)
            else:
                if (debug): print("\r No face detected, passing",end=" ", flush=True)
                continue
            
            int_cam_abs_pos = np.array(cam_abs_pos)
            
            # Compute error vector on known data
            # face coordinates are relative to top left of image, with 0,0 being the top left pixel.
            error_vector_px = target_loc-face_loc
            error_vector_len = np.sum(error_vector_px*error_vector_px)**0.5
                        
            # If we are outside the allowable error, command a correction.
            if (error_vector_len > ALLOWED_ERROR_N*frame.shape[1]): # De-normalize based on frame width.

                # Camera is commanded in degrees, convert using hafov and vafov to estimated pan / tilt correction.
                dx = -float(hafov*error_vector_px[0])/float(frame.shape[1]) # pan error in degrees
                dy = float(vafov*error_vector_px[1])/float(frame.shape[0]) # tilt error in degrees

                # Correction based on PID proportional controller and latency.
                cx = dx*pid.p
                cy = dy*pid.p
                cam_new_pos = int_cam_abs_pos + np.array((cx,cy)) # New absolute position (pan,tilt) in degrees.

                # For smooth movement, our correction should take about 5x the loop time.                
                pan_speed = ptz.pan_deg_per_sec_to_speed(abs(cx/(5*loop_time)))
                tilt_speed = ptz.tilt_deg_per_sec_to_speed(abs(cy/(5*loop_time)))
                ptz.send(ptz.cmd.ptz_to_abs_position(cam_new_pos[0],cam_new_pos[1],pan_speed,tilt_speed))


        except Exception as e:
            print("\n################ SERIOUS EXCEPTION OCCURRED ###############",flush=True)
            print(e,flush=True)
            print("\n")
            #time.sleep()
            print("\n ### RESUMING ###")
            #ptz.socket_flush()
            #ptz.s = ptz.getsocket()
            #ptz.dump()

    
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

    T = threading.Thread(target=tracker,args=(cam_ip,), kwargs={"debug":debug, "detector": DETECTOR}, daemon=True)
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
    sources=load_sources_from_db()
    for item in sources:
        item['haltTrackingThread']=None
    store_sources_to_db(sources)

    app.run(host="0.0.0.0",port=8091,debug=debug)
