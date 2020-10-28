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
__program_name__ = 'twitterarchivelikes2sql'
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
                      help="Path to input Twitter archive file")
    parser.add_option('', "--output",
                      action="store", dest="output_path", default=None,
                      help="Path to output notes SQLite directory")
    parser.add_option("", "--cache",
                      action="store", dest="url_dict", default=None,
                      help="JSON dictionary containing expanded URLs")      
    parser.add_option("", "--error",
                      action="store", dest="error_dict", default=None,
                      help="JSON dictionary containing unexpanded URLs and errors")                                         
    return parser

def process_twitter_archive_note(sqlconn, columns):
  # note_title
  if columns["note_title"] is None:
    note_title = constants.NOTES_UNTITLED
  else:
    note_title = common.remove_line_breakers(columns["note_title"]).strip()

  print("processing '%s'" % (note_title,))

  # note_original_format (email, apple, icloud, joplin, bookmark, twitterarchive, twitterapi)
  note_original_format = "twitterarchive"

	# note_internal_date

  # note_title

  # note_url

  # note_data
  note_data = columns['note_data']
  if note_data is None:
    note_data = ''

  # note_data_format
  note_data_format = columns['note_data_format']

	# note_hash (hash the markdown text)
  h = hashlib.sha512()
  h.update(note_data.encode('utf-8'))
  note_hash = h.hexdigest()

  # apple_id
  apple_id = None

  # apple_title
  apple_title = None

  # apple_snippet
  apple_snippet = None

  # apple_folder

  # apple_created

  # apple_last_modified

  # apple_data
  apple_data = None

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
      # Check if input directory exists
      common.error("input file '%s' does not exist." % (inputPath,))
  else:
    common.error("input file not specified.")

  urlDictPath = ''

  url_dict = {}
  if hasattr(options, 'url_dict') and options.url_dict:
    urlDictPath = os.path.abspath(os.path.expanduser(options.url_dict))
    url_dict = common.load_dict(urlDictPath)

  errorDictPath = ''

  error_dict = {}
  if hasattr(options, 'error_dict') and options.error_dict:
    errorDictPath = os.path.abspath(os.path.expanduser(options.error_dict))
    error_dict = common.load_dict(errorDictPath)

  outputPath = ''

  if hasattr(options, 'output_path') and options.output_path:
    outputPath = os.path.abspath(os.path.expanduser(options.output_path))
    if os.path.isdir(outputPath) == False:
      # Check if output directory exists
      common.error("output path '%s' does not exist." % (outputPath,))
  else:
    common.error("output path not specified.")

  twitterdbfile = inputPath

  notesdbfile = os.path.join(outputPath, 'notesdb.sqlite')

  if not os.path.isfile(twitterdbfile):
    common.error("input file does not exist")

  new_database = (not os.path.isfile(notesdbfile))

  twitter_sqlconn = sqlite3.connect(twitterdbfile,
    detect_types=sqlite3.PARSE_DECLTYPES)
  twitter_sqlconn.row_factory = sqlite3.Row
  twitter_sqlcur = twitter_sqlconn.cursor()

  sqlconn = sqlite3.connect(notesdbfile,
    detect_types=sqlite3.PARSE_DECLTYPES)
  sqlcur = sqlconn.cursor()

  if (new_database):
    notesdb.create_database(sqlconn=sqlconn, db_schema_version=__db_schema_version__, email_address=options.email_address)

  db_settings = notesdb.get_db_settings(sqlcur, __db_schema_version__)
  notesdb.check_db_settings(db_settings, '%prog', __version__, __db_schema_min_version__, __db_schema_version__)

  twitter_sqlcur.execute('''SELECT tweetId, 
fullText, 
expandedUrl
FROM archive_like''')

  notes_to_convert_results = twitter_sqlcur.fetchall()
  current = 0
  for row in notes_to_convert_results:
    note_folder = "Twitter"

    add_date = datetime.now()

    note_url  = row['expandedUrl']
    note_text, url_dict, error_dict = common.expand_urls(row['fullText'], url_dict, error_dict)
    note_title = common.defaultTitleFromBody(note_text.splitlines()[0])

    note_data = note_text + "\n\n" + note_url

    current += 1
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
    columns["note_data_format"] = 'text/markdown'
    columns["apple_folder"] = note_folder
    columns["apple_created"] = add_date.strftime("%Y-%m-%d %H:%M:%S.%f")
    columns["apple_last_modified"] = columns["apple_created"]

    process_twitter_archive_note(sqlconn, columns)
 
  sqlconn.commit()

  if urlDictPath == "":
    urlDictPath = "./url_dict.json"
  common.save_dict(urlDictPath, url_dict)

  if errorDictPath == "":
    errorDictPath = "./error_dict.json"
  common.save_dict(errorDictPath, error_dict)

if __name__ == "__main__":
  main(sys.argv[1:])

