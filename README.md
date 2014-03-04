# PyRemoteZip

### License: BSD

PyRemoteZip is a pure python module to extract files from remote zip archives without downloading the whole zip archive.

### Usage

        from pyremotezip import remotezip.RemoteZip
        rz = RemoteZip(<some_url_here>)
        toc = rz.getTableOfContents()
        
        # want file at pos 2
        output = rz.extractFile(toc[0]['filename'])
