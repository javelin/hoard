# -*- coding: utf-8 -*-

# clean.py
# Utility to clean emacs back up files and python object files
# Copyright (c) 2012 Mark Jundo P Documento

import glob, os

def clean(path):
    for fn in glob.glob('*'):
        if os.path.isdir(fn):
            os.chdir(fn)
            clean(fn)
            os.chdir('..')
        elif os.path.isfile(fn) and (fn.endswith('~') or fn.endswith('.pyc')):
            os.remove(fn)

if __name__ == '__main__':
    clean('.')
