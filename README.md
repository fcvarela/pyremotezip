# PyRemoteZip

PyRemoteZip is a pure python module to extract files from remote zip archives without downloading the whole zip archive.

### Usage

        from pyremotezip import RemoteZip
        rz = RemoteZip(<some_url_here>)
        toc = rz.getTableOfContents()
        
        # want file at pos 2
        output = rz.extractFile(toc[2]['filename'])

### Contributing

Have you forked and improved this? Please submit your pull requests and raise issues here!
