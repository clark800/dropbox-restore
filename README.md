dropbox-restore
===============

Restore any dropbox folder to a previous state. If a file did not exist at the specified time,
then no action will be taken for that file (files are not deleted automatically). To obtain the
exact previous state with no newer files, you can first backup and delete the directory before
running the script.

Example
-------
To restore the folder "/photos/nyc" to the way it was on March 9th, 2013:

    python2.7 restore.py /photos/nyc 2013-03-09
    
You will be prompted to confirm access to your Dropbox account through your web browser.

Installation
------------
First make sure that Python 2.7 and pip are installed. Then install the Dropbox Python API with the 
following command.

    pip install dropbox
