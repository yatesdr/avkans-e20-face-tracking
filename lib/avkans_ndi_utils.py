
import NDIlib as ndi
import numpy as np, time

class AvkansCamera:
    ip_address=None
    ndi_source=None
    ndi_sources=None
    recv=None
    ptz_supported=None

    def __init__(self):

        # Initialize NDIlib
        if not ndi.initialize():
            raise(Exception("NDI lib failed to initialize - Make sure ndi-python package is installed."))
        
    def search(self,ip_address:str=""):

        # Clear the source list.
        self.ndi_sources=None

        # Create find object, searching local and ip_address if passed in.
        if ip_address:
            fco = ndi.NDIlib.FindCreate(show_local_sources=True, p_groups=None, p_extra_ips=ip_address)
        else:
            fco = ndi.NDIlib.FindCreate(show_local_sources=True, p_groups=None)

        ndi_find_obj = ndi.find_create_v2(fco)
        
        

        if ndi_find_obj is None:
            raise(Exception("NDI Find object failed to initialize.   This is probably due to a bad installation of NDIlib"))
        
        ndi.find_wait_for_sources(ndi_find_obj,5000)

        self.ndi_sources = ndi.find_get_current_sources(ndi_find_obj)

        return self.ndi_sources
    
    def get_sources_as_dict(self,ip_address:str=""):
        ndi_sources=self.search(ip_address)
        print("ndi_sources:",ndi_sources)
        
        sl = list()
        for idx,s in enumerate(ndi_sources):
            sl.append({"index": idx, "name": s.ndi_name, "addr": s.url_address})
        return sl

    #### Connect to a camera by IP Address ######
    # ip_address:  The address of the camera:  "192.168.1.101"
    # port:  The expected connection port.   This is usually 5961 but NDI spec says its 5961 or higher depending on the stream.
    # netwait:  How long to search the network before moving on, in milliseconds.  Typically 1000ms works fine.
    def connect_by_ip(self,ip_address:str, port:int=5961, netwait:int=1000):

        self.search(ip_address)

        # See if a source matches the requested IP
        for idx, source in enumerate(self.ndi_sources):
            source_ip=source.url_address.split(":")[0]
            source_port=source.url_address.split(":")[1]

            if source_ip==ip_address and int(source_port)==int(port):
                self.ndi_source=self.ndi_sources[idx]

                # Source was found, link to NDI recv.
                ndi_recv_create = ndi.RecvCreateV3()
                #ndi_recv_create.color_format = ndi.RECV_COLOR_FORMAT_BGRX_BGRA
                ndi_recv_create.color_format = ndi.RECV_COLOR_FORMAT_RGBX_RGBA
                #ndi_recv_create.bandwidth=ndi.RECV_BANDWIDTH_LOWEST
                
                self.recv = ndi.recv_create_v3(ndi_recv_create)
                if self.recv is None:
                    raise(Exception("Source was found,but NDI recv object failed to create."))
                
                ndi.recv_connect(self.recv,self.ndi_source)
                return True
            
        return False

    def get_ptz_properties(self):
        return ndi.recv_ptz_is_supported(self.recv)
    
    def get_cv2_frame(self,timeout:int=250):    
        frame=None
        while frame is None:
            t,v,_,_=ndi.recv_capture_v2(self.recv,timeout)
            if t==ndi.FRAME_TYPE_VIDEO:
                frame=np.copy(v.data)
                ndi.recv_free_video_v2(self.recv,v)
        return frame


# Test & Examples
if __name__=="__main__":

    source_list = AvkansCamera().get_sources_as_dict()
    print("Sources: ",source_list)

    cam1 = AvkansCamera()
    result = cam1.connect_by_ip("192.168.35.37")
    print(result)

    for i in range(30):
        t=time.time()
        frame = cam1.get_cv2_frame()
        print(f"Got frame {i} in ",time.time()-t, " seconds.")

    t=time.time()
    frame = cam1.get_cv2_frame()
    print("Got frame in ",time.time()-t, " seconds.")

    t=time.time()
    frame = cam1.get_cv2_frame()
    print("Got frame in ",time.time()-t, " seconds.")
    print("Frame shape:  ",frame.shape)







        
        


    

    



