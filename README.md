dropbox-restore
===============

Restore any dropbox folder to a previous state. If a file did not exist at the specified time, it will be deleted.

Example
-------
To restore the folder "/photos/nyc" to the way it was on March 9th, 2013:

    python2.7 restore.py /photos/nyc 2013-03-09
    
Note that the path "/photos/nyc" should be relative to your Dropbox folder; it should not include the path to the Dropbox folder on your hard drive. You will be prompted to confirm access to your Dropbox account through your web browser.

Installation
------------
1. First make sure that Python 2.7 and pip are installed. 
2. Then install the Dropbox Python API with the following command.

    sudo pip install dropbox

3. Download restore.py from Github

Forking
-------
If you fork this project, you must obtain your own API keys from Dropbox and insert them into the APP\_KEY and APP\_SECRET fields.

Time
----
Specifying a time is not officially supported because the time zone is ignored currently. However, it seems like Dropbox always uses UTC, so you can try specifying UTC times at your own risk by specifying the date and time in the format YYYY-MM-DD-HH-MM-SS on the command line. Be warned that Dropbox's documentation does not guarantee that they will always use UTC, so this can break at any time.

Donations
---------
If you would like to make a donation, you can use the PayPal button on my website: http://cclark.me
