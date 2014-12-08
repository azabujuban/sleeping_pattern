__author__ = 'maxlevy'

from dropbox import client
import os

class DropboxHelper():

    def __init__(self):

        self.api_client = None
        try:
            access_token = 'qsEe-HKsKCEAAAAAAAAGVx_DNOVFQCrjtcsAEFNeTeenQ1NwKsis-51HZDpYjwG2'
            self.api_client = client.DropboxClient(access_token)
        except IOError:
            pass  # don't worry if it's not there

    def mirror_tlog_files(self, remote_folder, local_folder):
        """
        Copy file from Dropbox to local file and print out the metadata.

        Examples:
        Dropbox> get file.txt ~/dropbox-file.txt
        """

        local_folder = os.path.expanduser(local_folder) + '/' + remote_folder.split('/')[-1:][0]
        if not os.path.exists(local_folder):
            os.makedirs(local_folder)

        md = self.api_client.metadata(remote_folder)

        tlog_folders = [_['path'] for _ in md['contents'] if _['is_dir'] and not 'Media' in _['path']]

        for tlog_folder in tlog_folders:
            print('Checking in', tlog_folder)
            # step into that folder, adjust the local folder too
            self.mirror_tlog_files(tlog_folder, local_folder + "/" + tlog_folder.split("/")[-1:][0])

        tlog_paths = [_['path'] for _ in md['contents'] if 'TransactionLog' in _['path'][-len('TransactionLog0.tlog'):]]

        for tlog_path in tlog_paths:
            # if the size differs - copy it
            remote_size = self.api_client.metadata(tlog_path)['bytes']
            tlog_local_path = local_folder + '/' + tlog_path.split('/')[-1:][0]
            local_size = os.path.getsize(tlog_local_path) if os.path.exists(tlog_local_path) else 0

            if remote_size == local_size:
                #print('Skipping copy for ', tlog_path.split('/')[-1:][0], '- the local copy has the same size: ', tlog_local_path)
                continue

            to_file = open(tlog_local_path, "wb")

            f, metadata = self.api_client.get_file_and_metadata(tlog_path)

            print('Copying ', tlog_path.split('/')[-1:][0], ' into ', tlog_local_path)

            to_file.write(f.read())

    def do_ls(self, path):
        """list files in current remote directory"""
        resp = self.api_client.metadata(path)

        images = []

        if 'contents' in resp:
            for f in resp['contents']:
                name = os.path.basename(f['path'])

                #encoding = locale.getdefaultlocale()[1] or 'ascii'
                #self.stdout.write(('%s\n' % name).encode(encoding))

                images.append(name)

        return images

    def get_shared_url(self, file_pathname):

            url_short = self.do_share(file_pathname)
            # will get you something like https://db.tt/0By6ntxQ
            # now need to navigate there and take the real URL, someting like
            # https://www.dropbox.com/s/7m2nt9baimhejac/430D98CA-2F75-45EF-ACA1-9837992E8F8B.jpg?dl=0

            import urllib
            page = urllib.request.urlopen(url_short)
            url = page.geturl()

            # now just get rid of the ?dl=0 parameter
            from urllib.parse import urlparse
            o = urlparse(url)
            imgUrl = o.scheme + '://' + o.netloc + o.path

            return imgUrl

    def do_share(self, path):
        """Create a link to share the file at the given path."""
        return self.api_client.share(path)['url']

