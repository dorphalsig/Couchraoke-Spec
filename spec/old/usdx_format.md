# UltraStar Format Specification
VERSION: 1.1.0  
Last update: 21 Nov 2023
These are the official UltraStar Format specifications. The rules and requirements below dictate what an UltraStar textfile is and how each item should be interpreted.
For song creators, editor devs, database admins, and game devs.
## Encoding & TXT
Encoding has to be UTF-8 without BOM.
**Why?** UTF-8 without BOM is an encoding that can represent a vast number of symbols from all kinds of languages. Other encodings, like Windows code pages, are far more limited and are only suitable for a small family of languages.
File container has to be TXT.
**Why?** TXT files are simple and easy to understand for non-coders. You can read and edit them with a simple text editor. That is what made the format popular in the first place. Even though there are many markup languages, such as XML, TXT files should continue to be used unless there are good reasons to change that.
Empty lines are ignored.
**Why?** When editing a TXT file manually, empty lines can be helpful to separate different parts of a song. Lines that consist only of whitespace characters are considered empty.
## Mandatory Attributes
### `#VERSION` — new
The version attribute helps games and apps understand how up-to-date a song file is and how it should be treated. Ideally all TXT files will be upgraded to the latest version. The value is a version number according to semantic versioning. Song editors, managing tools, or TXT hostings should set this automatically.
```txt
#VERSION:1.1.0
```
### `#TITLE`
The title of the song. This is the song name that will appear in the song selection screen.
```txt
#TITLE:Song Title
```
### `#ARTIST`
The artist of the song. This is the name of the person or group who performed the song.
```txt
#ARTIST:Artist
```
### `#MP3` — deprecated
Filename of the audio file. This is the file that contains the sound of the song. It must be in the same folder as the TXT file and should have the same name as the folder.
All software supports at least `.mp3` CBR, `.wav`, and `.ogg` audio files.
Please use `#AUDIO`. `#MP3` will be removed in 2025.
```txt
#MP3:Artist - Title.mp3
```
### `#AUDIO` — new
Defines the audio file that contains the whole music in one file, consisting of vocals and instrumental(s). This is the new tag for the deprecated `#MP3` tag.
It must be in the same folder as the TXT file and should have the same name as the folder.
All software supports at least `.mp3` CBR, `.wav`, and `.ogg` audio files.
```txt
#AUDIO:Artist - Title.mp3
```
### `#BPM`
Speed of the song in UltraStar beats per minute. This is not the real song BPM.
UltraStar BPM is quarter notes, thus it is ideally quadruple the song’s BPM. “Ideally” means that any song could be tapped with any BPM, not necessarily related to the song’s actual BPM.
```txt
#BPM:400
```
## Notes
### Note description
A sung line is defined by:
- `NoteType`
- `StartBeat`
- `Length`
- `Pitch`
- `Text`
For note styles, see **NoteTypes**.
The `StartBeat` and `Length` must be calculated against `BPM`, `GAP`, and `Relative`. It is a beat number.
The pitch describes the note as a number. The number `0` corresponds to note `C4` and MIDI note `60`.
`Text` is the part of the lyrics that is sung in this note.
```txt
NoteType StartBeat Length Pitch Text
```
```txt
: 10 10 10 Text
```
### Word separators
Words are separated via a space in the `Text` part of a note. The separating space may come at the end of the previous note or at the start of the next note.
Before:
```txt
0 4 0 Hello|
8 4 0  World|
```
After:
```txt
0 4 0 Hello |
8 4 0 World|
```
The `|` is used to mark the end of the line for visualization purposes in the example above.
### End of phrase
`-` represents the end of a phrase and how long it lasts by the `StartBeat`.
The length is calculated against `BPM`, `GAP`, and `Relative`. It is a beat number.
```txt
- StartBeat
```
### End of file
`E` represents the end of a file.
```txt
E
```
### Player delimiter
`P1` or `P2` is a player delimiter. The following section of notes is for player 1 or player 2.
```txt
P1
```
### NoteTypes
#### Normal `:`
The normal note.
```txt
: 0 1 8 Normal
```
#### Golden `*`
The golden note. Gives twice the points of a normal note.
```txt
* 0 1 8 Golden
```
#### Freestyle `F`
Note that will not be scored.
```txt
F 0 1 8 Freestyle
```
#### Rap `R`
Rap note.
```txt
R 0 1 8 Rap
```
#### Rap Golden `G`
Golden rap note. Gives twice the points of a rap note.
```txt
G 0 1 8 RapGolden
```
## Optional Attributes
### `#GAP`
Delay for the start of the lyric in milliseconds.
It is used so that the first word starts at `0`. Otherwise, the delay gap would be added to the start of the first line.
```txt
#GAP:12345
```
### `#COVER`
Filename of the cover image. Should end with `*[CO].jpg`.
This is an image that shows the album cover or a picture related to the song. It should be in 1:1 aspect ratio. It should not be larger than `1920x1920px`.
All software supports at least JPG/JPEG files.
```txt
#COVER:Artist - Title [CO].jpg
```
### `#BACKGROUND`
Filename of the background image. Can be shown instead of a video or if no video is available. Should end with `*[BG].jpg`.
This will be shown when there is no `#VIDEO` available.
```txt
#BACKGROUND:Artist - Title [BG].jpg
```
### `#VIDEO`
Filename of the video file.
This is a video that shows a music video or other visual content related to the song.
The sound of the video is generally not played. Exception: if there is no audio file, UltraStar Deluxe and Vocaluxe play the audio track from the video.
It must be in a format supported by UltraStar, such as MP4 or AVI.
```txt
#VIDEO:Artist - Title.mp4
```
### `#VIDEOGAP`
Specifies the delay in seconds between the start of the video and the start of the song.
This value can be used to synchronize the video with the music. This attribute is useful when the video and audio files are not perfectly synchronized and you need to adjust the timing of the video to match the audio.
By setting a positive or negative value for `#VIDEOGAP`, you can delay or advance the start of the video relative to the start of the song.
```txt
#VIDEOGAP:12345
```
### `#VOCALS` — new
`#VOCALS` defines the audio file that contains only the vocals of a singer’s voice. It is the a cappella track.
This is useful when games have the feature to change the volume of a singer while playing a song from 100% to 0%, so that you can decide how loud the singer sings along to your own vocals.
Needs to be complemented with `#INSTRUMENTAL`.
It can also be used to sing a cappella with the singer.
Please add `[VOC]` to the file name.
```txt
#VOCALS:Artist - Title of the song [VOC].mp3
```
### `#INSTRUMENTAL` — new
`#INSTRUMENTAL` defines the audio file that contains only the instruments of a song without the singer’s voice. This is for real karaoke.
Please add `[INSTR]` to the file name.
```txt
#INSTRUMENTAL: Artist - Title of the song [INSTR].mp3
```
### `#GENRE`
Specifies the genre of the song. This information can be used to categorize songs by their musical style.
The value of the `#GENRE` attribute can be any text string that describes the genre of the song. Some common genres include Pop, Rock, Hip-Hop, Country, and Jazz.
You can add multiple tags and separate them with commas.
```txt
#GENRE:Pop, Rock, Punkfunk
```
### `#TAGS` — new
`#TAGS` allows you to add any reasonable keyword for this song. This helps categorize songs by keywords.
You can add multiple tags and separate them with commas. You can use `#TAGS` if `#EDITION` is not enough.
Some common keywords are:
- Party
- Feel-Good
- Charts
- Cover Songs
- Summer
- Love Songs
- Guilty Pleasure
- Disney
- Christmas
- Halloween
- Eurovision Song Contest `[YEAR]`
- Club
- Dancefloor
- Underground
- Mainstream
- Slow
```txt
#TAGS:Love Songs, Movie, 80s
```
### `#EDITION`
This attribute specifies a value out of a curated list where a song belongs.
Aside from this list, certain games can be used, such as SingStar - Pop Hits, GuitarHero Live, Rockband vol.4, Let’s Sing 2020.
Lists of editions:
- SingStar editions: https://github.com/bohning/usdb_syncer/wiki/SingStar-Editions
- RockBand editions: https://github.com/bohning/usdb_syncer/wiki/RockBand-Editions
- GuitarHero editions: https://github.com/bohning/usdb_syncer/wiki/GuitarHero-Editions
This information can be used to categorize songs by their edition.
You can add multiple values and separate them with commas.
```txt
#EDITION:SingStar Rocks! [DE]
```
### `#CREATOR`
Specifies the name of the person who created the UltraStar TXT file.
This information can be used to give credit to the person who created the file.
The value of the `#CREATOR` attribute can be any text string that represents the name of the person who created the UltraStar TXT file.
You can add multiple creators and separate them with commas.
```txt
#CREATOR:dagegg, bohning, roller girl
```
### `#LANGUAGE`
Specifies the language of the song. This information can be used to categorize songs by their language.
The value of the `#LANGUAGE` attribute should be English language names, not translated language names. For example, use `French`, not `Français` or `Französisch`.
You can add multiple languages and separate them with commas.
```txt
#LANGUAGE:English, French
```
### `#YEAR`
Specifies the year the song was released. This information can be used to categorize songs by their release date.
The value of the `#YEAR` attribute should be a four-digit number that represents the year the song was released.
```txt
#YEAR:2022
```
### `#START`
`#START` specifies the time in seconds from the beginning of the audio file at which the song starts.
This value can be used to skip any silence or intro at the beginning of the audio file.
The value should be positive integers that represent the start time of the song in seconds.
```txt
#START:1.5
```
### `#END`
Specifies the time in milliseconds from the beginning of the audio file at which the song ends.
This value can be used to stop playback before any silence or outro at the end of the audio file.
The value should be positive integers that represent the end time of the song in milliseconds.
Keep it simple: it is just seconds + `000`.
```txt
#END:678000
```
### `#PREVIEWSTART`
Specifies the time in seconds from the beginning of the audio file at which the preview of the song starts.
This value can be used to set the start time of the preview that is played when browsing songs.
```txt
#PREVIEWSTART:12,34
```
### `#MEDLEYSTARTBEAT`
Specifies the start beat of a medley section within the song.
This value can be used to create a medley of multiple songs by specifying which section of each song should be included in the medley.
Needs `#MEDLEYENDBEAT`.
```txt
#MEDLEYSTARTBEAT:10
```
### `#MEDLEYENDBEAT`
Specifies the end beat of a medley section within the song.
This value can be used to create a medley of multiple songs by specifying which section of each song should be included in the medley.
Needs `#MEDLEYSTARTBEAT`.
```txt
#MEDLEYENDBEAT:20
```
### `#CALCMEDLEY`
Specifies whether UltraStar should automatically calculate the medley section of the song.
If this attribute is set to `on`, UltraStar will automatically determine the most suitable section of the song for a medley based on the note data.
If it is set to `off`, the automatic medley calculation can be disabled.
```txt
#CALCMEDLEY:on
```
### `#P1` and `#P2`
Specify the names of the singers for a duet song.
These values can be used to display the names of the singers on screen during a duet.
```txt
#P1:John
```
### `#PROVIDEDBY` — new
`#PROVIDEDBY` helps to understand where a TXT file came from.
This is important because there are many third parties that host TXT files with different quality standards.
This information should normally be set automatically from the provider, but you can also set it manually with a song editor if you know where you got it from.
The value should be a URL.
```txt
#PROVIDEDBY: https://usdb.animux.de
```
### `#COMMENT`
Use `#COMMENT` to write any important information in the text file that might be interesting for song creators.
Right now there is no definition for what this attribute should be used for exactly.
It is not displayed in the games.
```txt
#COMMENT:made with Karedi and YASS Editor
```
## Deprecated
Here are all the `#` attributes that you should not use anymore.
Why? They are technically not necessary today or are duplicates from the history of UltraStar games.
### `#RESOLUTION`
Changes the grid resolution of the UltraStar Deluxe editor.
Only for the editor and not for singing.
```txt
#RESOLUTION:
```
### `#NOTESGAP`
Nobody knows what this was meant for, but it was found in some older game code.
Do not use it.
```txt
#NOTESGAP:
```
### `#RELATIVE`
Specifies whether the note timings in the file are relative to the previous note or absolute.
If this attribute is set to `yes`, the note timings are relative to the previous note.
If it is set to `no` or not present, the note timings are absolute.
If this line is missing, then the timestamps are absolute.
Relative timestamps make working on a TXT file easier, because if you want to insert a pause, you do not have to adjust all following timestamps, but only the ones until the end of the line.
Switching from absolute to relative and back is easy using either UltraStar Manager or the USDX editor.
```txt
#RELATIVE:yes
```
### `#DUETSINGERP1` / `#DUETSINGERP2`
Specify the names of the singers for a duet song.
These values can be used to display the names of the singers on screen during a duet.
This is a duplicate. Use `#P1` and `#P2` instead.
```txt
#DUETSINGERP1:John
```
### `#ENCODING`
Specifies the character encoding used in the TXT file.
This attribute can be used to ensure that special characters are displayed correctly.
Possible values are `UTF-8`, `CP1252`, and `CP1250`.
This is not needed. All TXT should be UTF-8 without BOM.
```txt
#ENCODING:UTF8
```
### More duplicates
`#AUTHOR` is a duplicate of `#CREATOR`.
`#PREVIEW` is a duplicate of `#PREVIEWSTART`.
`#ALBUM`, `#SOURCE`, `#YOUTUBE`, `#LENGTH`, and `#FIXER` are not necessary.
Please change or delete these tags to update TXT files.
```txt
#AUTHOR, #FIXER, #ALBUM, #SOURCE, #YOUTUBE, #LENGTH
```