"""What the settings page shows, and in what order.

Every entry names a path that already exists in config/config.yaml. The help
text is taken from that file's own comments rather than invented; where the
file says nothing, neither does this.

Nothing here reaches a secret: server.secret_key and the values held in
config/secrets.key are refused by the endpoint, whatever this file says.

    path      dotted, as the API takes it
    label     what the field is called on screen
    kind      switch | number | text | select
    help      one line under the control, or None
    options   for select: a list of (value, label)
"""

GROUPS = (
    ("Main server",
     "The listener server: the page the congregation opens.",
     (
         ("server.host", "Host", "text", "0.0.0.0 listens on every interface.", None),
         ("server.port", "Port", "number", None, None),
         ("server.use_https", "Serve over HTTPS", "switch", None, None),
         ("server.external_url", "External URL", "text",
          "Set this when the server is reached through a tunnel or a reverse "
          "proxy, e.g. https://your-tunnel.example.com. The admin panel then "
          "uses it instead of connecting directly. Leave empty for none.", None),
         ("server.debug", "Debug mode", "switch", "Never enable in production.", None),
     )),

    ("Admin server",
     "This panel.",
     (
         ("admin_server.host", "Host", "text", None, None),
         ("admin_server.port", "Port", "number", None, None),
         ("admin_server.use_https", "Serve over HTTPS", "switch",
          "Production needs this: the Web Speech API only records on a secure "
          "origin.", None),
         ("admin_server.debug", "Debug mode", "switch", "Never enable in production.", None),
     )),

    ("Authentication",
     "The admin password and the speaker accounts live in config/secrets.key "
     "and in the accounts list; neither is editable here.",
     (
         ("authentication.enabled", "Require sign-in", "switch", None, None),
         ("authentication.admin_username", "Admin username", "text", None, None),
         ("authentication.session_timeout", "Session timeout", "number",
          "Seconds before a signed-in session expires.", None),
     )),

    ("Features",
     None,
     (
         ("features.text_to_speech", "Text-to-speech", "switch", None, None),
         ("features.real_time_sync", "Real-time sync", "switch", None, None),
         ("features.export_enabled", "Allow exports", "switch", None, None),
         ("features.dark_mode", "Dark mode toggle", "switch", None, None),
         ("features.session_analytics.enabled", "Session analytics", "switch",
          "Duration, word count, peak viewers, translation calls, TTS plays "
          "and Bible references found. Shown in Session Stats.", None),
     )),

    ("Bible references",
     "When this is on the server scans every finalized transcription for "
     "references such as \"John 3:16\", and fetches the verse from bolls.life. "
     "Verse text is shown under the caption and is not translated.",
     (
         ("features.bible_detection.enabled", "Detect Bible references", "switch", None, None),
         ("features.bible_detection.source_translation", "Source translation", "text",
          "A bolls.life code. Public domain: WEB, KJV, ASV, YLT, DARBY. "
          "Modern: NIV, NLT, ESV, NASB, CSB. Chinese traditional: CUV. "
          "An unsupported code returns nothing.", None),
         ("features.bible_detection.max_verses", "Verses per reference", "number",
          "How many verses one reference may show.", None),
         ("features.bible_detection.api_timeout", "Lookup timeout", "number",
          "Seconds to wait for bolls.life.", None),
     )),

    ("Database",
     None,
     (
         ("database.enabled", "Keep transcriptions on disk", "switch",
          "Survives a restart.", None),
         ("database.type", "Type", "select", None,
          (("sqlite", "SQLite"), ("postgresql", "PostgreSQL"), ("mysql", "MySQL"))),
         ("database.path", "SQLite file", "text", None, None),
     )),

    ("Export",
     None,
     (
         ("export.default_format", "Default format", "select", None,
          (("srt", "SRT subtitles"), ("txt", "Plain text"),
           ("json", "JSON"), ("csv", "CSV"))),
         ("export.output_directory", "Output directory", "text", None, None),
         ("export.include_timestamps", "Include timestamps", "switch", None, None),
         ("export.include_corrections", "Include corrections", "switch", None, None),
     )),

    ("Logging",
     None,
     (
         ("logging.level", "Level", "select", "INFO or WARNING in production.",
          (("DEBUG", "DEBUG"), ("INFO", "INFO"), ("WARNING", "WARNING"),
           ("ERROR", "ERROR"), ("CRITICAL", "CRITICAL"))),
         ("logging.file", "Log file", "text", None, None),
         ("logging.max_bytes", "Rotate at", "number", "Bytes per log file.", None),
         ("logging.backup_count", "Files kept", "number", None, None),
         ("logging.format", "Format", "text", "A Python logging format string.", None),
     )),

    ("Branding",
     "Off by default. When it is on, these replace the names and the mark "
     "across the three pages. Image paths are relative to app/static.",
     (
         ("oem.enabled", "Use custom branding", "switch", None, None),
         ("oem.branding.app_name", "Application name", "text", None, None),
         ("oem.branding.user_title", "Listener page title", "text", None, None),
         ("oem.branding.admin_title", "Admin page title", "text", None, None),
         ("oem.branding.login_title", "Login page title", "text", None, None),
         ("oem.assets.brand_icon", "Brand icon", "text",
          "An image path such as oem/images/logo.png.", None),
         ("oem.assets.favicon", "Favicon", "text", None, None),
         ("oem.assets.login_icon", "Login icon", "text", None, None),
         ("oem.advanced.mobile_show_title", "Show the full title on a phone", "switch", None, None),
         ("oem.advanced.icon_scale", "Icon scale", "number", "1.0 is the normal size.", None),
     )),

    ("Connections",
     None,
     (
         ("advanced.websocket.ping_timeout", "Ping timeout", "number", "Seconds.", None),
         ("advanced.websocket.ping_interval", "Ping interval", "number", "Seconds.", None),
         ("advanced.websocket.max_message_size", "Maximum message", "number", "Bytes.", None),
         ("advanced.performance.max_concurrent_translations",
          "Concurrent translations", "number", None, None),
         ("advanced.performance.translation_timeout", "Translation timeout", "number",
          "Seconds.", None),
         ("advanced.performance.cache_size", "Translation cache", "number",
          "How many translations to keep.", None),
     )),

    ("Security",
     "The blocking limits are set high on purpose: a page refresh can trip a "
     "validation check, and a low limit locks out the room.",
     (
         ("advanced.security.cors_origins", "Allowed origins", "text",
          "\"*\" in development. Name your domains in production.", None),
         ("advanced.security.rate_limit_enabled", "Rate limiting", "switch", None, None),
         ("advanced.security.max_requests_per_minute", "Requests a minute", "number",
          "Per IP address.", None),
         ("advanced.security.max_login_attempts", "Failed sign-ins before a ban",
          "number", None, None),
         ("advanced.security.login_attempt_window_minutes", "Failed sign-in window",
          "number", "Minutes before the count resets.", None),
         ("advanced.security.login_rate_limit", "Sign-in attempts a minute", "number",
          None, None),
         ("advanced.security.max_ws_connections", "WebSocket connections", "number",
          "At once, per IP address.", None),
         ("advanced.security.max_rate_violations", "Rate violations before blocking",
          "number", None, None),
         ("advanced.security.max_suspicious_patterns",
          "Suspicious requests before blocking", "number",
          "Path traversal, SQL injection and the like.", None),
         ("advanced.security.block_duration_minutes", "Block for", "number",
          "Minutes.", None),
     )),
)


def paths():
    return [f[0] for _, _, fields in GROUPS for f in fields]
