# Project Structure

## Directory Organization

```
Shorts/
├── src/                     # Main application code
│   ├── apps/               # Different app interfaces
│   │   ├── streamlit_app.py    # Web interface
│   │   ├── app.py              # Tkinter desktop app
│   │   └── app_tkinter_backup.py
│   ├── core/               # Core business logic
│   │   ├── auth_system.py      # Authentication system
│   │   └── youtube_shorts_generator.py
│   └── utils/              # Utility functions
│       ├── error_handler.py
│       └── print_error.py
├── config/                 # Configuration files
├── data/                   # Data files (JSON, TXT)
│   ├── channels.json
│   ├── users.json
│   └── pending_users.json
├── docs/                   # Documentation
├── scripts/                # Utility scripts
│   ├── api_fix_example.py
│   ├── fix_google_drive_users.py
│   └── reset_users.py
├── tests/                  # Test files
│   ├── streamlit_app_test.py
│   └── test_forms.py
├── backup/                 # Backup files
├── credentials/            # Authentication files
│   ├── credentials.json
│   └── token.json
├── main.py                 # Main entry point
├── requirements.txt
└── README.md
```

## Usage

### Run Streamlit Web App (Default)
```bash
python main.py
# or
python main.py --app streamlit
```

### Run Tkinter Desktop App
```bash
python main.py --app tkinter
```

### Direct Access
```bash
# Web app
streamlit run src/apps/streamlit_app.py

# Desktop app (from src/apps/)
python app.py
```

## File Descriptions

### Applications (`src/apps/`)
- **streamlit_app.py**: Modern web interface using Streamlit
- **app.py**: Desktop application using Tkinter
- **app_tkinter_backup.py**: Backup version of desktop app

### Core Logic (`src/core/`)
- **auth_system.py**: User authentication and authorization
- **youtube_shorts_generator.py**: YouTube Shorts content generation logic

### Utilities (`src/utils/`)
- **error_handler.py**: Error handling utilities
- **print_error.py**: Error printing utilities

### Data Files (`data/`)
- **channels.json**: Channel configuration
- **users.json**: User data
- **pending_users.json**: Users awaiting approval

### Scripts (`scripts/`)
- **api_fix_example.py**: API debugging examples
- **fix_google_drive_users.py**: Google Drive user management
- **reset_users.py**: User data reset utility

### Tests (`tests/`)
- **streamlit_app_test.py**: Streamlit application tests
- **test_forms.py**: Form validation tests