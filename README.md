# About
**movenotes** is a set of utilities to migrate from Apple Notes to:

* GMail Apple Notes
* Joplin

The Apple Notes app does not provide a ***move all*** action to move all Apple Notes in a folder to GMail.


[gyb](https://github.com/jay0lee/got-your-back/wiki) is used to import and export note email messages to and from GMail.

[mac_apt](https://github.com/ydkhatri/mac_apt/wiki) is used to extract the Apple Notes database from iOS device backups.

[readnotes](https://github.com/renesugar/readnotes) is used to extract Apple Notes from the Notes app databases for iOS and Mac OS.

[bookmarks](https://github.com/renesugar/bookmarks) is used to extract bookmarks to be moved to GMail or Joplin as notes.

[chrometabs](https://github.com/renesugar/chrometabs) is used to extract the current tabs from Google Chrome to be moved to GMail or Joplin as notes.

[listurls](https://github.com/renesugar/listurls) is used to extract URLs from text files to be moved to GMail or Joplin as notes.

[filterurls](https://github.com/renesugar/filterurls) is used to filter URLs from text files to be moved to GMail or Joplin as notes.

[twitter-to-sqlite](https://github.com/dogsheep/twitter-to-sqlite) is used to extract Twitter likes via the Twitter API.

[jq](https://github.com/stedolan/jq) is used to format JSON files.

# Usage

## Extract Apple Notes

### Extract MacOS Notes Databases

In the example, see the *~/output_macos/Export/NOTES* directory for copies of files to process using *readnotes*.

The *mac_apt.db* file does not contain a complete representation of the note text.

```
python3 mac_apt.py -o ~/output_macos -s -x MOUNTED / NOTES
```

### Extract MacOS Notes

See the [readnotes](https://github.com/renesugar/readnotes) README for how to extract notes from the Apple Notes databases.

### Extract iOS Notes Databases

Use Finder to create a local iOS backup and then use *mac_apt* to extract the notes from the backup.

In the example, see the *~/output_ios/Export/IDEVICEBACKUPS* directory for copies of files to process using *readnotes*.

The *mac_apt.db* file does not contain a complete representation of the note text.

```
python3 mac_apt.py -o ~/output_ios -s -x MOUNTED / IDEVICEBACKUPS
```

Rename *4f98687d8ab0d6d1a371110e6b7300f6e465bef2* from iOS backup to *NoteStore.sqlite*.

Name of notes SQLite database varies depending upon OS version:

| Database | OS Version |
|----------|------------|
| NotesV1.storedata | Mountain Lion |
| NotesV2.storedata | Mavericks |
|NotesV4.storedata | Yosemite |
|NotesV6.storedata | El Capitan and Sierra |
|NotesV7.storedata | HighSierra |
|NoteStore.sqlite  | El Capitan+ |

```
python3 mac_apt_artifact_only.py -i ~/output_ios/NoteStore.sqlite -o ~/output_ios_notes -s NOTES
```

Currently, *mac_apt* does not extract *public.url* attachments in Apple Notes (see [<https://github.com/ydkhatri/mac_apt/issues/33>). Any URLs in public.url attachments will be missing from the note text until public.url attachments are supported.

### Extract iOS Notes

See the [readnotes](https://github.com/renesugar/readnotes) README for how to extract notes from the Apple Notes databases.

### Extract iCloud Notes
To obtain a copy of your data:

1. Log in to [privacy.apple.com](https://privacy.apple.com).
2. Select the "Get started" link under the "Get a copy of your data" heading.
3. Tick the boxes of the categories of data you want to download (Notes).
4. Press Continue.
5. Select your preferred maximum file size (Apple will split up the data into chunks, up to a maximum of 25 GB) and press Continue.

After the download is ready, extract it into a local folder.

### Load iCloud Notes into database
```
python3 -B icloud2sql.py --email your.email@address.com --input ~/iCloudNotes --output ~/notesdb
```
## Download GMail Apple Notes

### Download GMail notes as EML files using [GYB](https://github.com/jay0lee/got-your-back/wiki)
```
./gyb --email your.email@address.com  --action estimate --search "label:Notes"
```
```
./gyb --email your.email@address.com  --search "label:Notes"
```
### Load EML notes into database
```
python3 -B gyb2eml.py --email your.email@address.com --action list-files --local-folder ~/gyb/GYB-GMail-Backup-your.email@address.com > filelist.txt
```
```
python3 -B eml2sql.py --email your.email@address.com --filelist ./filelist.txt --output ~/notesdb
```

## Convert Emails into Notes

### Convert MBOXes to EMLs
```
python3 -B mbox2eml.py --email your.email@address.com --input ./mboxes --output ~/note_emls
```
```
python3 -B filelist.py --path ~/note_emls --extensions ".eml" > filelist.txt
```
### Load EMLs into database
```
python3 -B eml2sql.py --email your.email@address.com --filelist ./filelist.txt --output ~/notesdb
```
### Convert EMLs in database to Apple Note EMLs
```
python3 -B sql2eml.py --email your.email@address.com --input ~/notesdb --output ~/note_emls
```
## Move Apple Notes to GMail Folder

### Save database as EML notes
```
python3 -B sql2eml.py --email your.email@address.com --input ~/notesdb --output ~/note_emls
```
### Package EML notes as an MBOX file
```
python3 -B eml2mbox.py --email your.email@address.com --input ~/note_emls --output ~/mboxes
```
### Load EML notes MBOX into GMail
```
./gyb --email your.email@address.com --action restore-mbox --local-folder ~/mboxes --label-restored Notes
```

## Move Apple Notes to Joplin
### Load iCloud Notes into database
```
python3 -B icloud2sql.py --email your.email@address.com --input ~/icloud_notes --output ./output
```
### Load MacOS Notes into database
```
python3 -B macapt2sql.py --email your.email@address.com --input ~/macos_notes --output ~/notesdb
```
### Load iOS Notes into database
```
python3 -B macapt2sql.py --email your.email@address.com --input ~/ios_notes --output ~/notesdb
```
### Load iOS Notes into database and move all notes to folder "Notes"
```
python3 -B macapt2sql.py --email your.email@address.com --input ~/ios_notes --output ~/notesdb --folder Notes
```

### Load Joplin Notes into database
```
python3 -B joplin2sql.py --email your.email@address.com --input ~/JoplinNotesRAW --output ~/notesdb
```

### Remove duplicate notes from database

Remove duplicate notes across all folders.

```
python3 -B removedups.py --email your.email@address.com --input ~/notedb
```

### Clean resources directory

Remove unused resource files across all folders.

```
python3 -B cleanres.py --email rene.sugar@gmail.com --input ~/notesdb
```
### Convert database to Joplin Notes
```
python3 -B sql2joplin.py --email your.email@address.com --input ~/notedb --output ~/JoplinNotesRAW_New
```

## Convert Bookmarks to Notes

### Load Firefox bookmark backup into database

[Firefox Profile Folder](http://kb.mozillazine.org/Profile_folder_-_Firefox)

[sessionstore-backups folder](https://support.mozilla.org/en-US/questions/1091640#answer-800491)

Select a backup in *~/Library/Application\ Support/Firefox/Profiles/yourprofile.default/bookmarkbackups*

[Decompress Mozilla Firefox bookmarks backup files](https://github.com/andikleen/lz4json)

```
./lz4jsoncat ./sample.jsonlz4

python3 -B ffbookmarks.py --path ./sample.json
```

```
python3 -B url2sql.py --email your.email@address.com --input ./urls.txt --output ~/notesdb --folder Bookmarks
```

### Load Firefox bookmarks into database
```
python3 -B ffplaces.py --path ~/Library/Application\ Support/Firefox/Profiles/yourprofile.default/places.sqlite
```

```
python3 -B url2sql.py --email your.email@address.com --input ./urls.txt --output ~/notesdb --folder Bookmarks
```

### Load Firefox tabs into database

[Firefox Profile Folder](http://kb.mozillazine.org/Profile_folder_-_Firefox)

[sessionstore-backups folder](https://support.mozilla.org/en-US/questions/1091640#answer-800491)

*~/Library/Application\ Support/Firefox/Profiles/n8hzydqt.default/sessionstore-backups/recovery.js*

```
python3 -B ffrecovery.py --path ~/Library/Application\ Support/Firefox/Profiles/yourprofile.default/sessionstore.js
```

```
python3 -B url2sql.py --email your.email@address.com --input ./urls.txt --output ~/notesdb --folder Bookmarks
```

### Load Chrome bookmarks into database

```
python3 -B chbookmarks.py --path ~/Library/Application\ Support/Google/Chrome/Default/Bookmarks > urls.txt
```
```
python3 -B url2sql.py --email your.email@address.com --input ./urls.txt --output ~/notesdb --folder Bookmarks
```

### Load Chrome tabs into database

```
python3 -B chrometabs.py --path ~/Library/Application\ Support/Google/Chrome/Default/Current\ Tabs > urls.txt
```
```
python3 -B url2sql.py --email your.email@address.com --input ./urls.txt --output ~/notesdb --folder Bookmarks
```

### Load Safari bookmarks into database

```
python3 -B sfbookmarks.py --path ~/Library/Safari/Bookmarks.plist > urls.txt
```
```
python3 -B url2sql.py --email your.email@address.com --input ./urls.txt --output ~/notesdb --folder Bookmarks
```

### List URLs in text files

Extract text data into a file using *strings* and then use *listurls.py* to extract the URLs in the text.

The titles will be retrieved online which can take some time. If the title cannot be retrieved, the URL will be used as the title.

```
python3 -B listurls.py --path ./input --output ./urls.txt
```

### Format URLs into Firefox bookmark HTML file

```
python3 -B htmlbackup.py --path ./urls.txt > bookmarks.html
```

### Extract URLs from Firefox or Chrome bookmark HTML files

```
python3 -B htmlbookmarks.py --path ./input --output ./urls.txt --backup
```

### Filter URLs from URL backup file

The sites.txt file contains sites and URLs to filter out of the URL files.

```
python3 -B filterurls.py --path ./input --sites ./sites.txt --output ./urls.txt --backup
```

### Load bookmark URLs into database

If the title matches the URL, titles will be retrieved online which can take some time. If the title cannot be retrieved, the URL will be used as the title.

```
python3 -B url2sql.py --email your.email@address.com --input ./urls.txt --output ~/notesdb --folder Bookmarks
```

## Convert Twitter Likes to Notes

### Extract Twitter Likes from API

```
twitter-to-sqlite favorites faves.db
```

### Extract Twitter Likes from Archive

See [How to download your Twitter archive](https://help.twitter.com/en/managing-your-account/how-to-download-your-twitter-archive) on Twitter's website for how to download a copy of your Twitter archive.

```
$ twitter-to-sqlite import archiveYYYYMMDD.db ./twitter-YYYY-MM-DD-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/data/like.js
```

### Load Twitter likes from Archive into database

```
python3 -B twitterarchivelikes2sql.py --email your.email@address.com --input /path/to/Twitter/archive/likes/archiveYYYYMMDD.db --output ~/twitterdb --cache ./url_dict.json --error ./error_dict.json
```

### Expand Shortened URLs

The Twitter archive contains shortened URLs using Twitter's URL shortener.

Other URL shorteners are also used by the authors of the tweets.

Over time, these URL shorteners can become unavailable so the URLs need to be expanded. The Twitter archive data may contain shortened URLs that can no longer be expanded for this reason.

If there are expansion errors, this step will need to be repeated.

```
python3 -B expandurls.py --cache ./url_dict.json --error ./error_dict.json
```

```
cat url_dict.json | jq '.' > temp.txt
cp temp.txt url_dict.json
rm temp.txt

cat error_dict.json | jq '.' > temp.txt
cp temp.txt error_dict.json
rm temp.txt
```

Wipe the Twitter database and re-run the step to load the database with the cache of expanded URLs.

```
rm ~/twitterdb/*
```

### Load Twitter Likes from API into database

```
python3 -B twitterlikes2sql.py --email your.email@address.com --input /path/to/Twitter/API/likes/faves.db --output ~/twitterdb --cache ./url_dict.json --error ./error_dict.json
```

### Expand Shortened URLs

Expand shortened URLs in the Twitter likes.


Wipe the Twitter database and re-run the step to load the database with the cache of expanded URLs.

```
rm ~/twitterdb/*
```

### Convert database to Jopin Notes

```
python3 -B sql2joplin.py --email your.email@address.com --input ~/twitterdb --output ~/JoplinNotesRAW_Twitter
```