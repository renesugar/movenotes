import regex
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

import hashlib

import mailbox

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
# This program loads a directory of RFC822 email files into an mbox file.
#

global __name__, __author__, __email__, __version__, __license__
__program_name__ = 'eml2mbox'
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

def process_email(filename, mbox):
  print("processing %s" % (filename,))
  with open(filename, 'r') as fp:
    try:
        mbox.add(fp)
    except:
        mbox.close()
        raise

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
  
  mboxfile = os.path.join(outputPath, str(uuid.uuid4()).replace('-', '') + '.mbox')

  output_mbox = mailbox.mbox(mboxfile, create=True)
  output_mbox.lock()

  count = 0
  for filename in os.listdir(inputPath):
    if filename.split('.')[-1] == "eml":
      filePath = os.path.join(inputPath, filename)
      process_email(filePath, output_mbox)
      count += 1
  output_mbox.close()

if __name__ == "__main__":
  main(sys.argv[1:])

