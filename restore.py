#!/usr/bin/env python2.7
import sys, os, dropbox, time, argparse, json, requests, math, codecs
from pprint import pprint
from datetime import datetime
from functools import partial


APP_KEY = 'hacwza866qep9o6'   # INSERT APP_KEY HERE
APP_SECRET = 'kgipko61g58n6uc'     # INSERT APP_SECRET HERE
DELAY = 0.001 # delay between each file (try to stay under API rate limits)
API_RETRY_DELAY = 1
API_RETRY_MAX = 3

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

def human_time(seconds):
    time_string = ''
    seconds_left = seconds

    day = ( 24 * 60 * 60 )
    days = math.floor(seconds_left / day)
    seconds_left = seconds_left - (days * day)
    if days == 1:
        time_string += '1 day, '
    elif days > 1:
        time_string += '%i days, ' % days

    hour = ( 60 * 60 )
    hours = math.floor(seconds_left / hour)
    seconds_left = seconds_left - (hours * hour)
    if hours == 1:
        time_string += '1 hour, '
    elif hours > 1:
        time_string += '%i hours, ' % hours

    minute = 60
    minutes = math.floor(seconds_left / minute)
    seconds_left = seconds_left - (minutes * minute)
    if minutes == 1:
        time_string += '1 minute, '
    elif minutes > 1:
        time_string += '%i minutes ' % minutes

    if time_string != '':
        time_string += 'and '

    time_string += '%i seconds' % seconds_left
    return time_string

def api_call(fun, *args, **kwargs):
    global DELAY, API_RETRY_DELAY, API_RETRY_MAX
    attempt = 0
    time.sleep(DELAY)
    while attempt < API_RETRY_MAX:
        attempt += 1
        try:
            response = fun(*args, **kwargs)
            done = True
        except dropbox.exceptions.InternalServerError as e:
            request_id, status_code, body = e
            if attempt >= API_RETRY_MAX:
                print(  'There is an issue with the Dropbox server. Aborted after %i attempts.' % attempt )
                print( repr(fun) )
                print( repr(args) )
                print( repr(kwargs) )
                print( str(e) )
                raise
            time.sleep(API_RETRY_DELAY)
        except requests.exceptions.ReadTimeout as e:
            if attempt >= API_RETRY_MAX:
                print(   'Could not receive data from server. Aborted after %i attempts.' % attempt )
                print( repr(fun) )
                print( repr(args) )
                print( repr(kwargs) )
                print( str(e) )
                raise
            time.sleep(API_RETRY_DELAY)
        except requests.exceptions.ConnectionError as e:
            if attempt >= API_RETRY_MAX:
                print(   'Connection error. Aborted after %i attempts.' % attempt )
                print( repr(fun) )
                print( repr(args) )
                print( repr(kwargs) )
                print( str(e) )
                raise
            time.sleep(API_RETRY_DELAY)
        except dropbox.exceptions.RateLimitError as e:
            request_id, error, backoff = e
            time.sleep(backoff)
            DELAY *= 1.1
            if attempt >= API_RETRY_MAX:
                print(   'Rate limit error. Aborted after %i attempts.' % attempt )
                print( repr(fun) )
                print( repr(args) )
                print( repr(kwargs) )
                print( str(e) )
                raise
        # except dropbox.exceptions.ApiError as e:
        #     raise
        except:
            raise
    return response

def authorize():
    print(    'New Dropbox API token is required' )
    APP_KEY = raw_input('App key: ')
    APP_SECRET = raw_input('App secret: ')
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
    return dropbox.Dropbox(access_token)

def parse_date(s):
    a = s.split('+')[0].strip()
    return datetime.strptime(a, '%a, %d %b %Y %H:%M:%S')

def sort_deleted_first(item):
    return type(item) != dropbox.files.DeletedMetadata

def restore_folder(dbx, path, cutoff_datetime, verbose=True, job_path=False, skip_nondeleted=False):
    remote_folder_notrail = path.rstrip(u'/')
    remote_folder = remote_folder_notrail + u'/'
    print(u'Reading folder: ' + remote_folder.encode('utf8'))
    try:
        remote_list_part = api_call(dbx.files_list_folder, remote_folder_notrail, recursive=True, include_deleted=True)
    except dropbox.rest.ErrorResponse as e:
        print(str(e))
        print(HELP_MESSAGE)
        return
    remote_list = remote_list_part.entries
    while remote_list_part.has_more:
        print '\rItems found: %i' % len(remote_list),
        sys.stdout.flush()
        try:
            remote_list_part = api_call(dbx.files_list_folder_continue, remote_list_part.cursor)
        except dropbox.rest.ErrorResponse as e:
            print(str(e))
            print(HELP_MESSAGE)
            return
        remote_list += remote_list_part.entries
        #print pprint(remote_list)
    checked_files = []
    if job_path and os.path.isfile(job_path):
        with codecs.open(job_path,encoding='utf8') as f:
            checked_files = f.read().splitlines()
    timers = [time.time()]
    time_start = time.time()
    remote_paths = []
    remote_list_length = len(remote_list)
    remote_item_i = 0
    for item in sorted(remote_list, key=sort_deleted_first):
        remote_item_i += 1
        remote_path = item.path_lower
        timers = timers[-9:] + [time.time()]
        if remote_path in checked_files:
            continue
        progress = float(remote_item_i) / float(remote_list_length)
        time_pr_item = (timers[-1] - timers[0]) / float(len(timers))
        time_left = ( remote_list_length - remote_item_i ) * time_pr_item
        #print repr(timers)
        print "\n%i / %i %5.2f%% ETL: %s" % ( remote_item_i, remote_list_length, progress * 100.0, human_time(time_left)),
        print remote_path,
        is_folder = type(item) == dropbox.files.FolderMetadata
        is_deleted = type(item) == dropbox.files.DeletedMetadata
        if skip_nondeleted and not is_deleted:
            continue
        # if is_deleted:
        #     print repr(item)
        if not is_folder:
            try:
                revisions = api_call(dbx.files_list_revisions, remote_path, limit=10)
            except dropbox.exceptions.ApiError as e:
                #pprint(dir(e))
                #pprint(dir(e.error))
                if is_deleted and 'not_file' in str(e.error): # Is deleted folder, skip
                    is_folder = True
            except dropbox.exceptions.InternalServerError as e:
                print str(e),
                continue
        if not is_folder:
            #print u'Revisions of ' + remote_path
            #current_rev = item.rev
            last_rev = None
            for revision in revisions.entries:
                revision.server_modified = revision.server_modified
                if last_rev == None or revision.server_modified > last_rev.server_modified:
                    last_rev = revision
            if last_rev != None and last_rev.server_modified > cutoff_datetime:
                if is_deleted:
                    print '[RD]',
                    restored = api_call(dbx.files_restore, remote_path, last_rev.rev)
                    #print repr(restored)
                elif item.rev != last_rev.rev:
                    print '[RL]',
                    #restored = api_call(dbx.files_restore, remote_path, last_rev.rev)
                    #print repr(restored)
                #print 'Last revision is < cutoff'
        if job_path:
            codecs.open(job_path, 'a',encoding='utf8').write(remote_path+u'\n')
                            
                


        # if is_deleted:
        #     remote_paths.append(remote_path)
    # for remote_path in sorted(remote_paths_sorted):
    #     print remote_path.encode('utf8')
        #print remote_path.encode('utf8')
    # for item in folder.get('contents', []):
    #     if item.get('is_dir', False):
    #         restore_folder(client, item['path'], cutoff_datetime, verbose)
    #     else:
    #         restore_file(client, item['path'], cutoff_datetime, item.get('is_deleted', False), verbose)
        #time.sleep(DELAY)


def main():
    global uid, args
    parser = argparse.ArgumentParser()
    parser.add_argument("-j", "--job", help="Log checked files to this file, and skip previously checked files.")
    parser.add_argument("-u", "--undelete", help="Only recover deleted files. Skips revision check for non-deleted files.")
    parser.add_argument("cutoff", help="Restore to date formatted as: YYYY-MM-DD")
    parser.add_argument("folder", nargs='*', help="Folder(s) to restore. Can either be a local path in your Dropbox folder, or a folder relative to your Dropbox root.", default=[''])
    args = parser.parse_args()
    cutoff = args.cutoff
    cutoff_datetime = datetime(*map(int, cutoff.split('-')))
    if (datetime.utcnow() - cutoff_datetime).days >= 30:
        sys.exit(HISTORY_WARNING)
    if cutoff_datetime > datetime.utcnow():
        sys.exit('Cutoff date must be in the past')
    job_path = args.job
    skip_nondeleted = args.undelete
    dbx = login('token.dat')
    account_info = dbx.users_get_current_account()
    uid = account_info.account_id
    print 'Logged in as %s, uid: %s' % (account_info.email, uid)
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
        if os.path.exists(root_path) and len(dropbox_roots) > 0:
            root_path = os.path.realpath(root_path)
            for dropbox_root in dropbox_roots:
                root_path = root_path.replace(dropbox_root, '')
        restore_folder(dbx, root_path, cutoff_datetime, verbose=True, job_path=job_path, skip_nondeleted=skip_nondeleted)


if __name__ == '__main__':
    main()
