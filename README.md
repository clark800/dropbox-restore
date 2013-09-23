dropbox-restore
===============

Restore any dropbox folder to a previous state. If a file did not exist at the specified time,
it will be deleted.


Example
-------
To restore the folder "/photos/nyc" to the way it was on March 9th, 2013:

    python2.7 restore.py /photos/nyc 2013-03-09
    
Note that the path "/photos/nyc" should be relative to your Dropbox folder; it should not include the path to
the Dropbox folder on your hard drive.
You will be prompted to confirm access to your Dropbox account through your web browser.

Installation
------------
First make sure that Python 2.7 and pip are installed. Then install the Dropbox Python API with the 
following command.

    pip install dropbox
