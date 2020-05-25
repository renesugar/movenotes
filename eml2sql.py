import re
import os
import argparse
import sys
import errno
import optparse
import sqlite3
import uuid

import email
import email.utils
from email.message import EmailMessage
from email.parser import BytesParser, Parser
from email.policy import default

from bs4 import BeautifulSoup

import hashlib

import notesdb
import common

#
# MIT License
#
# https://opensource.org/licenses/MIT
#
# Copyright 2020 Rene Sugar
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

#
# Description:
#
# This program loads a directory of RFC822 email files into a SQLite database.
#

global __name__, __author__, __email__, __version__, __license__
__program_name__ = 'eml2sql'
__author__ = 'Rene Sugar'
__email__ = 'rene.sugar@gmail.com'
__version__ = '1.00'
__license__ = 'MIT License (https://opensource.org/licenses/MIT)'
__website__ = 'https://github.com/renesugar'
__db_schema_version__ = '1'
__db_schema_min_version__ = '1'

ALL_EXTS = ['.eml']

def _get_option_parser():
    parser = optparse.OptionParser('%prog [options]',
                                   version='%prog ' + __version__)
    parser.add_option('', "--email",
                      action="store", dest="email_address", default=None,
                      help="Email address")
    parser.add_option('', "--output",
                      action="store", dest="output_path", default=None,
                      help="Path to output SQLite directory")
    parser.add_option("", "--filelist",
                      action="store", dest="filelist", default=[],
                      help="file containing list of RFC822 email files to be loaded")
    return parser

def extract_filenames(args):
  filenames = []
  for arg in args:
    if os.path.splitext(arg)[1] in ALL_EXTS:
      if not os.path.exists(arg):
        common.error('%s: no such a file or directory' % (arg, ))
      filenames.append(arg)
  return filenames

def extract_filelist(options):
  filenames = []
  if not os.path.exists(options.filelist):
    common.error('%s: no such filelist file' % (options.filelist, ))
  with open(options.filelist, "r") as filelist_file:
    lines = filelist_file.readlines()
  for line in lines:
    filename = line.strip()
    if filename.startswith("#"):
      # Skip files that are commented out
      continue
    if (filename.endswith('.eml')):
      filename = filename.replace("$CWD", os.getcwd())
      if not os.path.exists(filename):
          common.error('%s: Invalid filelist entry - no such file or directory' % (line, ))
      filenames.append(filename)
  return filenames

def process_message(filename, email_address, sqlconn, sqlcur):
  print("processing %s" % (filename,))

  # process email messages as notes

  # load email message from file
  with open(filename, 'rb') as fp:
    msg = email.message_from_binary_file(fp, policy=default)

  # email_filename
  email_filename = filename

  # use email address from command line for "From" header (discard "From" header from message)
  # email_from
  email_from = email_address

  # discard recipient list

  # note_original_format (email, apple, icloud, joplin, twitter)
  note_original_format = "email"

  # email_date
  email_date = msg.get('date')
  if email_date is None:
    email_date = email.utils.formatdate()
  # note_internal_date
  note_internal_date = email.utils.parsedate_to_datetime(email_date)
  # email_x_mail_created_date
  email_x_mail_created_date = msg.get('x-mail-created-date')
  if email_x_mail_created_date is None:
    email_x_mail_created_date = email_date

  # email_subject
  email_subject = msg.get('subject')
  if email_subject is None:
    email_subject = "New Note"
  # note_title
  note_title = common.remove_line_breakers(email_subject).strip()

  # email_body
  msg_body = msg.get_body(preferencelist=('html', 'plain'))
  email_body = msg_body.get_content()
  # note_data
  note_data = email_body
  # email_content_type
  if hasattr(msg_body['content-type'], 'content_type'):
    email_content_type = msg_body['content-type'].content_type
  else:
    email_content_type = 'text/plain'
  # note_data_format
  note_data_format = email_content_type
  # email_content_transfer_encoding
  email_content_transfer_encoding = msg_body['content-transfer-encoding']

  markdown_text = ''
  if note_data_format == 'text/plain':
    markdown_text = common.text_to_markdown(note_data)
  elif note_data_format == 'text/html':
    markdown_text = common.html_to_markdown(note_data)
  elif note_data_format == 'text/markdown':
    # no conversion required
    markdown_text = note_data

  # note_data
  note_data = markdown_text

  # note_data_format
  note_data_format = 'text/markdown'

  # note_hash (hash the plain text)
  h = hashlib.sha512()
  h.update(note_data.encode('utf-8'))
  note_hash = h.hexdigest()

  # email_x_uniform_type_identifier
  email_x_uniform_type_identifier = "com.apple.mail-note"

  # email_mime_version
  email_mime_version = msg.get('mime-version')
  if email_mime_version is None:
    email_mime_version = "1.0"
  # email_x_universally_unique_identifier
  email_x_universally_unique_identifier = msg.get('X-Universally-Unique-Identifier')
  if email_x_universally_unique_identifier is None:
    email_x_universally_unique_identifier = common.create_universally_unique_identifier().upper()
  # email_message_id
  email_message_id = msg.get('message-id')
  if email_message_id is None:
    email_message_id = common.create_message_id()

  columns = {}
  columns["note_type"] = "note"
  columns["note_uuid"] = None
  columns["note_parent_uuid"] = None
  columns["note_original_format"] = note_original_format
  columns["note_internal_date"] = note_internal_date
  columns["note_hash"] = note_hash
  columns["note_title"] = note_title
  columns["note_data"] = note_data
  columns["note_data_format"] = note_data_format
  columns["note_url"] = None
  columns["email_filename"] = email_filename
  columns["email_from"] = email_from
  columns["email_x_uniform_type_identifier"] = email_x_uniform_type_identifier
  columns["email_content_type"] = email_content_type
  columns["email_content_transfer_encoding"] = email_content_transfer_encoding
  columns["email_mime_version"] = email_mime_version
  columns["email_date"] = email_date
  columns["email_x_mail_created_date"] = email_x_mail_created_date
  columns["email_subject"] = email_subject
  columns["email_x_universally_unique_identifier"] = email_x_universally_unique_identifier
  columns["email_message_id"] = email_message_id
  columns["email_body"] = email_body

  notesdb.add_email_note(sqlconn, columns)
  sqlconn.commit()

def main(args):
  parser = _get_option_parser()
  (options, args) = parser.parse_args(args)

  email_address = ''
  if hasattr(options, 'email_address') and options.email_address:
    email_address = options.email_address
    if common.check_email_address(email_address) == False:
      # Check if email address is valid
      common.error("email address '%s' is not valid." % (email_address,))
  else:
    common.error("email address not specified.")

  if hasattr(options, 'filelist') and options.filelist:
    filenames = extract_filelist(options)
  else:
    filenames = extract_filenames(args)
  filenames = [os.path.realpath(f) for f in filenames]

  outputPath = ''

  if hasattr(options, 'output_path') and options.output_path:
    outputPath = os.path.abspath(os.path.expanduser(options.output_path))
    if os.path.isdir(outputPath) == False:
      # Check if output directory exists
      common.error("output path '%s' does not exist." % (outputPath,))
  else:
    common.error("output path not specified.")
  
  notesdbfile = os.path.join(options.output_path, 'notesdb.sqlite')

  new_database = (not os.path.isfile(notesdbfile))

  sqlconn = sqlite3.connect(notesdbfile,
    detect_types=sqlite3.PARSE_DECLTYPES)
  sqlcur = sqlconn.cursor()

  if (new_database):
    notesdb.create_database(sqlconn=sqlconn, db_schema_version=__db_schema_version__, email_address=options.email_address)

  db_settings = notesdb.get_db_settings(sqlcur, __db_schema_version__)
  notesdb.check_db_settings(db_settings, '%prog', __version__, __db_schema_min_version__, __db_schema_version__)

  for f in filenames:
    process_message(f, email_address, sqlconn, sqlcur)

if __name__ == "__main__":
  main(sys.argv[1:])

