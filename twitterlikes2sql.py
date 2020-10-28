import re
import os
import argparse
import sys
import errno
import optparse
import sqlite3
import uuid
import json

import email
import email.utils
from email.message import EmailMessage
from email.parser import BytesParser, Parser
from email.policy import default

from datetime import datetime, timezone

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
__program_name__ = 'twitterikes2sql'
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

def makeTwitterTweetUrl(status_id):
  # https://twitter.com/i/web/status/1234567890123456789  
  if status_id is None:
    status_id = "0000000000000000000"
  return ("https://twitter.com/i/web/status/%s" % (status_id,))

def getTwitterProfileInfo(user_id, cursor):
  query = ("""SELECT screen_name, name, profile_image_url_https
FROM users
WHERE id = %s""" % (user_id,))
  cursor.execute(query)
  results = cursor.fetchall()
  for row in results:
    screen_name = row['screen_name']
    name = row['name']
    profile_image_url_https = row['profile_image_url_https']
    return (screen_name, name, profile_image_url_https)
  return None

def makeTwitterUserIdUrl(user_id):
  # https://twitter.com/intent/user?user_id=000000000000000000
  # https://twitter.com/i/user/0000000
  return ("https://twitter.com/i/user/%s" % (user_id,))

def makeTwitterScreennameUrl(screen_name):
  # https://twitter.com/screenname
  return ("https://twitter.com/%s" % (screen_name[1:],))

def makeTwitterHashtagUrl(hashtag):
  # https://twitter.com/hashtag/MyHashTag?src=hashtag_click
  return ("https://twitter.com/hashtag/%s?src=hashtag_click" % (hashtag[1:],))

def formatTwitterFrom(screen_name, name, profile_image_url):
  txt = """[<img width="49" height="49" src="%s"/>](https://twitter.com/%s)

[%s<br>@%s](https://twitter.com/%s)
"""
  return (txt % (profile_image_url, screen_name, name, screen_name, screen_name))

def getTwitterMediaInfo(expanded_url, cursor):
  query = ("""SELECT media_url_https, type as media_type, sizes, video_info, additional_media_info, source_status_id, source_user_id FROM media
WHERE expanded_url = "%s" """ % (expanded_url,))
  cursor.execute(query)
  results = cursor.fetchall()
  for row in results:
    media_url_https = row['media_url_https']
    media_type = row['media_type']
    sizes = row['sizes']
    video_info = row['video_info']
    additional_media_info = row['additional_media_info']
    source_status_id = row['source_status_id']
    source_user_id = row['source_user_id']
    return (media_url_https, media_type, sizes, video_info, additional_media_info, source_status_id, source_user_id)
  return None

def getMediaWidthHeight(sizes):
  sizes_dict = json.loads(sizes)
  if "small" in sizes_dict:
    width = str(sizes_dict["small"]["w"])
    height = str(sizes_dict["small"]["h"])
  elif "medium" in sizes_dict:
    width = str(sizes_dict["medium"]["w"])
    height = str(sizes_dict["medium"]["h"])
  elif "large" in sizes_dict:
    width = str(sizes_dict["large"]["w"])
    height = str(sizes_dict["large"]["h"])
  else:
    width = "100%"
    height = "100%"
  return (width, height)

def formatTwitterPhoto(expanded_url, media_info):
  media_url_https, media_type, sizes, video_info, additional_media_info, source_status_id, source_user_id = media_info
  width, height = getMediaWidthHeight(sizes)
  txt = ("""[<img width="%s" height="%s" src="%s"/>](%s)""" % (width, height, media_url_https, expanded_url,))
  return txt

def formatTwitterVideo(expanded_url, media_info):
  media_url_https, media_type, sizes, video_info, additional_media_info, source_status_id, source_user_id = media_info
  width, height = getMediaWidthHeight(sizes)
  video_info_dict = json.loads(video_info)
  txt = ("""\n\n<video controls width="%s" height="%s">""" % (width, height,))
  if "variants" in video_info_dict:
    variant_list = video_info_dict["variants"]
    for source in variant_list:
      txt += ("""\n  <source type="%s" src="%s"/>""" % (source["content_type"], source["url"],))
  txt += formatTwitterPhoto(expanded_url, media_info)
  txt += "</video>"
  return txt

def formatTwitterMedia(expanded_url, media_info):
  media_url_https, media_type, sizes, video_info, additional_media_info, source_status_id, source_user_id = media_info
  if media_type == "photo":
    return formatTwitterPhoto(expanded_url, media_info)
  return formatTwitterVideo(expanded_url, media_info)

def IsTwitterPhotoUrl(url):
  if url.startswith("https://twitter.com/"):
    lpos_status = url.find("/status/")
    rpos_status = url.rfind("/status/")
    if lpos_status == rpos_status and rpos_status != -1:
      lpos_photo = url.find("/photo/")
      rpos_photo = url.rfind("/photo/")
      if lpos_photo == rpos_photo and rpos_photo != -1 and rpos_status < rpos_photo:
        return True
  return False

def IsTwitterVideoUrl(url):
  if url.startswith("https://twitter.com/"):
    lpos_status = url.find("/status/")
    rpos_status = url.rfind("/status/")
    if lpos_status == rpos_status and rpos_status != -1:
      lpos_video = url.find("/video/")
      rpos_video = url.rfind("/video/")
      if lpos_video == rpos_video and rpos_video != -1 and rpos_status < rpos_video:
        return True
  return False

def IsTwitterMediaUrl(url):
  return IsTwitterPhotoUrl(url) or IsTwitterVideoUrl(url)

def formatTwitterUrls(txt, cursor):
  lines = txt.splitlines()
  expanded_lines = ""
  for line in lines:
    line = line.replace("\u2066", " ")
    line = line.replace("\u2069", " ")
    line = line.replace("https://", " https://")
    line = line.replace("http://", " http://")
    words = line.split()
    expanded_line = ""
    for word in words:
      if IsTwitterMediaUrl(word):
        media_info = getTwitterMediaInfo(word, cursor)
        if media_info is None:
          pass
        else:
          word = formatTwitterMedia(word, media_info)
      elif word[0:1] == "@":
        word = formatTwitterUrl(word, makeTwitterScreennameUrl(word))
      elif word[0:1] == "#":
        word = formatTwitterUrl(word, makeTwitterHashtagUrl(word))
      if expanded_line != "":
        expanded_line += " "
      expanded_line += word
    if expanded_lines != "":
      expanded_lines += "\n"
    expanded_lines += expanded_line
  return expanded_lines

def formatTwitterReplyingTo(display, link):
  txt = """Replying to

[%s](%s)"""
  return (txt % (display, link))

def formatTwitterUrl(display, link):
  txt = ("""[%s](%s)""" % (display, link))
  return txt

def formatTwitterDate(d):
  return d.astimezone().strftime("%I:%M %p · %b %d, %Y")

def getTwitterClientInfo(source_id, cursor):
  query = ("""SELECT name, url
FROM sources
WHERE id = "%s" """ % (source_id,))
  cursor.execute(query)
  results = cursor.fetchall()
  for row in results:
    url = row['url']
    name = row['name']
    return (name, url)
  return ("Twitter Web App", "https://help.twitter.com/using-twitter/how-to-tweet#source-labels")

def process_twitter_note(sqlconn, columns):
  # note_title
  if columns["note_title"] is None:
    note_title = constants.NOTES_UNTITLED
  else:
    note_title = common.remove_line_breakers(columns["note_title"]).strip()

  print("processing '%s'" % (note_title,))

  # note_original_format (email, apple, icloud, joplin, bookmark, twitterarchive, twitterapi)
  note_original_format = "twitterapi"

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

  twitter_sqlcur.execute('''SELECT tweets.id as id, 
tweets.user as user_id, 
screen_name, 
tweets.full_text as full_text, 
tweets.created_at as created_at, 
source, 
in_reply_to_status_id, 
in_reply_to_user_id, 
in_reply_to_screen_name 
FROM tweets
INNER JOIN users ON tweets.user = users.id''')

  notes_to_convert_results = twitter_sqlcur.fetchall()
  current = 0
  for row in notes_to_convert_results:
    note_folder = "Twitter"

    add_date = common.string_to_datetime(row['created_at'])

    note_url  = makeTwitterTweetUrl(row['id'])
    note_text, url_dict, error_dict = common.expand_urls(row['full_text'], url_dict, error_dict)
    media_note_text = formatTwitterUrls(note_text, twitter_sqlconn.cursor())
    note_title = common.defaultTitleFromBody(note_text.splitlines()[0])

# # NOTE: Change CSS in Joplin instead of putting CSS in markdown
#     note_data = """<style>
# video { 
#    width:100%;
#    height:auto;
# }
# </style>"""

    screen_name, name, profile_image_url = getTwitterProfileInfo(row['user_id'], twitter_sqlconn.cursor())

    # note_data += "\n\n"
    note_data = ""
    note_data += formatTwitterFrom(screen_name, name, profile_image_url)

    if row['in_reply_to_status_id'] is not None:
      note_data += "\n\n" + formatTwitterReplyingTo("@" + row['in_reply_to_screen_name'], makeTwitterTweetUrl(row['in_reply_to_status_id']))

    note_data += "\n\n" + media_note_text
    
    note_data += "\n\n" + formatTwitterUrl(formatTwitterDate(add_date), note_url)

    source_name, source_url = getTwitterClientInfo(row['source'], twitter_sqlconn.cursor())

    note_data += "·" + formatTwitterUrl(source_name, source_url)
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

    process_twitter_note(sqlconn, columns)
 
  sqlconn.commit()

  if urlDictPath == "":
    urlDictPath = "./url_dict.json"
  common.save_dict(urlDictPath, url_dict)

  if errorDictPath == "":
    errorDictPath = "./error_dict.json"
  common.save_dict(errorDictPath, error_dict)

if __name__ == "__main__":
  main(sys.argv[1:])

