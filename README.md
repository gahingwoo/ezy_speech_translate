# EzySpeechTranslate Real-Time Voice Translation System

A complete real-time speech-to-text and translation system, supporting administrator proofreading and audience display.

## System Architecture

```

Microphone Audio (PC / Virtual Audio Cable)
│
▼
ASR (OpenAI Whisper) Real-Time Transcription
│
▼
English Text Stream (Real-Time)
│
▼
MT (Google Translate) Machine Translation
│
▼
Chinese Machine Translated Text Stream
│
▼
Manual Proofreading (Qt6 Admin Interface)
│
▼
Subtitle Output / TTS Playback
│
▼
Audience End (Web Text Display + TTS)

````

## Features

### Core Features
- ✅ **Real-Time Speech Recognition**: High-accuracy ASR using OpenAI Whisper
- ✅ **Automatic Translation**: Real-time translation via Google Translate API (DeepL switch supported)
- ✅ **Administrator Proofreading**: Qt6 desktop interface for real-time editing and correction of translations
- ✅ **Audience Display**: Web-based real-time subtitle display, supporting TTS (Text-to-Speech)
- ✅ **WebSocket Push**: Real-time synchronization for all clients
- ✅ **Audio Source Selection**: Supports selecting different audio input devices
- ✅ **History Management**: Complete translation history logging and export functionality

### Admin Features
- Audio input device selection
- Real-time translation stream preview
- Line-by-line editing and proofreading of translations
- Clear history function
- Connection status monitoring

### Audience Features
- Real-time subtitle display
- Automatic TTS reading (toggle on/off)
- Speech rate and volume adjustment
- Manual click-to-read for single subtitles
- Subtitle file download
- Proofreading status indicator

## Installation Steps

### 1. System Dependencies

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install portaudio19-dev python3-dev python3-pyqt6 ffmpeg
````

#### macOS

```bash
brew install portaudio ffmpeg
```

#### Windows

  - Install [Python 3.10+](https://www.python.org/downloads/)
  - Install [FFmpeg](https://ffmpeg.org/download.html)

### 2\. Python Dependencies

```bash
# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### 3\. Directory Structure

```
EzySpeechTranslate/
├── app.py              # Flask Backend Service
├── admin_gui.py        # Qt6 Administrator Interface
├── requirements.txt    # Python Dependencies
├── README.md           # This file
└── templates/
    └── index.html      # Audience Webpage
```

## Usage

### 1\. Start the System (Recommended)

```bash
# Use the cross-platform Python startup script
python start.py
```

This is the simplest way, supporting Windows/Linux/macOS, with perfect Chinese display.

The startup script provides the following options:

  - [1] Start backend service only
  - [2] Start administrator interface only
  - [3] Start both simultaneously (Recommended)
  - [4] Run system diagnostics
  - [5] Reinstall dependencies

### 2\. Manual Startup

If you need to start manually:

```bash
# Terminal 1: Start Backend
python app.py

# Terminal 2: Start Admin Interface
# PyQt6 version
python admin_gui.py

# Or PySide6 version (if PyQt6 has DLL issues)
python admin_gui_pyside.py
```

### 3\. Open Audience End

Access in a browser:

```
http://localhost:5000
```

Or access on another device (ensure on the same network):

```
http://[Server_IP]:5000
```

## Workflow

### Administrator Operations

1.  **Select Audio Device**

      - Click "Refresh Devices" to load available audio inputs
      - Select the microphone or virtual audio cable from the dropdown menu
      - To use system audio, a virtual audio cable (like VB-Cable) is recommended

2.  **Start Recording**

      - Click the "▶ Start Recording" button
      - Speak English into the microphone
      - The system will automatically detect speech and transcribe it

3.  **Proofread Translation**

      - The table on the right displays all translation history
      - Edit the text directly in the "Chinese Translation" column
      - Click the "Save" button to submit the correction
      - Proofread translations will be marked in green

4.  **Manage History**

      - Click "🗑 Clear History" to remove all records
      - All clients will synchronize the update

### Audience Operations

1.  **View Subtitles**

      - Real-time translation results are displayed automatically
      - Proofread subtitles will show an "Edited" tag

2.  **TTS Reading**

      - Click "🔊 Enable TTS" to turn on automatic reading
      - Adjust speech rate (0.5x - 2.0x)
      - Adjust volume (0% - 100%)
      - Click the 🔊 icon on a single subtitle to read it individually

3.  **Download Subtitles**

      - Click "💾 Download Subtitles" to save the complete record
      - File format is TXT, including timestamps and bilingual text

## Advanced Configuration

### Using DeepL API

To use DeepL instead of Google Translate (for higher translation quality):

1.  Register for a [DeepL API](https://www.deepl.com/pro-api) key
2.  Install the dependency:
    ```bash
    pip install deepl
    ```
3.  Modify `app.py`:
    ```python
    import deepl
    translator = deepl.Translator("YOUR_API_KEY")

    # Replace the translation section with:
    result = translator.translate_text(english_text, target_lang="ZH")
    chinese_text = result.text
    ```

### Adjusting Whisper Model

Change the model size in `app.py`:

```python
whisper_model = whisper.load_model("base")  # tiny, base, small, medium, large
```

| Model | Size | Speed | Accuracy |
|------|------|-------|----------|
| tiny | 39M | Fastest | Lower |
| base | 74M | Fast | Medium |
| small | 244M | Medium | Good |
| medium | 769M | Slow | Very Good |
| large | 1550M | Slowest | Best |

### Using Virtual Audio Cable (Capturing System Audio)

#### Windows

1.  Install [VB-CABLE](https://vb-audio.com/Cable/)
2.  Set your playback device to VB-Cable
3.  Select "VB-Cable Output" in the Admin interface

#### macOS

1.  Install [BlackHole](https://github.com/ExistentialAudio/BlackHole)
2.  Create a Multi-Output Device (in Audio MIDI Setup)
3.  Select the BlackHole device in the Admin interface

#### Linux

Use PulseAudio or PipeWire to create a virtual audio device.

## Troubleshooting

### Issue: Cannot find audio device

  - Check if the microphone is connected correctly
  - Enable microphone permissions in system settings
  - Try clicking "Refresh Devices"

### Issue: Whisper transcription is inaccurate

  - Use a larger model (like medium or large)
  - Ensure the audio is clear and reduce background noise
  - Adjust microphone gain

### Issue: Poor translation quality

  - Consider using the DeepL API
  - Manually proofread through the Admin interface

### Issue: Webpage cannot connect

  - Check firewall settings
  - Ensure the Flask service is running
  - Try using `0.0.0.0` instead of `localhost`

## Tech Stack

  - **Backend**: Flask + Flask-SocketIO + WebSocket
  - **ASR**: OpenAI Whisper
  - **Translation**: Google Translate API / DeepL API
  - **Admin GUI**: PyQt6
  - **Audience Frontend**: HTML5 + JavaScript + Socket.IO
  - **TTS**: Web Speech API

## License

MIT License

## Contribution

Issues and Pull Requests are welcome\!

## Changelog

### v1.0.0 (2025-10-18)

  - ✅ Initial release
  - ✅ Real-time ASR + Translation
  - ✅ Qt6 Administrator Interface
  - ✅ Web Audience Frontend
  - ✅ TTS Support
  - ✅ Subtitle Download Functionality



