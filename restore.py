#!/usr/bin/env python
import sys, os, dropbox, time
from datetime import datetime

APP_KEY = ''   # INSERT APP_KEY HERE
APP_SECRET = ''     # INSERT APP_SECRET HERE
DELAY = 0.2 # delay between each file (try to stay under API rate limits)

HELP_MESSAGE = \
"""Note: You must specify the path starting with "/", where "/" is the root
of your dropbox folder. So if your dropbox directory is at "/home/user/dropbox"
and you want to restore "/home/user/dropbox/folder", the ROOTPATH is "/folder".

When specifying the optional RESUMEPATH, restore will only start after encountering the given
RESUMEPATH. Path comparisons are case-insensitive.
"""

resume_path = ''

def authorize():
    flow = dropbox.client.DropboxOAuth2FlowNoRedirect(APP_KEY, APP_SECRET)
    authorize_url = flow.start()
    print('1. Go to: ' + authorize_url)
    print('2. Click "Allow" (you might have to log in first)')
    print('3. Copy the authorization code.')
    try:
        input = raw_input
    except NameError:
        pass
    code = input("Enter the authorization code here: ").strip()
    access_token, user_id = flow.finish(code)
    return access_token


def login(token_save_path):
    if os.path.exists(token_save_path):
        with open(token_save_path) as token_file:
            access_token = token_file.read()
    else:
        access_token = authorize()
        with open(token_save_path, 'w') as token_file:
            token_file.write(access_token)
    return dropbox.client.DropboxClient(access_token)


def parse_date(s):
    a = s.split('+')[0].strip()
    return datetime.strptime(a, '%a, %d %b %Y %H:%M:%S')


def restore_file(client, path, cutoff_datetime, is_deleted, verbose=False):
    global resume_path

    if resume_path:
        if resume_path == path.lower():
            print('Resuming at ' + path)
            resume_path = None
        else:
            print('Skipping ' + path)
            return

    revisions = client.revisions(path.encode('utf8'))
    current_rev = revisions[0]['rev']

    revision_dict = dict((parse_date(r['modified']), r) for r in revisions)

    # skip if current revision is the same as it was at the cutoff
    if max(revision_dict.keys()) < cutoff_datetime:
        if verbose:
            print(path + ' SKIP')
        return

    # look for the most recent revision before the cutoff
    pre_cutoff_modtimes = [d for d in revision_dict.keys()
                           if d < cutoff_datetime]
    if len(pre_cutoff_modtimes) > 0:
        modtime = max(pre_cutoff_modtimes)
        rev = revision_dict[modtime]['rev']
        delete = revision_dict[modtime].get('is_deleted', False)

        unchanged = rev == current_rev or delete == is_deleted

        if verbose:
            print(path + ' ' + str(modtime) + ' ' + ('unchanged' if unchanged else ''))
            # print(str(revision_dict))
        if not unchanged:
            for retry_count in range(20):
                try:
                    restore_result = client.restore(path.encode('utf8'), rev)
                    break
                except dropbox.rest.ErrorResponse as e:
                    print('Error in restore: ' + str(e))
                    if e.status == 500:
                        print('Retrying')
                        time.sleep(2)
                    else:
                        raise
            else:
                raise

            # print(str(restore_result))
    else:   # there were no revisions before the cutoff, so delete
        if verbose:
            print(path + ' ' + ('SKIP' if is_deleted else 'DELETE'))
        if not is_deleted:
            client.file_delete(path.encode('utf8'))


def restore_folder(client, path, cutoff_datetime, verbose=False):
    if verbose:
        print('Restoring folder: ' + path)
    if resume_path:
        path_lower = path.lower()
        if path_lower != resume_path[0:len(path_lower)]:
            print('Skipping folder: ' + path)
            return

    try:
        folder = client.metadata(path.encode('utf8'), list=True,
                                 include_deleted=True)
    except dropbox.rest.ErrorResponse as e:
        print(str(e))
        print(HELP_MESSAGE)
        return
    for item in folder.get('contents', []):
        if item.get('is_dir', False):
            restore_folder(client, item['path'], cutoff_datetime, verbose)
        else:
            restore_file(client, item['path'], cutoff_datetime,
                         item.get('is_deleted', False), verbose)
        time.sleep(DELAY)


def main():
    global resume_path
    if len(sys.argv) < 3:
        usage = 'usage: {0} ROOTPATH YYYY-MM-DD [RESUMEPATH]\n{1}'
        sys.exit(usage.format(sys.argv[0], HELP_MESSAGE))
    root_path_encoded, cutoff = sys.argv[1:3]
    root_path = root_path_encoded.decode(sys.stdin.encoding)
    if len(sys.argv) >= 4:
        resume_path = sys.argv[3].decode(sys.stdin.encoding).lower()
    cutoff_datetime = datetime(*map(int, cutoff.split('-')))
    client = login('token.dat')
    restore_folder(client, root_path, cutoff_datetime, verbose=True)


if __name__ == '__main__':
    main()
