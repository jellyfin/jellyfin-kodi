import os
import time
import errno
import xbmc

class Lock:
    
    def __init__(self, filename):
        self.filename = filename
        self.delay = 0.5
        self.timeout = 10
        self.is_locked = False
        self.fd = None
    
    def acquire(self):
        start_time = time.time()
        while True:
            try:
                self.fd = os.open(self.filename, os.O_CREAT|os.O_RDWR|os.O_EXCL)
                break;
            except OSError as e:
                if (time.time() - start_time) >= self.timeout:
                    xbmc.log("File_Lock_On " + self.filename + " timed out")
                    return False
                #xbmc.log("File_Lock_On " + self.filename + " error " + str(e))
            time.sleep(self.delay)
        self.is_locked = True
        xbmc.log("File_Lock_On " + self.filename + " obtained")
        return True
        
    def release(self):
        if self.is_locked:
            os.close(self.fd)
            os.unlink(self.filename)
            self.is_locked = False
            xbmc.log("File_Lock_On " + self.filename + " released")
        
    def __del__(self):
        self.release()
        