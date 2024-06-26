import socket, select, time, threading, queue, asyncio
socket.setdefaulttimeout(1)

# Class for interacting with AVkans via Visca-TCP.   Implements the most useful sub-set of the
# published functionality that actually worked in testing.
class AvkansControl:
    ip_address=None
    port=None
    s = None
    debug=False
    discard_packets=None # List of packets, valid items are "ACK" or "COMPLETE" or both.

    def __init__(self,ip_address,port=1259,debug=False,discard_packets=[]):
        self.ip_address=ip_address
        self.port=port
        self.cmd=AvkansTCPCommands()
        self.debug=debug
        self.in_q=queue.Queue()
        self.out_q=queue.Queue()
        self.discard_packets=discard_packets
        self.halt = threading.Event()
        self.halt.clear()
        t = threading.Thread(target=self.twrapper, args=(self.ip_address,self.port,self.in_q,self.out_q,self.halt),daemon=True)
        t.start()
    
    # Wrapper for managing the tcp thread.
    def twrapper(self,ip,port,in_q,out_q,halt):

        self.in_q=in_q
        self.out_q=out_q
        while (not halt.isSet()):
            try:

                self.tcp_thread(ip,port,self.in_q,self.out_q)
            except BaseException as e:
                print('{!r}; restarting thread'.format(e))
                #time.sleep(3)
            else:
                print('Bad thread, restarting')
        print("Exiting twrapper by halt command")
        return
    
    # Receives all comms from Avkans camera, and puts complete messages into in q
    def tcp_thread(self,ip,port,in_q:queue.Queue,out_q:queue.Queue):

        # Open a socket
        print("R1 ", end="",flush=True)
        s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        #s.setsockopt(socket.SOL_SOCKET,socket.SO_KEEPALIVE,1)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        print("R2 ", end="",flush=True)
        s.settimeout(0.5)
        print("R3 ", end="", flush=True)
        s.connect((ip,port))
        print("R4 ", end="", flush=True)
        self.s=s

        # Listens and pushes complete messages to q
        buff=[]
        msg=[]

        # Dump queues on reload
        while not in_q.empty:
            print("Dumping in_q...",flush=True)
            in_q.get(timeout=0.5)
            time.sleep(0.05)
        print("Done.",flush=True)
        while not out_q.empty:
            print("Dumping out_q...",flush=True)
            out_q.get(timeout=0.5)
            time.sleep(0.05)
        print("Done.",flush=True)
        sock_miss=0

        #self.in_q.put(bytearray.fromhex("90 51 FF"))
        
        while(True):
            # Send data in the out_q
            if not out_q.empty():
                #print("SENDING 1 ",end="",flush=True)
                omsg = out_q.get(timeout=0.2)
                s.sendall(omsg)
                #print("SENDING 2 ", omsg, end="",flush=True)

            # Check for data waiting to be read
            ready = select.select([self.s],[],[],0.01)

            if ready[0]:
                
                #print("RECV 2 ",end="",flush=True)
                buff+=s.recv(1024)
                #print("Buff: ",buff)
                if len(buff)==0:
                    #s.shutdown(socket.SHUT_RDWR)
                    s.close()
                    raise Exception("TCP Socket buffer was indicated as ready but nothing returned.   Bad socket?")
                
                while len(buff)>0:    
                    sock_miss=0
                    msg.append(buff[0])
                    buff=buff[1:]
                    if msg[-1]==b'': # Socket hang
                        print("RECV3 ",end="", flush=True)
                        #s.shutdown(socket.SHUT_RDWR)
                        s.close()
                        raise Exception("[ Exception ] - Socket returned empty byte - exiting tcp_thread()")
                    if msg[-1]==0xFF: # End of message footer.
                        #print("MSGCOMPLETE ",end="",flush=True)
                        
                        # We can discard packets based on the discard_packets notes.
                        if "ACK" in self.discard_packets and msg and len(msg)==3 and msg[1]&0xF0==0x40:
                            #print("[ Notice ]:  Discarding ACK based on discard_packet settings: ",msg)
                            pass
                        elif "COMPLETE" in self.discard_packets and msg and len(msg)==3 and msg[1]&0xF0==0x50:
                            #print("[ Notice ]:  Discarding COMPLETE based on discard_packet settings: ",msg)
                            pass
                        elif "ERRORS" in self.discard_packets and msg and len(msg)==4 and msg[1]&0xF0==0x60:
                            print("[ Notice ]:  Discarding ERROR packet based on discard_packet settings: ",msg)
                            pass
                        elif msg and len(msg)==4 and msg[1]&0xF0==0x60:
                            print("[ Warning ]:  'ERROR' packet received - Dropping from queue: ",msg)
                        else:
                            in_q.put(msg)

                        msg=[]
            else:
                print(".",end="",flush=True)
                sock_miss+=1
                #time.sleep(0.05)
                if sock_miss > 100:
                    print("[ ERROR ] - Socket missed too many times in read.   Restarting TCP thread.")
                    return 0
                    
                    

    # Sends a packet and reads and returns a message response.
    def send(self,bytes:bytearray):
        #if (self.debug): print("[ INFO ] - Sending bytes in ptz.send(): ",bytes, end="")
        self.out_q.put(bytes)

    # Reads the socket until it finds a start and end, then returns
    # the complete message.
    # If blocking=False, it will only start a read when data is available, 
    # but will block until the packet footer is received.
    def recv(self,timeout=1):
        try:
            #print("Checking queue...")
            m=self.in_q.get(timeout=timeout)
            #print(m)
            return m
        except queue.Empty:
            print("[ Warning ] - Queue should not be empty in recv call: ",self.in_q,timeout)
            return False
            

    # Monitors for motion complete responses after commanding a move
    # with a monitored timeout (defaults to 60 seconds)
    def wait_complete(self):
        valid_complete = bytearray.fromhex("90 51 FF")
        msg = self.recv()

        if msg and len(msg)==3 and msg[0]==0x90 and msg[1]&0xF0==0x50 and msg[2]==0xFF:
            return True        
        else:
            print("[ Warning ] - wait_complete expected [90 5x FF] but received another message: ",msg)
            return False

    def dump(self):
        while(not self.in_q.empty):
            self.recv()
    
    # Helper function to get camera current position and return it in degrees.
    # Response:  (pan,tilt) in degrees.
    # Optionally returns a timestamp estimating the time at position.   This timestamp can be useful 
    # for forecasting motion positions during moves, and is "guessed" by taking the midpoint of the 
    # timestamps at packet send and valid response received.
    def ptz_get_position(self, return_ts=False):
        ts1=time.time()
        self.dump()
        self.send(self.cmd.q_ptz_pos)
        buff=self.recv()

        #try:
        #    buff=self.recv(timeout=1)
        #except:
        #    print("[ WARNING ] - No position response received!!!")
        #    return False

        if buff and len(buff)!=11:
            print("[ Warning ] - ptz_get_position expected 11 byte response, got ",len(buff),flush=True)
            print("               Dumping buffer: ",buff, flush=True)
            return False
            #raise Exception(f"Buff does not meet length requirements in ptz_get_position.   Buff: {buff}")
        
        elif buff and len(buff)==11 and buff[1]==0x50: # Valid response
            ts2=time.time()
            w=buff[2:6]; z=buff[6:10]
            pan_pos= w[0]<<12 | w[1]<<8 | w[2]<<4 | w[3]
            tilt_pos= z[0]<<12 | z[1]<<8 | z[2]<<4 | z[3]

            # Pan range for Avkans E20 is -175 to +175 degrees, and indicated by bytes w as follows:
            # 0x0001 to 0x0990 = panned to right in 2447 steps over full range.   0x990=last step on pan right, for example.
            # 0xFFFE to 0xF670 = pan to left in 2446 steps over full range.  0xFFFE=first step left, 0xF670=last step.
            if pan_pos>=0 and pan_pos<=0x990:
                pan_angle = pan_pos/0x990*175
            elif pan_pos>=0xF670 and pan_pos<=0xFFFF:
                pan_angle = -(0xFFFE-pan_pos)/(0xfffe-0xf670)*175
            else: 
                raise Exception("[ ERROR ] - Pan Angle was found as Nonetype! ",buff)
                pan_angle=None

            # Tilt range for Avkans E20 is -29.8 to +90 degrees, and indicated by bytes z as follows:
            #       0x0001 to 0x0510 is tilt up from smallest to largest in 1295 steps.    0x510 is max tilt up.
            #       0xFFFE to 0xFE51 is tilt down from smallest to largest in 429 steps.   FE51 is max down tilt.
            if tilt_pos>=0 and tilt_pos<=0x510: # positive tilt
                tilt_angle = tilt_pos/0x510*90
            elif tilt_pos>=0xFE51 and tilt_pos<=0xFFFF:
                tilt_angle = -(0xFFFE-tilt_pos)/(0xFFFE-0xFE51)*29.8
            else: 
                raise Exception("[ ERROR ] - Tilt angle was found as NoneType! ", buff)
                tilt_angle=None

            if return_ts:
                return (pan_angle,tilt_angle), (ts1+ts2)/2.
            else:
                return (pan_angle,tilt_angle)
        
        else:
            print("[ ERROR ] - ptz_get_position received malformed response: ", buff, flush=True)
            
            
        print("[ ERROR ] - ptz_get_position returned outside of control.  ", buff, flush=True)
        return False
            


    # Returns the magnification setting of current zoom (from 1 to 20x for E20)
    def ptz_get_zoom_mag(self):
        e20_zoom=20. # Advertised as 20x zoom range.
        zoom_count=0x4000 # Manual states 0x0 is full wide, 0x4000 is full tele

        self.dump()
        self.send(self.cmd.q_zoom_pos)
        buff=self.recv()

        if buff and len(buff)!=7:
            print("[ Warning ] - ptz_get_zoom_mag: expected response of 7, got ",len(buff))
            print("[ > > > > > ] Dumping response: ",buff)

        elif buff and len(buff)==7 and buff[1]==0x50 and buff[6]==0xFF:
            z=buff[2:6]
            zoom_pos= z[0]<<12 | z[1]<<8 | z[2]<<4 | z[3]
            return (1+(e20_zoom-1)*zoom_pos/zoom_count)
        else:
            print("[ Warning ] - Malformed response in ptz_get_zoom_mag: ",buff)
            return False


    # Returns the horizontal angular field of view in degrees at the current lens setting.
    # AVKans E20 is specified as 60.7 degrees field of view at full wide, with a 20x zoom.
    # These assumptions have not been directly characterized with a real camera, but seem to work fine.
    def ptz_get_hfov(self):
        e20_fov=60.7 # FOV in manual at max wide zoom is specified as 60.7 degrees.
        mag = self.ptz_get_zoom_mag()
        if (mag):
            return e20_fov/mag
        else:
            return False
    
    # Flushes socket with a 1ms timeout without processing data.
    # Returns true if data was flushed, false if it timed out.
    # This is kinda dangerous to use, but is sometimes needed.
    # Consider using recv(blocking=False) instead.
    def socket_flush(self):
        s=self.getsocket()
        s.setblocking(False)
        dump=s.recv(1024)
        s.setblocking(True)

        ready=select.select([self.s],[],[],0.001)
        if ready[0]:
            dump = s.recv(1024)
            return True
        return False

        
    # Helper function to convert a speed value to estimated deg/s
    # This is quantized over 24 steps by the camera stepper drivers, 
    # and accel and decel parameters are difficult to estimate.
    # Use as a good starting point to have at least some idea of angular pan speeds.
    def pan_speed_to_deg_per_second(self,speed:float): # 0 to 1
        ss=speed*91.082+5.0982
        return ss
    
    # Pan speed is quantized, and sometimes it's useful to know the 
    # estimated quantization between speeds.   Send a value 0 to 24 and 
    # get back the estimated angular speed in deg/s
    def pan_raw_speed_to_deg_per_second(self,speed:int): # 0 to 24
        ss=speed*3.7937+6.4944
        return ss
    
    # Converts target degrees per second to a normalized speed vector in range 0,1
    # Useful with most absolute movement functions for planning coordinated moves.
    def pan_deg_per_sec_to_speed(self,deg_per_sec:float): # 0 to 93 typical for E20
        ss = (deg_per_sec-5.0982)/91.082
        if ss>1.0: ss=1.0
        if ss<0: ss=0.0
        return(ss)
    
    # Returns the closest speed step (0 to 24 dec) to the requested deg/second pan speed.
    # Useful for timing / coordinating pan and tilt moves.
    def pan_deg_per_sec_to_raw_speed(self,deg_per_sec:float): # 0 to 93 typical for E20
        ss = round((deg_per_sec-6.4944)/3.7937)
        if (ss<0): ss=0
        if (ss>24): ss=24
        return ss
    
    # Helper function to convert a speed value to estimated deg/s
    # This is quantized over 20 steps by the camera stepper drivers, 
    # and accel and decel parameters are difficult to estimate.
    # Use as a good starting point to have at least some idea of angular tilt speeds.
    def tilt_speed_to_deg_per_second(self,speed:float): # 0 to 1
        ss=speed*44.456+3.4522
        return ss
    
    # Tilt speed is quantized, and sometimes it's useful to know the 
    # estimated quantization between speeds.   Send a value 0 to 20 and 
    # get back the estimated angular speed in deg/s
    def tilt_raw_speed_to_deg_per_second(self,speed:int): # 0 to 20
        ss=speed*2.2228+3.4522
        return ss
    
    # Converts target degrees per second to a normalized speed vector in range 0,1
    # Useful with absolute movement functions for planning coordinated moves.
    def tilt_deg_per_sec_to_speed(self,deg_per_sec:float): # 0 to 46 deg/s typical for E20 tilt
        ss = (deg_per_sec-3.4522)/44.456
        if ss>1.0: ss=1.0
        if ss<0: ss=0.0
        return(ss)
    
    # Returns the closest speed step (0 to 20 dec) to the requested deg/second tilt speed.
    # Useful for timing / coordinating pan and tilt moves.
    def tilt_deg_per_sec_to_raw_speed(self,deg_per_sec:float): # 0 to 46 deg/s typical for E20 tilt
        ss = round((deg_per_sec-3.4522)/2.2228)
        if (ss<0): ss=0
        if (ss>20): ss=20
        return ss
    


# Helper class for forming TCP Commands compatible with AVKans cameras.
# Note:  Does not run commands, just makes them.   To run commands, use the base class.
# In some cases, does not return any value (setting ptz speeds, for example) but mostly it
# directly returns a command that can be run via TCP socket.
class AvkansTCPCommands:

    def __init__(self):
        pass

    # Every command is a tuple consisting of a byte array and the expected response.
    # If more than one response is expected, "ack" and "values", then the response can be a list of lengths.

    # Power control
    power_on    = bytearray.fromhex(f"81 01 04 00 02 FF")
    power_off   = bytearray.fromhex(f"81 01 04 00 03 FF")

    # Zoom control
    zoom_stop   =bytearray.fromhex(f"81 01 04 00 03 FF")
    zoom_tele   =bytearray.fromhex(f"81 01 04 07 02 FF")
    zoom_wide   =bytearray.fromhex(f"81 01 04 07 03 FF")

    def zoom_tele_at_speed(self,zoom_speed): # 0-7
        if zoom_speed>7 or zoom_speed<0: p=5
        else: p=zoom_speed
        return bytearray.fromhex(f"81 01 04 07 2{p} FF")
    
    def zoom_wide_at_speed(self,zoom_speed): # 0-7
        if zoom_speed>7 or zoom_speed<0: p=5
        else: p=zoom_speed
        return bytearray.fromhex(f"81 01 04 07 3{p} FF")
    
    def zoom_set_position(self,pos:int=0.5):
        if pos<0: pos=0
        if pos>1: pos=1
        pos=int(pos*0x4000) # 4000 is full-count for zoom tele.
        p=f'{(pos&0xF000)>>12:02x}' # High nibble
        q=f'{(pos&0xF00)>>8:02x}' # 
        r=f'{(pos&0xF0)>>4:02x}' #
        s=f'{(pos&0xF):02x}' # Low nibble
        cmd = (f"81 01 04 47 {p} {q} {r} {s} FF")
        print(cmd)
        return bytearray.fromhex(cmd)

    # Focus control - Tested working in E20 Firmware 1.0.10
    focus_stop      =bytearray.fromhex(f"81 01 04 08 00 FF")
    focus_far       =bytearray.fromhex(f"81 01 04 08 02 FF")
    focus_near      =bytearray.fromhex(f"81 01 04 08 03 FF")

    focus_mode_autofocus        =bytearray.fromhex("81 01 04 38 02 FF")
    focus_mode_manual           =bytearray.fromhex("81 01 04 38 03 FF")
    focus_mode_toggle_autofocus =bytearray.fromhex("81 01 04 38 10 FF")

    # Focus lock did not work on E20 firmware 1.0.10
    # focus_lock      =bytearray.fromhex("81 0a 04 68 02 FF")  
    # focus_unlock    =bytearray.fromhex("81 0a 04 68 03 FF")

    def focus_far_at_speed(self,zoom_speed): # 0-7, low-high
        return bytearray.fromhex(f"81 01 04 08 2{zoom_speed} FF")
    
    def focus_near_at_speed(self,zoom_speed): # 0-7
        return bytearray.fromhex(f"81 01 04 08 3{zoom_speed} FF")
    
    def focus_direct(self,pos:float):  # 0 to 1
        if pos<0: pos=0
        if pos>1: pos=1
        pos=int(pos*0xFFFF)
        p=f'{(pos&0xF000)>>12:02x}' # High nibble
        q=f'{(pos&0xF00)>>8:02x}' # 
        r=f'{(pos&0xF0)>>4:02x}' #
        s=f'{(pos&0xF):02x}' # Low nibble
        return bytearray.fromhex(f"81 01 04 48 {p} {q} {r} {s} FF")
    
    # Preset controls
    def pset_set_recall_speed(self,speed):  # 0-1
        if speed>1: speed=1
        if speed<0: speed=0
        return bytearray.fromhex(f"81 01 06 01 {int(speed*24.):02x} FF")

    def pset_recall(self,pset):
        pp=f"{pset:02x}"
        return bytearray.fromhex(f"81 01 04 3F 02 {pp} FF")
    
    def pset_store(self,pset):
        pp=f"{pset:02x}"
        return bytearray.fromhex(f"81 01 04 3F 01 {pp} FF")

    def pset_clear(self,pset):
        pp=f"{pset:02x}"
        return bytearray.fromhex(f"81 01 04 3F 00 {pp} FF")
        
    # NDI Mode control did not work on AvKans E20 firmware 1.0.10
    #cam_ndi_mode_high   =bytearray.fromhex(f"81 0B 01 01 FF")
    #cam_ndi_mode_medium =bytearray.fromhex(f"81 0B 01 02 FF")
    #cam_ndi_mode_low    =bytearray.fromhex(f"81 0B 01 03 FF")
    #cam_ndi_mode_off    =bytearray.fromhex(f"81 0B 01 04 FF")

    # Pan and tilt controls controls all work.
    def ptz_up(self,speed:float):
        return bytearray.fromhex(f"81 01 06 01 {'00'} {int(speed*20.):02x} 03 01 FF")
    
    def ptz_down(self,speed:float):
        return bytearray.fromhex(f"81 01 06 01 {'00'} {int(speed*20.):02x} 03 02 FF")
    
    def ptz_left(self,speed:float):
        return bytearray.fromhex(f"81 01 06 01 {int(speed*24.):02x} {'00'} 01 03 FF")
    
    def ptz_right(self,speed:float):
        return bytearray.fromhex(f"81 01 06 01 {int(speed*24):02x} {'00'} 02 03 FF")
    
    def ptz_upleft(self,pan_speed:float,tilt_speed:float):
        return bytearray.fromhex(f"81 01 06 01 {int(pan_speed*24.):02x} {int(tilt_speed*20.):02x} 01 01 FF")
    
    def ptz_upright(self,pan_speed:float,tilt_speed:float):
        return bytearray.fromhex(f"81 01 06 01 {int(pan_speed*24.):02x} {int(tilt_speed*20.):02x} 02 01 FF")
    
    def ptz_downleft(self,pan_speed:float,tilt_speed:float):
        return bytearray.fromhex(f"81 01 06 01 {int(pan_speed*24.):02x} {int(tilt_speed*20.):02x} 01 02 FF")
    
    def ptz_downright(self,pan_speed:float,tilt_speed:float):
        return bytearray.fromhex(f"81 01 06 01 {int(pan_speed*24.):02x} {int(tilt_speed*20.):02x} 02 02 FF")
    
    ptz_stop        =bytearray.fromhex(f"81 01 06 01 {'01'} {'01'} 03 03 FF")

    # PTZ Home does work, but has a nasty bug when called from deep CCW tilt.
    # Recommend to use ptz_zero_zero instead, but home works most of the time.
    ptz_home        =bytearray.fromhex(f"81 01 06 04 FF")
    ptz_zero_zero   =bytearray.fromhex(f"81 01 06 02 18 14 00 00 00 00 00 00 00 00 FF")
    
    # This works but not really sure what it does?
    ptz_reset       =bytearray.fromhex(f"81 01 06 05 FF")

    # Works great.
    def ptz_zoom(self,zoom:float):  # 1 to 20x for Avkans E20
        if zoom<1: zoom=1
        if zoom>20: zoom=20

        z=int(0x4000*((zoom-1)/19.)) # Manual states that zoom is PQRS from 0 to 0x4000
        p=f"{(z&0xf000)>>12:02x}"
        q=f"{(z&0xf00)>>8:02x}"
        r=f"{(z&0xf0)>>4:02x}"
        s=f"{(z&0xf):02x}"

        print("z: ",hex(z))
        print("Zoom pqrs: ",p,q,r,s)

        return bytearray.fromhex(f"81 01 04 47 {p} {q} {r} {s} FF")

    
    # Avkans E20 absolute positioning works and is as follows:
    # Pan position:  E20 has +/- 175 degrees for pan.
    #       0000 or FFFF = home position
    #       0x0001 to 0x0990 = pan to right in 2447 steps over full range.   0x990=last step on pan right, for example.
    #       0xFFFE to 0xF670 = pan to left in 2446 steps over full range.  0xFFFE=first step left, 0xF670=last step.
    #
    # Tilt position: E20 has +90 degrees for tilt, and unspecified down angle, but inferred as -29.8 degrees from step count.
    #       0x0000 or 0xFFFF = home position (no tilt)
    #       0x0001 to 0x0510 is tilt up from smallest to largest in 1295 steps.    0x510 is max tilt up at 90 degrees.
    #       0xFFFE to 0xFE51 is tilt down from smallest to largest in 429 steps.   FE51 is max down tilt at about -30 degrees.
    #
    # Speed notation is 0-24 decimal (0x00-0x18 hex) for pan, and 0-20 decimal (0x00-0x14 hex) for tilt.
    #
    # Pan Speed characterization:  0 to 24 corresponds to about 6 deg/s to 94 deg/sec and is fairly linear, as expected with stepper drive.
    #       E20 Pan speed can be modeled as deg/s = 3.8*speed+6.5 with an R^2 value > 0.95 
    #       for (speed in range 0-24 decimal)
    #       For normalized speed commands in range (0,1) model as deg/s = 91*speed+5.1, speed 0 to 1.0
    #
    # Tilt Speed Characterization:  0 to 20 decimal (0x00-0x14 hex) corresponds to about 3.1 to 46.2 deg/s and is also fairly linear.
    #       For discrete hex values (0 to 20 / 0x0 to 0x14), model as deg/s = 2.22*speed+3.5
    #       For normalized speed values (0 to 1), model as deg/s = 44.4*speed+3.5
    #
    # Note that speeds set to 0 are just the slowest speed, they're not actually "no speed".   To stop, use the ptz_stop command.
    #
    # Position commands can be interrupted by a new command, and will not send a "complete" packet if they are.
    def ptz_to_abs_position(self,pan_angle:float,tilt_angle:float,pan_speed:float,tilt_speed:float): # 0 to 1, 0 to 1

        # Pan angle from -175 to +175
        if pan_angle<-175: pan_angle=-175
        if pan_angle>175: pan_angle=175

        # Tilt angle from -28 to +90
        if tilt_angle<-29: tilt_angle=-29
        if tilt_angle>90: tilt_angle=90

        # Compute pan values, including "home" at 0x0000 in positive angles.
        if pan_angle>=0:
            panpos = int(pan_angle/175.*(0x990))
        elif pan_angle<0:
            panpos = int(0xFFFF+pan_angle/175.*0x98F)

        # Compute tilt value
        if tilt_angle>=0:
            tiltpos = int(tilt_angle/90.*0x510)
        elif tilt_angle<0:
            tiltpos = int(0xFFFF+(tilt_angle/29.8)*0x1AE)
        
        if (pan_speed>1): pan_speed=1.
        if (pan_speed<0): pan_speed=0.
        if (tilt_speed>1): tilt_speed=1.
        if (tilt_speed<0): tilt_speed=0.

        #print("Pan position cmd: ",hex(panpos))
        #print("Tilt position cmd: ",hex(tiltpos))

        y1=f'{(panpos&0xF000)>>12:02x}'
        y2=f'{(panpos&0xF00)>>8:02x}'
        y3=f'{(panpos&0xF0)>>4:02x}'
        y4=f'{(panpos&0xF):02x}'

        z1=f'{(tiltpos&0xF000)>>12:02x}'
        z2=f'{(tiltpos&0xF00)>>8:02x}'
        z3=f'{(tiltpos&0xF0)>>4:02x}'
        z4=f'{(tiltpos&0xF):02x}'
        #print("Debug:  moving to YYYY , ZZZZ: ",y1,y2,y3,y4,",",z1,z2,z3,z4)
        return bytearray.fromhex(f'81 01 06 02 {int(pan_speed*24.):02x} {int(tilt_speed*20.):02x} {y1} {y2} {y3} {y4} {z1} {z2} {z3} {z4} FF')
    
    # Intended for smaller moves, limited to +/- 30 degrees in pan and +/- 15 degrees in tilt.
    # The relative positions are a bit wonky, haven't played with these much yet.
    def ptz_to_rel_position(self,pan_angle:float,tilt_angle:float,pan_speed:float,tilt_speed:float):
        if (pan_angle>30): pan=1
        if (pan_angle<-30): pan=0
        if (tilt_angle>15): tilt=15
        if (tilt_angle<-15): tilt=-15

        if (pan_speed>1): pan_speed=1
        if (pan_speed<0): pan_speed=0
        if (tilt_speed>1): tilt_speed=1
        if (tilt_speed<0): tilt_speed=0

        # Compute relative pan values, including "home" at 0x0000 in positive angles.
        if pan_angle>=0:
            panpos = int(pan_angle/175*(0x990))
        elif pan_angle<0:
            panpos = int(0xFFFF+pan_angle/175*0x98F)

        # Compute tilt value
        if tilt_angle>=0:
            tiltpos = int(tilt_angle/90.*0x510)
        elif tilt_angle<0:
            tiltpos = int(0xFFFF+(tilt_angle/29.8)*0x1AE)

        y1=f'{(panpos&0xF000)>>12:02x}'
        y2=f'{(panpos&0xF00)>>8:02x}'
        y3=f'{(panpos&0xF0)>>4:02x}'
        y4=f'{(panpos&0xF):02x}'

        z1=f'{(tiltpos&0xF000)>>12:02x}'
        z2=f'{(tiltpos&0xF00)>>8:02x}'
        z3=f'{(tiltpos&0xF0)>>4:02x}'
        z4=f'{(tiltpos&0xF):02x}'
        return bytearray.fromhex(f'81 01 06 03 {int(pan_speed*24.):02x} {int(tilt_speed*20.):02x} {y1} {y2} {y3} {y4} {z1} {z2} {z3} {z4} FF')


    # White balance modes
    # These commands work but don't seem to have a big impact.   Bug report filed with AVkans on Jun 1 / 2024.
    wb_mode_auto     =bytearray.fromhex(f"81 01 04 35 00 FF")
    wb_mode_indoor   =bytearray.fromhex(f"81 01 04 35 01 FF")
    wb_mode_outdoor  =bytearray.fromhex(f"81 01 04 35 02 FF")

    # Manually control color temp in up / down increments.
    # These do not work for some reason - Bug report submitted to Avkans.
    # TODO:  Fix after updated firmware is completed.
    #wb_mode_manual   =bytearray.fromhex(f"81 01 04 35 05 FF")  # Set mode
    #wb_manual_reset  =bytearray.fromhex(f"81 01 04 20 00 FF")
    #wb_manual_up     =bytearray.fromhex(f"81 01 04 20 02 FF")
    #wb_manual_down   =bytearray.fromhex(f"81 01 04 20 03 FF")
    #wb_mode_kelvin   =bytearray.fromhex(f"81 01 04 35 20 FF")  # Set mode

    # Also does not work in 1.0.10 firmware.
    #def wb_set_kelvin(self,temp):
    #    # p,q = 0x00-0x37 corresponds to 2500-8000K.
    #    pq=int((temp-2500.)/(8000-2500.)*0x37)  # Base16 math
    #    p=f'{((pq&0xF0)>>4):02x}' # High nibble
    #    q=f'{(pq&0xF):02x}' # Low nibble
    #    print("pq,p,q: ",pq,p,q)
    #
    #    return bytearray.fromhex(f'81 01 04 20 {p} {q} FF')
    
    # Query commands
    q_power         =bytearray.fromhex(f"81 09 04 00 FF")
    q_zoom_pos      =bytearray.fromhex(f"81 09 04 47 FF")
    q_zoom_position=q_zoom_pos
    q_focus_af_mode =bytearray.fromhex(f"81 09 04 38 FF")
    q_focus_pos     =bytearray.fromhex(f"81 09 04 48 FF")
    q_wb_mode       =bytearray.fromhex(f"81 09 04 35 FF")
    q_ptz_pos       =bytearray.fromhex(f"81 09 06 12 FF")
    q_ptz_position= q_ptz_pos

    r_ack = bytes.fromhex(f"90 40 FF")
    r_complete = bytearray.fromhex(f"90 50 FF")
    r_err_syntax = bytearray.fromhex(f"90 60 02 FF")
    r_err_cmd_buffer_full = bytearray.fromhex(f"90 60 03 FF")
    r_err_cmd_canceled = bytearray.fromhex(f"90 60 04 FF")
    r_err_nosocket = bytearray.fromhex(f"90 60 05 FF")
    r_err_cmd_noexec = bytearray.fromhex(f"90 60 41 FF")





# Example usage below.
if (__name__=="__main__"):#

    # Create with IP on default port (1259)
    cam1=AvkansControl("192.168.1.101")

    # Create by IP on other port
    cam1=AvkansControl("192.168.1.101",1259)

    # Create object and assign the IP and port later
    cam1=AvkansControl("")
    cam1.ip_address="192.168.35.37"
    cam1.port=1259

    # Connect to camera
    cam1.connect()

    # send command to camera
    #print("power on")
    #cam1.send_raw(cam1.cmd.power_on)

    # Go to home position
    print("Going to 0,0")
    cam1.send(cam1.cmd.ptz_zero_zero)
    cam1.wait_complete()

    # Go to +45,+20 position
    print("Going to 45,20")
    cam1.send(cam1.cmd.ptz_to_abs_position(45,20,1,1))
    cam1.wait_complete()

    # Go to home position
    print("Going to 0,0")
    cam1.send(cam1.cmd.ptz_zero_zero)
    cam1.wait_complete()

    # Set zoom level at 50%
    print("Zoom 50%")
    cam1.send(cam1.cmd.zoom_set_position(0.5))
    cam1.wait_complete()

    # Set zoom level at 50%
    print("Zoom 100%")
    cam1.send(cam1.cmd.zoom_set_position(1))
    cam1.wait_complete()

    # Zoom out
    print("Zoom 0%")
    cam1.send(cam1.cmd.zoom_wide)
    cam1.wait_complete()
    # Set white balance color temperature to 5500 Kelvin
    # Unfortunately this doesn't work in Firmware 1.0.10
    # cam1.send_raw(cam1.cmd.wb_set_kelvin(5500))







