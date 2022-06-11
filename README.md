# Hoarder

A virtual manager for your digital hoarding needs.
It's a program that lets you define hotkeys to copy contents from different sources
and send them to other sources. You can think of it as a simple specialized clipboard manager.
The only thing the program lets you do for now is to define hotkeys to trigger Ctrl-C on selected text
and save the text as [Anki](https://apps.ankiweb.net/) flashcards - mainly useful for sentence mining.

## Introduction

I spend most of my time online reading content in foreign languages (e.g. English).
As every language learner knows, whatever is your level in your target language,
there is no end to the words or expressions unknown to you that you encounter every day.
At the beginning of my language learning journey, I used to learn vocabulary mostly from simple-minded vocabulary flashcards void of context. Soon I discovered the joy of learning from immersion in native content.
Passive immersion is ineffecient and time-consuming though, so many avid language learners developed tools
to help themselves and fellow learners learn efficiently. These tools help you "mine" sentences from content
you consume in your target language and automatically create Anki flaschards for you.
Examples of such tools are [subs2srs](http://subs2srs.sourceforge.net/) and [mpvacious](https://github.com/Ajatt-Tools/mpvacious). I use many of these tools for sentence mining from videos, but I wanted to have
my specialized tool for mining from textual sources such as books and articles. I used to use Evernote
for saving any sentence with unknown word/phrases that my eyes fall on, then import them to Anki.
Evernote was great for sentence mining: it allows you to set a global hotkey (in the desktop version)
to clip selected text. Moreover, if you're reading online content in a web browser, it remembers the link of the current tab. I wanted to go further though and have the ability to take screenshots, define multiple hotkeys that save to different sources, and so on.
I then started writing a simple AutoHotkey script for that. My AutoHotkey skills are horrible though.
I don't like the syntax and am not motivated enough to learn the language properly to be able to extend the script.
So I set to write a Python program that I can extend more easily and that can benefit from access to
a lot of libraries.

## Usage

The only function implemented currently is importing to Anki via the [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on (You need to have it installed). You define hotkeys and other configurations in a file named `config.json` under [src](./src).

An example config file is the following:

```json
[
  {
    "hotkey": "Ctrl+Alt+O",
    "notetype": "English Vocabulary",
    "deck": "en::vocab",
    "target_field": "Word",
    "screenshot_field": "References"
  },
  {
    "hotkey": "Ctrl+Alt+J",
    "notetype": "Japanese Mined Sentence",
    "deck": "ja::mined sentences",
    "target_field": "Sentence",
    "screenshot_field": "Image"
  }
]
```

The format will change in the future as I add more features.

After defining your hotkeys, install dependencies (preferably in a [virtual environment](https://docs.python.org/3/library/venv.html)) and run the program using:

```
pip install -r requirements.txt
python src/main.py
```

There is no graphical interface yet, except for a system tray icon that shows notifications and lets you quit the program (You can also use `Ctrl+Alt+Q`).

Now, press some hotkey you defined in the config file and you should see a notification pops up telling you that the selected text was copied. Go to Anki and check the created note.

## Credit

Libraries & tools used:

- [PyQt5](https://pypi.org/project/PyQt5/) for the GUI.
- [pyqtkeybind](https://pypi.org/project/pyqtkeybind/) for registering global hotkeys.
- [mss](https://pypi.org/project/mss/) for taking screenshots.
- [jaraco](https://pypi.org/project/jaraco.clipboard/) for getting text from the clipboard in HTML format.
- [PyAutoGUI](https://pypi.org/project/PyAutoGUI/) for triggering Ctrl-C.
- [AnkiConnect](https://ankiweb.net/shared/info/2055492159) for creating Anki cards.
- The tray icon is adapted from [Clipboard minus](https://icons.getbootstrap.com/icons/clipboard-minus/) from Bootstrap icons.

## TODO

- [ ] Provide prebuilt binaries.
- [ ] Save the source of clipped text (e.g. title of window, link of web page, etc.)
- [ ] Add option to save contents in some file in some format instead of sending them directly to Anki and other soruces. Also provide another option to sync with those sources when needed.
- [ ] A graphical interface.
- [ ] lots and lots of bug fixes.

## History

3 years ago, I wrote a similar program that saves copied vocabulary to plain text files for importing to Anki.
It was written in C and used the Windows API for clipboard management and triggering hotkeys. It also used the [IUP](https://www.tecgraf.puc-rio.br/iup/) library for the GUI (I challenged myself to write the whole thing using pure Windows API functions and gave up eventually.) The whole thing was a mess.
