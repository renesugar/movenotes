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

from datetime import datetime

import hashlib

import notesdb
import common
import constants

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
# This program loads a mac_apt notes database into a SQLite database.
#

global __name__, __author__, __email__, __version__, __license__
__program_name__ = 'macapt2sql'
__author__ = 'Rene Sugar'
__email__ = 'rene.sugar@gmail.com'
__version__ = '1.00'
__license__ = 'MIT License (https://opensource.org/licenses/MIT)'
__website__ = 'https://github.com/renesugar'
__db_schema_version__ = '1'
__db_schema_min_version__ = '1'

def _get_option_parser():
    parser = optparse.OptionParser('%prog [options]',
                                   version='%prog ' + __version__)
    parser.add_option('', "--email",
                      action="store", dest="email_address", default=None,
                      help="Email address")
    parser.add_option("", "--input",
                      action="store", dest="input_path", default=None,
                      help="Path to input MacOS SQLite directory")
    parser.add_option('', "--output",
                      action="store", dest="output_path", default=None,
                      help="Path to output notes SQLite directory")
    parser.add_option("", "--folder",
                      action="store", dest="merge_folder", default=None,
                      help="Folder name to override current notes folders")
    parser.add_option("", "--exclude",
                      action="store", dest="exclude_folders", default=None,
                      help="Folder names to exclude from folder name override")
    return parser

def process_apple_note(sqlconn, columns):
  # note_title
  if columns["apple_title"] is None:
    note_title = "New Note"
  else:
    note_title = common.remove_line_breakers(columns["apple_title"]).strip()

  print("processing '%s'" % (note_title,))

  # note_original_format (email, apple, icloud, joplin, bookmark)
  note_original_format = "apple"

	# note_internal_date
  try:
    note_internal_date = datetime.strptime(columns["apple_last_modified"], "%Y-%m-%d %H:%M:%S.%f")
  except ValueError as ve:
    note_internal_date = datetime.now()

  # note_data
  note_data = str(columns["apple_data"])
  if note_data is None:
    note_data = ''

  # note_data_format
  if note_data.find('<html>') != -1:
    note_data_format = 'text/html'
  else:
    note_data_format = 'text/plain'

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

  # NOTE: BeautifulSoup loses URL for <a href="url">text</a>
  #       when converting HTML to plain text

	# note_hash (hash the markdown text)
  h = hashlib.sha512()
  h.update(note_data.encode('utf-8'))
  note_hash = h.hexdigest()

  columns["note_original_format"] = note_original_format
  columns["note_internal_date"] = note_internal_date
  columns["note_hash"] = note_hash
  columns["note_title"] = note_title
  columns["note_url"] = None
  columns["note_data"] = note_data
  columns["note_data_format"] = note_data_format

  notesdb.add_apple_note(sqlconn, columns)
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

  inputPath = ''

  if hasattr(options, 'input_path') and options.input_path:
    inputPath = os.path.abspath(os.path.expanduser(options.input_path))
    if os.path.isdir(inputPath) == False:
      # Check if input directory exists
      common.error("input path '%s' does not exist." % (inputPath,))
  else:
    common.error("input path not specified.")

  outputPath = ''

  if hasattr(options, 'output_path') and options.output_path:
    outputPath = os.path.abspath(os.path.expanduser(options.output_path))
    if os.path.isdir(outputPath) == False:
      # Check if output directory exists
      common.error("output path '%s' does not exist." % (outputPath,))
  else:
    common.error("output path not specified.")
  
  merge_folder = None
  if hasattr(options, 'merge_folder') and options.merge_folder:
    merge_folder = options.merge_folder
  
  exclude_merge = []
  if hasattr(options, 'exclude_folders') and options.exclude_folders:
    exclude_merge = options.exclude_folders.lstrip(",").split(",")
    exclude_merge[:] = [x.strip() for x in exclude_merge]

  macosdbfile = os.path.join(inputPath, 'mac_apt.db')

  notesdbfile = os.path.join(outputPath, 'notesdb.sqlite')

  if not os.path.isfile(macosdbfile):
    common.error("input file does not exist")

  new_database = (not os.path.isfile(notesdbfile))

  macos_sqlconn = sqlite3.connect(macosdbfile,
    detect_types=sqlite3.PARSE_DECLTYPES)
  macos_sqlconn.row_factory = sqlite3.Row
  macos_sqlcur = macos_sqlconn.cursor()

  sqlconn = sqlite3.connect(notesdbfile,
    detect_types=sqlite3.PARSE_DECLTYPES)
  sqlcur = sqlconn.cursor()

  if (new_database):
    notesdb.create_database(sqlconn=sqlconn, db_schema_version=__db_schema_version__, email_address=options.email_address)

  db_settings = notesdb.get_db_settings(sqlcur, __db_schema_version__)
  notesdb.check_db_settings(db_settings, '%prog', __version__, __db_schema_min_version__, __db_schema_version__)

  macos_sqlcur.execute('''SELECT ID,
Title,
Snippet,
Folder,
Created,
LastModified,
Data,
AttachmentID,
AttachmentPath,
AccountDescription,
AccountIdentifier,
AccountUsername,
Version,
User,
Source FROM Notes''')

  notes_to_convert_results = macos_sqlcur.fetchall()
  current = 0
  for row in notes_to_convert_results:
    apple_folder = row['Folder']

    if merge_folder is not None:
      if apple_folder in exclude_merge:
        pass
      else:
        # merge folder
        apple_folder = merge_folder

    current += 1
    columns = {}
    columns["note_type"] = "note"
    columns["note_uuid"] = None
    columns["note_parent_uuid"] = None
    columns["note_tag_uuid"] = None
    columns["note_note_uuid"] = None
    columns["note_original_format"] = None
    columns["note_internal_date"] = None
    columns["note_hash"] = None
    columns["note_title"] = None
    columns["note_url"] = None
    columns["note_data"] = None
    columns["note_data_format"] = None
    columns["apple_id"] = row['ID']
    columns["apple_title"] = row['Title']
    columns["apple_snippet"] = row['Snippet']
    columns["apple_folder"] = apple_folder
    columns["apple_created"] = row['Created']
    columns["apple_last_modified"] = row['LastModified']
    columns["apple_data"] = row['Data']
    columns["apple_attachment_id"] = row['AttachmentID']
    columns["apple_attachment_path"] = row['AttachmentPath']
    columns["apple_account_description"] = row['AccountDescription']
    columns["apple_account_identifier"] = row['AccountIdentifier']
    columns["apple_account_username"] = row['AccountUsername']
    columns["apple_version"] = row['Version']
    columns["apple_user"] = row['User']
    columns["apple_source"] = row['Source']

    process_apple_note(sqlconn, columns)
 
  sqlconn.commit()

if __name__ == "__main__":
  main(sys.argv[1:])

