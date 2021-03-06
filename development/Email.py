#!/usr/bin/python

"""Email.py: Sends text or HTML emails with optional attachments."""
"""Intended for use with bBox plug-in, hence the odd variable declarations"""

__version__     = "3.5.0"
__author__      = "Donovan Chandler"
__copyright__   = "Copyright 2013, Beezwax Datatools, Inc."
__credits__     = ["Simon Brown", "unknown"]


import email.Encoders as encoders
from email.MIMEBase import MIMEBase
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.MIMEImage import MIMEImage
from email.MIMEAudio import MIMEAudio

import mimetypes
import os
import re
import smtplib


class Email:
    """
    Sends HTML email with optional attachments.
    Compiled from various sources.
    """
    def __init__(self, smtpServer, smtpPort=25, hostname='', username='', password='', debugLevel=0):
        """
        Create a new empty email message object.

        @param smtpServer: The address of the SMTP server
        @param smtpPort: Optional. Defaults to 25. Common ports include 25, 587.
        @param username: Optional.
        @param password: Optional.
        @param debugLevel: Optional. 0 for less info; 1 for more info (may cause some messages to fail compared to 0)

        """
        self._addressDelimiters = ',\n\r'  # characters that split multiple addresses
        self._attachmentDelimiters = '\n\r'  # characters that split attachment paths
        self._textBody = None
        self._hostname = hostname
        self._htmlBody = None
        self._subject = ""
        self._smtpServer = smtpServer
        self._smtpPort = smtpPort
        self._username = username
        self._password = password
        self._debugLevel = debugLevel
        self._replyTo = None
        # Don't bother with complex validation, because it won't cover everything
        self._reEmail = re.compile("^[^@]+@[^@]+\.[^@]+$")
        self.clearRecipients()
        self.clearAttachments()

    def send(self):
        """
        Send the email message represented by this object.
        """
        # Validate message
        if self._textBody is None and self._htmlBody is None:
            raise Exception("Error! Must specify at least one body type (HTML or Text)")
        if len(self._to) == 0:
            raise Exception("Must specify at least one recipient")

        # Create the message part
        if self._textBody is not None and self._htmlBody is None:
            msg = MIMEText(self._textBody, "plain")
        elif self._textBody is None and self._htmlBody is not None:
            msg = MIMEText(self._htmlBody, "html")
        else:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(self._textBody, "plain"))
            msg.attach(MIMEText(self._htmlBody, "html"))

        # Add attachments, if any
        if len(self._attach) != 0:
            tmpmsg = msg
            msg = MIMEMultipart()
            msg.attach(tmpmsg)
        for fname, attachname in self._attach:
            if not os.path.exists(fname):
                raise Exception("File '{0}' does not exist.  Not attaching to email.".format(fname))
                continue
            if not os.path.isfile(fname):
                raise Exception("Attachment '{0}' is not a file.  Not attaching to email.".format(fname))
                continue
            # Guess at encoding type
            ctype, encoding = mimetypes.guess_type(fname)
            if ctype is None or encoding is not None:
                # No guess could be made so use a binary type.
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)
            if maintype == 'text':
                fp = open(fname)
                attach = MIMEText(fp.read(), _subtype=subtype)
                fp.close()
            elif maintype == 'image':
                fp = open(fname, 'rb')
                attach = MIMEImage(fp.read(), _subtype=subtype)
                fp.close()
            elif maintype == 'audio':
                fp = open(fname, 'rb')
                attach = MIMEAudio(fp.read(), _subtype=subtype)
                fp.close()
            else:
                fp = open(fname, 'rb')
                attach = MIMEBase(maintype, subtype)
                attach.set_payload(fp.read())
                fp.close()
                # Encode the payload using Base64
                encoders.encode_base64(attach)
            # Set the filename parameter
            if attachname is None:
                filename = os.path.basename(fname)
            else:
                filename = attachname
            attach.add_header('Content-Disposition', 'attachment', filename=filename)
            msg.attach(attach)

        # Complete header
        # This is where To, CC, BCC are differentiated
        msg['Subject'] = self._subject
        msg['From'] = self._from
        msg['To'] = ", ".join(self._to)
        msg['CC'] = ", ".join(self._cc)
        msg['BCC'] = ", ".join(self._bcc)
        if self._replyTo is not None:
            msg['reply-to'] = self._replyTo
        msg.preamble = "You need a MIME enabled mail reader to see this message"
        msg = msg.as_string()
        allRecipients = self._to + self._cc + self._bcc

        # Send message
        try:
            server = smtplib.SMTP(self._smtpServer, self._smtpPort, self._hostname, 5)
            server.set_debuglevel(self._debugLevel)
            server.ehlo()
            if self._username:
                if server.has_extn('STARTTLS'):
                    server.starttls()
                else:
                    server.quit()
                    server = smtplib.SMTP_SSL(self._smtpServer, self._smtpPort, self._hostname)
                    server.set_debuglevel(self._debugLevel)
                server.ehlo()  # re-identify ourselves over secure connection
                server.login(self._username, self._password)

            result = server.sendmail(self._from, allRecipients, msg)
        except Exception, err:
            raise err
        finally:
            try:
                server.quit()
            except Exception:
                pass
        return result

    def setSubject(self, subject):
        """
        Set the subject of the email message.
        """
        self._subject = subject

    def setFrom(self, address):
        """
        Set the email sender.
        """
        if not self.validateEmailAddress(address):
            raise Exception("Invalid FROM email address '{0}'".format(address))
        self._from = address

    def clearRecipients(self):
        """
        Remove all currently defined recipients for
        the email message.
        """
        self._to = []
        self._cc = []
        self._bcc = []

    def addRecipient(self, address, type='TO'):
        """
        Add a new recipient to the email message.
        """
        if not self.validateEmailAddress(address):
            raise Exception("Invalid {1} email address '{0}'".format(address, type))
        if type == 'CC':
            self._cc.append(address)
        elif type == 'BCC':
            self._bcc.append(address)
        else:
            self._to.append(address)

    def addRecipients(self, addressList, type=None):
        """
        Add one or more reciepients to the email message.
        """
        for address in re.split('[' + self._addressDelimiters + ']\s*', addressList.strip(self._addressDelimiters)):
            if type is not None:
                self.addRecipient(address, type)
            else:
                self.addRecipient(address)

    def setTextBody(self, body):
        """
        Set the plain text body of the email message.
        """
        self._textBody = body

    def setHtmlBody(self, body):
        """
        Set the HTML portion of the email message.
        """
        self._htmlBody = body

    def setReplyTo(self, address):
        """
        Set Reply-To address.
        """
        if not self.validateEmailAddress(address):
            raise Exception("Invalid REPLY-TO email address '{0}'".format(address))
        else:
            self._replyTo = address

    def clearAttachments(self):
        """
        Remove all file attachments.
        """
        self._attach = []

    def addAttachment(self, filepath, attachname=None):
        """
        Add a file attachment to this email message.

        @param filepath: The full path and file name of the file
                      to attach.
        @type filepath: String
        @param attachname: This will be the name of the file in
                           the email message if set.  If not set
                           then the filename will be taken from
                           the filepath parameter above.
        @type attachname: String
        """
        if filepath is None:
            return
        self._attach.append((filepath, attachname))

    def addAttachments(self, filepathList):
        """
        Add one or more file attachments to the email message.
        """
        for thisFile in re.split('[' + self._attachmentDelimiters + ']\s*', filepathList.strip(self._attachmentDelimiters)):
            self.addAttachment(thisFile)

    def validateEmailAddress(self, address):
        """
        Validate the specified email address.

        @return: True if valid, False otherwise
        @rtype: Boolean
        """
        if self._reEmail.search(address) is None:
            return False
        return True


# Enable for debugging
# Remember to replace [at] strings
if True:
    attachmentPath = ""
    attachmentPath = os.path.abspath(os.path.join(__file__, os.pardir)) + "/_tests/cats_are_evil.gif"
    bccAddress = ""
    bodyHTML = "The following should be <b>bold</b>\n<br>\n"
    bodyText = "This is the plain text version"
    ccAddress = "EmailProTesting@gmail.com"
    debugLevel = 1
    fromAddress = "Test Account <EmailProTesting@gmail.com>"
    hostname = "beezwax.net"
    replyAddress = "EmailProTesting@gmail.com"
    subject = "TEST bBox HTML Email"
    toAddress = "EmailProTesting@gmail.com, EmailProTesting@gmail.com"
    ## Server settings - SSL
    # emailServer = "mail.beezwax.net"
    # smtpPort = 587
    # username = "donovan_c[at]beezwax.net"
    # password = "__FILL_ME_IN__"
    ## Server settings - TLS
    emailServer = "smtp.gmail.com"
    smtpPort = 587
    username = "EmailProTesting"
    password = "jmuuN34TBvTzCF"
    ## Server settings - open relay
    # emailServer = "__FILL_ME_IN__"
    # smtpPort = 25
    # username = ""
    # password = ""


# Localize parameters instantiated by bBox
mFrom = fromAddress.encode('utf-8')
mPort = smtpPort
mServer = emailServer
mSubject = subject.encode('utf-8')
mTo = toAddress.encode('utf-8')

try:
    mBodyHTML = bodyHTML.encode('utf-8')
except Exception, e:
    mBodyHTML = ''

try:
    mBodyText = bodyText.encode('utf-8')
except Exception, e:
    mBodyText = ''

if mBodyHTML == '' and mBodyText == '':
    raise Exception("bodyHTML or bodyText must be declared for message body.")

try:
    mBCC = bccAddress.encode('utf-8')
except Exception, e:
    mBCC = ''

try:
    mCC = ccAddress.encode('utf-8')
except Exception, e:
    mCC = ''

try:
    mReplyTo = replyAddress.encode('utf-8')
except Exception, e:
    mReplyTo = ''

try:
    mFile = attachmentPath.encode('utf-8')
except Exception, e:
    mFile = ''

try:
    mPassword = password.encode('utf-8')
except Exception, e:
    mPassword = ''

try:
    mUsername = username.encode('utf-8')
except Exception, e:
    mUsername = ''

try:
    mHostname = hostname
except Exception, e:
    mHostname = ''

try:
    mDebugLevel = debugLevel
except Exception, e:
    mDebugLevel = 0


try:
    # Create and send message
    m = Email(mServer, mPort, mHostname, mUsername, mPassword, mDebugLevel)
    m.setFrom(mFrom)
    m.addRecipients(mTo)
    if mCC:
        m.addRecipients(mCC, 'CC')
    if mBCC:
        m.addRecipients(mBCC, 'BCC')
    if mReplyTo:
        m.setReplyTo(mReplyTo)
    m.setSubject(mSubject)
    # Set HTML text last, so that it's preferred, if present
    # According to RFC 2046, the last part of a multipart message preferred
    if mBodyText:
        m.setTextBody(mBodyText)
    if mBodyHTML:
        m.setHtmlBody(mBodyHTML)
    if mFile:
        m.addAttachments(mFile)
    print m.send()

except Exception, err:
    print str(err)
