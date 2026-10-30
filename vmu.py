"""Project-owned raw VMU storage with atomic, conditional phase writes."""
import fcntl,hashlib,os,struct,tempfile,threading
from pathlib import Path
from contextlib import contextmanager
SIZE=256*512
class VmuConflict(ValueError):pass

def blank_image():
    image=bytearray(SIZE);root=255*512;fat=254*512
    image[root:root+16]=b'\x55'*16
    image[root+48:root+56]=bytes([0x20,0,1,1,0,0,0,5])
    for offset,value in [(64,255),(66,0),(68,255),(70,254),(72,1),(74,253),(76,13),(78,0),(80,200),(82,31)]:struct.pack_into('<H',image,root+offset,value)
    for block in range(256):struct.pack_into('<H',image,fat+block*2,0xfffc if block<200 else block-1 if 241<block<=253 else 0xfffa)
    return bytes(image)

def etag(data):return '"'+hashlib.sha256(data).hexdigest()+'"'

class VmuStore:
    def __init__(self,project):self.folder=Path(project)/'.local/vmu';self.path=self.folder/'a1.bin';self.lock=threading.RLock()
    @contextmanager
    def locked(self):
        with self.lock:
            self.folder.mkdir(parents=True,exist_ok=True)
            with (self.folder/'a1.bin.lock').open('a+b') as handle:
                fcntl.flock(handle,fcntl.LOCK_EX)
                try:yield
                finally:fcntl.flock(handle,fcntl.LOCK_UN)
    def atomic(self,data):
        fd,name=tempfile.mkstemp(prefix='a1-',suffix='.tmp',dir=self.folder)
        try:
            with os.fdopen(fd,'wb') as handle:handle.write(data);handle.flush();os.fsync(handle.fileno())
            os.replace(name,self.path)
        finally:
            if os.path.exists(name):os.unlink(name)
    def read_locked(self):
        if not self.path.exists():self.atomic(blank_image())
        data=self.path.read_bytes()
        if len(data)!=SIZE:raise ValueError('Existing VMU image is not 128 KiB; it was preserved unchanged')
        return data
    def load(self):
        with self.locked():return self.read_locked()
    def write_phase(self,block,phase,data,expected):
        if type(block) is not int or not 0<=block<256 or type(phase) is not int or not 0<=phase<4 or len(data)!=128:raise ValueError('VMU writes require one valid 128-byte phase')
        with self.locked():
            current=self.read_locked()
            if expected!=etag(current):raise VmuConflict('VMU changed in another session. Write rejected; existing save preserved.')
            output=bytearray(current);offset=block*512+phase*128;output[offset:offset+128]=data;self.atomic(output);return etag(output)
    def status(self):
        data=self.load();formatted=data[255*512:255*512+16]==b'\x55'*16
        count=struct.unpack_from('<H',data,255*512+80)[0]
        free=sum(struct.unpack_from('<H',data,254*512+i*2)[0]==0xfffc for i in range(min(count,256))) if formatted else None
        return {'slot':'A1','bytes':SIZE,'formatted':formatted,'userBlocks':count if formatted else None,'freeBlocks':free,'sha256':hashlib.sha256(data).hexdigest(),'storage':'project-local file'}
