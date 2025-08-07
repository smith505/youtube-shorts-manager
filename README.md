# YouTube Shorts Manager

A web-based application for managing multiple YouTube channels and generating AI-powered shorts scripts with real-time collaboration through Google Drive.

## Features

- **Multi-Channel Management**: Create and manage multiple YouTube channels with unique base prompts
- **AI Script Generation**: Generate YouTube Shorts scripts using Claude AI
- **Title Deduplication**: Automatically avoid repeating movie titles across scripts
- **Real-time Collaboration**: All data stored on Google Drive for instant sharing
- **User Authentication**: Advanced login system with email approval workflow
- **Password Protection**: Admin-protected prompt editing

## Setup Instructions

### Prerequisites
1. Anthropic API key for Claude AI
2. Google Cloud Project with Drive API enabled
3. OAuth 2.0 credentials for Google Drive access

### Local Development
1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up Google Drive API credentials (save as `credentials.json`)
4. Set environment variable: `export ANTHROPIC_API_KEY="your_api_key"`
5. Run: `streamlit run streamlit_app.py`

### Streamlit Cloud Deployment
1. Fork this repository to your GitHub account
2. Connect to Streamlit Cloud
3. Add secrets in app settings:
   - `ANTHROPIC_API_KEY = "your_anthropic_api_key"`
4. Deploy!

## Usage

1. **Register/Login**: Create an account (requires admin approval)
2. **Create Channels**: Add new YouTube channels with base prompts
3. **Generate Scripts**: Select a channel and generate AI-powered scripts
4. **Collaborate**: All changes sync instantly via Google Drive

## Tech Stack

- **Frontend**: Streamlit
- **AI**: Anthropic Claude API
- **Storage**: Google Drive API
- **Auth**: bcrypt password hashing
- **Deployment**: Streamlit Cloud

## File Structure

- `streamlit_app.py` - Main application
- `auth_system.py` - User authentication system
- `requirements.txt` - Python dependencies
- `.streamlit/config.toml` - Streamlit configuration
- `.streamlit/secrets.toml` - API keys (not committed)