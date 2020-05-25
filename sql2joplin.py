import re
import os
import argparse
import sys
import errno
import optparse
import sqlite3
import uuid

import urllib
from urllib.parse import urlparse

import mimetypes
import email
import email.utils
from email.message import EmailMessage
from email.parser import BytesParser, Parser
from email.policy import default

from bs4 import BeautifulSoup

from markdown2 import Markdown

from collections import namedtuple

from datetime import datetime
from pytz import timezone

import hashlib
import shutil

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
# This program exports notes as Joplin notes from a SQLite database.
#

global __name__, __author__, __email__, __version__, __license__
__program_name__ = 'sql2joplin'
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
                      help="Path to input SQLite directory")
    parser.add_option('', "--output",
                      action="store", dest="output_path", default=None,
                      help="Path to output emails directory")
    return parser

def process_joplin_folder(output_path, email_address, folder_dict, folder_name, folder_id, folder_parent_id):
  # process folder

  if folder_name is None:
    folder_name = constants.NOTES_FOLDER_NAME

  if len(folder_name.strip()) == 0:
    folder_name = constants.NOTES_FOLDER_NAME

  if folder_name in folder_dict:
    # folder already created
    return (None, None)

  if folder_id is not None:
    pass
  elif folder_name == constants.NOTES_FOLDER_NAME:
    folder_id = constants.NOTES_FOLDER_UUID
  else:
    folder_id = common.create_uuid_string()

  if folder_parent_id is None:
    folder_parent_id = ''

  filename = folder_id + ".md"

  outputFilename = os.path.join(output_path, filename)

  print("processing folder '%s' (%s)" % (folder_name, outputFilename,))

  created_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
  updated_time = created_time

  data = '''%s

id: %s
created_time: %s
updated_time: %s
user_created_time: %s
user_updated_time: %s
encryption_cipher_text: 
encryption_applied: 0
parent_id: %s
is_shared: 0
type_: 2'''

  lines = data % (folder_name, folder_id, created_time, updated_time, created_time, updated_time, folder_parent_id)
  # save folder to file
  with open(outputFilename, 'w') as fp:
    fp.write(lines)

  return (folder_name, folder_id)

def process_joplin_note(output_path, email_address, folder_dict, row):
  # Round-trip Joplin note

  note_type = row['note_type']
  note_uuid = row['note_uuid']
  note_parent_uuid = row['note_parent_uuid']
  note_tag_uuid = row['note_tag_uuid']
  note_note_uuid = row['note_note_uuid']
  note_original_format = row['note_original_format']
  note_internal_date = row['note_internal_date']
  note_hash = row['note_hash']
  note_title = row['note_title']
  note_data = row['note_data']
  note_data_format = row['note_data_format']
  note_url = row['note_url']
  apple_folder = row['apple_folder']

  # Convert note text to markdown format

  markdown_text = ''
  if note_data_format == 'text/plain':
    markdown_text = common.text_to_markdown(note_data)
  elif note_data_format == 'text/html':
    markdown_text = common.html_to_markdown(note_data)
  elif note_data_format == 'text/markdown':
    # no conversion required
    markdown_text = note_data
  else:
    # no body
    markdown_text = ''

  lines = markdown_text
  
  lines += '\n'

  for column_key in row.keys():
    if column_key.startswith('joplin_'):
      # output Joplin columns
      joplin_name = common.remove_prefix(column_key, 'joplin_')
      joplin_value = row[column_key]
      if joplin_value is not None:
        lines += ("%s: %s\n" % (joplin_name, joplin_value))

  if lines.endswith('\n'):
    lines = lines[:-1]

  filename = note_uuid + ".md"

  outputFilename = os.path.join(output_path, filename)

  # save note to file
  with open(outputFilename, 'w') as fp:
    fp.write(lines)


def _save_resource(output_path, resource_id, filepath, filename, file_extension, internal_date):
  file_size = os.path.getsize(filepath)

  if file_extension is not None:
    file_extension = file_extension.lstrip(".")
  else:
    file_extension = ''

  type_, subtype_ = common.getFileMimeType(filepath)

  mime_type = type_ + '/' + subtype_

  # NOTE: SQLite3 returning column as string even though sqlite3.PARSE_DECLTYPES specified
  internal_date = common.string_to_datetime(internal_date)

  created_time = internal_date.astimezone(timezone('UTC')).strftime('%Y-%m-%dT%H:%M:%S.%fZ')

  data = '''%s 

id: %s
mime: %s
filename: 
created_time: %s
updated_time: %s
user_created_time: %s
user_updated_time: %s
file_extension: %s
encryption_cipher_text: 
encryption_applied: 0
encryption_blob_encrypted: 0
size: %s
is_shared: 0
type_: 4'''

  lines = ''
  lines += data % (filename, resource_id, mime_type, created_time, created_time, created_time, created_time, file_extension, str(file_size))

  resource_filename = resource_id + ".md"

  outputFilename = os.path.join(output_path, resource_filename)

  # save note to file
  with open(outputFilename, 'w') as fp:
    fp.write(lines)

def _copy_resource(url, output_path, note_internal_date, attach_id=None):
  output_url = None

  outputResourcesPath = os.path.join(output_path, 'resources')

  urlTuple = urllib.parse.urlsplit(url)

  # Copy local files to resources directory
  if urlTuple.scheme == 'file' and urlTuple.netloc == '':
    if os.path.isfile(urlTuple.path) == True:
      attachmentPath, filename = os.path.split(urlTuple.path)

      basename, extension = os.path.splitext(filename)

      # /Users/username/Library/Group Containers/group.com.apple.notes/Media/12345678-1234-1234-1234-123456789012/filename.ext
      if urlTuple.path.count('/') == 8 and urlTuple.path.split('/')[-4] == 'group.com.apple.notes' and urlTuple.path.split('/')[-3] == 'Media':
        attachment_id = urlTuple.path.split('/')[-2]
      else:
        if attach_id is not None:
          attachment_id = attach_id
        else:
          attachment_id = common.create_uuid_string()

      outputAttachmentPath = os.path.join(outputResourcesPath, common.format_uuid_string(attachment_id)+extension)

      shutil.copy2(urlTuple.path, outputAttachmentPath)

      UrlParts = namedtuple('UrlParts', 'scheme netloc path query fragment')

      # Create 'joplin' scheme URL that gets translated by html2txt
      output_url = urllib.parse.urlunsplit(UrlParts('joplin', '', '/' + common.format_uuid_string(attachment_id) + '/' + filename, '', ''))

      # Create Joplin resource note for note attachment
      _save_resource(output_path, common.format_uuid_string(attachment_id), outputAttachmentPath, filename, extension, note_internal_date)

  return output_url

def _save_note(output_path, email_address, folder_dict, columns):
  note_type = columns['note_type']
  note_uuid = columns['note_uuid']
  note_parent_uuid = columns['note_parent_uuid']
  note_original_format = columns['note_original_format']
  note_internal_date = columns['note_internal_date']
  note_hash = columns['note_hash']
  note_title = columns['note_title']
  note_data = columns['note_data']
  note_data_format = columns['note_data_format']
  note_url = columns['note_url']
  apple_folder = columns['apple_folder']

  # Convert note text to markdown format

  markdown_text = ''
  if note_data_format == 'text/plain':
    markdown_text = common.text_to_markdown(note_data)
  elif note_data_format == 'text/html':
    markdown_text = common.html_to_markdown(note_data)
  elif note_data_format == 'text/markdown':
    # no conversion required
    markdown_text = note_data

  # NOTE: SQLite3 returning column as string even though sqlite3.PARSE_DECLTYPES specified
  note_internal_date = common.string_to_datetime(note_internal_date)

  created_time = note_internal_date.astimezone(timezone('UTC')).strftime('%Y-%m-%dT%H:%M:%S.%fZ')

  data = '''
id: %s
parent_id: %s
created_time: %s
updated_time: %s
is_conflict: 0
latitude: 0.00000000
longitude: 0.00000000
altitude: 0.0000
author: 
source_url: 
is_todo: 0
todo_due: 0
todo_completed: 0
source: joplin
source_application: net.cozic.joplin-mobile
application_data: 
order: 0
user_created_time: %s
user_updated_time: %s
encryption_cipher_text: 
encryption_applied: 0
markup_language: 1
is_shared: 0
type_: 1'''

  lines = ''
  lines += markdown_text
  lines += '\n'

  lines += data % (note_uuid, note_parent_uuid, created_time, created_time, created_time, created_time)

  filename = note_uuid + ".md"

  outputFilename = os.path.join(output_path, filename)

  # save note to file
  with open(outputFilename, 'w') as fp:
    fp.write(lines)

def process_note(output_path, email_address, folder_dict, row):
  note_type = row['note_type']
  note_uuid = row['note_uuid']
  note_parent_uuid = row['note_parent_uuid']
  note_original_format = row['note_original_format']
  note_internal_date = row['note_internal_date']
  note_hash = row['note_hash']
  note_title = row['note_title']
  note_data = row['note_data']
  note_data_format = row['note_data_format']
  note_url = row['note_url']
  apple_folder = row['apple_folder']

  # note_type
  if note_type is None:
    note_type = "note"

  # note_uuid
  if note_uuid is None:
    note_uuid = common.create_uuid_string()

  # apple_folder
  if apple_folder is None:
    apple_folder = common.constants.NOTES_FOLDER_NAME
    note_parent_uuid = common.constants.NOTES_FOLDER_UUID

  # note_parent_uuid
  if note_parent_uuid is None:
    if apple_folder in folder_dict:
      note_parent_uuid = folder_dict[apple_folder]

  if row['note_title'] is None:
    note_title = "New Note"
  else:
    note_title = common.remove_line_breakers(row['note_title']).strip()

  print("processing '%s'" % (note_title,))

  columns = {}
  columns['note_type'] = note_type
  columns['note_uuid'] = note_uuid
  columns['note_parent_uuid'] = note_parent_uuid
  columns["note_original_format"] = note_original_format
  columns["note_internal_date"] = note_internal_date
  columns["note_hash"] = note_hash
  columns["note_title"] = note_title
  columns["note_url"] = note_url
  columns["note_data"] = note_data
  columns["note_data_format"] = note_data_format
  columns["apple_folder"] = apple_folder

  apple_attachment_id = row['apple_attachment_id']
  apple_attachment_path = row['apple_attachment_path']

  columns["apple_attachment_id"] = apple_attachment_id
  columns["apple_attachment_path"] = apple_attachment_path

  # Convert note text to HTML

  update_links = True
  html_text = ''
  if note_data_format == 'text/plain':
    html_text = common.text_to_html(note_data)
    columns["note_data"] = html_text
    # Update note_data_format to text/html
    columns["note_data_format"] = 'text/html'
  elif note_data_format == 'text/html':
    html_text = note_data
  else:
    # Markdown text originated from Joplin
    update_links = False

  # Extract list of file:// links for text/plain or text/html notes

  outputResourcesPath = os.path.join(output_path, 'resources')

  # Update file:// links with location of files in resources directory

  if update_links == True:
    soup = BeautifulSoup(html_text, "html.parser")

    # Links
    for a in soup.findAll('a', href=True):
      url = a['href']

      # Copy file to resources folder
      updated_url = _copy_resource(url, output_path, note_internal_date)

      if updated_url is not None:
        a['href'] = updated_url

    # Image Links
    for img in soup.findAll('img', src=True):
      url = img['src']

      # Copy file to resources folder
      updated_url = _copy_resource(url, output_path, note_internal_date)

      if updated_url is not None:
        img['src'] = updated_url

    # Copy attachment to resources folder and update path in note text
    # https://docs.python.org/3/library/shutil.html#shutil.copy2

    if apple_attachment_path is not None:
      if os.path.isfile(apple_attachment_path) == True:
        UrlParts = namedtuple('UrlParts', 'scheme netloc path query fragment')
        # Create 'file' scheme URL that gets translated by html2txt
        url = urllib.parse.urlunsplit(UrlParts('file', '', apple_attachment_path, '', ''))

        updated_url = _copy_resource(url, output_path, note_internal_date)

        if updated_url is not None:
          urlTuple = urllib.parse.urlsplit(updated_url)
          mime_type_, mime_subtype_ = common.getFileMimeType(urlTuple.path)

          if apple_attachment_id is None:
            common.error("Apple attachment ID missing for '%s'" % (urlTuple.path,))
          attachmentPath, attachmentFilename = os.path.split(urlTuple.path)
          if mime_type_ == "image":
            attachmentTag = ('<img src="%s"/>' % (urlTuple.path,))
          else:
            attachmentTag = ('<a href="%s"/>' % (urlTuple.path,))       

          # NOTE: A URL immediately after a "<br>" tag is not displayed in Joplin
          #       e.g. <br>\n<http://www.google.com>
          #       https://github.com/laurent22/joplin/issues/3270
          
          # Add attachment link to HTML note text
          if html_text.find('</section>') != -1:
            html_text = html_text.replace('</section>', '\n\n' + attachmentTag + '</section>')
          elif html_text.find('</body>') != -1:
            html_text = html_text.replace('</body>', '\n\n' + attachmentTag + '</body>')
          else:
            html_text += '\n\n' + attachmentTag

    # Update HTML with modified links
    columns["note_data"] = html_text

  # Create Joplin note
  _save_note(output_path, email_address, folder_dict, columns)

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

  inputResourcesPath = os.path.join(inputPath, 'resources')

  outputResourcesPath = os.path.join(outputPath, 'resources')

  notesdbfile = os.path.join(options.input_path, 'notesdb.sqlite')

  new_database = (not os.path.isfile(notesdbfile))

  sqlconn = sqlite3.connect(notesdbfile,
    detect_types=sqlite3.PARSE_DECLTYPES)
  sqlconn.row_factory = sqlite3.Row
  sqlcur = sqlconn.cursor()

  if (new_database):
    common.error("database not found")

  db_settings = notesdb.get_db_settings(sqlcur, __db_schema_version__)
  notesdb.check_db_settings(db_settings, '%prog', __version__, __db_schema_min_version__, __db_schema_version__)

  # Create Joplin resources directory
  if not os.path.isdir(outputResourcesPath):
    os.makedirs(outputResourcesPath)

  # Copy resources from SQLite resources directory to Joplin resources directory
  for filename in os.listdir(inputResourcesPath):
    filePath = os.path.join(inputPath, filename)
    if os.path.isfile(filePath) == True:
      shutil.copy2(filePath, outputResourcesPath)

  #
  # Create folders for notes from email, apple, icloud
  # 
  sqlcur.execute('''SELECT DISTINCT 
apple_folder,
joplin_id,
joplin_parent_id FROM notes
                    WHERE note_original_format != "joplin" AND NOT apple_folder IS NULL
                    ORDER BY
                    note_internal_date DESC''')

  folder_dict = {}

  notes_to_convert_results = sqlcur.fetchall()
  folder_count = 0
  for row in notes_to_convert_results:
    folder_count += 1

    folder_name = row['apple_folder']
    folder_id   = row['joplin_id']
    folder_parent_id = row['joplin_parent_id']

    if (folder_name is not None) and (folder_id is None):
      # notes from email, apple, icloud
      folder_name, folder_id = process_joplin_folder(outputPath, email_address, \
        folder_dict, folder_name, folder_id, folder_parent_id)
      folder_dict[folder_name] = folder_id

  if folder_count == 0:
    # Create default "Notes" folder
    folder_name = constants.NOTES_FOLDER_NAME
    folder_id   = constants.NOTES_FOLDER_UUID
    folder_parent_id = None
    folder_name, folder_id = process_joplin_folder(outputPath, email_address, \
      folder_dict, folder_name, folder_id, folder_parent_id)

    if folder_name is not None:
      folder_dict[folder_name] = folder_id

  sqlcur.execute('''SELECT note_id,
note_type,
note_uuid,
note_parent_uuid,
note_tag_uuid,
note_note_uuid,
note_original_format,
note_internal_date,
note_hash,
note_title,
note_data,
note_data_format,
note_url,
email_filename,
email_from,
email_x_uniform_type_identifier,
email_content_type,
email_content_transfer_encoding,
email_mime_version,
email_date,
email_x_mail_created_date,
email_subject,
email_x_universally_unique_identifier,
email_message_id,
email_body,
apple_id,
apple_title,
apple_snippet,
apple_folder,
apple_created,
apple_last_modified,
apple_data,
apple_attachment_id,
apple_attachment_path,
apple_account_description,
apple_account_identifier,
apple_account_username,
apple_version,
apple_user,
apple_source,
joplin_id,
joplin_parent_id,
joplin_type_,
joplin_created_time,
joplin_updated_time,
joplin_is_conflict,
joplin_latitude,
joplin_longitude,
joplin_altitude,
joplin_author,
joplin_source_url,
joplin_is_todo,
joplin_todo_due,
joplin_todo_completed,
joplin_source,
joplin_source_application,
joplin_application_data,
joplin_order,
joplin_user_created_time,
joplin_user_updated_time,
joplin_encryption_cipher_text,
joplin_encryption_applied,
joplin_encryption_blob_encrypted,
joplin_size,
joplin_markup_language,
joplin_is_shared,
joplin_note_id,
joplin_tag_id,
joplin_mime,
joplin_filename,
joplin_file_extension FROM notes
                      ORDER BY
                      note_internal_date DESC''')

  notes_to_convert_results = sqlcur.fetchall()
  current = 0
  for row in notes_to_convert_results:
    current += 1
    note_original_format = row['note_original_format']

    if note_original_format == "email":
      process_note(outputPath, email_address, folder_dict, row)
    elif note_original_format == "joplin":
      joplin_type = int(row['joplin_type_'])

      if joplin_type == constants.JoplinType.JOPLIN_TYPE_NOTE:
        process_joplin_note(outputPath, email_address, folder_dict, row)
      elif joplin_type == constants.JoplinType.JOPLIN_TYPE_FOLDER:
        process_joplin_note(outputPath, email_address, folder_dict, row)
      elif joplin_type == constants.JoplinType.JOPLIN_TYPE_SETTING:
        process_joplin_note(outputPath, email_address, folder_dict, row)
      elif joplin_type == constants.JoplinType.JOPLIN_TYPE_RESOURCE:
        process_joplin_note(outputPath, email_address, folder_dict, row)
      elif joplin_type == constants.JoplinType.JOPLIN_TYPE_TAG:
        process_joplin_note(outputPath, email_address, folder_dict, row)
      elif joplin_type == constants.JoplinType.JOPLIN_TYPE_NOTE_TAG:
        process_joplin_note(outputPath, email_address, folder_dict, row)
      elif joplin_type == constants.JoplinType.JOPLIN_TYPE_SEARCH:
        process_joplin_note(outputPath, email_address, folder_dict, row)
      elif joplin_type == constants.JoplinType.JOPLIN_TYPE_ALARM:
        process_joplin_note(outputPath, email_address, folder_dict, row)
      elif joplin_type == constants.JoplinType.JOPLIN_TYPE_MASTER_KEY:
        process_joplin_note(outputPath, email_address, folder_dict, row)
      elif joplin_type == constants.JoplinType.JOPLIN_TYPE_ITEM_CHANGE:
        process_joplin_note(outputPath, email_address, folder_dict, row)
      elif joplin_type == constants.JoplinType.JOPLIN_TYPE_NOTE_RESOURCE:
        process_joplin_note(outputPath, email_address, folder_dict, row)
      elif joplin_type == constants.JoplinType.JOPLIN_TYPE_RESOURCE_LOCAL_STATE:
        process_joplin_note(outputPath, email_address, folder_dict, row)
      elif joplin_type == constants.JoplinType.JOPLIN_TYPE_REVISION:
        process_joplin_note(outputPath, email_address, folder_dict, row)
      elif joplin_type == constants.JoplinType.JOPLIN_TYPE_MIGRATION:
        process_joplin_note(outputPath, email_address, folder_dict, row)
      elif joplin_type == constants.JoplinType.JOPLIN_TYPE_SMART_FILTER:
        process_joplin_note(outputPath, email_address, folder_dict, row)
      else:
        common.error("unknown Joplin note type")
    elif note_original_format == "icloud":
      process_note(outputPath, email_address, folder_dict, row)
    elif note_original_format == "apple":
      process_note(outputPath, email_address, folder_dict, row)
    elif note_original_format == "bookmark":
      process_note(outputPath, email_address, folder_dict, row)
    else:
      common.error("unknown note type")
 
  sqlconn.commit()

if __name__ == "__main__":
  main(sys.argv[1:])

