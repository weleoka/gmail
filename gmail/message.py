import datetime
import email
import re
import time
import os
from email.header import decode_header, make_header
from imaplib import ParseFlags
from .utf import encode as encode_utf7, decode as decode_utf7

class Message():


    def __init__(self, mailbox, uid):
        self.uid = uid
        self.mailbox = mailbox
        self.gmail = mailbox.gmail if mailbox else None

        self.message = None
        self.headers = {}

        self.subject = str()
        self.body = None
        self.html = str()
        self.raw_headers = None # The undecoded message headers.
        self.raw_message = None # The undecoded message bytestring.
        self.decoded_headers = None # The imaplib message metadata headers.

        self.to = str()
        self.fr = str()
        self.cc = str()
        self.delivered_to = None

        self.sent_at = None

        self.flags = []
        self.labels = []

        self.thread_id = None
        self.thread = []
        self.message_id = None

        self.attachments = []



    def is_read(self):
        return ('\\Seen' in self.flags)

    def read(self):
        flag = '\\Seen'
        self.gmail.imap.uid('STORE', self.uid, '+FLAGS', flag)
        if flag not in self.flags: self.flags.append(flag)

    def unread(self):
        flag = '\\Seen'
        self.gmail.imap.uid('STORE', self.uid, '-FLAGS', flag)
        if flag in self.flags: self.flags.remove(flag)

    def is_starred(self):
        return ('\\Flagged' in self.flags)

    def star(self):
        flag = '\\Flagged'
        self.gmail.imap.uid('STORE', self.uid, '+FLAGS', flag)
        if flag not in self.flags: self.flags.append(flag)

    def unstar(self):
        flag = '\\Flagged'
        self.gmail.imap.uid('STORE', self.uid, '-FLAGS', flag)
        if flag in self.flags: self.flags.remove(flag)

    def is_draft(self):
        return ('\\Draft' in self.flags)

    def has_label(self, label):
        full_label = '%s' % label
        return (full_label in self.labels)

    def add_label(self, label):
        full_label = '%s' % label
        self.gmail.imap.uid('STORE', self.uid, '+X-GM-LABELS', full_label)
        if full_label not in self.labels: self.labels.append(full_label)

    def remove_label(self, label):
        full_label = '%s' % label
        self.gmail.imap.uid('STORE', self.uid, '-X-GM-LABELS', full_label)
        if full_label in self.labels: self.labels.remove(full_label)


    def is_deleted(self):
        return ('\\Deleted' in self.flags)

    def delete(self):
        flag = '\\Deleted'
        self.gmail.imap.uid('STORE', self.uid, '+FLAGS', flag)
        if flag not in self.flags: self.flags.append(flag)

        trash = '"[Gmail]/Trash"' if '"[Gmail]/Trash"' in self.gmail.labels() else '"[Gmail]/Bin"'
        if self.mailbox.name not in ['"[Gmail]/Bin"', '"[Gmail]/Trash"']:
            self.move_to(trash)

    # def undelete(self):
    #     flag = '\\Deleted'
    #     self.gmail.imap.uid('STORE', self.uid, '-FLAGS', flag)
    #     if flag in self.flags: self.flags.remove(flag)


    def move_to(self, name):
        self.gmail.copy(self.uid, name, self.mailbox.name)
        if name not in ['"[Gmail]/Bin"', '"[Gmail]/Trash"']:
            self.delete()



    def archive(self):
        self.move_to('"[Gmail]/All Mail"')

    def parse_headers(self, message):
        hdrs = {}
        for hdr in list(message.keys()):
            hdrs[hdr] = message[hdr]
        return hdrs

    def parse_flags(self, headers):
        return list(ParseFlags(headers))
        # flags = re.search(r'FLAGS \(([^\)]*)\)', headers).groups(1)[0].split(' ')

    def parse_labels(self, headers):
        if re.search(r'X-GM-LABELS \(([^\)]+)\)', headers):
            labels = re.search(r'X-GM-LABELS \(([^\)]+)\)', headers).groups(1)[0].split(' ')
            return [l.replace('"', '') for l in labels]
        else:
            return list()

    def parse_subject(self, encoded_subject):
        dh = decode_header(encoded_subject)
        default_charset = ''
        return ''.join([t[0] + t[1] if t[1] else t[0] + default_charset for t in dh ])


    def parse(self, raw_message):
        self.raw_headers = raw_message[0]
        # 49 (X-GM-THRID 1571527226466073498 X-GM-MSGID 1571527226466073498 X-GM-LABELS ("\\Important") UID 122 FLAGS () BODY[] {7088}
        self.decoded_headers = self.raw_headers.decode()
        self.raw_message = raw_message[1]

        # This should return a message object, which we can then run get_payload on.
        self.message = email.message_from_bytes(self.raw_message)
        self.flags = self.parse_flags(self.raw_headers)
        self.labels = self.parse_labels(self.decoded_headers)
        self.headers = self.parse_headers(self.message)
        
        self.to = self.headers['To']
        self.fr = self.headers['From']
        self.delivered_to = self.headers['Delivered-To']
        self.sent_at = self.headers['Date']
        # self.sent_at = datetime.datetime.fromtimestamp(time.mktime(email.utils.parsedate_tz(self.message['date'])[:9]))
        self.subject = self.headers['Subject']

        if re.search(r'X-GM-THRID (\d+)', self.decoded_headers):
            self.thread_id = re.search(r'X-GM-THRID (\d+)', self.decoded_headers).groups(1)[0]
        if re.search(r'X-GM-MSGID (\d+)', self.decoded_headers):
            self.message_id = re.search(r'X-GM-MSGID (\d+)', self.decoded_headers).groups(1)[0]

        if self.message.get_content_maintype() == "multipart":
            for content in self.message.walk():
                ctype = content.get_content_type()
                cdispo = str(content.get('Content-Disposition'))

                # skip any text/plain (txt) attachments
                if ctype == 'text/plain' and 'attachment' not in cdispo:
                    self.body = content.get_payload(decode=True)
                    break
    
                elif ctype == "text/html":
                    self.html = content.get_payload(decode=True)
                    break

        elif self.message.get_content_maintype() == "text":
            self.body = self.message.get_payload(decode=True)

        if isinstance(self.body, bytes):
            # If MAIL software has not set Content-Transfer-Encoding:
            try:
                # Default decode utf-8
                self.body = self.body.decode()

            except UnicodeDecodeError:

                try:
                    print("Message is not UTF-8 encoded. Trying latin-1.")
                    self.body = self.body.decode(encoding='latin-1')

                except UnicodeDecodeError:
                    print("Message not UTF-8 or latin-1 encoded. Fallback to UTF-8 errors='replace'")
                    self.body = self.body.decode(errors='replace')
        
        # Parse attachments into attachment objects array for this message
        # self.attachments = [
        #     Attachment(attachment) for attachment in self.message._payload
        #         if not isinstance(attachment, str) and attachment.get('Content-Disposition') is not None
        # ]
        for message_part in self.message._payload:
            if not isinstance(message_part, str):
                content_disposition = message_part.get("Content-Disposition", None)
            
                if content_disposition:
                    dispositions = content_disposition.strip().split(";")

                    if bool(content_disposition and dispositions[0].lower() == "attachment"):
                        self.attachments.append(Attachment(message_part))


    def fetch(self):
        if not self.message:
            response, results = self.gmail.imap.uid('FETCH', self.uid, '(BODY.PEEK[] FLAGS X-GM-THRID X-GM-MSGID X-GM-LABELS)')

            self.parse(results[0])

        return self.message

    # returns a list of fetched messages (both sent and received) in chronological order
    def fetch_thread(self):
        self.fetch()
        original_mailbox = self.mailbox
        self.gmail.use_mailbox(original_mailbox.name)

        # fetch and cache messages from inbox or other received mailbox
        response, results = self.gmail.imap.uid('SEARCH', None, '(X-GM-THRID ' + self.thread_id + ')')
        received_messages = {}
        uids = results[0].split(' ')
        if response == 'OK':
            for uid in uids: received_messages[uid] = Message(original_mailbox, uid)
            self.gmail.fetch_multiple_messages(received_messages)
            self.mailbox.messages.update(received_messages)

        # fetch and cache messages from 'sent'
        self.gmail.use_mailbox('"[Gmail]/Sent Mail"')
        response, results = self.gmail.imap.uid('SEARCH', None, '(X-GM-THRID ' + self.thread_id + ')')
        sent_messages = {}
        uids = results[0].split(' ')
        if response == 'OK':
            for uid in uids: sent_messages[uid] = Message(self.gmail.mailboxes['"[Gmail]/Sent Mail"'], uid)
            self.gmail.fetch_multiple_messages(sent_messages)
            self.gmail.mailboxes['"[Gmail]/Sent Mail"'].messages.update(sent_messages)

        self.gmail.use_mailbox(original_mailbox.name)

        # combine and sort sent and received messages
        return sorted(list(dict(list(received_messages.items()) + list(sent_messages.items())).values()), key=lambda m: m.sent_at)


class Attachment:

    def __init__(self, attachment):
        self.name = attachment.get_filename()
        # Raw file data
        self.payload = attachment.get_payload(decode=True)
        # Filesize in kilobytes
        self.size = int(round(len(self.payload)/1000.0))

    def save(self, path=None, name=None):
        if name:
            self.name = name
        if path is None:
            # Save as name of attachment if there is no path specified
            path = self.name
        elif os.path.isdir(path):
            # If the path is a directory, save as name of attachment in that directory
            path = os.path.join(path, self.name)

        with open(path, 'wb') as f:
            f.write(self.payload)
