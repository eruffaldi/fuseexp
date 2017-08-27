#!/usr/bin/env python
#
# Experimental FUSE: minimal example
# Emanuele Ruffaldi 2017
#
from __future__ import print_function, absolute_import, division

import logging

from errno import ENOENT
from stat import S_IFDIR, S_IFREG
from sys import argv, exit
from time import time

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn, fuse_get_context


class Context(LoggingMixIn, Operations):

    def __init__(self,url):
        self.url = url
        super(LoggingMixIn, self).__init__()
        super(Operations, self).__init__()

    def makeurl(self,path):
        
    'Example filesystem to demonstrate fuse_get_context()'

    def getattr(self, path, fh=None):
        uid, gid, pid = fuse_get_context()
        if path == '/':
            st = dict(st_mode=(S_IFDIR | 0o755), st_nlink=2)
        elif path == '/uid':
            size = len('%s\n' % uid)
            st = dict(st_mode=(S_IFREG | 0o444), st_size=size)
        elif path == '/gid':
            size = len('%s\n' % gid)
            st = dict(st_mode=(S_IFREG | 0o444), st_size=size)
        elif path == '/pid':
            size = len('%s\n' % pid)
            st = dict(st_mode=(S_IFREG | 0o444), st_size=size)
        else:
            raise FuseOSError(ENOENT)
        st['st_ctime'] = st['st_mtime'] = st['st_atime'] = time()
        return st

    def getxattr(self, path, name, position=0):

        attrs = self.files[path].get('attrs', {})

        try:
            return attrs[name]
        except KeyError:
            return ''       # Should return ENOATTR
    def read(self, path, size, offset, fh):
        uid, gid, pid = fuse_get_context()
        encoded = lambda x: ('%s\n' % x).encode('utf-8')

        if path == '/uid':
            return encoded(uid)
        elif path == '/gid':
            return encoded(gid)
        elif path == '/pid':
            return encoded(pid)

        raise RuntimeError('unexpected path: %r' % path)

    def readdir(self, path, fh):
        return ['.', '..', 'uid', 'gid', 'pid']

    # Disable unused operations:
    access = None
    flush = None
    getxattr = None
    listxattr = None
    open = None
    opendir = None
    release = None
    releasedir = None
    statfs = None


if __name__ == '__main__':
    if len(argv) != 3:
        print('usage: %s <http> <mountpoint>' % argv[0])
        exit(1)

    logging.basicConfig(level=logging.DEBUG)

    fuse = FUSE(Context(argv[1]), argv[2], foreground=True, ro=True)