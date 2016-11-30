import urllib2
import zlib

from urllib2 import HTTPError
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
        self.request = None
        self.start = None
        self.end = None
        self.directory_end = None
        self.raw_bytes = None
        self.directory_size = None


    def __file_exists(self):
        # check if file exists
        headRequest = urllib2.Request(self.zipURI)
        headRequest.get_method = lambda: 'HEAD'
        try:
            response = urllib2.urlopen(headRequest)
            self.filesize = int(response.info().getheader('Content-Length'))
            return True
        except HTTPError as e:
            print '%s' % e
            return False

    def getDirectorySize(self):
        if not self.__file_exists():
            raise FileNotFoundException()

        # now request bytes from that size minus a 64kb max zip directory length
        self.request = urllib2.Request(self.zipURI)
        self.start = self.filesize - (65536)
        self.end = self.filesize - 1
        self.request.headers['Range'] = "bytes=%s-%s" % (self.start, self.end)
        handle = urllib2.urlopen(self.request)

        # make sure the response is ranged
        return_range = handle.headers.get('Content-Range')
        if return_range != "bytes %d-%d/%s" % (self.start, self.end, self.filesize):
            raise Exception("Ranged requests are not supported for this URI")

        # got here? we're fine, read the contents
        self.raw_bytes = handle.read()

        # now find the end-of-directory: 06054b50
        # we're on little endian maybe
        self.directory_end = self.raw_bytes.find("\x50\x4b\x05\x06")
        if self.directory_end < 0:
            raise Exception("Could not find end of directory")

        # now find the size of the directory: offset 12, 4 bytes
        self.directory_size = unpack("i", self.raw_bytes[self.directory_end+12:self.directory_end+16])[0]

        return self.directory_size

    def requestContentDirectory(self):
        self.start = self.filesize - self.directory_size
        self.end = self.filesize - 1
        self.request.headers['Range'] = "bytes=%s-%s" % (self.start, self.end)
        handle = urllib2.urlopen(self.request)

        # make sure the response is ranged
        return_range = handle.headers.get('Content-Range')
        if return_range != "bytes %d-%d/%s" % (self.start, self.end, self.filesize):
            raise Exception("Ranged requests are not supported for this URI")

        # got here? we're fine, read the contents
        self.raw_bytes = handle.read()
        self.directory_end = self.raw_bytes.find("\x50\x4b\x05\x06")


    def getTableOfContents(self):
        """
        This function populates the internal tableOfContents list with the contents
        of the zip file TOC. If the server does not support ranged requests, this will raise
        and exception. It will also throw an exception if the TOC cannot be found.
        """

        self.directory_size = self.getDirectorySize()
        if self.directory_size > 65536:
            self.directory_size += 2
            self.requestContentDirectory()


        # and find the offset from start of file where it can be found
        directory_start = unpack("i", self.raw_bytes[self.directory_end + 16: self.directory_end + 20])[0]

        # find the data in the raw_bytes
        self.raw_bytes = self.raw_bytes
        current_start = directory_start - self.start
        filestart = 0
        compressedsize = 0
        tableOfContents = []

        try:
            while True:
                # get file name size (n), extra len (m) and comm len (k)
                zip_n = unpack("H", self.raw_bytes[current_start + 28: current_start + 28 + 2])[0]
                zip_m = unpack("H", self.raw_bytes[current_start + 30: current_start + 30 + 2])[0]
                zip_k = unpack("H", self.raw_bytes[current_start + 32: current_start + 32 + 2])[0]

                filename = self.raw_bytes[current_start + 46: current_start + 46 + zip_n]

                # check if this is the index file
                filestart = unpack("I", self.raw_bytes[current_start + 42: current_start + 42 + 4])[0]
                compressedsize = unpack("I", self.raw_bytes[current_start + 20: current_start + 20 + 4])[0]
                uncompressedsize = unpack("I", self.raw_bytes[current_start + 24: current_start + 24 + 4])[0]
                tableItem = {
                    'filename': filename,
                    'compressedsize': compressedsize,
                    'uncompressedsize': uncompressedsize,
                    'filestart': filestart
                }
                tableOfContents.append(tableItem)

                # not this file, move along
                current_start = current_start + 46 + zip_n + zip_m + zip_k
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
            raise FileNotFoundException()

        fileRecord = files[0]

        # got here? need to fetch the file size
        metaheadroom = 1024  # should be enough
        request = urllib2.Request(self.zipURI)
        start = fileRecord['filestart']
        end = fileRecord['filestart'] + fileRecord['compressedsize'] + metaheadroom
        request.headers['Range'] = "bytes=%s-%s" % (start, end)
        handle = urllib2.urlopen(request)

        # make sure the response is ranged
        return_range = handle.headers.get('Content-Range')
        if return_range != "bytes %d-%d/%s" % (start, end, self.filesize):
            raise Exception("Ranged requests are not supported for this URI")

        filedata = handle.read()

        # find start of raw file data
        zip_n = unpack("H", filedata[26:28])[0]
        zip_m = unpack("H", filedata[28:30])[0]

        # check compressed size
        has_data_descriptor = bool(unpack("H", filedata[6:8])[0] & 8)
        comp_size = unpack("I", filedata[18:22])[0]
        if comp_size == 0 and has_data_descriptor:
            # assume compressed size in the Central Directory is correct
            comp_size = fileRecord['compressedsize']
        elif comp_size != fileRecord['compressedsize']:
            raise Exception("Something went wrong. Directory and file header disagree of compressed file size")

        raw_zip_data = filedata[30 + zip_n + zip_m: 30 + zip_n + zip_m + comp_size]
        uncompressed_data = ""
        
        # can't decompress if stored without compression
        compression_method = unpack("H", filedata[8:10])[0]
        if compression_method == 0:
          return raw_zip_data

        dec = zlib.decompressobj(-zlib.MAX_WBITS)
        for chunk in raw_zip_data:
            rv = dec.decompress(chunk)
            if rv:
                uncompressed_data = uncompressed_data + rv

        return uncompressed_data


class FileNotFoundException(Exception):
    pass