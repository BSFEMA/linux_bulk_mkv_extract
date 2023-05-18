# Linux Bulk MKV Extract
A bulk MKV extract utility for Linux using Python and GTK+

## Purpose:
I wanted to re-make my original [mkv_extractor](https://github.com/BSFEMA/mkv_extractor) python application to have a proper GUI.   I couldn't find a good mkvextract frontend for Linux, so I decided to make my own. This currently exports all tracks (audio, video, subtitles) as well as chapters and attachments. I have never used mkv [tags, CUE sheets, timestamps, cues], so I'm not going to bother with them here.

## Functionality:
* Point it at a folder and it will display for every .mkv file in that folder the following:
  * file name
  * video tracks
  * audio tracks
  * subtitle tracks
  * chapters
  * attachments
* Next, choose the output type:
  * Execute Commands:  Runs the commands on all mkv files
  * Output Commands:  Gives you the command lines to run in a terminal.
* Next, choose what to extract:
  * Everything
  * Tracks (Video + Audio + Subtitles)
  * Video
  * Audio
  * Subtitles
  * Chapters
  * Attachments 
* Next, click the Process Files button.
* HINT:  I recommend my own [Linux File Rename Utility](https://github.com/BSFEMA/linux_file_rename_utility) for bulk renaming of files in Linux! 

## Author:
BSFEMA

## Started:
2023-05-15

## Screenshot:
![screenshot](https://github.com/BSFEMA/linux_bulk_mkv_extract/raw/master/screenshot.png)

## Prerequisites:
You need to have MKVToolNix installed:  https://mkvtoolnix.download/downloads.html  Try running "mkvmerge --version" in terminal.  If that works, then you are good to go, otherwise install MKVToolNix

## Command Line Parameters:
There is just 1.  It is the folder path that will be used to start looking at the *.mkv files from.  If this value isn't provided, then the starting path will be where this application file is located.  The intention is that you can call this application from a context menu from a file browser (e.g. Nemo) and it would automatically load up that folder.

## Nemo Action:

You can create a nemo action file so that you can right-click in a folder and launch the linux_bulk_mkv_extract.py application from there.

Example (filename = "linux_bulk_mkv_extract.nemo_action") 

    [Nemo Action]
    Name=Linux Bulk MKV Extract
    Quote=double
    Exec=python3 "[PATH_TO]/linux_bulk_mkv_extract.py" %F
    Selection=any
    Extensions=any
    Icon-Name=python3

Save the "linux_bulk_mkv_extract.nemo_action" file to "~/.local/share/nemo/actions".

Context menus might be possible for other file managers, but that will be up to you to figure out ;)

## Resources:
https://mkvtoolnix.download/doc/mkvextract.html