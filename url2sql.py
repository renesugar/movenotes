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

from datetime import datetime, timedelta, timezone

import hashlib

import plistlib

import urllib.request

import notesdb
import constants
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
# This program loads URL bookmarks into a SQLite database.
#

global __name__, __author__, __email__, __version__, __license__
__program_name__ = 'url2sql'
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
                      action="store", dest="input_path", default=[],
                      help="Path to input URL bookmarks")
    parser.add_option('', "--output",
                      action="store", dest="output_path", default=None,
                      help="Path to output SQLite directory")
    parser.add_option("", "--folder",
                      action="store", dest="note_folder", default="Bookmarks",
                      help="Folder name to store bookmark notes")
    return parser

def process_url_note(sqlconn, columns):
  # note_title
  if columns["note_title"] is None:
    note_title = constants.NOTES_UNTITLED
  else:
    note_title = common.remove_line_breakers(columns["note_title"]).strip()

  print("processing '%s'" % (note_title,))

  # note_original_format (email, apple, icloud, joplin, bookmark)
  note_original_format = "bookmark"

	# note_internal_date

  # note_title

  # note_url

  # note_data
  note_data = columns['note_data']
  if note_data is None:
    note_data = ''

  # note_data_format
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

	# note_hash (hash the markdown text)
  h = hashlib.sha512()
  h.update(note_data.encode('utf-8'))
  note_hash = h.hexdigest()

  # apple_id
  apple_id = None

  # apple_title
  apple_title = note_title

  # apple_snippet
  apple_snippet = note_title

  # apple_folder

  # apple_created

  # apple_last_modified

  # apple_data
  apple_data = note_data

  # apple_attachment_id
  apple_attachment_id = None

  # apple_attachment_path
  apple_attachment_path = None

  # apple_account_description
  apple_account_description = None

  # apple_account_identifier
  apple_account_identifier = None

  # apple_account_username
  apple_account_username = None

  # apple_version
  apple_version = None

  # apple_user
  apple_user = None

  # apple_source
  apple_source = None

  columns["note_type"] = "note"
  columns["note_uuid"] = None
  columns["note_parent_uuid"] = None
  columns["note_original_format"] = note_original_format
  #columns["note_internal_date"] = note_internal_date
  columns["note_hash"] = note_hash
  columns["note_title"] = note_title
  columns["note_data"] = note_data
  columns["note_data_format"] = note_data_format
  columns["apple_id"] = apple_id
  columns["apple_title"] = apple_title
  columns["apple_snippet"] = apple_snippet
  #columns["apple_folder"] = apple_folder
  #columns["apple_created"] = apple_created
  #columns["apple_last_modified"] = apple_last_modified
  columns["apple_data"] = apple_data
  columns["apple_attachment_id"] = apple_attachment_id
  columns["apple_attachment_path"] = apple_attachment_path
  columns["apple_account_description"] = apple_account_description
  columns["apple_account_identifier"] = apple_account_identifier
  columns["apple_account_username"] = apple_account_username
  columns["apple_version"] = apple_version
  columns["apple_user"] = apple_user
  columns["apple_source"] = apple_source

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
    if os.path.isfile(inputPath) == False:
      # Check if input file exists
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
  
  note_folder = None
  if hasattr(options, 'note_folder') and options.note_folder:
    note_folder = options.note_folder

  notesdbfile = os.path.join(outputPath, 'notesdb.sqlite')

  new_database = (not os.path.isfile(notesdbfile))

  sqlconn = sqlite3.connect(notesdbfile,
    detect_types=sqlite3.PARSE_DECLTYPES)
  sqlcur = sqlconn.cursor()

  if (new_database):
    notesdb.create_database(sqlconn=sqlconn, db_schema_version=__db_schema_version__, email_address=options.email_address)

  db_settings = notesdb.get_db_settings(sqlcur, __db_schema_version__)
  notesdb.check_db_settings(db_settings, '%prog', __version__, __db_schema_min_version__, __db_schema_version__)

  with open(inputPath, 'r') as fp:
    lines = fp.readlines()

    if (len(lines) % 4) != 0:
      # File consists of a title line followed by date created, date modified and a URL line
      # for each bookmark
      print("Error: Uneven number of lines in file.\n")
      sys.exit(1)

    titles = {}
    index = 0
    while index < len(lines):
      note_title = lines[index].strip()
      add_date = datetime.strptime(lines[index+1].strip(), '%Y-%m-%d %H:%M:%S.%f')
      last_modified = datetime.strptime(lines[index+2].strip(), '%Y-%m-%d %H:%M:%S.%f')
      note_url = lines[index+3].strip()

      # Get title for URL if possible
      if note_title == note_url:
        try:
          if note_url in titles:
            # cached title
            note_title = titles[note_url]
          else:
            # request title
            with urllib.request.urlopen(note_url) as response:
              html = response.read()
              soup = BeautifulSoup(html, features="html.parser")
              note_title = soup.title.string
              if note_title is None:
                note_title = note_url
              else:
                # cache title
                titles[note_url] = note_title
        except:
          pass
      if note_title == '':
        note_title = 'New Note'
            
      note_data = note_title + '\n\n' + note_url
      columns = {}
      columns["note_type"] = "note"
      columns["note_uuid"] = None
      columns["note_parent_uuid"] = None
      columns["note_original_format"] = None
      columns["note_internal_date"] = add_date
      columns["note_hash"] = None
      columns["note_title"] = note_title
      columns["note_url"] = note_url
      columns["note_data"] = note_data
      columns["note_data_format"] = None
      columns["apple_folder"] = note_folder
      columns["apple_created"] = add_date.strftime("%Y-%m-%d %H:%M:%S.%f")
      columns["apple_last_modified"] = last_modified.strftime("%Y-%m-%d %H:%M:%S.%f")
      process_url_note(sqlconn, columns)

      index += 4

if __name__ == "__main__":
  main(sys.argv[1:])

