# OEM Images - Custom Branding Assets

Store your custom branding images here.

## Directory Structure

```
app/static/oem/images/
├── logo.png          # Brand icon for UI pages
├── favicon.ico       # Website favicon
└── [other images]
```

## How to Use

### 1. Add Your Images

Place your custom images in this directory:
- `logo.png` - Your brand/company logo
- `favicon.ico` - Your website favicon
- Any other custom images

### 2. Update config.yaml

Reference your images in `/config/config.yaml`:

```yaml
oem:
  enabled: true
  assets:
    brand_icon: "oem/images/logo.png"      # Used on user/admin pages
    favicon: "oem/images/favicon.ico"      # Website favicon
    login_icon: "oem/images/logo.png"      # Used on login page
```

## Image Format Guidelines

- **Brand Icon (logo.png)**
  - Format: PNG, SVG, or JPEG
  - Recommended size: 48x48 to 256x256 pixels
  - Should have transparent background for best appearance

- **Favicon (favicon.ico)**
  - Format: ICO format (traditional) or your favicon format
  - Size: 16x16, 32x32, or 64x64 pixels
  - Recommended: 32x32 pixels

- **Login Icon (login_icon)**
  - Format: PNG, SVG, or JPEG
  - Can be same as brand_icon or different
  - Recommended size: 64x64 to 256x256 pixels

## Path Detection

The frontend automatically detects image paths:

- **Relative paths** (e.g., `"oem/images/logo.png"`):
  - Automatically prefixed with `/static/`
  - Served as: `/static/oem/images/logo.png`

- **Emoji** (e.g., `"🎙️"`):
  - Used directly as text

- **Absolute paths** (e.g., `"/static/oem/images/logo.png"`):
  - Used as-is

## Troubleshooting

### Images Not Showing

1. **Check file exists**: Verify your image file is in this directory
2. **Check path in config**: Verify the path in `config.yaml` matches your filename
3. **Clear browser cache**: Sometimes browsers cache old images
4. **Check file format**: Ensure file format is supported (PNG, JPEG, SVG, ICO)

### Example - Adding a Custom Logo

```bash
# Copy your logo to the images directory
cp /path/to/your/logo.png /Users/woo/PycharmProjects/ezy_speech_translate/app/static/oem/images/

# Update config.yaml
# - Change: brand_icon: "oem/images/logo.png"
# - If your file is my-logo.png, the config stays the same
# - If your file has different name, update: brand_icon: "oem/images/my-logo.png"
```

## Additional Notes

- All paths are case-sensitive on Linux/Mac
- Restart your Flask server after adding new images
- Images are served via Flask's static file handler
- Maximum file size depends on your server configuration

For more information, see `OEM_REFERENCE.md` in the project root.
