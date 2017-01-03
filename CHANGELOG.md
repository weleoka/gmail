* Updates January 2017

- Fields in bytestring are now returned decoded with utf-8.
This is for my own usage and I understand that email could be in other encoding.

- No time date parsing. For my usage date can just be a normal pre-formatted string from mail service provider.



* Updates December 2016*

- Ported with 2to3

- Python3 encoding and decoding utilities for the IMAP modified UTF-7 encoding.
Updated with version from: https://github.com/MarechJ/py3_imap_utf7

- In Python3 messages will be unicode (utf8) encoded by default unless the
text is passed a a bytes object (the inverse is true in Python 2)

- Change Gmail() constructor to accept imap connection instance from external source.
This is so that the module can be used, but custom logging and connection debugging cand be in place for making the imap connection.