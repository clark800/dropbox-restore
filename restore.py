#!/usr/bin/env python
import sys, os, dropbox, time
from datetime import datetime

APP_KEY = 'hacwza866qep9o6'   # INSERT APP_KEY HERE
APP_SECRET = 'kgipko61g58n6uc'     # INSERT APP_SECRET HERE
DELAY = 0.2 # delay between each file (try to stay under API rate limits)

HELP_MESSAGE = \
"""Note: You must specify the path starting with "/", where "/" is the root
of your dropbox folder. So if your dropbox directory is at "/home/user/dropbox"
and you want to restore "/home/user/dropbox/folder", the ROOTPATH is "/folder".
"""

HISTORY_WARNING = \
"""Dropbox only keeps historical file versions for 30 days (unless you have
enabled extended version history). Please specify a cutoff date within the past
30 days, or if you have extended version history, you may remove this check
from the source code."""

def authorize():
    flow = dropbox.DropboxOAuth2FlowNoRedirect(APP_KEY, APP_SECRET)
    authorize_url = flow.start()
    print('1. Go to: ' + authorize_url)
    print('2. Click "Allow" (you might have to log in first)')
    print('3. Copy the authorization code.')
    try:
        input = raw_input
    except NameError:
        pass
    code = input("Enter the authorization code here: ").strip()
    return  flow.finish(code).access_token


def login(token_save_path):
    if os.path.exists(token_save_path):
        with open(token_save_path) as token_file:
            access_token = token_file.read()
    else:
        access_token = authorize()
        with open(token_save_path, 'w') as token_file:
            token_file.write(access_token)
    return dropbox.Dropbox(access_token)


def parse_date(s):
    a = s.split('+')[0].strip()
    return datetime.strptime(a, '%a, %d %b %Y %H:%M:%S')


def restore_file(client, path, cutoff_datetime, is_deleted, verbose=False):
    revisions = client.files_list_revisions(path.encode('utf8'))
    revision_dict = dict((r.server_modified, r) for r in revisions.entries)

    # skip if current revision is the same as it was at the cutoff
    if max(revision_dict.keys()) < cutoff_datetime:
        if verbose:
            print(path.encode('utf8') + ' SKIP')
        return

    # look for the most recent revision before the cutoff
    pre_cutoff_modtimes = [d for d in revision_dict.keys()
                           if d < cutoff_datetime]
    if len(pre_cutoff_modtimes) > 0:
        modtime = max(pre_cutoff_modtimes)
        rev = revision_dict[modtime].rev
        if verbose:
            print(path.encode('utf8') + ' ' + str(modtime))
        client.files_restore(path.encode('utf8'), rev)
    else:   # there were no revisions before the cutoff, so delete
        if verbose:
            print(path.encode('utf8') + ' ' + ('SKIP' if is_deleted else 'DELETE'))
        # TODO: Restore functionality whereby a file that didn't exist at that
        # point in time will get deleted.
        #if not is_deleted:
        #    client.file_delete(path.encode('utf8'))


def restore_folder(client, path, cutoff_datetime, verbose=False):
    if verbose:
        print('Restoring folder: ' + path.encode('utf8'))
    try:
        folder = client.files_list_folder(path.encode('utf8'),
                                          include_deleted=True)
    except dropbox.exceptions.ApiError as e:
        print(str(e))
        print(HELP_MESSAGE)
        return
    for item in folder.entries:
        if isinstance(item, dropbox.files.FolderMetadata):
            restore_folder(client, item.path_lower, cutoff_datetime, verbose)
        else:
            # TODO: Restore functionality whereby a file that didn't exist at that
            # point in time will get deleted.
            restore_file(client, item.path_lower, cutoff_datetime,
                         False, verbose)
        time.sleep(DELAY)


def main():
    if len(sys.argv) != 3:
        usage = 'usage: {0} ROOTPATH YYYY-MM-DD\n{1}'
        sys.exit(usage.format(sys.argv[0], HELP_MESSAGE))
    root_path_encoded, cutoff = sys.argv[1:]
    root_path = root_path_encoded.decode(sys.stdin.encoding)
    cutoff_datetime = datetime(*map(int, cutoff.split('-')))
    if (datetime.utcnow() - cutoff_datetime).days >= 30:
        sys.exit(HISTORY_WARNING)
    if cutoff_datetime > datetime.utcnow():
        sys.exit('Cutoff date must be in the past')
    client = login('token.dat')
    restore_folder(client, root_path, cutoff_datetime, verbose=True)


if __name__ == '__main__':
    main()
