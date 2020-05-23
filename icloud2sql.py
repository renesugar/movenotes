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
import shutil

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
# This program loads an iCloud notes archive into a SQLite database.
#

global __name__, __author__, __email__, __version__, __license__
__program_name__ = 'icloud2sql'
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
                      help="Path to input iCloud notes archive")
    parser.add_option('', "--output",
                      action="store", dest="output_path", default=None,
                      help="Path to output SQLite directory")
    return parser

def process_icloud_note(sqlconn, resources_path, columns):
  note_title = columns['note_title']

  # note_title
  if columns["note_title"] is None:
    note_title = "New Note"
  else:
    note_title = common.remove_line_breakers(columns["note_title"]).strip()

  print("processing '%s'" % (note_title,))

  # note_original_format (email, apple, icloud, joplin, twitter)
  note_original_format = "icloud"

	# note_internal_date
  note_internal_date = columns['note_internal_date']

  # note_url
  note_url = columns['note_url']

  # note_data
  note_data = columns['note_data']
  if note_data is None:
    note_data = ''

  # note_data_format
  note_data_format = 'text/plain'

  # apple_id
  apple_id = None

  # apple_title
  apple_title = note_title

  # apple_snippet
  apple_snippet = note_title

  # apple_folder
  apple_folder = columns['apple_folder']
  if apple_folder is None:
    apple_folder = constants.NOTES_FOLDER_NAME
  # apple_created
  apple_created = note_internal_date.strftime("%Y-%m-%d %H:%M:%S.%f")

  # apple_last_modified
  apple_last_modified = apple_created

  note_attachments = columns['note_attachments']

  # apple_attachment_id
  apple_attachment_id = None

  # apple_attachment_path
  apple_attachment_path = None

  # Copy resources from iCloud directory to SQLite resources directory
  first_image  = False
  first_attach = False
  attachment_urls = '\n'
  for filepath in note_attachments:
    pathname, filename = os.path.split(filepath)

    basename, file_extension = os.path.splitext(filename)

    if os.path.isfile(filepath) == True:
      unique_id = common.create_uuid_string()
      output_filepath = os.path.join(resources_path, unique_id+file_extension)
      shutil.copy2(filepath, output_filepath)

      mime_type, mime_subtype = common.getFileMimeType(filename)

      if mime_type != "image" and first_attach == False:
        first_attach = True
        # pick first non-image attachment as the Apple note attachment
        apple_attachment_id = common.format_univesally_unique_identifier(unique_id)
        apple_attachment_path = output_filepath
      elif first_image == False:
        first_image = True
        # otherwise, pick first image attachment as the Apple note attachment
        apple_attachment_id = common.format_univesally_unique_identifier(unique_id)
        apple_attachment_path = output_filepath

      attachment_urls += '\n'
      attachment_urls += '[' + filename + ']('
      attachment_urls += 'file://' + output_filepath + ')\n'

  # update note text with new location of local attachment URLs

  note_data += attachment_urls

	# note_hash (hash the plain text)
  h = hashlib.sha512()
  h.update(note_data.encode('utf-8'))
  note_hash = h.hexdigest()

  # apple_data
  apple_data = note_data

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
  columns["note_tag_uuid"] = None
  columns["note_note_uiid"] = None
  columns["note_original_format"] = note_original_format
  columns["note_internal_date"] = note_internal_date
  columns["note_hash"] = note_hash
  columns["note_title"] = note_title
  columns["note_data"] = note_data
  columns["note_data_format"] = note_data_format
  columns["note_url"] = note_url
  columns["apple_id"] = apple_id
  columns["apple_title"] = apple_title
  columns["apple_snippet"] = apple_snippet
  columns["apple_folder"] = apple_folder
  columns["apple_created"] = apple_created
  columns["apple_last_modified"] = apple_last_modified
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
    if os.path.isdir(inputPath) == False:
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
  
  outputResourcesPath = os.path.join(outputPath, 'resources')

  notesdbfile = os.path.join(options.output_path, 'notesdb.sqlite')

  new_database = (not os.path.isfile(notesdbfile))

  sqlconn = sqlite3.connect(notesdbfile,
    detect_types=sqlite3.PARSE_DECLTYPES)
  sqlcur = sqlconn.cursor()

  if (new_database):
    notesdb.create_database(sqlconn=sqlconn, db_schema_version=__db_schema_version__, email_address=options.email_address)
    
  db_settings = notesdb.get_db_settings(sqlcur, __db_schema_version__)
  notesdb.check_db_settings(db_settings, '%prog', __version__, __db_schema_min_version__, __db_schema_version__)

  # Create SQLite resources directory
  if not os.path.isdir(outputResourcesPath):
    os.makedirs(outputResourcesPath)

  for filename in os.listdir(inputPath):
    filePath = os.path.join(inputPath, filename)
    if os.path.isdir(filePath) == True:
      # a note folder
      note_folder = filename
      for note in os.listdir(filePath):
        notePath = os.path.join(filePath, note)
        if os.path.isdir(notePath) == True:
          # a note
          note_internal_date = datetime.now()
          note_title = note
          note_attachments = []
          note_text_lines = []
          note_link_lines = []
          for notepart in os.listdir(notePath):
            notepartPath = os.path.join(notePath, notepart)
            if os.path.isdir(notepartPath) == True:
              if notepart == "Attachments":
                # attachments
                for attachment in os.listdir(notepartPath):
                  attachmentPath = os.path.join(notepartPath, attachment)
                  note_attachments.append(attachmentPath)
            elif os.path.isfile(notepartPath) == True:
              if notepart == "Links.txt":
                # links
                with open(notepartPath, 'r') as fp:
                  for line in fp:
                    note_link_lines.append(line)
              elif notepart.split('.')[-1] == "txt":
                # note created date
                try:
                  note_internal_date = datetime.strptime(notepart[-24:-4], '%Y-%m-%dT%H/%M/%SZ')
                except ValueError as ve:
                  try:
                    note_internal_date = datetime.strptime(notepart[-24:-4], '%Y-%m-%dT%H:%M:%SZ')
                  except ValueError as ve:
                    note_internal_date = datetime.now()
                # note text
                with open(notepartPath, 'r') as fp:
                  for line in fp:
                    note_text_lines.append(line)
          all_lines = note_text_lines
          all_lines.append('\n')
          all_lines.extend(note_link_lines)
          note_data = ''.join(all_lines)

          columns = {}
          columns["note_attachments"] = note_attachments # not stored in database
          columns["note_type"] = "note"
          columns["note_uuid"] = None
          columns["note_parent_uuid"] = None
          columns["note_original_format"] = None
          columns["note_internal_date"] = note_internal_date
          columns["note_hash"] = None
          columns["note_title"] = note_title
          columns["note_url"] = None
          columns["note_data"] = note_data
          columns["note_data_format"] = None
          columns["apple_folder"] = note_folder

          process_icloud_note(sqlconn, outputResourcesPath, columns)

if __name__ == "__main__":
  main(sys.argv[1:])

