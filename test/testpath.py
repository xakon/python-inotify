#!/usr/bin/env py.test

# This testing script can be run either from python 3 or python 2. Run with
# `py.test test.py` or `py.test-2.7 test.py`.
#
# This script will try to import the inotify module from the build directory in
# ../build/lib.linux-{platform}-{pyversion}/inotify relative to its own
# location. If that directory cannot be found it will import the inotify module
# from the default path.


# from __future__ import print_function

import sys, os, errno, shutil, tempfile, itertools
import pytest
from pathlib import PosixPath as P

if not sys.platform.startswith('linux'): raise Exception("This module will only work on Linux")

# Find the package to test. We first try an inotify in the current directory,
# then try to find one in the build directory of this package, and else we
# import from the default path.
un = os.uname()
ver = '.'.join(str(x) for x in sys.version_info[:2])
testdir = os.path.dirname(os.path.abspath(__file__))
inotify_dir = os.path.normpath(testdir + '/../build/lib.{sys}-{plat}-{ver}/'.format(
    sys=un[0].lower(), plat=un[4], ver=ver))
idx = None
if os.path.exists(inotify_dir+'/inotify') and not inotify_dir in sys.path:
  # Insert at the beginning of sys.path, but not before the current directory
  # as we do not want to override an explicit inotify package in the current
  # directory.
  try:
    idx = next(i for i, p in enumerate(sys.path) if p and os.path.samefile(p, '.'))
  except StopIteration:
    # In interactive mode, there is no entry for the current directory, but the
    # first entry of sys.path is the empty string which is interpreted as
    # current directory. So if a path to the current directory is not found,
    # insert after this first empty string.
    idx = 0
  sys.path.insert(idx + 1, inotify_dir)
del un, ver, testdir, idx


import inotify

print("\nTesting inotify module from", inotify.__file__)


# from IPython.terminal.ipapp import TerminalIPythonApp
from IPython import embed as ipythonembed
# ipapp = TerminalIPythonApp.instance()
# ipapp.initialize(argv=[]) # argv=[] instructs IPython to ignore sys.argv


@pytest.fixture(autouse=True)
def preparedir(request):
  # global tempdir
  tempdir = tempfile.mkdtemp(prefix='inotify-test-tmpdir-')
  request.addfinalizer(lambda tempdir=tempdir: shutil.rmtree(tempdir))
  os.chdir(tempdir)
  open('testfile', 'w').close()
  os.mkdir('testdir')


@pytest.fixture(scope='module')
def symlinkmax():
  symlinkmax = pathresolver.get_symlinkmax()
  print('\ndetected system SYMLINKMAX:', symlinkmax)
  return symlinkmax

def makelinkchain(target, directory, numlinks):
  for i in range(1, numlinks+1):
    name = 'l'+str(i)
    os.symlink(target, 'directory/'+name)
    target = name


@pytest.fixture
def w():
  return inotify.PathWatcher()


def test_open(w):
  mask = inotify.IN_OPEN | inotify.IN_CLOSE
  w.add('testfile', mask)
  watch = w._paths[P('testfile')]
  import pdb; pdb.set_trace()

  assert len(watch.links) == 2
  assert watch.path == P('testfile')
  assert watch.watcher == w
  assert watch.mask == mask
  link = watch.links[0]
  assert link.idx == 0
  assert link.path == str(P.getcwd())
  assert link.rest == 'testfile'
  link = watch.links[1]
  assert link.idx == 1
  assert link.path == str(P.getcwd()['testfile'])
  assert link.rest == P('.')
  linkmask = mask | inotify.IN_MOVE | inotify.IN_DELETE
  assert link.mask == linkmask
  assert link.watch == watch
  wd = link.wd
  assert wd.callbacks[None] == [(linkmask, link.handle_event)]
  assert wd.mask == linkmask
  assert wd.watcher == w
  watchdesc = wd.wd
  assert w._watchdescriptors[watchdesc] == wd
  assert w._paths[P('testfile')] == watch
  
  open('testfile').close()
  ev1, ev2 = w.read(block=False)
  assert ev1.open
  assert ev2.close
  assert ev2.close_nowrite
  w.close()


def test_linkchange(w):
  os.symlink('testfile', 'link3')
  os.symlink('link3', 'link2')
  os.symlink('link2', 'link1')
  w.add('link1', inotify.IN_OPEN)
  watch = w._paths[P('link1')]
  assert len(watch.links) == 4
  w1, w2, w3, wt  = watch.links
  assert [str(w.path[w.name]) for w in (w1, w2, w3)] == 'link1 link2 link3'.split()
  assert (wt.path, wt.name) == (P('testfile'), None)
  assert w1.wd == w2.wd == w3.wd
  desc = w1.wd
  linkmask = inotify.IN_MOVE | inotify.IN_DELETE | inotify.IN_CREATE | inotify.IN_ONLYDIR
  assert desc.callbacks[P('link1')] == [(linkmask, w1.handle_event)]
  assert desc.callbacks[P('link2')] == [(linkmask, w2.handle_event)]
  assert desc.callbacks[P('link3')] == [(linkmask, w3.handle_event)]

  os.rename('link2', 'link2new')
  e = w.read()
  assert len(e) == 1
  e1 = e[0]
  assert e1.link_changed
  assert len(w._watchdescriptors) == 1
  assert len(watch.links) == 1
  assert len(list(itertools.chain(*watch.links[0].wd.callbacks.values()))) == 1

  os.rename('link1', 'link1new')
  e = w.read()
  assert len(e) == 1
  e1 = e[0]
  assert e1.link_changed
  assert len(w._watchdescriptors) == 0
  assert len(watch.links) == 0

  # ipythonembed()

# def test_move(w):
#   w.add('.', inotify.IN_MOVE)
#   assert w.read(0) == []
#   os.rename('testfile', 'targetfile')
#   ev = w.read(0)
#   for e in ev:
#     if e.name == 'testfile':
#       assert e.moved_from
#     if e.name == 'targetfile':
#       assert e.moved_to
#   assert ev[0].cookie and ev[0].cookie == ev[1].cookie


# def test_alias(w):
#   '''The inotify system maps watch requests to aliases (e.g. symlinks) to the
#   same watch descriptor, so we need to be sure that a watch is only really
#   removed if all paths it is watching are dismissed.'''

#   os.symlink('testfile', 'testlink')
#   w1 = w.add('testfile', inotify.IN_OPEN)
#   w2 = w.add('testlink', inotify.IN_OPEN)
#   assert w1 == w2
#   assert set(w.paths()) == {'testfile', 'testlink'}
#   assert w.get_watch('testfile') == w.get_watch('testlink')
#   assert len(w.watches()) == 1
#   open('testlink').close()
#   ev = w.read(0)
#   assert len(ev) == 1
#   w.remove_path('testfile')
#   open('testlink').close()
#   ev = w.read(0)
#   assert len(ev) == 1


# def test_delete(w):
#     w.add('testfile', inotify.IN_DELETE_SELF)
#     os.remove('testfile')
#     ev1, ev2 = w.read(0)
#     assert ev1.delete_self
#     assert ev2.ignored
#     assert w.num_watches() == 0

# def test_wrongpath(w):
#     with pytest.raises(OSError) as excinfo:
#         w.add('nonexistant', inotify.IN_OPEN)
#     assert excinfo.value.errno == os.errno.ENOENT
#     with pytest.raises(OSError) as excinfo:
#         w.add_all('nonexistant', inotify.IN_OPEN)
#     assert excinfo.value.errno == os.errno.ENOENT