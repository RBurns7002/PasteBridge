# PasteBridge - Clipboard to Web Notepad

A frictionless way to transfer text from your Android phone to your PC. Copy text on your phone, tap one button, and it instantly appears on a web notepad you can access from your computer.

## Quick Start

### On Your Phone
1. Download the APK from [Releases](../../releases)
2. Install and open the app
3. Note your unique code (e.g., `warmfern34`)

### On Your PC
1. Go to: **https://pastebridge.preview.emergentagent.com/api/**
2. Enter your code
3. The notepad view opens and auto-refreshes

### Transfer Text
1. Copy any text on your phone
2. Open PasteBridge app
3. Tap **"Capture & Send"**
4. Text appears on your PC!

## Features

- **Memorable Codes**: Easy-to-type codes like `suntiger42` instead of random strings
- **One-Tap Capture**: Large button to quickly send clipboard
- **Auto-Refresh**: Web notepad updates every 3 seconds
- **Copy Buttons**: Each entry has a copy button for easy pasting on PC
- **Mini Mode**: Compact view with draggable capture button
- **Session Persistence**: Your code persists between app opens

## Use Cases

- Copy a link from your phone to paste on PC
- Transfer notes, addresses, or phone numbers
- Share code snippets from mobile to desktop
- Quick text transfer without cables or cloud sync

## Installation via Obtainium

1. Install [Obtainium](https://github.com/ImranR98/Obtainium) on your Android
2. Add this repo URL: `https://github.com/YOUR_USERNAME/YOUR_REPO`
3. Obtainium will auto-update when new versions are released

## Building Locally

```bash
cd frontend
yarn install
eas build --platform android --profile preview --local
```

## Tech Stack

- **Frontend**: React Native / Expo
- **Backend**: FastAPI + MongoDB
- **Build**: EAS (Expo Application Services)

## License

MIT
