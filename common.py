import re
import os
import argparse
import sys
import errno
import optparse
import sqlite3
import uuid
import json

import mimetypes
import email
import email.utils
from email.message import EmailMessage
from email.parser import BytesParser, Parser
from email.policy import default

import urllib
from urllib.parse import urlparse
from urllib.parse import unquote
from urllib.parse import quote

import mistune

from collections import namedtuple

from datetime import datetime, timezone
#from pytz import timezone

from html2txt import converters

import html

import hashlib

import requests

import time

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

def unshorten_url(url, url_dict, error_dict, http_timeout=5):
  isError = False
  sleepSeconds = 0.1
  maxRetries = 1
  tries = 0
  error_msg = "empty"
  expanded_url = ""

  if url in url_dict:
    return (url_dict[url], url_dict, error_dict)
  while tries < maxRetries:
    try:
      isError = False
      expanded_url = requests.head(url, allow_redirects=True, timeout=http_timeout).url
    except requests.exceptions.ConnectionError:
      isError = True
      error_msg = ("ERROR: URL '%s' was not expanded due to new connection error" % (url,))
      expanded_url = url
    except requests.exceptions.ReadTimeout:
      isError = True
      error_msg = ("ERROR: URL '%s' was not expanded due to read timeout" % (url,))
      expanded_url = url
    except requests.exceptions.Timeout:
      isError = True
      error_msg = ("ERROR: URL '%s' was not expanded due to timeout" % (url,))
      expanded_url = url
    except requests.exceptions.TooManyRedirects:
      isError = True
      error_msg = ("ERROR: URL '%s' was not expanded due to too many redirects" % (url,))
      expanded_url = url
    except Exception as e:
      error_msg = "ERROR: " + str(e)

    if isError == True:
      time.sleep(sleepSeconds)
      sleepSeconds += 0.1
      tries += 1
    else:
      break

  if isError == False and expanded_url != "" and expanded_url is not None:
    url_dict[url] = expanded_url

    if url in error_dict:
      del error_dict[url]
  else:
    error_dict[url] = error_msg

  return (expanded_url, url_dict, error_dict)

def length_short_link(s, url_prefix):
  pos = s.find(url_prefix)
  path_pos = -1
  if pos >= 0:
    path_pos = pos + len(url_prefix)
    while s[path_pos:path_pos+1].isalnum():
      path_pos += 1
  if path_pos > 0:
    path_len = path_pos - pos
  else:
    path_len = 0
  return path_len 

def length_https_tco_link(s):
  return length_short_link(s, "https://t.co/")

def length_http_tco_link(s):
  return length_short_link(s, "http://t.co/")

def cleanup_https_tco_url(s):
  if s.startswith("https://t.co/"):
    path_len = length_https_tco_link(s)
    if path_len < 23:
      s = s[0:path_len]
    else:
      s = s[0:23]
  return s

def cleanup_http_tco_url(s):
  pos = s.find("http://t.co/")
  if pos >= 0:
    path_len = length_http_tco_link(s[pos:])
    s = s[pos:pos+path_len]
  return s

def cleanup_tco_url(s):
  return cleanup_http_tco_url(cleanup_https_tco_url(s))

def space_http_tco_links(s):
  pos = s.find("http://t.co/")
  while pos >= 0:
    path_len = length_http_tco_link(s[pos:])
    s = s[:pos] + " " + s[pos:pos+path_len] + " " + s[pos+path_len:]
    pos += (12 + path_len + 2) # length of http://t.co prefix plus path plus 2 spaces
    pos = s.find("http://t.co/", pos)
  return s

def space_https_tco_links(s):
  pos = s.find("https://t.co/")
  while pos >= 0:
    s = s[:pos] + " " + s[pos:pos+23] + " " + s[pos+23:]
    pos += 25 # length of t.co link plus 2 spaces
    pos = s.find("https://t.co/", pos)
  return s

def expand_urls(txt, url_dict, error_dict):
  lines = space_http_tco_links(space_https_tco_links(txt)).splitlines()
  expanded_lines = ""
  for line in lines:
    words = line.split()
    expanded_line = ""
    for word in words:
      if word.startswith("https://") or word.startswith("http://"):
        word, url_dict, error_dict = unshorten_url(word, url_dict, error_dict)
      # if word.startswith("https://t.co/"):
      #   word, url_dict, error_dict = unshorten_url(word, url_dict, error_dict)
      # elif word.startswith("http://t.co/"):
      #   word, url_dict, error_dict = unshorten_url(word, url_dict, error_dict)        
      # elif word.startswith("https://bit.ly/"):
      #   word, url_dict, error_dict = unshorten_url(word, url_dict, error_dict)
      # elif word.startswith("http://bit.ly/"):
      #   word, url_dict, error_dict = unshorten_url(word, url_dict, error_dict)
      # elif word.startswith("https://ow.ly/"):
      #   word, url_dict, error_dict = unshorten_url(word, url_dict, error_dict)
      # elif word.startswith("http://ow.ly/"):
      #   word, url_dict, error_dict = unshorten_url(word, url_dict, error_dict)
      # elif word.startswith("https://buff.ly/"):
      #   word, url_dict, error_dict = unshorten_url(word, url_dict, error_dict)
      # elif word.startswith("http://buff.ly/"):
      #   word, url_dict, error_dict = unshorten_url(word, url_dict, error_dict)
      # elif word.startswith("https://tinyurl.com/"):
      #   word, url_dict, error_dict = unshorten_url(word, url_dict, error_dict)
      # elif word.startswith("http://tinyurl.com/"):
      #   word, url_dict, error_dict = unshorten_url(word, url_dict, error_dict)
      if expanded_line != "":
        expanded_line += " "
      expanded_line += word
    if expanded_lines != "":
      expanded_lines += "\n"
    expanded_lines += expanded_line
  return (expanded_lines, url_dict, error_dict)

def save_dict(file, mydict):
  with open(file, 'w') as fp:
    json.dump(mydict, fp)

def load_dict(file):
  mydict = {}
  if os.path.isfile(file):
    with open(file, "r") as fp:
      mydict = json.load(fp)
  return mydict

def escape_url(link):
  if link is None:
    link = ""
  # () are not safe in a markdown URL
  safe = '/#:*?=%@+,&'
  return html.escape(quote(html.unescape(link), safe=safe))

def escape_html(s):
  if s is None:
    s = ""
  return html.escape(html.unescape(s)).replace('&#x27;', "'")

def url_path_endswith(url, suffix):
  if url is None:
    return False

  urlTuple = urllib.parse.urlsplit(url)
  if urlTuple.path.endswith(suffix):
    return True
  return False

def url_path_extension(url):
  if url is None:
    return ''

  urlTuple = urllib.parse.urlsplit(url)

  path, filename = os.path.split(urlTuple.path)

  basename, extension = os.path.splitext(filename)

  return extension

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

def defaultTitleFromBody(body):
  if body is not None and len(body) > 0:
    lines = body.strip().split('\n')
    output = lines[0].strip()
    # Remove the first #, *, etc.
    while len(output) > 0:
      c = output[0]
      if c in ['#', ' ', '\n', '\t', '*', '`', '-']:
        output = output[1:]
      else:
        break
    return output.strip()
  return 'Untitled'
  
def text_to_html(data):
  markdown = mistune.Markdown() 
  html_text = markdown.render(escape_html(data))
  return html_text

def text_to_markdown(data):
  return html_to_markdown(text_to_html(data))

class NoAutolinkRenderer(mistune.Renderer):
  def __init__(self, escape=True, allow_harmful_protocols=None):
    super(NoAutolinkRenderer, self).__init__(escape=escape, allow_harmful_protocols=allow_harmful_protocols)

  def autolink(self, link, is_email=False):
    return link

def markdown_to_html(data):
  # NOTE: Autolinking is only done when converting from text to markdown
  noautolink_renderer = NoAutolinkRenderer()
  markdown = mistune.Markdown(renderer=noautolink_renderer) 
  return markdown.render(data)

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