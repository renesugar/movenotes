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

import http
import urllib
from urllib.parse import urlparse

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
__program_name__ = 'expandurls'
__author__ = 'Rene Sugar'
__email__ = 'rene.sugar@gmail.com'
__version__ = '1.00'
__license__ = 'MIT License (https://opensource.org/licenses/MIT)'
__website__ = 'https://github.com/renesugar'
__db_schema_version__ = '1'
__db_schema_min_version__ = '1'

def AlternateExpandUrl(url, previous_url=None, http_timeout=5):
  try:
    parsed = urlparse(url)
    if parsed.scheme == 'https':
      h = http.client.HTTPSConnection(parsed.netloc, timeout=http_timeout)
    else:
      h = http.client.HTTPConnection(parsed.netloc, timeout=http_timeout)
    resource = parsed.path
    if parsed.query != "": 
      resource += "?" + parsed.query
    try:
      h.request('HEAD', 
                resource, 
                headers={'User-Agent': 'curl/7.64.1'})
      response = h.getresponse()
    except Exception as e:
      error_msg = "ERROR: " + str(e)
      return (url, error_msg)
    if (300 <= response.status < 400 ) and response.getheader('Location'):
      red_url = response.getheader('Location')
      if red_url == previous_url:
          return (red_url, "")
      return AlternateExpandUrl(red_url, previous_url=url) 
    else:
      return (url, "")
  except Exception as e:
    error_msg = "ERROR: " + str(e)
    return (url, error_msg)

def _get_option_parser():
    parser = optparse.OptionParser('%prog [options]',
                                   version='%prog ' + __version__)
    parser.add_option("", "--cache",
                      action="store", dest="url_dict", default=None,
                      help="JSON dictionary containing expanded URLs")      
    parser.add_option("", "--error",
                      action="store", dest="error_dict", default=None,
                      help="JSON dictionary containing unexpanded URLs and errors")                                         
    return parser

def main(args):
  parser = _get_option_parser()
  (options, args) = parser.parse_args(args)

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

  # Clean incorrectly parsed t.co URLs

  url_dict_copy = dict(url_dict)

  for url, expanded_url in url_dict_copy.items():
    if url.startswith("https://t.co/") and len(url) != 23:
      if url in url_dict:
        del url_dict[url]
      if url in error_dict:
        del error_dict[url]
      error_dict[url] = "cleanup"
    elif False == expanded_url.startswith("http"):
      print("WARNING: Invalid expansion for " + url)
      if url in url_dict:
        del url_dict[url]
      if url in error_dict:
        del error_dict[url]
      error_dict[url] = "retry"      
    elif expanded_url.startswith("https://t.co/"):
      if url in url_dict:
        del url_dict[url]
      if url in error_dict:
        del error_dict[url]
      error_dict[url] = "retry"
    elif expanded_url.startswith("http://t.co/"):
      if url in url_dict:
        del url_dict[url]
      if url in error_dict:
        del error_dict[url]
      error_dict[url] = "retry"

  error_dict_copy = dict(error_dict)

  # NOTE: http://newscienti.st/ link service not available
  # NOTE: http://mnt.to/ link service not available

  for url, error_msg in error_dict_copy.items():
    expanded_url, url_dict, error_dict = common.unshorten_url(common.cleanup_tco_url(url), url_dict, error_dict)
    if url == expanded_url or (url.startswith("http://t.co/") and expanded_url.startswith("https://t.co/")):
      # Try HTTPS connection to URL shortening service
      expanded_url, error_msg = AlternateExpandUrl(common.cleanup_tco_url(url))

      if False == expanded_url.startswith("http") and error_msg == "":
        # No error message was returned
        expanded_url = common.cleanup_tco_url(url)
        error_msg = "Invalid URL expansion"

      print("ERROR: " + expanded_url + ": " + error_msg)
      # Try HTTP connection to URL shortening service

      if error_msg != "":
        if expanded_url.startswith("http://t.co/"):
          http_url = common.cleanup_http_tco_url(expanded_url)
        elif expanded_url.startswith("https://t.co/"):
          http_url = common.cleanup_https_tco_url(expanded_url)
        elif expanded_url.startswith("https://reliawire.com/"):
          urlTuple = urllib.parse.urlparse(expanded_url)
          http_url = urllib.parse.urlunparse(urllib.parse.ParseResult(scheme="http", netloc="sciencebeta.com", path=urlTuple.path, params=urlTuple.params, query=urlTuple.query, fragment=urlTuple.fragment))
        elif expanded_url.startswith("https://preview.ajc.com/"):
          urlTuple = urllib.parse.urlparse(expanded_url)
          http_url = urllib.parse.urlunparse(urllib.parse.ParseResult(scheme="http", netloc="ajc.com", path=urlTuple.path, params=urlTuple.params, query=urlTuple.query, fragment=urlTuple.fragment))
        else:
          urlTuple = urllib.parse.urlparse(expanded_url)
          http_url = urllib.parse.urlunparse(urllib.parse.ParseResult(scheme="http", netloc=urlTuple.netloc, path=urlTuple.path, params=urlTuple.params, query=urlTuple.query, fragment=urlTuple.fragment))
        expanded_url, error_msg = AlternateExpandUrl(http_url)
        if expanded_url.endswith("/cookieAbsent") or expanded_url.endswith("/cookieAbsent?code=null"):
          expanded_url, _, _ = common.unshorten_url(http_url, {}, {})
          error_msg = "AlternateExpandUrl failed (/cookieAbsent) and retried with unshorten_url"
        elif expanded_url.startswith("http"):
          pass
        else:
          expanded_url, _, _ = common.unshorten_url(http_url, {}, {})
          error_msg = "AlternateExpandUrl failed and retried with unshorten_url"
        if expanded_url.startswith("https://trib.in/"):
          urlTuple = urllib.parse.urlparse(expanded_url)
          http_url = urllib.parse.urlunparse(urllib.parse.ParseResult(scheme="http", netloc=urlTuple.netloc, path=urlTuple.path, params=urlTuple.params, query=urlTuple.query, fragment=urlTuple.fragment))
          expanded_url, error_msg = AlternateExpandUrl(http_url)

        print("HTTP: IN:  " + http_url)
        print("HTTP: OUT: " + expanded_url + ": " + error_msg)
    else:
      expanded_url = common.cleanup_tco_url(expanded_url)
      print(url + ": " + expanded_url)

    if expanded_url.startswith("https://t.co/") and url.startswith("https://t.co/"):
      if url in url_dict:
        del url_dict[url]
      if url in error_dict:
        del error_dict[url]
      error_dict[url] = "retry"
    else:
      url_dict[url] = expanded_url
      if url in error_dict:
        del error_dict[url]

  if urlDictPath == "":
    urlDictPath = "./url_dict.json"
  common.save_dict(urlDictPath, url_dict)

  if errorDictPath == "":
    errorDictPath = "./error_dict.json"
  common.save_dict(errorDictPath, error_dict)

if __name__ == "__main__":
  main(sys.argv[1:])

