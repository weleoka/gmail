* Updates December 2016*

- Ported with 2to3

- Python3 encoding and decoding utilities for the IMAP modified UTF-7 encoding.
Updated with version from: https://github.com/MarechJ/py3_imap_utf7

- Change Gmail() constructor to accept imap connection instance from external source.
This is so that the module can be used, but custom logging and connection debugging cand be in place for making the imap connection.