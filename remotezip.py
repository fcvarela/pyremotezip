# -*- coding: utf-8 -*-
# -*- Mode: Python; py-ident-offset: 4 -*-
# vim:ts=4:sw=4:et

import urllib2
from urllib2 import HTTPError
import zlib
from struct import unpack

class RemoteZip(object):
    """
    This class extracts single files from a remote ZIP file by using HTTP ranged requests
    """
    def __init__(self, zipURI):
        """
        zipURI should be an HTTP URL hosted on a server that supports ranged requests.
        The init function will determine if the file exists and raise a urllib2 exception if not.
        """
        self.filesize = None
        self.zipURI = zipURI
        self.tableOfContents = None

    def __file_exists(self):
        # check if file exists
        headRequest = urllib2.Request(self.zipURI)
        headRequest.get_method = lambda : 'HEAD'
        try:
            response = urllib2.urlopen(headRequest)
            self.filesize = int(response.info().getheader('Content-Length'))
            return True
        except HTTPError, e:
            print '%s' % e
            return False

    def getTableOfContents(self):
        """
        This function populates the internal tableOfContents list with the contents
        of the zip file TOC. If the server does not support ranged requests, this will raise
        and exception. It will also throw an exception if the TOC cannot be found.
        """

        if not self.__file_exists():
            raise FileNotFoundException()

        # now request bytes from that size minus a 64kb max zip directory length
        request = urllib2.Request(self.zipURI)
        start = self.filesize-(65536)
        end = self.filesize-1
        request.headers['Range'] = "bytes=%s-%s" % (start, end)
        handle = urllib2.urlopen(request)

        # make sure the response is ranged
        return_range = handle.headers.get('Content-Range')
        if return_range != "bytes %d-%d/%s" % (start, end, self.filesize):
            raise Exception("Ranged requests are not supported for this URI")

        # got here? we're fine, read the contents
        raw_bytes = handle.read()

        # now find the end-of-directory: 06054b50
        # we're on little endian maybe
        directory_end = raw_bytes.find("\x50\x4b\x05\x06")
        if directory_end < 0:
            raise Exception("Could not find end of directory")

        # now find the size of the directory: offset 12, 4 bytes
        directory_size = unpack("i", raw_bytes[directory_end+12:directory_end+16])[0]

        # and find the offset from start of file where it can be found
        directory_start = unpack("i", raw_bytes[directory_end+16:directory_end+20])[0]

        # find the data in the raw_bytes
        current_start = directory_start-start
        filestart = 0
        compressedsize = 0
        tableOfContents = []

        try:
            while True:
                # get file name size (n), extra len (m) and comm len (k)
                zip_n = unpack("H", raw_bytes[current_start+28:current_start+28+2])[0]
                zip_m = unpack("H", raw_bytes[current_start+30:current_start+30+2])[0]
                zip_k = unpack("H", raw_bytes[current_start+32:current_start+32+2])[0]

                filename = raw_bytes[current_start+46:current_start+46+zip_n]

                # check if this is the index file
                filestart = unpack("I", raw_bytes[current_start+42:current_start+42+4])[0]
                compressedsize = unpack("I", raw_bytes[current_start+20:current_start+20+4])[0]
                uncompressedsize = unpack("I", raw_bytes[current_start+24:current_start+24+4])[0]
                tableItem = {
                    'filename': filename,
                    'compressedsize': compressedsize,
                    'uncompressedsize': uncompressedsize,
                    'filestart': filestart
                }
                tableOfContents.append(tableItem)

                # not this file, move along
                current_start = current_start + 46+zip_n+zip_m+zip_k
        except:
            pass

        self.tableOfContents = tableOfContents
        return tableOfContents

    def extractFile(self, filename):
        """
        This function will extract a single file from the remote zip without downloading
        the entire zip file. The filename argument should match whatever is in the 'filename'
        key of the tableOfContents.
        """
        files = [x for x in self.tableOfContents if x['filename'] == filename]
        if len(files) == 0:
            raise "Could not find specified file"

        fileRecord = files[0]

        # got here? need to fetch the file size
        metaheadroom = 1024 # should be enough
        request = urllib2.Request(self.zipURI)
        end = fileRecord['filestart']+fileRecord['compressedsize']+metaheadroom
        request.headers['Range'] = "bytes=%s-%s" % (fileRecord['filestart'], end)
        handle = urllib2.urlopen(request)
        filedata = handle.read()

        # find start of raw file data
        zip_n = unpack("H", filedata[26:28])[0]
        zip_m = unpack("H", filedata[28:30])[0]

        # check compressed size
        comp_size = unpack("I", filedata[18:22])[0]
        if comp_size != fileRecord['compressedsize']:
            raise Exception("Something went wrong. Directory and file header disagree of compressed file size")

        raw_zip_data = filedata[30+zip_n+zip_m:30+zip_n+zip_m+comp_size]
        uncompressed_data = ""

        dec = zlib.decompressobj(-zlib.MAX_WBITS)
        for chunk in raw_zip_data:
            rv = dec.decompress(chunk)
            if rv:
                uncompressed_data = uncompressed_data + rv

        return uncompressed_data


class FileNotFoundException(Exception):
    pass
