import sys, os, dropbox, time
from datetime import datetime

APP_KEY = 'hacwza866qep9o6'
APP_SECRET = 'kgipko61g58n6uc'
DELAY = 0.2 # delay between each file (try to stay under API rate limits)


def authorize():
    flow = dropbox.client.DropboxOAuth2FlowNoRedirect(APP_KEY, APP_SECRET)
    authorize_url = flow.start()
    print('1. Go to: ' + authorize_url)
    print('2. Click "Allow" (you might have to log in first)')
    print('3. Copy the authorization code.')
    code = raw_input("Enter the authorization code here: ").strip()
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


def restore_file(client, path, cutoff_datetime, verbose=False):
    revisions = client.revisions(path)
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
        if verbose:
            print(path + ' ' + str(modtime))
        client.restore(path, rev)
    else:   # there were no revisions before the cutoff, so delete
        if verbose:
            print(path + ' DELETE')
        client.file_delete(path)


def restore_folder(client, path, cutoff_datetime, verbose=False):
    if verbose:
        print('Restoring folder: ' + path)
    folder = client.metadata(path, list=True, include_deleted=True)
    for item in folder.get('contents', []):
        if item.get('is_dir', False):
            restore_folder(client, item['path'], cutoff_datetime, verbose)
        else:
            restore_file(client, item['path'], cutoff_datetime, verbose)
        time.sleep(DELAY)


def main():
    if len(sys.argv) != 3:
        sys.exit('usage: {0} ROOTPATH YYYY-MM-DD'.format(sys.argv[0]))
    root_path, cutoff = sys.argv[1:]
    cutoff_datetime = datetime(*map(int, cutoff.split('-')))
    client = login('token.dat')
    restore_folder(client, root_path, cutoff_datetime, verbose=True)


if __name__ == '__main__':
    main()
