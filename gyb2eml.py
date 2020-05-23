# Copyright 2016 Jay Lee
# Copyright 2020 Rene Sugar
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

global __name__, __author__, __email__, __version__, __license__
__program_name__ = 'gyb2eml'
__author__ = 'Rene Sugar'
__email__ = 'rene.sugar@gmail.com'
__version__ = '1.00'
__license__ = 'Apache License 2.0 (https://www.apache.org/licenses/LICENSE-2.0)'
__website__ = 'https://github.com/renesugar/gyb2mbox'
__db_schema_version__ = '6'
__db_schema_min_version__ = '6'        #Minimum for restore

global options, gmail

import argparse
import importlib
import sys
import os
import os.path
import time
import calendar
import random
import struct
import platform
import datetime
import socket
import sqlite3
import ssl
import email
import hashlib
import re
import string
from itertools import islice, chain
import base64
import json
import xml.etree.ElementTree as etree
from urllib.parse import urlencode
import configparser
import webbrowser

import httplib2

def getGYBVersion(divider="\n"):
  return ('gyb2mbox %s~DIV~%s~DIV~%s - %s~DIV~Python %s.%s.%s %s-bit \
%s~DIV~%s %s' % (__version__, __website__, __author__, __email__,
sys.version_info[0], sys.version_info[1], sys.version_info[2],
struct.calcsize('P')*8, sys.version_info[3], platform.platform(),
platform.machine())).replace('~DIV~', divider)

def SetupOptionParser(argv):
  parser = argparse.ArgumentParser(add_help=False)
  parser.add_argument('--email',
    dest='email',
    help='Full email address of user or group to act against')
  action_choices = ['backup','restore', 'restore-group', 'restore-mbox', 'list-files']
  parser.add_argument('--action',
    choices=action_choices,
    dest='action',
    default='backup',
    help='Action to perform. Default is backup.')
  parser.add_argument('--local-folder',
    dest='local_folder',
    help='Optional: On backup, restore, estimate, local folder to use. \
Default is GYB-GMail-Backup-<email>',
    default='XXXuse-email-addressXXX')
  parser.add_argument('--noresume', 
    action='store_true',
    help='Optional: On restores, start from beginning. Default is to resume \
where last restore left off.')
  parser.add_argument('--debug',
    action='store_true',
    dest='debug',
    help='Turn on verbose debugging and connection information \
(troubleshooting)')
  parser.add_argument('--version',
    action='store_true',
    dest='version',
    help='print GYB version and quit')
  parser.add_argument('--short-version',
    action='store_true',
    dest='shortversion',
    help='Just print version and quit')
  parser.add_argument('--help',
    action='help',
    help='Display this message.')
  return parser.parse_args(argv)

def getProgPath():
  if os.environ.get('STATICX_PROG_PATH', False):
    # StaticX static executable
    return os.path.dirname(os.environ['STATICX_PROG_PATH'])
  elif getattr(sys, 'frozen', False):
    # PyInstaller exe
    return os.path.dirname(sys.executable)
  else:
    # Source code
    return os.path.dirname(os.path.realpath(__file__))

def get_db_settings(sqlcur):
  try:
    sqlcur.execute('SELECT name, value FROM settings')
    db_settings = dict(sqlcur) 
    return db_settings
  except sqlite3.OperationalError as e:
    if e.message == 'no such table: settings':
      print("\n\nSorry, this version of GYB requires version %s of the \
database schema. Your backup folder database does not have a version."
 % (__db_schema_version__))
      sys.exit(6)
    else: 
      print("%s" % e)

def check_db_settings(db_settings, action, user_email_address):
  if (db_settings['db_version'] < __db_schema_min_version__  or
      db_settings['db_version'] > __db_schema_version__):
    print("\n\nSorry, this backup folder was created with version %s of the \
database schema while GYB %s requires version %s - %s for restores"
% (db_settings['db_version'], __version__, __db_schema_min_version__,
__db_schema_version__))
    sys.exit(4)
 
def main(argv):
  global options
  options = SetupOptionParser(argv)
  if options.debug:
    httplib2.debuglevel = 4
  if options.version:
    print(getGYBVersion())
    print('Path: %s' % getProgPath())
    print(ssl.OPENSSL_VERSION)
    sys.exit(0)
  if options.shortversion:
    sys.stdout.write(__version__)
    sys.exit(0)
  if not options.email:
    print('ERROR: --email is required.')
    sys.exit(1)
  if options.local_folder == 'XXXuse-email-addressXXX':
    options.local_folder = "GYB-GMail-Backup-%s" % options.email

  if not os.path.isdir(options.local_folder):
    print('ERROR: Folder %s does not exist. Cannot restore.'
      % options.local_folder)
    sys.exit(3)

  sqldbfile = os.path.join(options.local_folder, 'msg-db.sqlite')
  
  # If we're not doing a estimate or if the db file actually exists we open it
  # (creates db if it doesn't exist)
  if os.path.isfile(sqldbfile):
    global sqlconn
    global sqlcur
    sqlconn = sqlite3.connect(sqldbfile,
      detect_types=sqlite3.PARSE_DECLTYPES)
    sqlcur = sqlconn.cursor()
    db_settings = get_db_settings(sqlcur)
    check_db_settings(db_settings, options.action, options.email)

  # LIST-FILES #
  if options.action == 'list-files':
    sqlcur.execute('''SELECT message_num, message_internaldate, \
      message_filename FROM messages
                      ORDER BY \
                      message_internaldate DESC''') # All messages

    messages_to_restore_results = sqlcur.fetchall()
    current = 0
    for x in messages_to_restore_results:
      current += 1
      message_filename = x[2]
      message_num = x[0]
      if not os.path.isfile(os.path.join(options.local_folder,
        message_filename)):
        print('WARNING! file %s does not exist for message %s'
          % (os.path.join(options.local_folder, message_filename),
            message_num))
        print('  this message will be skipped.')
        continue
      print(os.path.join(options.local_folder, message_filename))
    sqlconn.commit()

if __name__ == '__main__':
  if sys.version_info[0] < 3 or sys.version_info[1] < 6:
    print('ERROR: GYB2EML requires Python 3.6 or greater.')
    sys.exit(3)
  elif sys.version_info[1] >= 7:
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    sys.stdin.reconfigure(encoding='utf-8', errors='backslashreplace')
  try:
    main(sys.argv[1:])
  except MemoryError:
    print('''ERROR: GYB ran out of memory during %s. Try the following:

1) Use a 64-bit version of GYB. It has access to more memory.
2) Add "--memory-limit 100" argument to GYB to reduce memory usage.''' % options.action)
    sys.exit(5)
  except ssl.SSLError as e:
    if e.reason == 'NO_PROTOCOLS_AVAILABLE':
      print('ERROR: %s - Please adjust your --tls-min-version and --tls-max-version arguments.' % e.reason)
    else:
      raise
  except KeyboardInterrupt:
    try:
      sqlconn.commit()
      sqlconn.close()
      print()
    except NameError:
      pass
    sys.exit(4)
