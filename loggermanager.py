#!/usr/bin/env python3

#   MIT License
#
#   Copyright (c) 2019 Paul Elliott
#
#   Permission is hereby granted, free of charge, to any person obtaining a copy
#   of this software and associated documentation files (the "Software"), to deal
#   in the Software without restriction, including without limitation the rights
#   to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#   copies of the Software, and to permit persons to whom the Software is
#   furnished to do so, subject to the following conditions:
#
#   The above copyright notice and this permission notice shall be included in all
#   copies or substantial portions of the Software.
#
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#   IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#   FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#   AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#   LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#   OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#   SOFTWARE.

#   This is an extremely simplistic attempt at managing logging to multiple sinks
#   at the same time. You would probably be better off with another python logging
#   library like loguru.

import logging
import smtplib
from os import path, remove, replace
from email.mime.text import MIMEText
from enum import IntEnum
from sys import stdout

class File_Logger:

    """ Class for logging to files. Handles rotation of logfiles if required """

    def __init__(self, logger, min_log_level):
        self.logger = logger
        self.log_handler = None
        self.min_log_level = min_log_level
        self.log_formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                                               datefmt="%H:%M:%S")
        self.rotated_logfiles = []

    def rotate_old_logfiles(self, logfile, num_rotated):
        if logfile not in self.rotated_logfiles:
            if(path.isfile(logfile)):

                if path.isfile("{}.{}".format(logfile, num_rotated)):
                    remove("{}.{}".format(logfile, num_rotated))

                for file_ver in range(num_rotated, 0, -1):
                    if file_ver > 1:
                        target_file = "{}.{}".format(logfile, (file_ver - 1))
                    else:
                        target_file = logfile

                    if path.isfile(target_file):
                        replace(target_file, "{}.{}".format(logfile, file_ver))

                self.rotated_logfiles.append(logfile)

    def setup(self, logfile, num_rotated):

        # There can be only one...
        if self.log_handler is not None:
            self.logger.removeHandler(self.log_handler)

        if logfile != '':

            self.rotate_old_logfiles(logfile, num_rotated)

            self.log_handler = logging.FileHandler(logfile)

            self.logger.addHandler(self.log_handler)
            self.logger.setLevel(self.min_log_level)
            self.log_handler.setFormatter(self.log_formatter)

class Mail_Logger:

    """ Class to send logs via email """

    def __init__(self, min_log_level):
        self.initialised = False
        self.min_log_level = min_log_level
        self.body = ""

    def setup(self, server, from_email, to_email, subject):
        if self.initialised and self.body != "" and (server != self.server or from_email
                                                     != self.from_email or to_email
                                                     != self.to_email or subject
                                                     != self.subject):
            Send(self)

        self.server = server
        self.from_email = from_email
        self.to_email = to_email
        self.subject = subject
        self.initialised = True

    def log(self, log_level, body):

        if self.initialised == True:
            if log_level >= self.min_log_level:
                self.body = self.body + body + "\n"

    def Send(self):

        if self.initialised == True:
            email_msg = MIMEText(self.body)
            email_msg["Subject"] = self.subject
            email_msg["From"] = self.from_email
            email_msg["To"] = self.to_email

            # Send the message via the SMTP server, but don't include the
            # envelope header.
            mail_server = smtplib.SMTP(self.server)
            mail_server.sendmail(self.from_email, self.to_email, email_msg.as_string())
            mail_server.quit()

            self.body = ""
            self.initialised = False

class StdOut_Logger:

    """ Class to send logs to stdout  """

    def __init__(self, logger, min_log_level):
        self.logger = logger
        self.min_log_level = min_log_level
        self.log_formatter = logging.Formatter("%(levelname)s %(message)s")

        self.log_handler = logging.StreamHandler(stdout)
        self.log_handler.setLevel(min_log_level)

        self.logger.addHandler(self.log_handler)
        self.logger.setLevel(self.min_log_level)

class Loglevel(IntEnum):

    CRITICAL = logging.CRITICAL
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARN = logging.WARN
    ERROR = logging.ERROR

    NOTVALID = -1

class Logger_Manager:

    """
    Main interface for Logger_Manager. Logger_Manager can log to stdout, automatically rotated
    file and mail at the same time. This was originally designed for use in daemon type tasks
    Where a log of what happened needs to be kept, and also potentially mailed once the task is
    done
    """

    def __init__(self, min_log_level = Loglevel.INFO):

        self.logger = logging.getLogger("Logger_Manager")
        self.min_log_level = min_log_level

        self.File_Logger = None
        self.stdout_logger = None
        self.mail_logger = None

    def setup_logfile(self, logfile, num_rotated, min_log_level = Loglevel.NOTVALID):

        """ Setup and enable file logging """

        # TODO - should check for existance of log path etc here.

        if min_log_level == Loglevel.NOTVALID:
            min_log_level = self.min_log_level

        if self.File_Logger is None:
            self.File_Logger = File_Logger(self.logger, min_log_level)

        self.File_Logger.setup(logfile, num_rotated)

    def setup_mail(self, server, from_email, to_email, subject,
                   min_log_level = Loglevel.NOTVALID):

        """ Setup and enable logging via mail """

        if min_log_level == Loglevel.NOTVALID:
            min_log_level = self.min_log_level

        if self.mail_logger is None:
            self.mail_logger = Mail_Logger(min_log_level)

        self.mail_logger.setup(server, from_email, to_email, subject)

    def setup_stdout(self, min_log_level = Loglevel.NOTVALID):

        """ Setup and enable logging via stdout """

        if min_log_level == Loglevel.NOTVALID:
            min_log_level = self.min_log_level

        if self.stdout_logger is None:
            self.stdout_logger = StdOut_Logger(self.logger, min_log_level)

    def log(self, log_level, message):

        """ The main log function, this will go to all registered components """

        if self.mail_logger is not None:
            self.mail_logger.log(log_level, message)

        if self.logger.hasHandlers():
            self.logger.log(log_level, message)

    def send_mail(self):

        """
        Call when the accumulated logs need to be sent via mail, does nothing
        if mail logger not setup
        """
        if self.mail_logger is not None:
            self.mail_logger.Send()

