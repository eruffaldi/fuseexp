#!/usr/bin/env python
#
# Experimental FUSE: union all listing
# Emanuele Ruffaldi 2017
#
# 
# file located in two
# /PATH/FILE/@0 -> symbolic link to effective
# /PATH/FILE/@2 -> symbolic link to first 
#
# TODO: update part of three -> suffixe tree instead of self.paths

from __future__ import with_statement

import os
import sys
import errno
import stat
import signal
from fuse import FUSE, FuseOSError, Operations

class Entry:
    def __init__(self,name,attr):
        self.name = name
        self.attr = attr
        self.paths = {}
        self.isdir = False

class Folder:
    def __init__(self,name,attr,full):
        self.name = name
        self.attr = attr
        self.full = full
        self.children = []
        self.isdir = True
    
class PassthroughLinkMulti(Operations):
    def __init__(self, roots):
        self.roots = roots
        self.paths = {}
        self.root = Folder("","","")
        # DO SCAN
        self.scan()
        signal.signal(signal.SIGUSR1, self.scan)
        print "scandone"

    def scan(self):
        self.paths = {}
        self.paths[""] = self.root
        self.root.full = self.roots[0]
        self.root.children = []
        for i,r in enumerate(self.roots):
            q = r.split("=")
            if len(q) == 1:
                realroot = q[0]
                fakeroot = ""
            else:
                realroot = q[0]
                fakeroot = q[1]
            for root, dirs, files in os.walk(realroot):
                # make dirs
                relroot = root[len(r)+1:]
                if fakeroot != "":
                        relroot =  os.path.join(fakeroot,relroot)
                if relroot == "":
                    parent = self.root
                else:
                    parent = self.paths.get(relroot)
                    if parent is None:
                        parent = self.root
                    print "relroot",relroot,parent
                for d in dirs:
                    fd = os.path.join(root,d)
                    fd_rel = os.path.join(relroot,d)
                    print "dir",d,fd,fd_rel
                    x = self.paths.get(fd_rel)
                    if x is None:
                        x = Folder(d,os.lstat(fd),fd)
                        self.paths[fd_rel] = x
                        if parent is not None:
                            parent.children.append(x)
                    elif not x.isdir:
                        print "\ttype mismatch, ignore"
                for f in files:
                    fp = os.path.join(root,f)
                    fp_rel = os.path.join(relroot,f)
                    print "file",f,fp,fp_rel
                    x = self.paths.get(fp_rel)
                    if x is not None:
                        if x.isdir:
                            print "\ttype mismatch, ignore"
                            continue
                        x.paths[i] = fp
                    else:
                        x = Entry(f,os.lstat(fp))
                        x.paths[i] = fp
                        self.paths[fp_rel] = x
                        if parent is not None:
                            parent.children.append(x)
                        # TODO assume same file


    # DIR -> DIR
    # FILE -> DIR
    # FILE/@0 is first
    def _split_path(self, partial):
        if partial.startswith("/"):
            partial = partial[1:]
        if partial == "":
            return "",None
        y = partial.split(os.sep)
        print "accessing",y
        if y[-1][0] == "@":
            return os.sep.join(y[0:-1]),int(y[-1][1:])
        else:
            return partial,None

    def _solve_path(self, partial):
        path,index = self._split_path(partial)
        x = self.paths.get(path)
        print "solving",partial,"as",path,index
        if x is None:
            print "cannot solve",partial,"with",path,"index",index
            print "paths:",self.paths.keys()
            raise FuseOSError(errno.EACCES)
        elif index is not None:
            if not x.isdir:
                return x,x.paths[index]
            else:
                raise FuseOSError(errno.EACCES)
        else:
            return x,x.full if x.isdir else None

    # Filesystem methods
    # ==================

    def access(self, path, mode):
        print "access",path
        entry,full_path = self._solve_path(path)
        if entry == self.root:
            print "\troot",entry,full_path
            return
        if full_path is not None:        
            if not os.access(full_path, mode):
                raise FuseOSError(errno.EACCES)
        elif entry is None:
            raise FuseOSError(errno.EACCES)
        print "\tok"

    def chmod(self, path, mode):
        return -1

    def chown(self, path, uid, gid):
        return -1

    def getattr(self, path, fh=None):
        entry,full_path = self._solve_path(path)
        print "getattr",path,"gives",entry,full_path
        if entry is self.root:
            full_path = self.root.full
        elif entry is None:
            raise FuseOSError(errno.EACCES)
        if full_path is not None:        
            print "getattr! ",path,"as",full_path
            st = os.lstat(full_path)            
            x = dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime','st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))
            print "x" ,x,st
            if not stat.S_ISDIR(x["st_mode"]):
                x["st_mode"] |= stat.S_IFLNK
            return x
        elif not entry.isdir:
            print "masking file as folder",path,entry.paths
            st = os.lstat(entry.paths.values()[0])
            x = dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                         'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))
            x["st_mode"] = stat.S_IFDIR
            x["st_size"] = 0
            return x

    def readdir(self, path, fh):
        print "dirring",path
        entry,full_path = self._solve_path(path)
        if entry.isdir:
            # REAL
            dirents = ['.', '..']
            if os.path.isdir(full_path):
                dirents.extend(os.listdir(full_path))
            for r in dirents:
                yield r
        elif full_path != "":
            # SIMULATED
            for k in entry.paths.keys():
                yield "@%d" % k
        else:
            # not a directory
            pass

    def readlink(self, path):
        print "link",path
        # we do not support double _solve_path links
        entry,full_path = self._solve_path(path)
        if not entry.isdir and full_path != "":
            return full_path

    def mknod(self, path, mode, dev):
        return -1

    def rmdir(self, path):
        return -1

    def mkdir(self, path, mode):
        return -1

    def statfs(self, path):
        stv = os.statvfs(self.roots[0])
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))



def main(mountpoint, roots):
    print "mounting",mountpoint
    FUSE(PassthroughLinkMulti(roots), mountpoint, nothreads=True, foreground=True)

if __name__ == '__main__':
    main(sys.argv[1],sys.argv[2:])