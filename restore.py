#!/usr/bin/env python2.7
import sys, os, dropbox, time, argparse, json, pprint
from datetime import datetime
from functools import partial

APP_KEY = 'hacwza866qep9o6'   # INSERT APP_KEY HERE
APP_SECRET = 'kgipko61g58n6uc'     # INSERT APP_SECRET HERE
DELAY = 0.001 # delay between each file (try to stay under API rate limits)

try:
    import dropbox_restore_config
    try:
        APP_KEY = dropbox_restore_config.APP_KEY
        APP_SECRET = dropbox_restore_config.APP_SECRET
    except AttributeError:
        print('Could not load app credentials from external files. Using values from ' + sys.argv[0])
except ImportError:
    pass

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

def wait(fun, *args, **kwargs):
    global DELAY
    time.sleep(DELAY)
    done = False
    while not done:
        try:
            response = fun(*args, **kwargs)
            done = True
        except dropbox.rest.ErrorResponse as e:
            if str(e).startswith('[503]'):
                time.sleep(float(str(e).strip().split()[-1]))
                DELAY *= 1.1
            else:
                raise
    return response

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
    global args, uid
    try:
        revisions = wait(client.revisions, path.encode('utf8'))
    except dropbox.rest.ErrorResponse as e:
        print(str(e))
        return
    revision_dict = dict((parse_date(r['modified']), r) for r in revisions)
    last_revision_dict = revision_dict[ max( revision_dict.keys() ) ]
    # skip if current revision is the same as it was at the cutoff
    reason = False
    if max(revision_dict.keys()) < cutoff_datetime:
        reason = 'Not modified after restoration point'
    elif not args.allusers:
        if args.user and args.user != last_revision_dict['modifier']['email']:
            reason = 'Modified by another user: ' + last_revision_dict['modifier']['email']
        elif last_revision_dict['modifier']['uid'] != uid:
            reason = 'Modified by another user: ' + last_revision_dict['modifier']['email']
    if reason:
        if verbose:
            print(path.encode('utf8') + ' SKIP: ' + reason)
        return

    # look for the most recent revision before the cutoff
    pre_cutoff_modtimes = [d for d in revision_dict.keys()
                           if d < cutoff_datetime]
    if len(pre_cutoff_modtimes) > 0:
        modtime = max(pre_cutoff_modtimes)
        rev = revision_dict[modtime]['rev']
        if verbose:
            print(path.encode('utf8') + ' ' + str(modtime))
        if not args.do_nothing: wait(client.restore, path.encode('utf8'), rev)
    else:   # there were no revisions before the cutoff, so delete
        if args.delete and not is_deleted:
            if verbose:
                print(path.encode('utf8') + ' ' + 'DELETE')
            if not args.do_nothing: wait(client.file_delete, path.encode('utf8'))
        else:
            if verbose:
                print(path.encode('utf8') + ' ' + 'SKIP')


def restore_folder(client, path, cutoff_datetime, verbose=False):
    if verbose:
        print('Restoring folder: ' + path.encode('utf8'))
    try:
        folder = wait(client.metadata, path.encode('utf8'), list=True, include_deleted=True)
    except dropbox.rest.ErrorResponse as e:
        print(str(e))
        print(HELP_MESSAGE)
        return
    for item in folder.get('contents', []):
        if item.get('is_dir', False):
            restore_folder(client, item['path'], cutoff_datetime, verbose)
        else:
            restore_file(client, item['path'], cutoff_datetime, item.get('is_deleted', False), verbose)
        #time.sleep(DELAY)


def main():
    global uid, args
    parser = argparse.ArgumentParser()
    #parser.add_argument("-d", "--delay", help="Set a specific delay (in seconds) between calls, to stay below API rate limits.", type=float, default=False)
    parser.add_argument("--delete", help="Delete files that did not exist at the specified time.", default=False)
    parser.add_argument("-n", "--do_nothing", help="Do not apply any changes. Only show what would be done.", action="store_true")
    parser.add_argument("-g", "--allusers", help="Restore files last modified by any user (global), not just you (applies to shared resources).", action="store_true")
    parser.add_argument("-u", "--user", help="Only affect files last modified by USER (applies to shared resources).")
    parser.add_argument("cutoff", help="Restore to date formatted as: YYYY-MM-DD")
    parser.add_argument("folder", nargs='+', help="Folder(s) to restore. Can either be a local path in your Dropbox folder, or a folder relative to your Dropbox root.")
    args = parser.parse_args()
    cutoff = args.cutoff
    cutoff_datetime = datetime(*map(int, cutoff.split('-')))
    if (datetime.utcnow() - cutoff_datetime).days >= 30:
        sys.exit(HISTORY_WARNING)
    if cutoff_datetime > datetime.utcnow():
        sys.exit('Cutoff date must be in the past')
    client = login('token.dat')
    account_info = client.account_info()
    uid = account_info['uid']
    print 'Logged in as %s, uid: %s' % (account_info['email'], account_info['uid'])
    dropbox_roots = []
    try:
        for account, details in json.loads(open(os.path.expanduser('~/.dropbox/info.json')).read()).iteritems(): # Mac only
            for key, value in details.iteritems():
                if key == 'path':
                    dropbox_roots.append(os.path.realpath(value))
    except IOError:
        pass
    for root_path_encoded in args.folder:
        root_path = root_path_encoded.decode(sys.stdin.encoding)
        if os.path.exists(root_path):
            root_path = os.path.realpath(root_path)
            for dropbox_root in dropbox_roots:
                root_path = root_path.replace(dropbox_root, '')
        restore_folder(client, root_path, cutoff_datetime, verbose=True)


if __name__ == '__main__':
    main()
