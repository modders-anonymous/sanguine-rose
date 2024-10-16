import sqlite3
import os
import gzip
import traceback

def traceReader(x):
    # print("'"+str(x)+"'")
    pass

class BinaryReader:
    def __init__(self,contents):
        self.contents = contents
        self.offset = 0

    def ReadString(self):
        len = int(self.contents[self.offset])
        self.offset += 1
        # print(len)
        bytes = self.contents[self.offset:self.offset+len]
        self.offset += len
        s = bytes.decode('cp1252')
        traceReader(s)
        return s

    def ReadInt16(self):
        bytes = self.contents[self.offset:self.offset+2]
        self.offset += 2
        i = int.from_bytes(bytes,byteorder='little',signed=True)
        traceReader(i)
        return i
        
    def ReadUint16(self):
        bytes = self.contents[self.offset:self.offset+2]
        self.offset += 2
        i = int.from_bytes(bytes,byteorder='little',signed=False)
        traceReader(i)
        return i
        
    def ReadInt32(self):
        bytes = self.contents[self.offset:self.offset+4]
        self.offset += 4
        i = int.from_bytes(bytes,byteorder='little',signed=True)
        traceReader(i)
        return i

    def ReadUint32(self):
        bytes = self.contents[self.offset:self.offset+4]
        self.offset += 4
        i = int.from_bytes(bytes,byteorder='little',signed=False)
        traceReader(i)
        return i

    def ReadInt64(self):
        bytes = self.contents[self.offset:self.offset+8]
        self.offset += 8
        i = int.from_bytes(bytes,byteorder='little',signed=True)
        traceReader(i)
        return i

    def ReadUint64(self):
        bytes = self.contents[self.offset:self.offset+8]
        self.offset += 8
        i = int.from_bytes(bytes,byteorder='little',signed=False)
        traceReader(i)
        return i
        
    def ReadBoolean(self):
        b = self.contents[self.offset]
        self.offset += 1
        traceReader(b)
        return bool(b)

    def ReadByte(self):
        b = self.contents[self.offset]
        self.offset += 1
        traceReader(b)
        return b

    def ReadBytes(self,n):
        bytes = self.contents[self.offset:self.offset+n]
        self.offset += n
        traceReader(bytes)
        return bytes
        
    def isEOF(self):
        return self.offset == len(self.contents)
        
    def dbg(self):
        print(self.contents[self.offset:])
        
class Img:
    def __init__(self,br):
        traceReader('Img:')
        self.w = br.ReadUint16()
        self.h = br.ReadUint16()
        self.mip = br.ReadByte()
        self.fmt = br.ReadByte()
        self.phash = br.ReadBytes(40)
        
    def dbg(self):
        return '{ w='+str(self.w)+' h='+str(self.h)+' mip='+str(self.mip)+' fmt='+str(self.fmt)+' phash=['+str(len(self.phash))+']}'
 
class HashedFile:
    def __init__(self,br):
        traceReader('HashedFile:')
        self.path = br.ReadString()
        self.hash = br.ReadUint64()
        if br.ReadBoolean():
            self.img = Img(br)
            # print(self.img.__dict__)
            # br.dbg()
        else:
            self.img = None
        self.size = br.ReadInt64()
        assert(self.size>=0)
        n = br.ReadInt32()
        assert(n>=0)
        self.children = []
        for i in range(0,n):
            self.children.append(HashedFile(br))
            
    def dbg(self):
        s = '{ path='+self.path+' hash='+str(self.hash)
        if self.img:
            s += ' img=' + self.img.dbg()
        if len(self.children):
            s += ' children=['
            ci = 0
            for child in self.children:
                if ci:
                    s += ','
                s += child.dbg()
                ci += 1
            s += ']'
        s += ' }'
        return s

def parseContents(hash,contents):
    contents = gzip.decompress(contents)
    # print(contents)
    # print(rowi)
    # print(contents)
    try:
        br = BinaryReader(contents)
        
        hf = HashedFile(br)
        assert(br.isEOF())
        # print(br.contents[br.offset:])
        # print(str(hash)+':'+hf.dbg())
        return hf
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        return None

def normalizeHash(hash):
    if hash < 0:
        return hash + (1<<64)
    else:
        return hash

class ArchiveEntry:
    def __init__(self,archive_hash,intra_path,file_size,file_hash):
        self.archive_hash = archive_hash
        self.intra_path = intra_path
        self.file_size = file_size
        self.file_hash = file_hash

def loadVFS():
    home_dir = os.path.expanduser("~")
    con = sqlite3.connect(home_dir+'/AppData/Local/Wabbajack/GlobalVFSCache5.sqlite')
    cur = con.cursor()
    # rowi = -1
    nn = 0
    nx = 0
    archiveEntries = {}
    for row in cur.execute('SELECT Hash,Contents FROM VFSCache'): # WHERE Hash=-8778729428874073019"):
        # rowi += 1
        # print(row)
        # print(row[0])
        contents = row[1]
        # print(contents)
        # with open('gzipped', 'wb') as wfile:
        #    wfile.write(contents)
        hf = parseContents(row[0],contents)
        nn += 1
        if hf == None:
            nx += 1
        else:    
            for child in hf.children:
                if len(child.children)>0:
                    print("TODO: nested children: path="+child.path)
                    print(child.dbg())
                if archiveEntries.get(child.hash)!=None:
                    print("TODO: multiple entries for a file")
                archiveEntries[child.hash] = ArchiveEntry(hf.hash,child.path,child.size,child.hash)
    print('loadVFS: nn='+str(nn)+' nx='+str(nx))
    return archiveEntries

class Archive:
    def __init__(self,archive_hash,archive_modified,archive_path):
        self.archive_hash=archive_hash
        self.archive_modified=archive_modified
        self.archive_path=archive_path
        
    def eq(self,other):
        if self.archive_hash != other.archive_hash:
            return False
        if self.archive_modified != other.archive_modified:
            return False
        if self.archive_path != other.archive_path:
            return False
        return True

def loadHC():
    home_dir = os.path.expanduser("~")
    con = sqlite3.connect(home_dir+'/AppData/Local/Wabbajack/GlobalHashCache2.sqlite')
    cur = con.cursor()
    archives = {}
    nn = 0
    for row in cur.execute('SELECT Path,LastModified,Hash FROM HashCache'):
        hash = normalizeHash(row[2])
        
        olda = archives.get(hash)
        newa = Archive(hash,row[1],row[0])
        if olda!=None and not olda.eq(newa):
            # print("TODO: multiple archives: hash="+str(hash)+" old="+str(olda.__dict__)+" new="+str(newa.__dict__))
            # wait = input("Press Enter to continue.")
            pass
        else:
            archives[hash] = newa
    print('loadHC: nn='+str(nn))
    return archives
    
def findFile(chc,archives,archiveEntries,fpath):
    chc.execute("SELECT Path,LastModified,Hash FROM HashCache WHERE Path='"+fpath.lower()+"'")
    row = chc.fetchone()
    print(row)

    hash=normalizeHash(row[2])
    archiveEntry = archiveEntries[hash]
    #print(archiveEntry.__dict__)

    ahash = archiveEntry.archive_hash
    archive = archives[ahash]
    #print(archive.__dict__)
    return archiveEntry, archive


#############

archives = loadHC()
archiveEntries = loadVFS()

fpath = "C:\\Modding\\MO2\\mods\\Hvergelmir's Aesthetics - Brows\\Brows.esp"
fpath = fpath.replace("'","''")

home_dir = os.path.expanduser("~")
hc = sqlite3.connect(home_dir+'/AppData/Local/Wabbajack/GlobalHashCache2.sqlite')
#vfsc = sqlite3.connect(home_dir+'/AppData/Local/Wabbajack/GlobalVFSCache5.sqlite')
chc = hc.cursor()
#cvfsc = vfsc.cursor()

archiveEntry, archive = findFile(chc,archives,archiveEntries,fpath)
print(archiveEntry.__dict__)
print(archive.__dict__)

#chc.execute("SELECT Path,LastModified,Hash FROM HashCache WHERE Path='"+fpath.lower()+"'")
#row = chc.fetchone()
#print(row)

#hash=normalizeHash(row[2])
#archiveEntry = archiveEntries[hash]
#print(archiveEntry.__dict__)

#ahash = archiveEntry.archive_hash
#archive = archives[ahash]
#print(archive.__dict__)

#cvfsc.execute("SELECT Hash,Contents FROM VFSCache WHERE Hash="+str(hash))
#row2 = cvfsc.fetchone()
#print(row2)
#hf = parseContents(row2[1])
#hf.dbg()
