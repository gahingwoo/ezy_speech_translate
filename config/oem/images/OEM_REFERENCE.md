# OEM Configuration Reference

## Overview

All OEM (branding/customization) settings are configured in a single place: **`config/config.yaml`**

## Configuration Location

Edit the `oem` section in `config/config.yaml`:

```yaml
oem:
  # Enable/Disable OEM customization
  enabled: true
  
  branding:
    user_title: "EzySpeech User"      # User interface title
    admin_title: "EzySpeech Admin"    # Admin panel title
    login_title: "EzySpeech Admin"    # Login page title
    app_name: "EzySpeech"             # Application name
  
  assets:
    brand_icon: "🎙️"                  # Emoji or image path like "images/oem/logo.png"
    favicon: ""                        # Path like "images/oem/favicon.ico"
    login_icon: "🎙️"                  # Emoji or image path
  
  advanced:
    mobile_show_title: true            # Show full title on mobile
    icon_scale: 1.0                    # Icon scale multiplier
```

## Quick Start

### Enable/Disable OEM
```yaml
oem:
  enabled: true   # Enable custom branding
  # or
  enabled: false  # Use default branding
```

### Customize Titles
```yaml
oem:
  enabled: true
  branding:
    user_title: "MyApp - User"
    admin_title: "MyApp - Admin"
    app_name: "MyApp"
```

### Add Custom Images
1. Place images in `config/oem/images/`
2. Reference in config:
```yaml
oem:
  assets:
    brand_icon: "images/oem/logo.png"
    favicon: "images/oem/favicon.ico"
```

## Implementation

- **Manager**: `app/oem_manager.py`
- **Frontend Loader**: `app/static/js/oem-loader.js`
- **API Endpoint**: `GET /api/oem-config`

## File Structure

```
app/
├── oem_manager.py              # OEM configuration handler
├── static/
│   └── js/
│       └── oem-loader.js       # Frontend loader
└── user/server.py, admin/server.py  # Servers using OEM

config/
├── config.yaml                 # All OEM settings here
└── oem/
    └── images/                 # Store brand assets (logo, favicon, etc.)
```

## Features

- ✅ Single configuration file (`config.yaml`)
- ✅ Easy enable/disable toggle
- ✅ Support for emoji or image icons
- ✅ Dynamic favicon support
- ✅ Mobile-responsive
- ✅ No code changes needed
- ✅ Frontend auto-applies on page load

## API Response

When OEM is enabled:
```json
GET /api/oem-config
{
  "branding": {
    "user_title": "MyApp User",
    "admin_title": "MyApp Admin",
    "app_name": "MyApp"
  },
  "assets": {
    "brand_icon": "🎙️",
    "favicon": "",
    "login_icon": "🎙️"
  },
  "advanced": {
    "mobile_show_title": true,
    "icon_scale": 1.0
  }
}
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| OEM not working | Check `oem.enabled: true` in config.yaml |
| Settings not applied | Server was not restarted after config changes |
| Images not loading | Verify image path is relative to `/static` folder |
| Favicon not showing | Hard refresh browser (Ctrl+Shift+R) |

