import time
from fdlite import FaceDetection, FaceDetectionModel

class fdlite_inference:
    model = None
    detector = None

    def __init__(self):
        self.detector = FaceDetection(model_type=FaceDetectionModel.FULL)

    def get_pixel_target(self,frame):
        faces = self.detector(frame)
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

