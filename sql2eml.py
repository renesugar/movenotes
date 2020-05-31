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
# This program exports notes as a directory of RFC822 email files from a SQLite database.
#

global __name__, __author__, __email__, __version__, __license__
__program_name__ = 'sql2eml'
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

def _save_email(output_path, columns):
  # process email messages as notes

  email_address = columns["email_address"]
  email_date = columns["email_date"]
  email_x_mail_created_date = columns["email_x_mail_created_date"]
  email_subject = columns["email_subject"]
  email_body = columns["email_body"]
  email_content_type = columns["email_content_type"]
  email_x_universally_unique_identifier = columns["email_x_universally_unique_identifier"]
  email_message_id = columns["email_message_id"]

  filename = common.create_uuid_string() + ".eml"

  outputFilename = os.path.join(output_path, filename)

  print("processing %s" % (outputFilename,))

	# email_filename

  # use email address from command line for "From" header (discard "From" header from message)
  # email_from
  email_from = email_address

	# email_date
  if email_date is None:
    email_date = email_x_mail_created_date
  if email_date is None:
    email_date = email.utils.formatdate()

	# email_x_mail_created_date
  if email_x_mail_created_date is None:
    email_x_mail_created_date = email_date

  # email_subject
  if email_subject is None:
    email_subject = constants.NOTES_UNTITLED

	# email_body

	# email_content_type

  if email_content_type == 'text/plain':
    # email_body
    email_body = common.text_to_html(email_body)

    # email_content_type
    email_content_type = 'text/html'

	# email_content_transfer_encoding

	# email_x_uniform_type_identifier
  email_x_uniform_type_identifier = "com.apple.mail-note"

	# email_mime_version
  email_mime_version = "1.0"
	# email_x_universally_unique_identifier
  if email_x_universally_unique_identifier is None:
    email_x_universally_unique_identifier = common.create_universally_unique_identifier().upper()
  else:
    email_x_universally_unique_identifier = email_x_universally_unique_identifier.upper()
	# email_message_id
  if email_message_id is None:
    email_message_id = common.create_message_id()

  msg = EmailMessage()
  msg['From'] = email_from
  msg['Date'] = email_date
  msg['X-Uniform-Type-Identifier'] = email_x_uniform_type_identifier
  msg['X-Mail-Created-Date'] = email_x_mail_created_date
  msg['X-Universally-Unique-Identifier'] = email_x_universally_unique_identifier
  msg['Subject'] = email_subject
  msg['Message-Id'] = email_message_id
  msg.content_subtype = 'html'
  #msg.set_param("charset", "utf8", header='Content-Type', requote=True, charset=None, language='', replace=True)
  #msg.set_content(email_body)
  msg.set_payload(email_body, 'utf8')
  msg.replace_header('Content-Type','text/html')

  # save email message to file
  with open(outputFilename, 'wb') as fp:
    fp.write(msg.as_bytes())

def process_icloud_note(output_path, email_address, row):
  # NOTE: SQLite3 returning column as string even though sqlite3.PARSE_DECLTYPES specified
  internal_date = common.string_to_datetime(row['note_internal_date'])

  email_date = email.utils.format_datetime(internal_date)

  email_x_mail_created_date = email_date

  if row['note_title'] is None:
    email_subject = constants.NOTES_UNTITLED
  else:
    email_subject = common.remove_line_breakers(row['note_title']).strip()

  print("processing '%s'" % (email_subject,))

  if row['note_data_format'] == 'text/markdown':
    # email_body
    email_body = common.markdown_to_html(row['note_data'])

    # email_content_type
    email_content_type = 'text/html'
  else:
    # email_body
    email_body = row['note_data']

    # email_content_type
    email_content_type = row['note_data_format']

  email_x_universally_unique_identifier = None

  email_message_id = None

  columns = {}
  columns["email_address"] = email_address
  columns["email_date"] = email_date
  columns["email_x_mail_created_date"] = email_x_mail_created_date
  columns["email_subject"] = email_subject
  columns["email_body"] = email_body
  columns["email_content_type"] = email_content_type
  columns["email_x_universally_unique_identifier"] = email_x_universally_unique_identifier
  columns["email_message_id"] = email_message_id

  _save_email(output_path, columns)

def process_email(output_path, email_address, row):
  # process email messages as notes

  # email_subject
  email_subject = row['email_subject']
  if email_subject is None:
    email_subject = constants.NOTES_UNTITLED

  print("processing %s" % (email_subject,))

	# email_date
  email_date = row['email_date']
  if email_date is None:
    email_date = row['email_x_mail_created_date']
  if email_date is None:
    email_date = email.utils.formatdate()

	# email_x_mail_created_date
  email_x_mail_created_date = row['email_x_mail_created_date']
  if email_x_mail_created_date is None:
    email_x_mail_created_date = email_date

  if row['email_content_type'] == 'text/html':
    # email_body
    email_body = row['email_body']

    # email_content_type
    email_content_type = 'text/html'
  elif row['note_data_format'] == 'text/markdown':
    # email_body
    email_body = common.markdown_to_html(row['note_data'])

    # email_content_type
    email_content_type = 'text/html'
  else:
    # email_body
    email_body = row['note_data']

    # email_content_type
    email_content_type = row['note_data_format']

  # email_x_universally_unique_identifier
  email_x_universally_unique_identifier = row['email_x_universally_unique_identifier']

  # email_message_id
  email_message_id = row['email_message_id']

  columns = {}
  columns["email_address"] = email_address
  columns["email_date"] = email_date
  columns["email_x_mail_created_date"] = email_x_mail_created_date
  columns["email_subject"] = email_subject
  columns["email_body"] = email_body
  columns["email_content_type"] = email_content_type
  columns["email_x_universally_unique_identifier"] = email_x_universally_unique_identifier
  columns["email_message_id"] = email_message_id

  _save_email(output_path, columns)

def process_joplin_note(output_path, email_address, row):
  # NOTE: Apple Notes App does not allow attachments in GMail notes

  # email_subject
  email_subject = row['note_title']
  if email_subject is None:
    email_subject = constants.NOTES_UNTITLED

  print("processing %s" % (email_subject,))

	# email_date
  email_date = email.utils.format_datetime(datetime.strptime(row['note_internal_date'], "%Y-%m-%d %H:%M:%S"))
  if email_date is None:
    email_date = email.utils.formatdate()

	# email_x_mail_created_date
  email_x_mail_created_date = email.utils.format_datetime(datetime.strptime(row['apple_created'], "%Y-%m-%d %H:%M:%S"))
  if email_x_mail_created_date is None:
    email_x_mail_created_date = email_date

	# email_body
  email_body = common.markdown_to_html(row['note_data'])

	# email_content_type
  email_content_type = 'text/html'

  # email_x_universally_unique_identifier
  email_x_universally_unique_identifier = None

  # email_message_id
  email_message_id = None

  columns = {}
  columns["email_address"] = email_address
  columns["email_date"] = email_date
  columns["email_x_mail_created_date"] = email_x_mail_created_date
  columns["email_subject"] = email_subject
  columns["email_body"] = email_body
  columns["email_content_type"] = email_content_type
  columns["email_x_universally_unique_identifier"] = email_x_universally_unique_identifier
  columns["email_message_id"] = email_message_id

  _save_email(output_path, columns)

def process_apple_note(output_path, email_address, row):
  # NOTE: Apple Notes App does not allow attachments in GMail notes

  # email_subject
  email_subject = row['note_title']
  if email_subject is None:
    email_subject = constants.NOTES_UNTITLED

  print("processing %s" % (email_subject,))

	# email_date
  email_date = email.utils.format_datetime(datetime.strptime(row['note_internal_date'], "%Y-%m-%d %H:%M:%S"))
  if email_date is None:
    email_date = email.utils.formatdate()

	# email_x_mail_created_date
  email_x_mail_created_date = email.utils.format_datetime(datetime.strptime(row['apple_created'], "%Y-%m-%d %H:%M:%S"))
  if email_x_mail_created_date is None:
    email_x_mail_created_date = email_date

  if row['note_data_format'] == 'text/markdown':
    # email_body
    email_body = common.markdown_to_html(row['note_data'])

    # email_content_type
    email_content_type = 'text/html'
  else:
    # email_body
    email_body = row['note_data']

    # email_content_type
    email_content_type = row['note_data_format']

  # email_x_universally_unique_identifier
  email_x_universally_unique_identifier = None

  # email_message_id
  email_message_id = None

  columns = {}
  columns["email_address"] = email_address
  columns["email_date"] = email_date
  columns["email_x_mail_created_date"] = email_x_mail_created_date
  columns["email_subject"] = email_subject
  columns["email_body"] = email_body
  columns["email_content_type"] = email_content_type
  columns["email_x_universally_unique_identifier"] = email_x_universally_unique_identifier
  columns["email_message_id"] = email_message_id

  _save_email(output_path, columns)


def process_bookmark_note(output_path, email_address, row):
  # email_subject
  email_subject = row['note_title']
  if email_subject is None:
    email_subject = constants.NOTES_UNTITLED

  print("processing %s" % (email_subject,))

	# email_date
  email_date = email.utils.format_datetime(datetime.strptime(row['note_internal_date'], "%Y-%m-%d %H:%M:%S"))
  if email_date is None:
    email_date = email.utils.formatdate()

	# email_x_mail_created_date
  email_x_mail_created_date = email.utils.format_datetime(datetime.strptime(row['apple_created'], "%Y-%m-%d %H:%M:%S"))
  if email_x_mail_created_date is None:
    email_x_mail_created_date = email_date

  if row['note_data_format'] == 'text/markdown':
    # email_body
    email_body = common.markdown_to_html(row['note_data'])

    # email_content_type
    email_content_type = 'text/html'
  else:
    # email_body
    email_body = row['note_data']

    # email_content_type
    email_content_type = row['note_data_format']

  # email_x_universally_unique_identifier
  email_x_universally_unique_identifier = None

  # email_message_id
  email_message_id = None

  columns = {}
  columns["email_address"] = email_address
  columns["email_date"] = email_date
  columns["email_x_mail_created_date"] = email_x_mail_created_date
  columns["email_subject"] = email_subject
  columns["email_body"] = email_body
  columns["email_content_type"] = email_content_type
  columns["email_x_universally_unique_identifier"] = email_x_universally_unique_identifier
  columns["email_message_id"] = email_message_id

  _save_email(output_path, columns)

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
joplin_filename FROM notes
                    ORDER BY
                    note_internal_date DESC''')

  notes_to_convert_results = sqlcur.fetchall()
  current = 0
  for row in notes_to_convert_results:
    current += 1
    note_original_format = row['note_original_format']

    # Only convert notes to EML
    note_type = row['note_type']
    if note_type != "note":
      continue

    if note_original_format == "email":
      process_email(outputPath, email_address, row)
    elif note_original_format == "joplin":
      process_joplin_note(outputPath, email_address, row)
    elif note_original_format == "icloud":
      process_icloud_note(outputPath, email_address, row)
    elif note_original_format == "apple":
      process_apple_note(outputPath, email_address, row)
    elif note_original_format == "bookmark":
      process_bookmark_note(outputPath, email_address, row)
    else:
      common.error("unknown note format")
 
  sqlconn.commit()

if __name__ == "__main__":
  main(sys.argv[1:])

