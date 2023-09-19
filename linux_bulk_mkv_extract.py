#!/usr/bin/python3


"""
Application:  linux_bulk_mkv_extract.py
Author:  BSFEMA
Started:  2023-05-15
Prerequisites:  You need to have MKVToolNix installed:  https://mkvtoolnix.download/downloads.html
                Try running "mkvmerge --version" in terminal
                If that works, then you are good to go, otherwise install MKVToolNix
Command Line Parameters:  There is just 1:
                          It is the folder path that will be used to start looking at the *.mkv files from.
                          If this value isn't provided, then the starting path will be where this application file is located.
                          The intention is that you can call this application from a context menu from a file browser (e.g. Nemo) and it would automatically load up that folder.
Purpose:  I wanted to re-make my original [mkv_extractor](https://github.com/BSFEMA/mkv_extractor) python application to have a proper GUI.
          I couldn't find a good mkvextract frontend for Linux, so I decided to make my own.
          This currently exports all tracks (audio, video, subtitles) as well as chapters and attachments.
          I have never used mkv [tags, CUE sheets, timestamps, cues], so I'm not going to bother with them here.
Resources:  https://mkvtoolnix.download/doc/mkvpropedit.html
            https://docs.gtk.org/Pango/pango_markup.html
"""


import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk
from gi.repository import Gdk as gdk
import sys
import os
import re
import datetime
from operator import itemgetter
import subprocess
import json


default_folder_path = ""  # The path for the filechooser and data grid to work against.  This is the base folder to work against.
files_Full = []  # Holds all of the file information
files = []  # Holds only the file information for displaying in the data grid
konami_code = []  # Easter Egg to see if the Konami code has been entered in the About dialog.
languages_audio = []  # Holds the unique audio languages
languages_subtitle = []  # Holds the unique subtitle languages
languages_video = []  # Holds the unique subtitle languages
types_audio = []  # Holds the unique audio types (codex)
types_subtitle = []  # Holds the unique subtitle types (codex)
types_video = []  # Holds the unique subtitle types (codex)
ids_audio = []  # Holds the unique audio IDs
ids_subtitle = []  # Holds the unique subtitle ids
ids_video = []  # Holds the unique subtitle ids
command_lines = {}  # The full list of command lines, or the output of this application
output = ""  # The output of the command lines
multi_lines = False


class Main():
    def __init__(self):
        global multi_lines
        # Setup Glade Gtk
        self.builder = gtk.Builder()
        self.builder.add_from_file(os.path.join(sys.path[0], "linux_bulk_mkv_extract.glade"))  # Looking where the python script is located
        self.builder.connect_signals(self)
        # Get UI components
        window = self.builder.get_object("main_Window")
        window.connect("delete-event", gtk.main_quit)
        window.set_title('Linux Bulk MKV Extract')
        window.set_default_icon_from_file(os.path.join(sys.path[0], "linux_bulk_mkv_extract.svg"))  # Setting the "default" icon makes it usable in the about dialog. (This will take .ico, .png, and .svg images.)
        # Set the default size of the window
        window.resize(1140, 554)
        # Set the default data grid height (400)
        self.set_scrollwindow_Data_Grid_height(400)
        window.show()
        window.show_all()
        # This allows the use css styling
        provider = gtk.CssProvider()
        provider.load_from_path(os.path.join(sys.path[0], "linux_bulk_mkv_extract.css"))  # Looking where the python script is located
        gtk.StyleContext().add_provider_for_screen(gdk.Screen.get_default(), provider, gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        # Set initial_load to True so that the data grid doesn't refresh multiple times when various settings are being initialized
        self.initial_load = True
        # Set filechooser_Folder_Selecter and entry_Folder_path values to the default_folder_path
        filechooser_Folder_Selecter = self.builder.get_object("filechooser_Folder_Selecter")
        filechooser_Folder_Selecter.set_current_folder(default_folder_path)
        entry_Folder_path = self.builder.get_object("entry_Folder_path")
        entry_Folder_path.set_text(default_folder_path)
        # Set various objects to their defaults:
        button_Multi = self.builder.get_object("button_Multi")
        button_Multi.set_active(1)
        multi_lines = button_Multi.get_active()
        # Set the alignment of the Audio and Subtite data grid colums
        cellrenderer_Subtitles = self.builder.get_object("cellrenderer_Subtitles")
        cellrenderer_Audio = self.builder.get_object("cellrenderer_Audio")
        cellrenderer_Video = self.builder.get_object("cellrenderer_Video")
        cellrenderer_Attachments = self.builder.get_object("cellrenderer_Attachments")
        # alignment: (X/Horizontal, Y/Vertical)  [values 0.0-1.0]
        # (0,0) = Left, Top
        # (0,1) = Left, Bottom
        # (1,0) = Right, Top
        # (1,1) = Right, Botton
        cellrenderer_Subtitles.set_alignment(0, 0)
        cellrenderer_Audio.set_alignment(0, 0)
        cellrenderer_Video.set_alignment(0, 0)
        cellrenderer_Attachments.set_alignment(0, 0)
        # Set the button_Process image
        button_Process = self.builder.get_object("button_Process")
        button_Process.set_always_show_image(True)
        self.button_Process_image = gtk.Image()
        self.button_Process_image.set_from_file(os.path.join(sys.path[0], "linux_bulk_mkv_extract.svg"))
        self.button_Process_image.get_style_context().add_class('spinner')
        button_Process.set_image(self.button_Process_image)
        button_Process.set_image_position(gtk.PositionType.TOP)
        # Set combo_Title_Option to default value (i.e. 'Everything')
        combo_Option = self.builder.get_object("combo_Option")
        combo_Option.set_entry_text_column(0)
        combo_Option.set_active(0)
        # Set initial_load to False as the application settings should now be setup correctly
        self.initial_load = False
        self.repaint_GUI()  # Make sure GUI is up to date
        watch_cursor = gdk.Cursor(gdk.CursorType.WATCH)
        window.get_window().set_cursor(watch_cursor)  # Set curror to 'Waiting'
        self.repaint_GUI()  # Make sure GUI is up to date
        # Setup the data grid
        self.clear_Data_Grid()
        populate_files_Full()
        self.load_Data_Grid()
        self.resize_column_widths()
        self.repaint_GUI()  # Make sure GUI is up to date
        window.get_window().set_cursor(None)  # Set curror back to 'None'
        self.repaint_GUI()  # Make sure GUI is up to date

    """ ************************************************************************************************************ """
    #  These are the various widget's signal handler functions:  UI elements other than buttons & dialogs
    """ ************************************************************************************************************ """

    def repaint_GUI(self):
        # Defect #2 - Implement a waiting cursor to give an indication when the data grid is taking a long time to load.
        # Unfortunately, I haven't found an easier/better way to implement this...
        while gtk.events_pending():
            gtk.main_iteration_do(False)

    def filechooser_Folder_Selecter_fileset(self, widget):
        entry_Folder_path = self.builder.get_object("entry_Folder_path")
        entry_Folder_path.set_text(widget.get_filename())

    def entry_Folder_Path_changed(self, widget):
        if not self.initial_load:
            self.repaint_GUI()  # Make sure GUI is up to date
            window = self.builder.get_object("main_Window")
            watch_cursor = gdk.Cursor(gdk.CursorType.WATCH)
            window.get_window().set_cursor(watch_cursor)  # Set curror to 'Waiting'
            self.repaint_GUI()  # Make sure GUI is up to date
            current_path = widget.get_text()
            if os.path.isdir(current_path):
                widget.get_style_context().remove_class('red-foreground')
                # widget.get_style_context().add_class('black-foreground')
                # Reload the data grid now that a new (real) folder is selected
                global default_folder_path
                if current_path[-1:] == "/":  # remove the final "/" from a path
                    current_path = current_path[:-1]
                default_folder_path = current_path  # Now that the edited text is a folder, set the default_folder_path to use that
                self.clear_Data_Grid()
                populate_files_Full()
                self.load_Data_Grid()
                self.resize_column_widths()
            else:
                # widget.get_style_context().remove_class('black-foreground')
                widget.get_style_context().add_class('red-foreground')
            self.repaint_GUI()  # Make sure GUI is up to date
            window.get_window().set_cursor(None)  # Set curror back to 'None'
            self.repaint_GUI()  # Make sure GUI is up to date

    def set_scrollwindow_Data_Grid_height(self, new_height):  # Set the height of the data grid
        scrollwindow_Data_Grid = self.builder.get_object("scrollwindow_Data_Grid")
        if int(new_height) >= 0:
            scrollwindow_Data_Grid.set_size_request(scrollwindow_Data_Grid.get_allocated_width(), int(new_height))
        else:
            scrollwindow_Data_Grid.set_size_request(scrollwindow_Data_Grid.get_allocated_width(), 400)  # Default is 400

    """ ************************************************************************************************************ """
    #  These are the various widget's signal handler functions:  UI elements that are buttons & dialogs
    """ ************************************************************************************************************ """

    def button_Multi_toggled(self, widget):
        global multi_lines
        button_Multi = self.builder.get_object("button_Multi")
        multi_lines = button_Multi.get_active()
        populate_files_Full()
        self.button_Refresh_clicked(self)

    def button_Process_clicked(self, widget):
        global default_folder_path
        global files_Full
        global command_lines
        combo_Option = self.builder.get_object("combo_Option")
        entry_Audio_Languages = self.builder.get_object("entry_Audio_Languages")
        entry_Audio_Name = self.builder.get_object("entry_Audio_Name")
        entry_Audio_Types = self.builder.get_object("entry_Audio_Types")
        entry_Subtitles_Languages = self.builder.get_object("entry_Subtitles_Languages")
        entry_Subtitles_Name = self.builder.get_object("entry_Subtitles_Name")
        entry_Subtitles_Types = self.builder.get_object("entry_Subtitles_Types")
        entry_IDs_Audio = self.builder.get_object("entry_IDs_Audio")
        entry_IDs_Subtitles = self.builder.get_object("entry_IDs_Subtitles")
        command_lines.clear()
        command_lines = {}
        ################################################################################
        options = ""
        action = combo_Option.get_active()
        for i in range(len(files_Full)):
            options = ""
            if action == 0:  # Everything
                options = " tracks "
                options = options + export_all_videos(files_Full[i])
                options = options + export_all_audios(files_Full[i])
                options = options + export_all_subtitles(files_Full[i])
                options = options + export_chapters(files_Full[i])
                options = options + export_all_attachments(files_Full[i])
            elif action == 1:  # Tracks (audio + video + subtitles)
                options = " tracks "
                options = options + export_all_videos(files_Full[i])
                options = options + export_all_audios(files_Full[i])
                options = options + export_all_subtitles(files_Full[i])
            elif action == 2:  # Video
                options = " tracks "
                options = options + export_all_videos(files_Full[i])
            elif action == 3:  # Audio
                options = " tracks "
                options = options + export_all_audios(files_Full[i])
            elif action == 4:  # Subtitles
                options = " tracks "
                options = options + export_all_subtitles(files_Full[i])
            elif action == 5:  # Chapters
                options = options + export_chapters(files_Full[i])
            elif action == 6:  # Attachments
                options = options + export_all_attachments(files_Full[i])
            if len(options.strip()) < 1:
                command_lines[files_Full[i][0]] = "# Nothing to do..."
            else:
                if default_folder_path == "":
                    command = "mkvextract \"" + file + "\" " + options
                else:
                    command = "mkvextract \"" + default_folder_path + "/" + str(files_Full[i][0]) + "\" " + options
                command_lines[files_Full[i][0]] = command
        # Execute extraction command
        radio_Commands = self.builder.get_object("radio_Commands")
        radio_Execute = self.builder.get_object("radio_Execute")
        if radio_Commands.get_active() and not radio_Execute.get_active():
            self.dialog_Results(self)
        else:
            for file in command_lines:
                proc = subprocess.call(command_lines[file], shell=True, stdout=subprocess.PIPE)

    def dialog_Results(self, widget):  # Creates the "Results" dialog that displays the command line
        global command_lines
        global output
        # Make output
        output = ""
        for command in command_lines:
            output = output + "# " + str(command) + "\n"
            output = output + str(command_lines[command]) + "\n"
        # Create Dialog
        dialog = gtk.Dialog(title="Command Lines", parent=None)
        dialog.set_modal(True)
        dialog.set_default_size(1200, 600)
        area = dialog.get_content_area()
        dialog.add_buttons(gtk.STOCK_OK, gtk.ResponseType.OK)
        # Add a 'copy to clipboard' button
        button_copy_to_clipboard = gtk.Button(label="Copy output to Clipboard")
        button_copy_to_clipboard.connect("clicked", self.copy_output_to_clipboard)
        # Create textview
        dialog.textview = gtk.TextView()
        textbuffer = dialog.textview.get_buffer()
        dialog.textview.set_wrap_mode(gtk.WrapMode.WORD)
        textbuffer.set_text(str(output))
        # Create a scrolledwindow, so the text view fills the dialog and is resizable
        scrolledwindow = gtk.ScrolledWindow()
        scrolledwindow.set_hexpand(True)
        scrolledwindow.set_vexpand(True)
        scrolledwindow.add(dialog.textview)
        area.add(scrolledwindow)
        area.add(button_copy_to_clipboard)
        # Display the dialog
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def copy_output_to_clipboard(self, widget):
        global output
        self.clipboard = gtk.Clipboard.get(gdk.SELECTION_CLIPBOARD)
        self.clipboard.set_text(output, -1)

    def button_Refresh_clicked(self, widget):
        self.repaint_GUI()  # Make sure GUI is up to date
        window = self.builder.get_object("main_Window")
        watch_cursor = gdk.Cursor(gdk.CursorType.WATCH)
        window.get_window().set_cursor(watch_cursor)  # Set curror to 'Waiting'
        self.repaint_GUI()  # Make sure GUI is up to date
        self.clear_Data_Grid()
        populate_files_Full()
        self.load_Data_Grid()
        self.resize_column_widths()
        self.repaint_GUI()  # Make sure GUI is up to date
        window.get_window().set_cursor(None)  # Set curror back to 'None'
        self.repaint_GUI()  # Make sure GUI is up to date

    def button_About_clicked(self, widget):  # Creates the About Dialog
        about = gtk.AboutDialog()
        about.connect("key-press-event", self.about_dialog_key_press)  # Easter Egg:  Check to see if Konami code has been entered
        about.set_program_name("Linux Bulk MKV Extract")
        about.set_version("Version 1.1")
        about.set_copyright("Copyright (c) BSFEMA")
        about.set_comments("Python application using Gtk and Glade for bulk extracting MKV data in Linux")
        about.set_license_type(gtk.License(7))  # License = MIT_X11
        about.set_website("https://github.com/BSFEMA/linux_bulk_mkv_extract")
        about.set_website_label("https://github.com/BSFEMA/linux_bulk_mkv_extract")
        about.set_authors(["BSFEMA"])
        about.set_artists(["BSFEMA"])
        about.set_documenters(["BSFEMA"])
        about.run()
        about.destroy()

    def about_dialog_key_press(self, widget, event):  # Easter Egg:  Check to see if Konami code has been entered
        global konami_code
        keyname = gdk.keyval_name(event.keyval)
        if len(konami_code) == 10:
            konami_code.pop(0)
            konami_code.append(keyname)
        else:
            konami_code.append(keyname)
        if (konami_code == ['Up', 'Up', 'Down', 'Down', 'Left', 'Right', 'Left', 'Right', 'b', 'a']) or (konami_code == ['Up', 'Up', 'Down', 'Down', 'Left', 'Right', 'Left', 'Right', 'B', 'A']):
            self.dialog_BSFEMA(self)
            # print("Konami code entered:  " + str(konami_code))
            konami_code.clear()

    def dialog_BSFEMA(self, widget):  # Creates the "BSFEMA" dialog that just spins my logo
        dialog = gtk.Dialog(title="BSFEMA", parent=None)
        dialog.add_buttons(gtk.STOCK_OK, gtk.ResponseType.OK)
        dialog.set_modal(True)
        # dialog.set_default_size(200, 200)
        area = dialog.get_content_area()
        dialog.image = gtk.Image()
        dialog.image.set_from_file(os.path.join(sys.path[0], "linux_bulk_mkv_extract.svg"))
        dialog.image.get_style_context().add_class('spinner')
        area.add(dialog.image)
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    """ ************************************************************************************************************ """
    # These are the various class functions
    """ ************************************************************************************************************ """

    def entry_Add_File_Name_changed(self, widget):
        self.load_Data_Grid()
        self.resize_column_widths()

    def resize_column_widths(self):  # have the data grid columns automatically resize
        treeview_Data_Grid = self.builder.get_object("treeview_Data_Grid")
        treeviewcolumn_Current_Name = self.builder.get_object("treeviewcolumn_Current_Name")
        treeviewcolumn_Current_Name.queue_resize()
        treeviewcolumn_Video = self.builder.get_object("treeviewcolumn_Video")
        treeviewcolumn_Video.queue_resize()
        treeviewcolumn_Audio = self.builder.get_object("treeviewcolumn_Audio")
        treeviewcolumn_Audio.queue_resize()
        treeviewcolumn_Subtitles = self.builder.get_object("treeviewcolumn_Subtitles")
        treeviewcolumn_Subtitles.queue_resize()
        treeviewcolumn_Chapters = self.builder.get_object("treeviewcolumn_Chapters")
        treeviewcolumn_Chapters.queue_resize()
        treeviewcolumn_Attachments = self.builder.get_object("treeviewcolumn_Attachments")
        treeviewcolumn_Attachments.queue_resize()

    def clear_Data_Grid(self):  # Clears out the data grid and global files lists
        # treeview_Data_Grid = Select None
        treeview_Data_Grid = self.builder.get_object("treeview_Data_Grid")
        selection = treeview_Data_Grid.get_selection()
        selection.unselect_all()
        # Do the rest of the original clear_Data_Grid bits
        liststore_Data_Grid = self.builder.get_object("liststore_Data_Grid")
        liststore_Data_Grid.clear()
        global files
        global files_Full
        files.clear()
        files_Full.clear()

    def load_Data_Grid(self):  # Loads data grid with files list
        # files_Full[0] = Current_Name
        # files_Full[1] = New_Name
        # files_Full[2] = File_Size
        # files_Full[3] = File_Date
        # files_Full[4] = Audio
        # files_Full[5] = Subtitles
        # files_Full[6] = Status
        # files_Full[7] = (json data) {}
        # files_Full[8] = (video tracks) {}
        # files_Full[9] = (audio tracks) {}
        # files_Full[10] = (subtitle tracks) {}
        # files_Full[11] = Default tracks []
        # files_Full[12] = Chapters ""
        # files_Full[13] = Attachments []
        global files
        files.clear()
        liststore_Data_Grid = self.builder.get_object("liststore_Data_Grid")
        liststore_Data_Grid.clear()
        # Build files from files_Full
        # Get prefix and suffix for new file names
        for file in files_Full:
            if file[12] == 1: has_chapters = "Yes"
            else: has_chapters = "No"
            files.append([file[0], file[5], file[2], file[3], has_chapters, file[13]])
        # Build data grid from files
        for file in files:
            liststore_Data_Grid.append(file)


""" **************************************************************************************************************** """
# "class Main()" ends here...
# Beyond here lay functions...
""" **************************************************************************************************************** """


def get_list_of_mkv_files():  # Gets the list of all files and folder from the default_folder_path
    global default_folder_path
    file_list = []  # Temp list to be sorted
    file_list.clear()
    for filename in os.listdir(default_folder_path):
        if str(filename[-4:]).lower() == ".mkv":
            if os.path.isfile(default_folder_path + "/" + str(filename)):
                file_list.append(str(filename))
    file_list.sort()  # Get a sorted list of the files
    return file_list


def populate_files_Full():
    # This populates the files_Full list with all file/folder information, which is the basis of the data grid
    global files_Full
    # files_Full[0] = Current_Name
    # files_Full[1] = Title
    # files_Full[2] = Audio
    # files_Full[3] = Subtitles
    # files_Full[4] = Defaults
    # files_Full[5] = Video
    # files_Full[6] = ""
    # files_Full[7] = (json data) {}
    # files_Full[8] = (video tracks) {}
    # files_Full[9] = (audio tracks) {}
    # files_Full[10] = (subtitle tracks) {}
    # files_Full[11] = Default tracks
    # files_Full[12] = Chapters
    # files_Full[13] = Attachments
    files_Full.clear()
    files_temp = []
    files_temp = get_list_of_mkv_files()
    files_temp.sort()
    for file in files_temp:
        part0 = file
        part1 = ""
        part2 = ""
        part3 = ""
        part4 = ""
        part5 = ""
        part6 = ""
        # Get information from mkv file in json format:
        cmd = ["mkvmerge --identify --identification-format json \"" + default_folder_path + "/" + file + "\""]
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        json_data, err = proc.communicate()
        json_data = json_data.decode("utf-8")
        part7 = json.loads(json_data)  # json information of all objects in the mkv file
        part8 = {}
        part9 = {}
        part10 = {}
        part11 = []
        part12 = ""
        part13 = ""
        files_Full.append([part0, part1, part2, part3, part4, part5, part6, part7, part8, part9, part10, part11, part12, part13])
    # Get the track information
    parse_json_data()


def parse_json_data():
    global files_Full
    global languages_video
    global types_video
    global ids_video
    global languages_audio
    global types_audio
    global ids_audio
    global languages_subtitle
    global types_subtitle
    global ids_subtitle
    global multi_lines
    # Clear the lists
    languages_video.clear()
    languages_audio.clear()
    languages_subtitle.clear()
    types_video.clear()
    types_audio.clear()
    types_subtitle.clear()
    ids_video.clear()
    ids_audio.clear()
    ids_subtitle.clear()
    # Parse the json data to get the individual tracks for the various types
    for i in range(len(files_Full)):
        if "title" in files_Full[i][7]["container"]["properties"]:
            files_Full[i][1] = files_Full[i][7]["container"]["properties"]["title"]
        if not (files_Full[i][7].get("tracks") is None):
            command = ""
            for track in files_Full[i][7]["tracks"]:
                # track_type = track["properties"]["codec_id"]
                track_type = track["codec"]
                track_id = track["id"]
                if track["properties"].get("default_track") == True:
                    files_Full[i][11].append(str(track_id))
                    if len(files_Full[i][4]) == 0:
                        files_Full[i][4] = "<b>" + str(track_id) + "</b>-" + str(track["type"])
                    else:
                        files_Full[i][4] = files_Full[i][4] + "\n<b>" + str(track_id) + "</b>-" + str(track["type"])
                if track["type"] == "video":  # Populate the track IDs for the video tracks
                    if str(track_id) not in ids_audio:
                        ids_video.append(str(track_id))
                if track["type"] == "audio":  # Populate the track IDs for the audio tracks
                    if str(track_id) not in ids_audio:
                        ids_audio.append(str(track_id))
                if track["type"] == "subtitles":  # Populate the track IDs for the subtitle tracks
                    if str(track_id) not in ids_subtitle:
                        ids_subtitle.append(str(track_id))
                if "language_ietf" in track["properties"]:  # "language_ietf" isn't always a property...
                    track_lang = track["properties"]["language_ietf"]
                elif "language" in track["properties"]:
                    track_lang = track["properties"]["language"]
                else:
                    track_lang = ""
                if not (track["properties"].get("track_name") is None):
                    track_name = track["properties"]["track_name"]
                else:
                    track_name = ""
                if track["type"] == "video":
                    if "display_dimensions" in track["properties"]:
                        track_disdim = track["properties"]["display_dimensions"]
                    else:
                        track_disdim = ""
                    if track_lang not in languages_video:
                        languages_video.append(track_lang)
                    if track_type not in types_video:
                        types_video.append(track_type)
                    files_Full[i][8][track_id] = {"track_type": track_type, "track_lang": track_lang, "track_name": track_name, "track_disdim": track_disdim}
                elif track["type"] == "audio":
                    if track_lang not in languages_audio:
                        languages_audio.append(track_lang)
                    if track_type not in types_audio:
                        types_audio.append(track_type)
                    files_Full[i][9][track_id] = {"track_type": track_type, "track_lang": track_lang, "track_name": track_name}
                elif track["type"] == "subtitles":
                    if "encoding" in track["properties"]:
                        track_encode = track["properties"]["encoding"]
                    else:
                        track_encode = ""
                    if track_lang not in languages_subtitle:
                        languages_subtitle.append(track_lang)
                    if track_type not in types_subtitle:
                        types_subtitle.append(track_type)
                    files_Full[i][10][track_id] = {"track_type": track_type, "track_lang": track_lang, "track_name": track_name, "track_encode": track_encode}
                else:
                    print("Unknown track type = " + str(file))
    # Sort the lists
    languages_video.sort()
    languages_audio.sort()
    languages_subtitle.sort()
    types_video.sort()
    types_audio.sort()
    types_subtitle.sort()
    ids_video.sort()
    ids_audio.sort()
    ids_subtitle.sort()
    # Parse the individual tracks to get the easy list of audio and subtitles
    # files_Full[0] = Current_Name
    # files_Full[1] = Title
    # files_Full[2] = Audio
    # files_Full[3] = Subtitles
    # files_Full[4] = Defaults
    if multi_lines == True:
        multi_lines_string = "\n"
    else:
        multi_lines_string = ",  "
    for i in range(len(files_Full)):
        ##########################################################################################################################################
        video = ""
        for track in files_Full[i][8]:
            name = str(files_Full[i][8][track]["track_name"])
            if name == "":
                if len(video) > 0:
                    if str(track) in files_Full[i][11]:
                        video = video + str(multi_lines_string) + "<b>" + str(track) + "-" + str(files_Full[i][8][track]["track_lang"]) + " (" + str(files_Full[i][8][track]["track_type"]) + ")</b>"
                    else:
                        video = video + str(multi_lines_string) + str(track) + "-" + str(files_Full[i][8][track]["track_lang"]) + " (" + str(files_Full[i][8][track]["track_type"]) + ")"
                else:
                    if str(track) in files_Full[i][11]:
                        video = video + "<b>" + str(track) + "-" + str(files_Full[i][8][track]["track_lang"]) + " (" + str(files_Full[i][8][track]["track_type"]) + ")</b>"
                    else:
                        video = video + str(track) + "-" + str(files_Full[i][8][track]["track_lang"]) + " (" + str(files_Full[i][8][track]["track_type"]) + ")"
            else:
                if len(video) > 0:
                    if str(track) in files_Full[i][11]:
                        video = video + str(multi_lines_string) + "<b>" + str(track) + "-" + str(files_Full[i][8][track]["track_lang"]) + " ('" + str(name) + "' " + str(files_Full[i][8][track]["track_type"]) + ")</b>"
                    else:
                        video = video + str(multi_lines_string) + str(track) + "-" + str(files_Full[i][8][track]["track_lang"]) + " ('" + str(name) + "' " + str(files_Full[i][8][track]["track_type"]) + ")"
                else:
                    if str(track) in files_Full[i][11]:
                        video = video + "<b>" + str(track) + "-" + str(files_Full[i][8][track]["track_lang"]) + " ('" + str(name) + "' " + str(files_Full[i][8][track]["track_type"]) + ")</b>"
                    else:
                        video = video + str(track) + "-" + str(files_Full[i][8][track]["track_lang"]) + " ('" + str(name) + "' " + str(files_Full[i][8][track]["track_type"]) + ")"
        files_Full[i][5] = video
        ##########################################################################################################################################
        audio = ""
        for track in files_Full[i][9]:
            name = str(files_Full[i][9][track]["track_name"])
            name = name.replace("&", "&amp;")
            if name == "":
                if len(audio) > 0:
                    if str(track) in files_Full[i][11]:
                        audio = audio + str(multi_lines_string) + "<b>" + str(track) + "-" + str(files_Full[i][9][track]["track_lang"]) + " (" + str(files_Full[i][9][track]["track_type"]) + ")</b>"
                    else:
                        audio = audio + str(multi_lines_string) + str(track) + "-" + str(files_Full[i][9][track]["track_lang"]) + " (" + str(files_Full[i][9][track]["track_type"]) + ")"
                else:
                    if str(track) in files_Full[i][11]:
                        audio = audio + "<b>" + str(track) + "-" + str(files_Full[i][9][track]["track_lang"]) + " (" + str(files_Full[i][9][track]["track_type"]) + ")</b>"
                    else:
                        audio = audio + str(track) + "-" + str(files_Full[i][9][track]["track_lang"]) + " (" + str(files_Full[i][9][track]["track_type"]) + ")"
            else:
                if len(audio) > 0:
                    if str(track) in files_Full[i][11]:
                        audio = audio + str(multi_lines_string) + "<b>" + str(track) + "-" + str(files_Full[i][9][track]["track_lang"]) + " ('" + str(name) + "' " + str(files_Full[i][9][track]["track_type"]) + ")</b>"
                    else:
                        audio = audio + str(multi_lines_string) + str(track) + "-" + str(files_Full[i][9][track]["track_lang"]) + " ('" + str(name) + "' " + str(files_Full[i][9][track]["track_type"]) + ")"
                else:
                    if str(track) in files_Full[i][11]:
                        audio = audio + "<b>" + str(track) + "-" + str(files_Full[i][9][track]["track_lang"]) + " ('" + str(name) + "' " + str(files_Full[i][9][track]["track_type"]) + ")</b>"
                    else:
                        audio = audio + str(track) + "-" + str(files_Full[i][9][track]["track_lang"]) + " ('" + str(name) + "' " + str(files_Full[i][9][track]["track_type"]) + ")"
        files_Full[i][2] = audio
        subtitles = ""
        for track in files_Full[i][10]:
            name = str(files_Full[i][10][track]["track_name"])
            name = name.replace("&", "&amp;")
            if name == "":
                if len(subtitles) > 0:
                    if str(track) in files_Full[i][11]:
                        subtitles = subtitles + str(multi_lines_string) + "<b>" + str(track) + "-" + str(files_Full[i][10][track]["track_lang"]) + " (" + str(files_Full[i][10][track]["track_type"]) + ")</b>"
                    else:
                        subtitles = subtitles + str(multi_lines_string) + str(track) + "-" + str(files_Full[i][10][track]["track_lang"]) + " (" + str(files_Full[i][10][track]["track_type"]) + ")"
                else:
                    if str(track) in files_Full[i][11]:
                        subtitles = subtitles + "<b>" + str(track) + "-" + str(files_Full[i][10][track]["track_lang"]) + " (" + str(files_Full[i][10][track]["track_type"]) + ")</b>"
                    else:
                        subtitles = subtitles + str(track) + "-" + str(files_Full[i][10][track]["track_lang"]) + " (" + str(files_Full[i][10][track]["track_type"]) + ")"
            else:
                if len(subtitles) > 0:
                    if str(track) in files_Full[i][11]:
                        subtitles = subtitles + str(multi_lines_string) + "<b>" + str(track) + "-" + str(files_Full[i][10][track]["track_lang"]) + " ('" + str(name) + "' " + str(files_Full[i][10][track]["track_type"]) + ")</b>"
                    else:
                        subtitles = subtitles + str(multi_lines_string) + str(track) + "-" + str(files_Full[i][10][track]["track_lang"]) + " ('" + str(name) + "' " + str(files_Full[i][10][track]["track_type"]) + ")"
                else:
                    if str(track) in files_Full[i][11]:
                        subtitles = subtitles + "<b>" + str(track) + "-" + str(files_Full[i][10][track]["track_lang"]) + " ('" + str(name) + "' " + str(files_Full[i][10][track]["track_type"]) + ")</b>"
                    else:
                        subtitles = subtitles + str(track) + "-" + str(files_Full[i][10][track]["track_lang"]) + " ('" + str(name) + "' " + str(files_Full[i][10][track]["track_type"]) + ")"
        files_Full[i][3] = subtitles
        # Chapters
        if len(files_Full[i][7]['chapters']) > 0:
            files_Full[i][12] = 1
        else:
            files_Full[i][12] = 0
        # Attachments
        attachments = ""
        for item in files_Full[i][7]["attachments"]:
            if attachments == "": attachments = attachments + str(item['file_name']) + " (" + str(item['content_type']) + ")"
            else: attachments = attachments + str(multi_lines_string) + str(item['file_name']) + " (" + str(item['content_type']) + ")"
        files_Full[i][13] = attachments


def update_parameter_files_at_start(command_line_parameters):  # Fix and Validate the command lind parameter files list and add to parameter_files
    global parameter_files
    for param in command_line_parameters:
        # Remove the 'file://' part to get a valid 'path'
        temp_file_address = param.replace("file://", "")
        # Replace all percent-encoding with actual characters
        temp_file_address = temp_file_address.replace("%20", " ")
        temp_file_address = temp_file_address.replace("%21", "!")
        temp_file_address = temp_file_address.replace("%22", "\"")
        temp_file_address = temp_file_address.replace("%23", "#")
        temp_file_address = temp_file_address.replace("%24", "$")
        temp_file_address = temp_file_address.replace("%25", "%")
        temp_file_address = temp_file_address.replace("%26", "&")
        temp_file_address = temp_file_address.replace("%27", "\'")
        temp_file_address = temp_file_address.replace("%28", "(")
        temp_file_address = temp_file_address.replace("%29", ")")
        temp_file_address = temp_file_address.replace("%2A", "*")
        temp_file_address = temp_file_address.replace("%2B", "+")
        temp_file_address = temp_file_address.replace("%2C", ",")
        temp_file_address = temp_file_address.replace("%2D", "-")
        temp_file_address = temp_file_address.replace("%2E", ".")
        temp_file_address = temp_file_address.replace("%2F", "/")
        temp_file_address = temp_file_address.replace("%3A", ":")
        temp_file_address = temp_file_address.replace("%3B", ";")
        temp_file_address = temp_file_address.replace("%3C", "<")
        temp_file_address = temp_file_address.replace("%3D", "=")
        temp_file_address = temp_file_address.replace("%3E", ">")
        temp_file_address = temp_file_address.replace("%3F", "?")
        temp_file_address = temp_file_address.replace("%40", "@")
        temp_file_address = temp_file_address.replace("%5B", "[")
        temp_file_address = temp_file_address.replace("%5C", "\\")
        temp_file_address = temp_file_address.replace("%5D", "]")
        temp_file_address = temp_file_address.replace("%5E", "^")
        temp_file_address = temp_file_address.replace("%5F", "_")
        temp_file_address = temp_file_address.replace("%60", "`")
        temp_file_address = temp_file_address.replace("%7B", "{")
        temp_file_address = temp_file_address.replace("%7C", "|")
        temp_file_address = temp_file_address.replace("%7D", "}")
        temp_file_address = temp_file_address.replace("%7E", "~")
        if os.path.exists(temp_file_address):
            parameter_files.append(temp_file_address)
        else:
            print("There was a problem adding the following path from the command line parameters:  " + str(temp_file_address))


def export_all_audios(file):
    filename = file[0][0:len(file[0]) - 4]
    if len(file[9]) > 0:
        command = ""
        for track in file[9]:
            track_type = str(file[9][track]["track_type"]).upper()
            track_id = track
            track_lang = file[9][track]["track_lang"]
            if not (file[9][track]["track_name"] is None):
                track_filename = filename + ".track_" + str(track_id) + "." + file[9][track]["track_name"] + "." + str(track_lang)
            else:
                track_filename = filename + ".track_" + str(track_id) + "." + str(track_lang)
            # Give the subtitles file a proper extension
            """
            A_AAC/MPEG2/*, A_AAC/MPEG4/*, A_AAC 	All AAC files will be written into an AAC file with ADTS headers before each packet. The ADTS headers will not contain the deprecated emphasis field.
            A_AC3, A_EAC3 	These will be extracted to raw AC-3 files.
            A_ALAC 	ALAC tracks are written to CAF files.
            A_DTS 	These will be extracted to raw DTS files.
            A_FLAC 	FLAC tracks are written to raw FLAC files.
            A_MPEG/L2 	MPEG-1 Audio Layer II streams will be extracted to raw MP2 files.
            A_MPEG/L3 	These will be extracted to raw MP3 files.
            A_OPUS 	Opus(tm) tracks are written to OggOpus(tm) files.
            A_PCM/INT/LIT, A_PCM/INT/BIG 	Raw PCM data will be written to a WAV file. Big-endian integer data will be converted to little-endian data in the process.
            A_REAL/* 	RealAudio(tm) tracks are written to RealMedia(tm) files.
            A_TRUEHD, A_MLP 	These will be extracted to raw TrueHD/MLP files.
            A_TTA1 	TrueAudio(tm) tracks are written to TTA files. Please note that due to Matroska(tm)'s limited timestamp precision the extracted file's header will be different regarding two fields: data_length (the total number of samples in the file) and the CRC.
            A_VORBIS 	Vorbis audio will be written into an OggVorbis(tm) file.
            A_WAVPACK4 	WavPack(tm) tracks are written to WV files.
            """
            if "AAC" in track_type:
                track_filename = track_filename + ".aac"
            elif ("AC3" in track_type or "AC-3" in track_type):
                track_filename = track_filename + ".ac3"
            elif "ALAC" in track_type:
                track_filename = track_filename + ".caf"
            elif "DTS" in track_type:
                track_filename = track_filename + ".dts"
            elif "FLAC" in track_type:
                track_filename = track_filename + ".flac"
            elif ("MPEG/L2" in track_type or "MP2" in track_type):
                track_filename = track_filename + ".mp2"
            elif ("MPEG/L3" in track_type or "MP3" in track_type):
                track_filename = track_filename + ".mp3"
            elif "OPUS" in track_type:
                track_filename = track_filename + ".ogg"
            elif "PCM" in track_type:
                track_filename = track_filename + ".wav"
            elif "REAL" in track_type:
                track_filename = track_filename + ".ra"
            elif "TRUEHD" in track_type:
                track_filename = track_filename + ".thd"
            elif "MLP" in track_type:
                track_filename = track_filename + ".mlp"
            elif "TTA1" in track_type:
                track_filename = track_filename + ".tta"
            elif "VORBIS" in track_type:
                track_filename = track_filename + ".ogg"
            elif "WAVPACK4" in track_type:
                track_filename = track_filename + ".wv"
            # Build command line for current track
            if default_folder_path == "":
                command = command + "\"" + str(track_id) + ":" + str(track_filename) + "\" "
            else:
                command = command + "\"" + str(track_id) + ":" + str(default_folder_path) + "/" + str(track_filename) + "\" "
    else:
        command = ""
    return command


def export_all_videos(file):
    filename = file[0][0:len(file[0]) - 4]
    if len(file[8]) > 0:
        command = ""
        for track in file[8]:
            track_type = str(file[8][track]["track_type"]).upper()
            track_id = track
            track_lang = file[8][track]["track_lang"]
            if not (file[8][track]["track_name"] is None):
                track_filename = filename + ".track_" + str(track_id) + "." + file[8][track]["track_name"] + "." + str(track_lang)
            else:
                track_filename = filename + ".track_" + str(track_id) + "." + str(track_lang)
            # Give the video file a proper extension
            """
            V_MPEG1, V_MPEG2 	MPEG-1 and MPEG-2 video tracks will be written as MPEG elementary streams.
            V_MPEG4/ISO/AVC 	H.264 / AVC video tracks are written to H.264 elementary streams which can be processed further with e.g. MP4Box(tm) from the GPAC(tm) package.
            V_MPEG4/ISO/HEVC 	H.265 / HEVC video tracks are written to H.265 elementary streams which can be processed further with e.g. MP4Box(tm) from the GPAC(tm) package.
            V_MS/VFW/FOURCC 	Fixed FPS video tracks with this CodecID are written to AVI files.
            V_REAL/* 	RealVideo(tm) tracks are written to RealMedia(tm) files.
            V_THEORA 	Theora(tm) streams will be written within an Ogg(tm) container
            V_VP8, V_VP9 	VP8 / VP9 tracks are written to IVF files. 
            """
            if "V_MPEG1" in track_type or "V_MPEG2" in track_type:
                track_filename = track_filename + ".mpg"
            elif "AVC" in track_type:
                track_filename = track_filename + ".h264"
            elif "HEVC" in track_type:
                track_filename = track_filename + ".h265"
            elif "FOURCC" in track_type:
                track_filename = track_filename + ".avi"
            elif "V_REAL" in track_type:
                track_filename = track_filename + ".rm"
            elif track_type == "V_THEORA":
                track_filename = track_filename + ".ogg"
            elif "V_VP8" in track_type or "V_VP9" in track_type:
                track_filename = track_filename + ".ivf"
            # Build command line for current track
            if default_folder_path == "":
                command = command + "\"" + str(track_id) + ":" + str(track_filename) + "\" "
            else:
                command = command + "\"" + str(track_id) + ":" + str(default_folder_path) + "/" + str(track_filename) + "\" "
    else:
        command = ""
    return command


def export_all_subtitles(file):
    filename = file[0][0:len(file[0]) - 4]
    if len(file[10]) > 0:
        command = ""
        for track in file[10]:
            track_type = str(file[10][track]["track_type"]).upper()
            track_id = track
            track_lang = file[10][track]["track_lang"]
            if not (file[10][track]["track_name"] is None):
                track_filename = filename + ".track_" + str(track_id) + "." + file[10][track]["track_name"] + "." + str(track_lang)
            else:
                track_filename = filename + ".track_" + str(track_id) + "." + str(track_lang)
            # Give the subtitles file a proper extension
            """
            S_HDMV/PGS 	PGS subtitles will be written as SUP files.
            S_TEXT/SSA, S_TEXT/ASS, S_SSA, S_ASS 	SSA and ASS text subtitles will be written as SSA/ASS files respectively.
            S_TEXT/UTF8, S_TEXT/ASCII 	Simple text subtitles will be written as SRT files.
            S_VOBSUB 	VobSub(tm) subtitles will be written as SUB files along with the respective index files, as IDX files.
            S_TEXT/USF 	USF text subtitles will be written as USF files.
            S_TEXT/WEBVTT 	WebVTT text subtitles will be written as WebVTT files.
            """
            if "PGS" in track_type:
                track_filename = track_filename + ".sup"
            elif "ASS" in track_type:
                track_filename = track_filename + ".ass"
            elif "SSA" in track_type or 'SubStationAlpha'.upper() in track_type.upper():
                track_filename = track_filename + ".ssa"
            elif "SubRip".upper() in track_type.upper() or "SRT".upper() in track_type.upper():
                track_filename = track_filename + ".srt"
            elif "VOBSUB" in track_type:
                track_filename = track_filename + ".sub"
            elif "USF" in track_type:
                track_filename = track_filename + ".usf"
            elif "WEBVTT" in track_type:
                track_filename = track_filename + ".vtt"
            # Build command line for current track
            if default_folder_path == "":
                command = command + "\"" + str(track_id) + ":" + str(track_filename) + "\" "
            else:
                command = command + "\"" + str(track_id) + ":" + str(default_folder_path) + "/" + str(track_filename) + "\" "
    else:
        command = ""
    return command


def export_all_attachments(file):
    if len(file[7]["attachments"]) > 0:
        command = " attachments "
        for attachment in file[7]["attachments"]:
            id = attachment["id"]
            filename = attachment["file_name"]
            # Build command line for current attachment
            if default_folder_path == "":
                command = command + str(id) + ':\"' + str(filename) + "\" "
            else:
                command = command + str(id) + ':\"' + str(default_folder_path) + "/" + str(filename) + "\" "
    else:
        command = ""
    return command


def export_chapters(file):
    filename = file[0][0:len(file[0]) - 4]
    command = ""
    if file[12] == 1:
        if default_folder_path == "":
            command = " chapters \"" + str(filename) + ".chapters.xml\""
        else:
            command = " chapters \"" + default_folder_path + "/" + str(filename) + ".chapters.xml\""
    else:
        command = ""
    return command


if __name__ == '__main__':
    # Check for command line arguments, and set the default_folder_path appropriately
    if len(sys.argv) > 1:  # If there is a command line argument, check if it is a folder
        if os.path.isdir(sys.argv[1]):  # Valid folder:  so set the default_folder_path to it
            default_folder_path = sys.argv[1]
        elif os.path.isdir(os.path.dirname(os.path.abspath(sys.argv[1]))):  # If valid file path was sent:  use folder path from it.
            default_folder_path = os.path.dirname(os.path.abspath(sys.argv[1]))
        elif "file://" in sys.argv[1]:  # In case using 'Bulk Rename' option in Nemo, get file path from first parameter and auto-select the files.
            update_parameter_files_at_start(sys.argv[1:])  # Convert URL encoded files to paths
            if os.path.isdir(os.path.dirname(os.path.abspath(parameter_files[0]))):  # If the first file is a valid path:  use folder path from it.
                default_folder_path = os.path.dirname(os.path.abspath(parameter_files[0]))
            else:  # Invalid first file path:  so set the default_folder_path to where the python file is
                default_folder_path = sys.path[0]
        else:  # Invalid file/folder paths:  so set the default_folder_path to where the python file is
            default_folder_path = sys.path[0]
    else:  # No command line argument:  so set the default_folder_path to where the python file is
        default_folder_path = sys.path[0]
    main = Main()
    gtk.main()
