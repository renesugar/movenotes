import re
import os
import argparse
import sys
import errno
import optparse
import sqlite3
import uuid

import mimetypes
import email
import email.utils
from email.message import EmailMessage
from email.parser import BytesParser, Parser
from email.policy import default

from bs4 import BeautifulSoup

from markdown2 import Markdown

from datetime import datetime
from pytz import timezone

from html2txt import converters

import html

import hashlib

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

def parse_isoformat_datetime(s):
  if s[-1] == 'Z':
    s = s[:-1] + '+00:00'
  return datetime.fromisoformat(s)

def string_to_datetime(s):
  dt = None
  if isinstance(s, str):
    # NOTE: SQLite3 returning column as string even though sqlite3.PARSE_DECLTYPES specified
    try:
      dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except:
      try:
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S.%f")
      except:
        dt = datetime.fromisoformat(s)
  else:
    dt = s
  return dt
  
def check_email_address(email_address):  
  if(re.search(r'^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$',email_address)):  
    return True     
  else:  
    return False 

def error(msg):
  raise SystemExit('ERROR: %s' % (msg, ))

def remove_line_breakers(s):
  if s is None:
    return s
  t = s.replace('\n', ' ')
  t = t.replace('\r', ' ')
  t = t.replace('\v', ' ')
  t = t.replace('\x0b', ' ')
  t = t.replace('\f', ' ')
  t = t.replace('\x0c', ' ')
  t = t.replace('\x1c', ' ')
  t = t.replace('\x1d', ' ')
  t = t.replace('\x1e', ' ')
  t = t.replace('\x85', ' ')
  t = t.replace('\u2028', ' ')
  t = t.replace('\u2029', ' ')
  return t

def format_univesally_unique_identifier(uuid_string):
  # a56a1e70f3b14bb085f8b8d7794c05fc
  # X-Universally-Unique-Identifier: 115DADB6-28C5-4625-ACFA-CD36F846BE81
  return (uuid_string[0:8] + '-' + uuid_string[8:8+4] + '-' + uuid_string[12:12+4] + '-' + uuid_string[16:16+4] + '-' + uuid_string[20:]).upper()

def format_uuid_string(uuid_str):
  return uuid_str.replace('-', '').lower()

def create_uuid_string():
  return format_uuid_string(str(uuid.uuid4()))

def create_universally_unique_identifier():
  return str(uuid.uuid4())

def create_message_id(id_=None):
  if id_ is None:
    return ("<%s>@mail.gmail.com" % (create_uuid_string(),))
  else:
    return ("<%s>@mail.gmail.com" % (id_,))

def text_to_html(data):
  pattern = (
    r'((([A-Za-z]{3,9}:(?:\/\/)?)'  # scheme
    r'(?:[\-;:&=\+\$,\w]+@)?[A-Za-z0-9\.\-]+(:\[0-9]+)?'  # user@hostname:port
    r'|(?:www\.|[\-;:&=\+\$,\w]+@)[A-Za-z0-9\.\-]+)'  # www.|user@hostname
    r'((?:\/[\+~%\/\.\w\-_]*)?'  # path
    r'\??(?:[\-\+=&;%@\.\w_]*)'  # query parameters
    r'#?(?:[\.\!\/\\\w]*))?)'  # fragment
    r'(?![^<]*?(?:<\/\w+>|\/?>))'  # ignore anchor HTML tags
    r'(?![^\(]*?\))'  # ignore links in brackets (Markdown links and images)
)
  link_patterns = [(re.compile(pattern),r'\1')]
  markdown=Markdown(extras=["link-patterns"],link_patterns=link_patterns)
  html_text = markdown.convert(html.escape(data))
  return html_text

def text_to_markdown(data):
  return html_to_markdown(text_to_html(data))

def markdown_to_html(data):
  markdown=Markdown()
  return markdown.convert(data)

def markdown_to_text(data):
  markdown=Markdown()
  html_text = markdown.convert(data)
  soup = BeautifulSoup(html_text, "html.parser")
  plain_text = soup.get_text()
  return plain_text

def html_to_text(data, separator='\n'):
  soup = BeautifulSoup(data, "html.parser")
  text = soup.get_text(separator)
  return text

def html_to_markdown(data):
  markdown = converters.Html2Markdown().convert(data)
  return markdown

def remove_prefix(text, prefix):
  if text.startswith(prefix):
    return text[len(prefix):]
  return text

def checkExtension(file, exts=None):
  name, extension = os.path.splitext(file)
  extension = extension.lstrip(".")
  if exts is None:
    return True
  elif len(exts) == 0:
    return True
  elif len(extension) == 0:
    return False
  elif extension in exts:
    return True
  return False

def defaultTitleFromBody(line):
  # Remove the first #, *, etc.
  idx = 0
  title = line.strip()
  for c in title:
    if c in ['#', ' ', '\n', '\t', '*', '`', '-']:
      idx += 1
    else:
      break

  title = title[idx:80]

  if len(title) > 0:
    return title

  return 'Untitled'

def getFileMimeType(filepath):
  mimetypes.init()

  if filepath is None:
    return ('application', 'octet-stream')
  
  pathname, filename = os.path.split(filepath)

  basename, file_extension = os.path.splitext(filename)

  mimetype = 'application/octet-stream'
  try:
    mimetype = mimetypes.types_map[file_extension]
  except KeyError as ke:
    mimetype = 'application/octet-stream'

  mime_type_list = mimetype.split("/")
  mime_type, mime_subtype = [mime_type_list[i] for i in (0, 1)]

  return (mime_type, mime_subtype)

def getResourceFileName(resourcesPath, resource):
  matches = []
  for filename in os.listdir(resourcesPath):
    if filename.startswith(resource):
      matches.append(filename)

  return matches

def getResourceLinks(lines):
  # e.g. ![IMAGE.JPG](:/7dd8b560cbc1467693f024d650870a0c)
  #      [FILE.pdf](:/a56a1e70f3b14bb085f8b8d7794c05fc)
  # !?\[(.*)\]\(:\/([a-z0-9]+)\)
  pattern = re.compile(r'!?\[(.*)\]\(:\/([a-z0-9]+)\)', re.DOTALL)
  links = []
  for line in lines:
    for m in pattern.finditer(line):
      if m.end() > m.start():
        url = m.group(0)
        filename = m.group(1)
        resource = m.group(2)
        links.append((url, filename, resource))
  return links

def noteTypeFromJoplinType(type_):
  if int(type_) == constants.JoplinType.JOPLIN_TYPE_NOTE:
    return "note"
  elif int(type_) == constants.JoplinType.JOPLIN_TYPE_FOLDER:
    return "folder"
  elif int(type_) == constants.JoplinType.JOPLIN_TYPE_SETTING:
    return ''
  elif int(type_) == constants.JoplinType.JOPLIN_TYPE_RESOURCE:
    return "resource"
  elif int(type_) == constants.JoplinType.JOPLIN_TYPE_TAG:
    return "tag"
  elif int(type_) == constants.JoplinType.JOPLIN_TYPE_NOTE_TAG:
    return '' # TODO: Difference between TAG and NOTE_TAG?
  elif int(type_) == constants.JoplinType.JOPLIN_TYPE_SEARCH:
    return ''
  elif int(type_) == constants.JoplinType.JOPLIN_TYPE_ALARM:
    return ''
  elif int(type_) == constants.JoplinType.JOPLIN_TYPE_MASTER_KEY:
    return ''
  elif int(type_) == constants.JoplinType.JOPLIN_TYPE_ITEM_CHANGE:
    return ''
  elif int(type_) == constants.JoplinType.JOPLIN_TYPE_NOTE_RESOURCE:
    return ''
  elif int(type_) == constants.JoplinType.JOPLIN_TYPE_RESOURCE_LOCAL_STATE:
    return ''
  elif int(type_) == constants.JoplinType.JOPLIN_TYPE_REVISION:
    return ''
  elif int(type_) == constants.JoplinType.JOPLIN_TYPE_MIGRATION:
    return ''
  elif int(type_) == constants.JoplinType.JOPLIN_TYPE_SMART_FILTER:
    return ''

  return ''