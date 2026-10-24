# convertor

a local file converter for windows and mac. built it because i hate ads and uploading my files to random websites. runs completely offline.

## what it does

- images (convert, compress, resize, crop, watermark, strip metadata)
- pdfs (merge, split, redact, lock/unlock, compress, ocr text from scans)
- video (convert, trim, merge, gifs, extract audio)
- audio (convert, trim, fade, remove silence)
- documents (word/excel to pdf via libreoffice)
- files (split large files into chunks or join them back)
- 24 themes to pick from
- ctrl+v pastes screenshots right into the list

## how to run from source

install python, then run:

pip install -r requirements.txt
python main.py

## building the app

this repo has github actions set up. if you push to the main branch, github will build the windows .exe and mac .app for you automatically. check the actions tab to download them. 

if you want to build it yourself locally, run build_windows.bat or build_mac.sh.

## optional stuff

you need these installed for certain features to work, but the app will detect them and let you install them from the about tab.
- ffmpeg (for video/audio)
- libreoffice (for documents)
- tesseract (for ocr)

## testing

there is a self test script that makes its own files and runs over 250 checks on the backend. 

python selftest.py

## privacy

nothing leaves your pc. no servers, no accounts, no tracking.

<details>
  <summary>...</summary>
  <br>
  for my sweet girl
</details>