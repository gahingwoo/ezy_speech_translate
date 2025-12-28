const socket = io();

// TTS Settings
let ttsEnabled = false;
let ttsRate = 1.0;
let ttsVolume = 1.0;
let selectedVoice = null;
let availableVoices = [];

// Translation Data
let translations = [];
let targetLang = 'yue';
let displayMode = 'translation'; // 'translation' or 'transcription'
let sourceLanguage = null; // ASR source language from admin

// Search State
let searchQuery = '';
let visibleTranslationIds = new Set();

// Display Settings
let fontSize = 18;
let displayLanguage = 'en'; // Interface language: 'en' or 'zh'

// Internationalization strings
const i18n = {
    en: {
        // Header
        "brand": "EzySpeech Listener",
        "waiting": "Waiting",
        "online": "Online",
        "offline": "Offline",
        "search": "Search...",
        "toggleMenu": "Toggle mobile menu",
        "toggleSearch": "Toggle search",

        // Sidebar sections
        "displaySettings": "Display Settings",
        "displayMode": "Display Mode",
        "translation": "Translation",
        "transcriptionOnly": "Transcription Only",
        "targetLanguage": "Target Language",
        "textToSpeech": "Text-to-Speech",
        "enableTTS": "Enable TTS",
        "voice": "Voice",
        "speed": "Speed",
        "volume": "Volume",
        "export": "Export",
        "format": "Format",
        "download": "Download",
        "clearDisplay": "Clear Display",
        "settings": "Settings",
        "fontSize": "Font Size",
        "darkMode": "Dark Mode",
        "resetSettings": "Reset Settings",
        "about": "About",
        "displayLanguage": "Display Language",

        // Main content
        "liveTranslations": "Live Translations",
        "liveTranscriptions": "Live Transcriptions",
        "waitingTranslations": "Waiting for translations...",
        "waitingTranscriptions": "Waiting for transcriptions...",
        "waitingDesc": "Translations will appear here in real-time",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "Made with ❤️ by",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "Feedback",
        "version": "v3.3.0 • Open Source • MIT License",

        // Buttons and actions
        "copy": "Copy",
        "speak": "Speak",
        "corrected": "Corrected",
        "close": "Close",

        // Confirmations
        "confirmReset": "Reset all settings to default?\n\nThis will:\n• Reset display mode to Translation\n• Reset language to auto-detected\n• Reset theme to Light\n• Reset font size to 18px\n• Reset TTS settings\n• Keep your translations",
        "confirmClear": "Clear all translations from display?\n\nNote: This only clears your local view.",

        // Export
        "exportTitle": "EzySpeechTranslate Export",
        "generated": "Generated",
        "totalEntries": "Total Entries",
        "endOfExport": "End of Export",

        // Search
        "searchTranslations": "Search translations",

        // Sync
        "translationsUpdated": "Translations Updated"
    },
    zh: {
        // Header
        "brand": "EzySpeech 听众端",
        "waiting": "等待中",
        "online": "在线",
        "offline": "离线",
        "search": "搜索...",
        "toggleMenu": "切换移动菜单",
        "toggleSearch": "切换搜索",

        // Sidebar sections
        "displaySettings": "显示设置",
        "displayMode": "显示模式",
        "translation": "翻译",
        "transcriptionOnly": "仅转录",
        "targetLanguage": "目标语言",
        "textToSpeech": "文本转语音",
        "enableTTS": "启用 TTS",
        "voice": "语音",
        "speed": "速度",
        "volume": "音量",
        "export": "导出",
        "format": "格式",
        "download": "下载",
        "clearDisplay": "清除显示",
        "settings": "设置",
        "fontSize": "字体大小",
        "darkMode": "深色模式",
        "resetSettings": "重置设置",
        "about": "关于",
        "displayLanguage": "界面语言",

        // Main content
        "liveTranslations": "实时翻译",
        "liveTranscriptions": "实时转录",
        "waitingTranslations": "等待翻译...",
        "waitingTranscriptions": "等待转录...",
        "waitingDesc": "翻译将实时出现在这里",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "用 ❤️ 制作，由",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "問題回饋",
        "version": "v3.3.0 • 开源 • MIT 许可证",

        // Buttons and actions
        "copy": "复制",
        "speak": "朗读",
        "corrected": "已修正",
        "close": "关闭",

        // Confirmations
        "confirmReset": "重置所有设置为默认值？\n\n这将：\n• 将显示模式重置为翻译\n• 将语言重置为自动检测\n• 将主题重置为浅色\n• 将字体大小重置为 18px\n• 重置 TTS 设置\n• 保留您的翻译",
        "confirmClear": "清除显示中的所有翻译？\n\n注意：这仅清除您的本地视图。",

        // Export
        "exportTitle": "EzySpeechTranslate 导出",
        "generated": "生成时间",
        "totalEntries": "总条目数",
        "endOfExport": "导出结束",

        // Search
        "searchTranslations": "搜索翻译",

        // Sync
        "translationsUpdated": "翻译已更新"
    },
    'zh-tw': {
        // Header
        "brand": "EzySpeech 聽眾端",
        "waiting": "等待中",
        "online": "在線",
        "offline": "離線",
        "search": "搜尋...",
        "toggleMenu": "切換移動選單",
        "toggleSearch": "切換搜尋",

        // Sidebar sections
        "displaySettings": "顯示設定",
        "displayMode": "顯示模式",
        "translation": "翻譯",
        "transcriptionOnly": "僅轉錄",
        "targetLanguage": "目標語言",
        "textToSpeech": "文字轉語音",
        "enableTTS": "啟用 TTS",
        "voice": "語音",
        "speed": "速度",
        "volume": "音量",
        "export": "匯出",
        "format": "格式",
        "download": "下載",
        "clearDisplay": "清除顯示",
        "settings": "設定",
        "fontSize": "字體大小",
        "darkMode": "深色模式",
        "resetSettings": "重置設定",
        "about": "關於",
        "displayLanguage": "介面語言",

        // Main content
        "liveTranslations": "即時翻譯",
        "liveTranscriptions": "即時轉錄",
        "waitingTranslations": "等待翻譯...",
        "waitingTranscriptions": "等待轉錄...",
        "waitingDesc": "翻譯將即時出現在這裡",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "用 ❤️ 製作，由",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "回饋",
        "version": "v3.3.0 • 開源 • MIT 許可證",

        // Buttons and actions
        "copy": "複製",
        "speak": "朗讀",
        "corrected": "已修正",
        "close": "關閉",

        // Confirmations
        "confirmReset": "重置所有設定為預設值？\n\n這將：\n• 將顯示模式重置為翻譯\n• 將語言重置為自動偵測\n• 將主題重置為淺色\n• 將字體大小重置為 18px\n• 重置 TTS 設定\n• 保留您的翻譯",
        "confirmClear": "清除顯示中的所有翻譯？\n\n注意：這僅清除您的本地視圖。",

        // Export
        "exportTitle": "EzySpeechTranslate 匯出",
        "generated": "產生時間",
        "totalEntries": "總條目數",
        "endOfExport": "匯出結束",

        // Search
        "searchTranslations": "搜尋翻譯",

        // Sync
        "translationsUpdated": "翻譯已更新"
    },
    yue: {
        // Header
        "brand": "EzySpeech 聽眾端",
        "waiting": "等緊",
        "online": "上線",
        "offline": "離線",
        "search": "搜尋...",
        "toggleMenu": "切換流動選單",
        "toggleSearch": "切換搜尋",

        // Sidebar sections
        "displaySettings": "顯示設定",
        "displayMode": "顯示模式",
        "translation": "翻譯",
        "transcriptionOnly": "淨係轉錄",
        "targetLanguage": "目標語言",
        "textToSpeech": "文字轉語音",
        "enableTTS": "啟用 TTS",
        "voice": "語音",
        "speed": "速度",
        "volume": "音量",
        "export": "匯出",
        "format": "格式",
        "download": "下載",
        "clearDisplay": "清除顯示",
        "settings": "設定",
        "fontSize": "字體大細",
        "darkMode": "深色模式",
        "resetSettings": "重置設定",
        "about": "關於",
        "displayLanguage": "介面語言",

        // Main content
        "liveTranslations": "即時翻譯",
        "liveTranscriptions": "即時轉錄",
        "waitingTranslations": "等緊翻譯...",
        "waitingTranscriptions": "等緊轉錄...",
        "waitingDesc": "翻譯會即時出現喺度",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "用 ❤️ 製作，由",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "回饋",
        "version": "v3.3.0 • 開源 • MIT 許可證",

        // Buttons and actions
        "copy": "複製",
        "speak": "朗讀",
        "corrected": "已經修正",
        "close": "關閉",

        // Confirmations
        "confirmReset": "重置所有設定為預設值？\n\n呢個會：\n• 將顯示模式重置為翻譯\n• 將語言重置為自動偵測\n• 將主題重置為淺色\n• 將字體大細重置為 18px\n• 重置 TTS 設定\n• 保留您嘅翻譯",
        "confirmClear": "清除顯示中所有翻譯？\n\n注意：呢個淨係清除您嘅本地視圖。",

        // Export
        "exportTitle": "EzySpeechTranslate 匯出",
        "generated": "產生時間",
        "totalEntries": "總條目數",
        "endOfExport": "匯出結束",

        // Search
        "searchTranslations": "搜尋翻譯",

        // Sync
        "translationsUpdated": "翻譯已經更新"
    },
    ja: {
        // Header
        "brand": "EzySpeech リスナー",
        "waiting": "待機中",
        "online": "オンライン",
        "offline": "オフライン",
        "search": "検索...",
        "toggleMenu": "モバイルメニュー切り替え",
        "toggleSearch": "検索切り替え",

        // Sidebar sections
        "displaySettings": "表示設定",
        "displayMode": "表示モード",
        "translation": "翻訳",
        "transcriptionOnly": "文字起こしのみ",
        "targetLanguage": "ターゲット言語",
        "textToSpeech": "テキスト読み上げ",
        "enableTTS": "TTS を有効化",
        "voice": "音声",
        "speed": "速度",
        "volume": "音量",
        "export": "エクスポート",
        "format": "フォーマット",
        "download": "ダウンロード",
        "clearDisplay": "表示クリア",
        "settings": "設定",
        "fontSize": "フォントサイズ",
        "darkMode": "ダークモード",
        "resetSettings": "設定リセット",
        "about": "について",
        "displayLanguage": "表示言語",

        // Main content
        "liveTranslations": "ライブ翻訳",
        "liveTranscriptions": "ライブ文字起こし",
        "waitingTranslations": "翻訳を待機中...",
        "waitingTranscriptions": "文字起こしを待機中...",
        "waitingDesc": "翻訳がリアルタイムでここに表示されます",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "❤️ で作成：",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "フィードバック",
        "version": "v3.3.0 • オープンソース • MIT ライセンス",

        // Buttons and actions
        "copy": "コピー",
        "speak": "読み上げ",
        "corrected": "修正済み",
        "close": "閉じる",

        // Confirmations
        "confirmReset": "すべての設定をデフォルトにリセットしますか？\n\nこれにより：\n• 表示モードを翻訳にリセット\n• 言語を自動検出にリセット\n• テーマをライトにリセット\n• フォントサイズを18pxにリセット\n• TTS設定をリセット\n• 翻訳を保持",
        "confirmClear": "表示からすべての翻訳をクリアしますか？\n\n注意：これはローカルビューをクリアするだけです。",

        // Export
        "exportTitle": "EzySpeechTranslate エクスポート",
        "generated": "生成日時",
        "totalEntries": "総エントリ数",
        "endOfExport": "エクスポート終了",

        // Search
        "searchTranslations": "翻訳検索",

        // Sync
        "translationsUpdated": "翻訳が更新されました"
    },
    ko: {
        // Header
        "brand": "EzySpeech 리스너",
        "waiting": "대기 중",
        "online": "온라인",
        "offline": "오프라인",
        "search": "검색...",
        "toggleMenu": "모바일 메뉴 토글",
        "toggleSearch": "검색 토글",

        // Sidebar sections
        "displaySettings": "표시 설정",
        "displayMode": "표시 모드",
        "translation": "번역",
        "transcriptionOnly": "필사만",
        "targetLanguage": "대상 언어",
        "textToSpeech": "텍스트 음성 변환",
        "enableTTS": "TTS 활성화",
        "voice": "음성",
        "speed": "속도",
        "volume": "볼륨",
        "export": "내보내기",
        "format": "형식",
        "download": "다운로드",
        "clearDisplay": "표시 지우기",
        "settings": "설정",
        "fontSize": "글꼴 크기",
        "darkMode": "다크 모드",
        "resetSettings": "설정 재설정",
        "about": "정보",
        "displayLanguage": "표시 언어",

        // Main content
        "liveTranslations": "실시간 번역",
        "liveTranscriptions": "실시간 필사",
        "waitingTranslations": "번역 대기 중...",
        "waitingTranscriptions": "필사 대기 중...",
        "waitingDesc": "번역이 실시간으로 여기에 표시됩니다",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "❤️로 제작：",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "피드백",
        "version": "v3.3.0 • 오픈소스 • MIT 라이선스",

        // Buttons and actions
        "copy": "복사",
        "speak": "읽기",
        "corrected": "수정됨",
        "close": "닫기",

        // Confirmations
        "confirmReset": "모든 설정을 기본값으로 재설정하시겠습니까？\n\n이렇게 하면：\n• 표시 모드를 번역으로 재설정\n• 언어를 자동 감지로 재설정\n• 테마를 라이트로 재설정\n• 글꼴 크기를 18px로 재설정\n• TTS 설정 재설정\n• 번역 유지",
        "confirmClear": "표시에서 모든 번역을 지우시겠습니까？\n\n참고：로컬 뷰만 지웁니다。",

        // Export
        "exportTitle": "EzySpeechTranslate 내보내기",
        "generated": "생성 시간",
        "totalEntries": "총 항목 수",
        "endOfExport": "내보내기 종료",

        // Search
        "searchTranslations": "번역 검색",

        // Sync
        "translationsUpdated": "번역이 업데이트되었습니다"
    },
    es: {
        // Header
        "brand": "Oyente EzySpeech",
        "waiting": "Esperando",
        "online": "En línea",
        "offline": "Fuera de línea",
        "search": "Buscar...",
        "toggleMenu": "Alternar menú móvil",
        "toggleSearch": "Alternar búsqueda",

        // Sidebar sections
        "displaySettings": "Configuración de pantalla",
        "displayMode": "Modo de pantalla",
        "translation": "Traducción",
        "transcriptionOnly": "Solo transcripción",
        "targetLanguage": "Idioma objetivo",
        "textToSpeech": "Texto a voz",
        "enableTTS": "Habilitar TTS",
        "voice": "Voz",
        "speed": "Velocidad",
        "volume": "Volumen",
        "export": "Exportar",
        "format": "Formato",
        "download": "Descargar",
        "clearDisplay": "Limpiar pantalla",
        "settings": "Configuración",
        "fontSize": "Tamaño de fuente",
        "darkMode": "Modo oscuro",
        "resetSettings": "Restablecer configuración",
        "about": "Acerca de",
        "displayLanguage": "Idioma de interfaz",

        // Main content
        "liveTranslations": "Traducciones en vivo",
        "liveTranscriptions": "Transcripciones en vivo",
        "waitingTranslations": "Esperando traducciones...",
        "waitingTranscriptions": "Esperando transcripciones...",
        "waitingDesc": "Las traducciones aparecerán aquí en tiempo real",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "Hecho con ❤️ por",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "Comentarios",
        "version": "v3.3.0 • Código abierto • Licencia MIT",

        // Buttons and actions
        "copy": "Copiar",
        "speak": "Hablar",
        "corrected": "Corregido",
        "close": "Cerrar",

        // Confirmations
        "confirmReset": "Restablecer toda la configuración a los valores predeterminados?\n\nEsto hará:\n• Restablecer el modo de pantalla a Traducción\n• Restablecer el idioma a detección automática\n• Restablecer el tema a Claro\n• Restablecer el tamaño de fuente a 18px\n• Restablecer la configuración TTS\n• Mantener sus traducciones",
        "confirmClear": "Limpiar todas las traducciones de la pantalla?\n\nNota: Esto limpia solo su vista local.",

        // Export
        "exportTitle": "Exportación EzySpeechTranslate",
        "generated": "Generado",
        "totalEntries": "Total de entradas",
        "endOfExport": "Fin de la exportación",

        // Search
        "searchTranslations": "Buscar traducciones",

        // Sync
        "translationsUpdated": "Traducciones actualizadas"
    },
    fr: {
        // Header
        "brand": "Auditeur EzySpeech",
        "waiting": "En attente",
        "online": "En ligne",
        "offline": "Hors ligne",
        "search": "Rechercher...",
        "toggleMenu": "Basculer le menu mobile",
        "toggleSearch": "Basculer la recherche",

        // Sidebar sections
        "displaySettings": "Paramètres d'affichage",
        "displayMode": "Mode d'affichage",
        "translation": "Traduction",
        "transcriptionOnly": "Transcription seulement",
        "targetLanguage": "Langue cible",
        "textToSpeech": "Texte vers parole",
        "enableTTS": "Activer TTS",
        "voice": "Voix",
        "speed": "Vitesse",
        "volume": "Volume",
        "export": "Exporter",
        "format": "Format",
        "download": "Télécharger",
        "clearDisplay": "Effacer l'affichage",
        "settings": "Paramètres",
        "fontSize": "Taille de police",
        "darkMode": "Mode sombre",
        "resetSettings": "Réinitialiser les paramètres",
        "about": "À propos",
        "displayLanguage": "Langue d'interface",

        // Main content
        "liveTranslations": "Traductions en direct",
        "liveTranscriptions": "Transcriptions en direct",
        "waitingTranslations": "En attente de traductions...",
        "waitingTranscriptions": "En attente de transcriptions...",
        "waitingDesc": "Les traductions apparaîtront ici en temps réel",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "Fait avec ❤️ par",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "Commentaires",
        "version": "v3.3.0 • Open source • Licence MIT",

        // Buttons and actions
        "copy": "Copier",
        "speak": "Parler",
        "corrected": "Corrigé",
        "close": "Fermer",

        // Confirmations
        "confirmReset": "Réinitialiser tous les paramètres par défaut ?\n\nCela va :\n• Réinitialiser le mode d'affichage à Traduction\n• Réinitialiser la langue à détection automatique\n• Réinitialiser le thème à Clair\n• Réinitialiser la taille de police à 18px\n• Réinitialiser les paramètres TTS\n• Conserver vos traductions",
        "confirmClear": "Effacer toutes les traductions de l'affichage ?\n\nNote : Cela efface seulement votre vue locale.",

        // Export
        "exportTitle": "Exportation EzySpeechTranslate",
        "generated": "Généré",
        "totalEntries": "Nombre total d'entrées",
        "endOfExport": "Fin de l'exportation",

        // Search
        "searchTranslations": "Rechercher des traductions",

        // Sync
        "translationsUpdated": "Traductions mises à jour"
    },
    de: {
        // Header
        "brand": "EzySpeech Zuhörer",
        "waiting": "Warten",
        "online": "Online",
        "offline": "Offline",
        "search": "Suchen...",
        "toggleMenu": "Mobiles Menü umschalten",
        "toggleSearch": "Suche umschalten",

        // Sidebar sections
        "displaySettings": "Anzeigeeinstellungen",
        "displayMode": "Anzeigemodus",
        "translation": "Übersetzung",
        "transcriptionOnly": "Nur Transkription",
        "targetLanguage": "Zielsprache",
        "textToSpeech": "Text-zu-Sprache",
        "enableTTS": "TTS aktivieren",
        "voice": "Stimme",
        "speed": "Geschwindigkeit",
        "volume": "Lautstärke",
        "export": "Exportieren",
        "format": "Format",
        "download": "Herunterladen",
        "clearDisplay": "Anzeige löschen",
        "settings": "Einstellungen",
        "fontSize": "Schriftgröße",
        "darkMode": "Dunkler Modus",
        "resetSettings": "Einstellungen zurücksetzen",
        "about": "Über",
        "displayLanguage": "Anzeigesprache",

        // Main content
        "liveTranslations": "Live-Übersetzungen",
        "liveTranscriptions": "Live-Transkriptionen",
        "waitingTranslations": "Warten auf Übersetzungen...",
        "waitingTranscriptions": "Warten auf Transkriptionen...",
        "waitingDesc": "Übersetzungen erscheinen hier in Echtzeit",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "Gemacht mit ❤️ von",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "Feedback",
        "version": "v3.3.0 • Open Source • MIT-Lizenz",

        // Buttons and actions
        "copy": "Kopieren",
        "speak": "Sprechen",
        "corrected": "Korrigiert",
        "close": "Schließen",

        // Confirmations
        "confirmReset": "Alle Einstellungen auf Standard zurücksetzen?\n\nDies wird:\n• Anzeigemodus auf Übersetzung zurücksetzen\n• Sprache auf automatische Erkennung zurücksetzen\n• Thema auf Hell zurücksetzen\n• Schriftgröße auf 18px zurücksetzen\n• TTS-Einstellungen zurücksetzen\n• Ihre Übersetzungen behalten",
        "confirmClear": "Alle Übersetzungen aus der Anzeige löschen?\n\nHinweis: Dies löscht nur Ihre lokale Ansicht.",

        // Export
        "exportTitle": "EzySpeechTranslate Export",
        "generated": "Erstellt",
        "totalEntries": "Gesamtanzahl Einträge",
        "endOfExport": "Ende des Exports",

        // Search
        "searchTranslations": "Übersetzungen suchen",

        // Sync
        "translationsUpdated": "Übersetzungen aktualisiert"
    },
    ru: {
        // Header
        "brand": "Слушатель EzySpeech",
        "waiting": "Ожидание",
        "online": "Онлайн",
        "offline": "Офлайн",
        "search": "Поиск...",
        "toggleMenu": "Переключить мобильное меню",
        "toggleSearch": "Переключить поиск",

        // Sidebar sections
        "displaySettings": "Настройки отображения",
        "displayMode": "Режим отображения",
        "translation": "Перевод",
        "transcriptionOnly": "Только транскрибация",
        "targetLanguage": "Целевой язык",
        "textToSpeech": "Текст в речь",
        "enableTTS": "Включить TTS",
        "voice": "Голос",
        "speed": "Скорость",
        "volume": "Громкость",
        "export": "Экспорт",
        "format": "Формат",
        "download": "Скачать",
        "clearDisplay": "Очистить экран",
        "settings": "Настройки",
        "fontSize": "Размер шрифта",
        "darkMode": "Темный режим",
        "resetSettings": "Сбросить настройки",
        "about": "О программе",
        "displayLanguage": "Язык интерфейса",

        // Main content
        "liveTranslations": "Живые переводы",
        "liveTranscriptions": "Живые транскрибации",
        "waitingTranslations": "Ожидание переводов...",
        "waitingTranscriptions": "Ожидание транскрибаций...",
        "waitingDesc": "Переводы будут появляться здесь в реальном времени",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "Сделано с ❤️",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "Обратная связь",
        "version": "v3.3.0 • Открытый исходный код • Лицензия MIT",

        // Buttons and actions
        "copy": "Копировать",
        "speak": "Произнести",
        "corrected": "Исправлено",
        "close": "Закрыть",

        // Confirmations
        "confirmReset": "Сбросить все настройки по умолчанию?\n\nЭто:\n• Сбросит режим отображения на Перевод\n• Сбросит язык на автоопределение\n• Сбросит тему на Светлую\n• Сбросит размер шрифта на 18px\n• Сбросит настройки TTS\n• Сохранит ваши переводы",
        "confirmClear": "Очистить все переводы с экрана?\n\nПримечание: Это очистит только ваш локальный вид.",

        // Export
        "exportTitle": "Экспорт EzySpeechTranslate",
        "generated": "Создано",
        "totalEntries": "Всего записей",
        "endOfExport": "Конец экспорта",

        // Search
        "searchTranslations": "Поиск переводов",

        // Sync
        "translationsUpdated": "Переводы обновлены"
    },
    ar: {
        // Header
        "brand": "مستمع EzySpeech",
        "waiting": "انتظار",
        "online": "متصل",
        "offline": "غير متصل",
        "search": "بحث...",
        "toggleMenu": "تبديل القائمة المحمولة",
        "toggleSearch": "تبديل البحث",

        // Sidebar sections
        "displaySettings": "إعدادات العرض",
        "displayMode": "وضع العرض",
        "translation": "الترجمة",
        "transcriptionOnly": "النص فقط",
        "targetLanguage": "اللغة المستهدفة",
        "textToSpeech": "نص إلى كلام",
        "enableTTS": "تفعيل TTS",
        "voice": "الصوت",
        "speed": "السرعة",
        "volume": "الصوت",
        "export": "تصدير",
        "format": "التنسيق",
        "download": "تحميل",
        "clearDisplay": "مسح العرض",
        "settings": "الإعدادات",
        "fontSize": "حجم الخط",
        "darkMode": "الوضع المظلم",
        "resetSettings": "إعادة تعيين الإعدادات",
        "about": "حول",
        "displayLanguage": "لغة الواجهة",

        // Main content
        "liveTranslations": "الترجمات المباشرة",
        "liveTranscriptions": "النصوص المباشرة",
        "waitingTranslations": "انتظار الترجمات...",
        "waitingTranscriptions": "انتظار النصوص...",
        "waitingDesc": "ستظهر الترجمات هنا في الوقت الفعلي",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "صنع بـ ❤️ بواسطة",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "التعليقات",
        "version": "v3.3.0 • مفتوح المصدر • رخصة MIT",

        // Buttons and actions
        "copy": "نسخ",
        "speak": "نطق",
        "corrected": "تم التصحيح",
        "close": "إغلاق",

        // Confirmations
        "confirmReset": "إعادة تعيين جميع الإعدادات إلى الافتراضي؟\n\nسيؤدي ذلك إلى:\n• إعادة تعيين وضع العرض إلى الترجمة\n• إعادة تعيين اللغة إلى الكشف التلقائي\n• إعادة تعيين المظهر إلى الفاتح\n• إعادة تعيين حجم الخط إلى 18px\n• إعادة تعيين إعدادات TTS\n• الاحتفاظ بترجماتك",
        "confirmClear": "مسح جميع الترجمات من العرض؟\n\nملاحظة: هذا يمسح عرضك المحلي فقط.",

        // Export
        "exportTitle": "تصدير EzySpeechTranslate",
        "generated": "تم إنشاؤه",
        "totalEntries": "إجمالي الإدخالات",
        "endOfExport": "نهاية التصدير",

        // Search
        "searchTranslations": "البحث في الترجمات",

        // Sync
        "translationsUpdated": "تم تحديث الترجمات"
    },
    pt: {
        // Header
        "brand": "Ouvinte EzySpeech",
        "waiting": "Aguardando",
        "online": "Online",
        "offline": "Offline",
        "search": "Pesquisar...",
        "toggleMenu": "Alternar menu móvel",
        "toggleSearch": "Alternar pesquisa",

        // Sidebar sections
        "displaySettings": "Configurações de exibição",
        "displayMode": "Modo de exibição",
        "translation": "Tradução",
        "transcriptionOnly": "Apenas transcrição",
        "targetLanguage": "Idioma alvo",
        "textToSpeech": "Texto para fala",
        "enableTTS": "Habilitar TTS",
        "voice": "Voz",
        "speed": "Velocidade",
        "volume": "Volume",
        "export": "Exportar",
        "format": "Formato",
        "download": "Baixar",
        "clearDisplay": "Limpar exibição",
        "settings": "Configurações",
        "fontSize": "Tamanho da fonte",
        "darkMode": "Modo escuro",
        "resetSettings": "Redefinir configurações",
        "about": "Sobre",
        "displayLanguage": "Idioma da interface",

        // Main content
        "liveTranslations": "Traduções ao vivo",
        "liveTranscriptions": "Transcrições ao vivo",
        "waitingTranslations": "Aguardando traduções...",
        "waitingTranscriptions": "Aguardando transcrições...",
        "waitingDesc": "As traduções aparecerão aqui em tempo real",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "Feito com ❤️ por",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "Comentários",
        "version": "v3.3.0 • Código aberto • Licença MIT",

        // Buttons and actions
        "copy": "Copiar",
        "speak": "Falar",
        "corrected": "Corrigido",
        "close": "Fechar",

        // Confirmations
        "confirmReset": "Redefinir todas as configurações para o padrão?\n\nIsso irá:\n• Redefinir o modo de exibição para Tradução\n• Redefinir o idioma para detecção automática\n• Redefinir o tema para Claro\n• Redefinir o tamanho da fonte para 18px\n• Redefinir as configurações TTS\n• Manter suas traduções",
        "confirmClear": "Limpar todas as traduções da exibição?\n\nNota: Isso limpa apenas sua visualização local.",

        // Export
        "exportTitle": "Exportação EzySpeechTranslate",
        "generated": "Gerado",
        "totalEntries": "Total de entradas",
        "endOfExport": "Fim da exportação",

        // Search
        "searchTranslations": "Pesquisar traduções",

        // Sync
        "translationsUpdated": "Traduções atualizadas"
    },
    it: {
        // Header
        "brand": "Ascoltatore EzySpeech",
        "waiting": "In attesa",
        "online": "Online",
        "offline": "Offline",
        "search": "Cerca...",
        "toggleMenu": "Attiva/disattiva menu mobile",
        "toggleSearch": "Attiva/disattiva ricerca",

        // Sidebar sections
        "displaySettings": "Impostazioni schermo",
        "displayMode": "Modalità schermo",
        "translation": "Traduzione",
        "transcriptionOnly": "Solo trascrizione",
        "targetLanguage": "Lingua target",
        "textToSpeech": "Testo a voce",
        "enableTTS": "Abilita TTS",
        "voice": "Voce",
        "speed": "Velocità",
        "volume": "Volume",
        "export": "Esporta",
        "format": "Formato",
        "download": "Scarica",
        "clearDisplay": "Cancella schermo",
        "settings": "Impostazioni",
        "fontSize": "Dimensione font",
        "darkMode": "Modalità scura",
        "resetSettings": "Ripristina impostazioni",
        "about": "Informazioni",
        "displayLanguage": "Lingua interfaccia",

        // Main content
        "liveTranslations": "Traduzioni dal vivo",
        "liveTranscriptions": "Trascrizioni dal vivo",
        "waitingTranslations": "In attesa di traduzioni...",
        "waitingTranscriptions": "In attesa di trascrizioni...",
        "waitingDesc": "Le traduzioni appariranno qui in tempo reale",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "Fatto con ❤️ da",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "Commenti",
        "version": "v3.3.0 • Open source • Licenza MIT",

        // Buttons and actions
        "copy": "Copia",
        "speak": "Parla",
        "corrected": "Corretto",
        "close": "Chiudi",

        // Confirmations
        "confirmReset": "Ripristinare tutte le impostazioni ai valori predefiniti?\n\nQuesto:\n• Ripristinerà la modalità schermo a Traduzione\n• Ripristinerà la lingua a rilevamento automatico\n• Ripristinerà il tema a Chiaro\n• Ripristinerà la dimensione font a 18px\n• Ripristinerà le impostazioni TTS\n• Manterrà le tue traduzioni",
        "confirmClear": "Cancellare tutte le traduzioni dallo schermo?\n\nNota: Questo cancella solo la tua vista locale.",

        // Export
        "exportTitle": "Esportazione EzySpeechTranslate",
        "generated": "Generato",
        "totalEntries": "Totale voci",
        "endOfExport": "Fine esportazione",

        // Search
        "searchTranslations": "Cerca traduzioni",

        // Sync
        "translationsUpdated": "Traduzioni aggiornate"
    },
    nl: {
        // Header
        "brand": "EzySpeech Luisteraar",
        "waiting": "Wachten",
        "online": "Online",
        "offline": "Offline",
        "search": "Zoeken...",
        "toggleMenu": "Mobiel menu in-/uitschakelen",
        "toggleSearch": "Zoeken in-/uitschakelen",

        // Sidebar sections
        "displaySettings": "Weergave-instellingen",
        "displayMode": "Weergavemodus",
        "translation": "Vertaling",
        "transcriptionOnly": "Alleen transcriptie",
        "targetLanguage": "Doeltaal",
        "textToSpeech": "Tekst naar spraak",
        "enableTTS": "TTS inschakelen",
        "voice": "Stem",
        "speed": "Snelheid",
        "volume": "Volume",
        "export": "Exporteren",
        "format": "Formaat",
        "download": "Downloaden",
        "clearDisplay": "Weergave wissen",
        "settings": "Instellingen",
        "fontSize": "Lettergrootte",
        "darkMode": "Donkere modus",
        "resetSettings": "Instellingen resetten",
        "about": "Over",
        "displayLanguage": "Interfacetaal",

        // Main content
        "liveTranslations": "Live vertalingen",
        "liveTranscriptions": "Live transcripties",
        "waitingTranslations": "Wachten op vertalingen...",
        "waitingTranscriptions": "Wachten op transcripties...",
        "waitingDesc": "Vertalingen verschijnen hier in realtime",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "Gemaakt met ❤️ door",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "Feedback",
        "version": "v3.3.0 • Open source • MIT-licentie",

        // Buttons and actions
        "copy": "Kopiëren",
        "speak": "Spreken",
        "corrected": "Gecorrigeerd",
        "close": "Sluiten",

        // Confirmations
        "confirmReset": "Alle instellingen terugzetten naar standaard?\n\nDit zal:\n• Weergavemodus terugzetten naar Vertaling\n• Taal terugzetten naar automatische detectie\n• Thema terugzetten naar Licht\n• Lettergrootte terugzetten naar 18px\n• TTS-instellingen resetten\n• Uw vertalingen behouden",
        "confirmClear": "Alle vertalingen van het scherm wissen?\n\nOpmerking: Dit wist alleen uw lokale weergave.",

        // Export
        "exportTitle": "EzySpeechTranslate Export",
        "generated": "Gegenereerd",
        "totalEntries": "Totaal aantal items",
        "endOfExport": "Einde van export",

        // Search
        "searchTranslations": "Vertalingen zoeken",

        // Sync
        "translationsUpdated": "Vertalingen bijgewerkt"
    },
    pl: {
        // Header
        "brand": "Słuchacz EzySpeech",
        "waiting": "Oczekiwanie",
        "online": "Online",
        "offline": "Offline",
        "search": "Szukaj...",
        "toggleMenu": "Przełącz menu mobilne",
        "toggleSearch": "Przełącz wyszukiwanie",

        // Sidebar sections
        "displaySettings": "Ustawienia wyświetlania",
        "displayMode": "Tryb wyświetlania",
        "translation": "Tłumaczenie",
        "transcriptionOnly": "Tylko transkrypcja",
        "targetLanguage": "Język docelowy",
        "textToSpeech": "Tekst na mowę",
        "enableTTS": "Włącz TTS",
        "voice": "Głos",
        "speed": "Prędkość",
        "volume": "Głośność",
        "export": "Eksportuj",
        "format": "Format",
        "download": "Pobierz",
        "clearDisplay": "Wyczyść wyświetlanie",
        "settings": "Ustawienia",
        "fontSize": "Rozmiar czcionki",
        "darkMode": "Tryb ciemny",
        "resetSettings": "Resetuj ustawienia",
        "about": "O programie",
        "displayLanguage": "Język interfejsu",

        // Main content
        "liveTranslations": "Tłumaczenia na żywo",
        "liveTranscriptions": "Transkrypcje na żywo",
        "waitingTranslations": "Oczekiwanie na tłumaczenia...",
        "waitingTranscriptions": "Oczekiwanie na transkrypcje...",
        "waitingDesc": "Tłumaczenia będą pojawiać się tutaj w czasie rzeczywistym",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "Zrobione z ❤️ przez",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "Opinie",
        "version": "v3.3.0 • Open source • Licencja MIT",

        // Buttons and actions
        "copy": "Kopiuj",
        "speak": "Mów",
        "corrected": "Poprawione",
        "close": "Zamknij",

        // Confirmations
        "confirmReset": "Zresetować wszystkie ustawienia do domyślnych?\n\nTo spowoduje:\n• Zresetowanie trybu wyświetlania do Tłumaczenia\n• Zresetowanie języka do automatycznego wykrywania\n• Zresetowanie motywu do Jasnego\n• Zresetowanie rozmiaru czcionki do 18px\n• Zresetowanie ustawień TTS\n• Zachowanie twoich tłumaczeń",
        "confirmClear": "Wyczyścić wszystkie tłumaczenia z wyświetlacza?\n\nUwaga: To czyści tylko twój lokalny widok.",

        // Export
        "exportTitle": "Eksport EzySpeechTranslate",
        "generated": "Wygenerowano",
        "totalEntries": "Łączna liczba wpisów",
        "endOfExport": "Koniec eksportu",

        // Search
        "searchTranslations": "Szukaj tłumaczeń",

        // Sync
        "translationsUpdated": "Tłumaczenia zaktualizowane"
    },
    tr: {
        // Header
        "brand": "EzySpeech Dinleyici",
        "waiting": "Bekleniyor",
        "online": "Çevrimiçi",
        "offline": "Çevrimdışı",
        "search": "Ara...",
        "toggleMenu": "Mobil menüyü değiştir",
        "toggleSearch": "Aramayı değiştir",

        // Sidebar sections
        "displaySettings": "Görüntü ayarları",
        "displayMode": "Görüntü modu",
        "translation": "Çeviri",
        "transcriptionOnly": "Sadece transkripsiyon",
        "targetLanguage": "Hedef dil",
        "textToSpeech": "Metin okuma",
        "enableTTS": "TTS'yi etkinleştir",
        "voice": "Ses",
        "speed": "Hız",
        "volume": "Ses",
        "export": "Dışa aktar",
        "format": "Biçim",
        "download": "İndir",
        "clearDisplay": "Görüntüyü temizle",
        "settings": "Ayarlar",
        "fontSize": "Yazı tipi boyutu",
        "darkMode": "Koyu mod",
        "resetSettings": "Ayarları sıfırla",
        "about": "Hakkında",
        "displayLanguage": "Arayüz dili",

        // Main content
        "liveTranslations": "Canlı çeviriler",
        "liveTranscriptions": "Canlı transkripsiyonlar",
        "waitingTranslations": "Çeviriler bekleniyor...",
        "waitingTranscriptions": "Transkripsiyonlar bekleniyor...",
        "waitingDesc": "Çeviriler burada gerçek zamanlı olarak görünecek",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "❤️ ile yapıldı:",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "Geri bildirim",
        "version": "v3.3.0 • Açık kaynak • MIT Lisansı",

        // Buttons and actions
        "copy": "Kopyala",
        "speak": "Konuş",
        "corrected": "Düzeltildi",
        "close": "Kapat",

        // Confirmations
        "confirmReset": "Tüm ayarları varsayılana sıfırlamak istiyor musunuz?\n\nBu:\n• Görüntü modunu Çeviriye sıfırlayacak\n• Dili otomatik algılamaya sıfırlayacak\n• Temayı Açığa sıfırlayacak\n• Yazı tipi boyutunu 18px'e sıfırlayacak\n• TTS ayarlarını sıfırlayacak\n• Çevirilerinizi koruyacak",
        "confirmClear": "Görüntüden tüm çevirileri temizlemek istiyor musunuz?\n\nNot: Bu sadece yerel görünümünüzü temizler.",

        // Export
        "exportTitle": "EzySpeechTranslate Dışa Aktarma",
        "generated": "Oluşturuldu",
        "totalEntries": "Toplam giriş sayısı",
        "endOfExport": "Dışa aktarma sonu",

        // Search
        "searchTranslations": "Çevirilerde ara",

        // Sync
        "translationsUpdated": "Çeviriler güncellendi"
    },
    vi: {
        // Header
        "brand": "Người nghe EzySpeech",
        "waiting": "Đang chờ",
        "online": "Trực tuyến",
        "offline": "Ngoại tuyến",
        "search": "Tìm kiếm...",
        "toggleMenu": "Chuyển đổi menu di động",
        "toggleSearch": "Chuyển đổi tìm kiếm",

        // Sidebar sections
        "displaySettings": "Cài đặt hiển thị",
        "displayMode": "Chế độ hiển thị",
        "translation": "Dịch",
        "transcriptionOnly": "Chỉ phiên âm",
        "targetLanguage": "Ngôn ngữ đích",
        "textToSpeech": "Văn bản thành giọng nói",
        "enableTTS": "Bật TTS",
        "voice": "Giọng nói",
        "speed": "Tốc độ",
        "volume": "Âm lượng",
        "export": "Xuất",
        "format": "Định dạng",
        "download": "Tải xuống",
        "clearDisplay": "Xóa hiển thị",
        "settings": "Cài đặt",
        "fontSize": "Kích thước phông chữ",
        "darkMode": "Chế độ tối",
        "resetSettings": "Đặt lại cài đặt",
        "about": "Về",
        "displayLanguage": "Ngôn ngữ giao diện",

        // Main content
        "liveTranslations": "Dịch trực tiếp",
        "liveTranscriptions": "Phiên âm trực tiếp",
        "waitingTranslations": "Đang chờ dịch...",
        "waitingTranscriptions": "Đang chờ phiên âm...",
        "waitingDesc": "Dịch sẽ xuất hiện ở đây theo thời gian thực",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "Được tạo với ❤️ bởi",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "Phản hồi",
        "version": "v3.3.0 • Mã nguồn mở • Giấy phép MIT",

        // Buttons and actions
        "copy": "Sao chép",
        "speak": "Nói",
        "corrected": "Đã sửa",
        "close": "Đóng",

        // Confirmations
        "confirmReset": "Đặt lại tất cả cài đặt về mặc định?\n\nĐiều này sẽ:\n• Đặt lại chế độ hiển thị về Dịch\n• Đặt lại ngôn ngữ về tự động phát hiện\n• Đặt lại chủ đề về Sáng\n• Đặt lại kích thước phông chữ về 18px\n• Đặt lại cài đặt TTS\n• Giữ lại bản dịch của bạn",
        "confirmClear": "Xóa tất cả bản dịch khỏi màn hình?\n\nLưu ý: Điều này chỉ xóa chế độ xem cục bộ của bạn.",

        // Export
        "exportTitle": "Xuất EzySpeechTranslate",
        "generated": "Được tạo",
        "totalEntries": "Tổng số mục",
        "endOfExport": "Kết thúc xuất",

        // Search
        "searchTranslations": "Tìm kiếm bản dịch",

        // Sync
        "translationsUpdated": "Bản dịch đã được cập nhật"
    },
    th: {
        // Header
        "brand": "ผู้ฟัง EzySpeech",
        "waiting": "กำลังรอ",
        "online": "ออนไลน์",
        "offline": "ออฟไลน์",
        "search": "ค้นหา...",
        "toggleMenu": "สลับเมนูมือถือ",
        "toggleSearch": "สลับการค้นหา",

        // Sidebar sections
        "displaySettings": "การตั้งค่าการแสดงผล",
        "displayMode": "โหมดการแสดงผล",
        "translation": "การแปล",
        "transcriptionOnly": "เฉพาะการถอดเสียง",
        "targetLanguage": "ภาษาเป้าหมาย",
        "textToSpeech": "ข้อความเป็นเสียงพูด",
        "enableTTS": "เปิดใช้งาน TTS",
        "voice": "เสียง",
        "speed": "ความเร็ว",
        "volume": "ระดับเสียง",
        "export": "ส่งออก",
        "format": "รูปแบบ",
        "download": "ดาวน์โหลด",
        "clearDisplay": "ล้างการแสดงผล",
        "settings": "การตั้งค่า",
        "fontSize": "ขนาดตัวอักษร",
        "darkMode": "โหมดมืด",
        "resetSettings": "รีเซ็ตการตั้งค่า",
        "about": "เกี่ยวกับ",
        "displayLanguage": "ภาษาอินเทอร์เฟซ",

        // Main content
        "liveTranslations": "การแปลสด",
        "liveTranscriptions": "การถอดเสียงสด",
        "waitingTranslations": "กำลังรอการแปล...",
        "waitingTranscriptions": "กำลังรอการถอดเสียง...",
        "waitingDesc": "การแปลจะปรากฏที่นี่แบบเรียลไทม์",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "สร้างด้วย ❤️ โดย",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "ข้อเสนอแนะ",
        "version": "v3.3.0 • โอเพนซอร์ส • สัญญาอนุญาต MIT",

        // Buttons and actions
        "copy": "คัดลอก",
        "speak": "พูด",
        "corrected": "แก้ไขแล้ว",
        "close": "ปิด",

        // Confirmations
        "confirmReset": "รีเซ็ตการตั้งค่าทั้งหมดเป็นค่าเริ่มต้น?\n\nสิ่งนี้จะ:\n• รีเซ็ตโหมดการแสดงผลเป็นการแปล\n• รีเซ็ตภาษาเป็นการตรวจสอบอัตโนมัติ\n• รีเซ็ตธีมเป็นสว่าง\n• รีเซ็ตขนาดตัวอักษรเป็น 18px\n• รีเซ็ตการตั้งค่า TTS\n• เก็บการแปลของคุณไว้",
        "confirmClear": "ล้างการแปลทั้งหมดออกจากการแสดงผล?\n\nหมายเหตุ: สิ่งนี้จะล้างเฉพาะมุมมองในเครื่องของคุณ.",

        // Export
        "exportTitle": "การส่งออก EzySpeechTranslate",
        "generated": "สร้างเมื่อ",
        "totalEntries": "จำนวนรายการทั้งหมด",
        "endOfExport": "สิ้นสุดการส่งออก",

        // Search
        "searchTranslations": "ค้นหาการแปล",

        // Sync
        "translationsUpdated": "การแปลได้รับการอัปเดต"
    },
    id: {
        // Header
        "brand": "Pendengar EzySpeech",
        "waiting": "Menunggu",
        "online": "Online",
        "offline": "Offline",
        "search": "Cari...",
        "toggleMenu": "Alihkan menu seluler",
        "toggleSearch": "Alihkan pencarian",

        // Sidebar sections
        "displaySettings": "Pengaturan tampilan",
        "displayMode": "Mode tampilan",
        "translation": "Terjemahan",
        "transcriptionOnly": "Hanya transkripsi",
        "targetLanguage": "Bahasa target",
        "textToSpeech": "Teks ke ucapan",
        "enableTTS": "Aktifkan TTS",
        "voice": "Suara",
        "speed": "Kecepatan",
        "volume": "Volume",
        "export": "Ekspor",
        "format": "Format",
        "download": "Unduh",
        "clearDisplay": "Bersihkan tampilan",
        "settings": "Pengaturan",
        "fontSize": "Ukuran font",
        "darkMode": "Mode gelap",
        "resetSettings": "Atur ulang pengaturan",
        "about": "Tentang",
        "displayLanguage": "Bahasa antarmuka",

        // Main content
        "liveTranslations": "Terjemahan langsung",
        "liveTranscriptions": "Transkripsi langsung",
        "waitingTranslations": "Menunggu terjemahan...",
        "waitingTranscriptions": "Menunggu transkripsi...",
        "waitingDesc": "Terjemahan akan muncul di sini secara real-time",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "Dibuat dengan ❤️ oleh",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "Umpan balik",
        "version": "v3.3.0 • Sumber terbuka • Lisensi MIT",

        // Buttons and actions
        "copy": "Salin",
        "speak": "Bicara",
        "corrected": "Diperbaiki",
        "close": "Tutup",

        // Confirmations
        "confirmReset": "Atur ulang semua pengaturan ke default?\n\nIni akan:\n• Mengatur ulang mode tampilan ke Terjemahan\n• Mengatur ulang bahasa ke deteksi otomatis\n• Mengatur ulang tema ke Terang\n• Mengatur ulang ukuran font ke 18px\n• Mengatur ulang pengaturan TTS\n• Menyimpan terjemahan Anda",
        "confirmClear": "Bersihkan semua terjemahan dari tampilan?\n\nCatatan: Ini hanya membersihkan tampilan lokal Anda.",

        // Export
        "exportTitle": "Ekspor EzySpeechTranslate",
        "generated": "Dihasilkan",
        "totalEntries": "Total entri",
        "endOfExport": "Akhir ekspor",

        // Search
        "searchTranslations": "Cari terjemahan",

        // Sync
        "translationsUpdated": "Terjemahan diperbarui"
    },
    ms: {
        // Header
        "brand": "Pendengar EzySpeech",
        "waiting": "Menunggu",
        "online": "Dalam talian",
        "offline": "Luar talian",
        "search": "Cari...",
        "toggleMenu": "Togol menu mudah alih",
        "toggleSearch": "Togol carian",

        // Sidebar sections
        "displaySettings": "Tetapan paparan",
        "displayMode": "Mod paparan",
        "translation": "Terjemahan",
        "transcriptionOnly": "Transkripsi sahaja",
        "targetLanguage": "Bahasa sasaran",
        "textToSpeech": "Teks ke pertuturan",
        "enableTTS": "Dayakan TTS",
        "voice": "Suara",
        "speed": "Kelajuan",
        "volume": "Volum",
        "export": "Eksport",
        "format": "Format",
        "download": "Muat turun",
        "clearDisplay": "Kosongkan paparan",
        "settings": "Tetapan",
        "fontSize": "Saiz fon",
        "darkMode": "Mod gelap",
        "resetSettings": "Tetapkan semula tetapan",
        "about": "Tentang",
        "displayLanguage": "Bahasa antara muka",

        // Main content
        "liveTranslations": "Terjemahan langsung",
        "liveTranscriptions": "Transkripsi langsung",
        "waitingTranslations": "Menunggu terjemahan...",
        "waitingTranscriptions": "Menunggu transkripsi...",
        "waitingDesc": "Terjemahan akan muncul di sini secara langsung",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "Dibuat dengan ❤️ oleh",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "Maklum balas",
        "version": "v3.3.0 • Sumber terbuka • Lesen MIT",

        // Buttons and actions
        "copy": "Salin",
        "speak": "Bercakap",
        "corrected": "Diperbetulkan",
        "close": "Tutup",

        // Confirmations
        "confirmReset": "Tetapkan semula semua tetapan ke lalai?\n\nIni akan:\n• Tetapkan semula mod paparan ke Terjemahan\n• Tetapkan semula bahasa ke pengesanan automatik\n• Tetapkan semula tema ke Cerah\n• Tetapkan semula saiz fon ke 18px\n• Tetapkan semula tetapan TTS\n• Kekalkan terjemahan anda",
        "confirmClear": "Kosongkan semua terjemahan dari paparan?\n\nNota: Ini hanya mengosongkan paparan tempatan anda.",

        // Export
        "exportTitle": "Eksport EzySpeechTranslate",
        "generated": "Dihasilkan",
        "totalEntries": "Jumlah entri",
        "endOfExport": "Akhir eksport",

        // Search
        "searchTranslations": "Cari terjemahan",

        // Sync
        "translationsUpdated": "Terjemahan dikemas kini"
    },
    hi: {
        // Header
        "brand": "EzySpeech श्रोता",
        "waiting": "प्रतीक्षा कर रहा है",
        "online": "ऑनलाइन",
        "offline": "ऑफलाइन",
        "search": "खोजें...",
        "toggleMenu": "मोबाइल मेनू टॉगल करें",
        "toggleSearch": "खोज टॉगल करें",

        // Sidebar sections
        "displaySettings": "प्रदर्शन सेटिंग्स",
        "displayMode": "प्रदर्शन मोड",
        "translation": "अनुवाद",
        "transcriptionOnly": "केवल ट्रांसक्रिप्शन",
        "targetLanguage": "लक्ष्य भाषा",
        "textToSpeech": "पाठ से वाणी",
        "enableTTS": "TTS सक्षम करें",
        "voice": "आवाज़",
        "speed": "गति",
        "volume": "आवाज़",
        "export": "निर्यात",
        "format": "प्रारूप",
        "download": "डाउनलोड",
        "clearDisplay": "प्रदर्शन साफ़ करें",
        "settings": "सेटिंग्स",
        "fontSize": "फॉंट आकार",
        "darkMode": "डार्क मोड",
        "resetSettings": "सेटिंग्स रीसेट करें",
        "about": "के बारे में",
        "displayLanguage": "इंटरफेस भाषा",

        // Main content
        "liveTranslations": "लाइव अनुवाद",
        "liveTranscriptions": "लाइव ट्रांसक्रिप्शन",
        "waitingTranslations": "अनुवाद की प्रतीक्षा कर रहा है...",
        "waitingTranscriptions": "ट्रांसक्रिप्शन की प्रतीक्षा कर रहा है...",
        "waitingDesc": "अनुवाद यहां रीयल-टाइम में दिखाई देंगे",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "❤️ से बनाया गया:",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "प्रतिक्रिया",
        "version": "v3.3.0 • ओपन सोर्स • MIT लाइसेंस",

        // Buttons and actions
        "copy": "कॉपी",
        "speak": "बोलें",
        "corrected": "सुधार किया गया",
        "close": "बंद करें",

        // Confirmations
        "confirmReset": "सभी सेटिंग्स को डिफ़ॉल्ट पर रीसेट करें?\n\nयह करेगा:\n• प्रदर्शन मोड को अनुवाद पर रीसेट करें\n• भाषा को ऑटो-डिटेक्शन पर रीसेट करें\n• थीम को लाइट पर रीसेट करें\n• फॉंट आकार को 18px पर रीसेट करें\n• TTS सेटिंग्स रीसेट करें\n• आपके अनुवाद रखें",
        "confirmClear": "प्रदर्शन से सभी अनुवाद साफ़ करें?\n\nनोट: यह केवल आपके स्थानीय दृश्य को साफ़ करता है।",

        // Export
        "exportTitle": "EzySpeechTranslate निर्यात",
        "generated": "जनरेट किया गया",
        "totalEntries": "कुल प्रविष्टियाँ",
        "endOfExport": "निर्यात का अंत",

        // Search
        "searchTranslations": "अनुवाद खोजें",

        // Sync
        "translationsUpdated": "अनुवाद अपडेट किए गए"
    },
    ta: {
        // Header
        "brand": "EzySpeech கேட்போர்",
        "waiting": "காத்திருக்கிறது",
        "online": "ஆன்லைன்",
        "offline": "ஆஃப்லைன்",
        "search": "தேடு...",
        "toggleMenu": "மொபைல் மெனுவை மாற்று",
        "toggleSearch": "தேடலை மாற்று",

        // Sidebar sections
        "displaySettings": "காட்சி அமைப்புகள்",
        "displayMode": "காட்சி முறை",
        "translation": "மொழிபெயர்ப்பு",
        "transcriptionOnly": "எழுத்துப்படி மட்டுமே",
        "targetLanguage": "இலக்கு மொழி",
        "textToSpeech": "உரைக்கு குரல்",
        "enableTTS": "TTS செயல்படுத்து",
        "voice": "குரல்",
        "speed": "விரைவு",
        "volume": "ஒலியளவு",
        "export": "ஏற்றுமதி",
        "format": "வடிவம்",
        "download": "பதிவிறக்கம்",
        "clearDisplay": "காட்சியை அழி",
        "settings": "அமைப்புகள்",
        "fontSize": "எழுத்துரு அளவு",
        "darkMode": "இருள் முறை",
        "resetSettings": "அமைப்புகளை மீட்டமை",
        "about": "பற்றி",
        "displayLanguage": "இடைமுக மொழி",

        // Main content
        "liveTranslations": "நேரடி மொழிபெயர்ப்புகள்",
        "liveTranscriptions": "நேரடி எழுத்துப்படிகள்",
        "waitingTranslations": "மொழிபெயர்ப்புகளுக்காக காத்திருக்கிறது...",
        "waitingTranscriptions": "எழுத்துப்படிகளுக்காக காத்திருக்கிறது...",
        "waitingDesc": "மொழிபெயர்ப்புகள் இங்கு நேரடியாகக் காட்சியளிக்கும்",

        // About modal
        "aboutTitle": "EzySpeech",
        "madeBy": "❤️ கொண்டு உருவாக்கப்பட்டது:",
        "author": "Ga Hing Woo",
        "github": "GitHub",
        "feedback": "கருத்து",
        "version": "v3.3.0 • திறந்த மூலம் • MIT உரிமம்",

        // Buttons and actions
        "copy": "நகலெடு",
        "speak": "பேசு",
        "corrected": "திருத்தப்பட்டது",
        "close": "மூடு",

        // Confirmations
        "confirmReset": "அனைத்து அமைப்புகளையும் இயல்புநிலைக்கு மீட்டமைக்கவா?\n\nஇது செய்யும்:\n• காட்சி முறையை மொழிபெயர்ப்புக்கு மீட்டமைக்கும்\n• மொழியை தானியங்கு கண்டறிதலுக்கு மீட்டமைக்கும்\n• தீமை ஒளிர்வுக்கு மீட்டமைக்கும்\n• எழுத்துரு அளவை 18pxக்கு மீட்டமைக்கும்\n• TTS அமைப்புகளை மீட்டமைக்கும்\n• உங்கள் மொழிபெயர்ப்புகளை வைத்திருக்கும்",
        "confirmClear": "காட்சியில் இருந்து அனைத்து மொழிபெயர்ப்புகளையும் அழிக்கவா?\n\nகுறிப்பு: இது உங்கள் உள்ளூர்ப் பார்வையை மட்டுமே அழிக்கிறது.",

        // Export
        "exportTitle": "EzySpeechTranslate ஏற்றுமதி",
        "generated": "உருவாக்கப்பட்டது",
        "totalEntries": "மொத்த உள்ளீடுகள்",
        "endOfExport": "ஏற்றுமதியின் முடிவு",

        // Search
        "searchTranslations": "மொழிபெயர்ப்புகளைத் தேடு",

        // Sync
        "translationsUpdated": "மொழிபெயர்ப்புகள் புதுப்பிக்கப்பட்டன"
    }
};

/* ===================================
   XSS Protection
   =================================== */

function sanitizeInput(input) {
    if (typeof input !== 'string') return '';

    // Remove HTML tags and dangerous characters
    return input
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;')
        .replace(/\//g, '&#x2F;')
        .trim();
}

function validateText(text, maxLength = 10000) {
    if (!text || typeof text !== 'string') {
        return { valid: false, error: 'Invalid input' };
    }

    const trimmed = text.trim();

    if (trimmed.length === 0) {
        return { valid: false, error: 'Text cannot be empty' };
    }

    if (trimmed.length > maxLength) {
        return { valid: false, error: `Text too long (max ${maxLength} characters)` };
    }

    // Check for suspicious patterns
    const dangerousPatterns = [
        /<script/i,
        /javascript:/i,
        /on\w+\s*=/i,
        /<iframe/i,
        /<object/i,
        /<embed/i
    ];

    for (let pattern of dangerousPatterns) {
        if (pattern.test(trimmed)) {
            return { valid: false, error: 'Invalid characters detected' };
        }
    }

    return { valid: true, text: sanitizeInput(trimmed) };
}

// TTS Language Mapping
const TTS_LANG_MAP = {
    'yue': 'zh-HK',
    'zh-cn': 'zh-CN',
    'zh-tw': 'zh-TW',
    'ja': 'ja-JP',
    'ko': 'ko-KR',
    'es': 'es-ES',
    'fr': 'fr-FR',
    'de': 'de-DE',
    'ru': 'ru-RU',
    'ar': 'ar-SA',
    'pt': 'pt-PT',
    'it': 'it-IT',
    'nl': 'nl-NL',
    'pl': 'pl-PL',
    'tr': 'tr-TR',
    'vi': 'vi-VN',
    'th': 'th-TH',
    'id': 'id-ID',
    'ms': 'ms-MY',
    'hi': 'hi-IN',
    'ta': 'ta-IN'
};

// Language Detection Mapping
const BROWSER_LANG_MAP = {
    'zh-HK': 'yue',
    'zh-MO': 'yue',
    'yue': 'yue',
    'zh-CN': 'zh-cn',
    'zh-SG': 'zh-cn',
    'zh': 'zh-cn',
    'zh-TW': 'zh-tw',
    'ja': 'ja',
    'ja-JP': 'ja',
    'ko': 'ko',
    'ko-KR': 'ko',
    'es': 'es',
    'es-ES': 'es',
    'fr': 'fr',
    'fr-FR': 'fr',
    'de': 'de',
    'de-DE': 'de',
    'ru': 'ru',
    'ru-RU': 'ru',
    'ar': 'ar',
    'pt': 'pt',
    'pt-PT': 'pt',
    'it': 'it',
    'it-IT': 'it',
    'nl': 'nl',
    'nl-NL': 'nl',
    'pl': 'pl',
    'pl-PL': 'pl',
    'tr': 'tr',
    'tr-TR': 'tr',
    'vi': 'vi',
    'vi-VN': 'vi',
    'th': 'th',
    'th-TH': 'th',
    'id': 'id',
    'id-ID': 'id',
    'ms': 'ms',
    'ms-MY': 'ms',
    'hi': 'hi',
    'hi-IN': 'hi',
    'ta': 'ta',
    'ta-IN': 'ta'
};

/* ===================================
   Auto Language Detection
   =================================== */

function detectUserLanguage() {
    const browserLang = navigator.language || navigator.userLanguage;
    console.log('🌍 Browser language detected:', browserLang);

    // Try exact match first
    if (BROWSER_LANG_MAP[browserLang]) {
        console.log('✅ Exact match found:', BROWSER_LANG_MAP[browserLang]);
        return BROWSER_LANG_MAP[browserLang];
    }

    // Try base language (e.g., 'zh' from 'zh-Hans')
    const baseLang = browserLang.split('-')[0];
    if (BROWSER_LANG_MAP[baseLang]) {
        console.log('✅ Base language match found:', BROWSER_LANG_MAP[baseLang]);
        return BROWSER_LANG_MAP[baseLang];
    }

    // Check all browser languages
    if (navigator.languages && navigator.languages.length > 0) {
        for (let lang of navigator.languages) {
            if (BROWSER_LANG_MAP[lang]) {
                console.log('✅ Alternative language match found:', BROWSER_LANG_MAP[lang]);
                return BROWSER_LANG_MAP[lang];
            }
            const base = lang.split('-')[0];
            if (BROWSER_LANG_MAP[base]) {
                console.log('✅ Alternative base language match found:', BROWSER_LANG_MAP[base]);
                return BROWSER_LANG_MAP[base];
            }
        }
    }

    // Default to Cantonese
    console.log('ℹ️ No match found, using default: yue');
    return 'yue';
}

function detectDisplayLanguage() {
    const browserLang = navigator.language || navigator.userLanguage;
    console.log('🌐 Browser language for UI detected:', browserLang);

    // Check for exact matches first
    if (browserLang in i18n) {
        console.log('✅ Exact language match found:', browserLang);
        return browserLang;
    }

    // Check for language prefixes
    const langPrefix = browserLang.split('-')[0];

    // Map common language prefixes to our supported languages
    const langMap = {
        'zh': 'zh', // Chinese (generic)
        'en': 'en', // English
        'ja': 'ja', // Japanese
        'ko': 'ko', // Korean
        'es': 'es', // Spanish
        'fr': 'fr', // French
        'de': 'de', // German
        'ru': 'ru', // Russian
        'ar': 'ar', // Arabic
        'pt': 'pt', // Portuguese
        'it': 'it', // Italian
        'nl': 'nl', // Dutch
        'pl': 'pl', // Polish
        'tr': 'tr', // Turkish
        'vi': 'vi', // Vietnamese
        'th': 'th', // Thai
        'id': 'id', // Indonesian
        'ms': 'ms', // Malay
        'hi': 'hi', // Hindi
        'ta': 'ta'  // Tamil
    };

    if (langMap[langPrefix]) {
        console.log('✅ Language prefix match found:', langPrefix, '->', langMap[langPrefix]);
        return langMap[langPrefix];
    }

    // Special handling for Chinese variants
    if (langPrefix === 'zh') {
        if (browserLang.includes('tw') || browserLang.includes('hk') || browserLang.includes('hant')) {
            return 'zh-tw';
        } else if (browserLang.includes('yue') || browserLang.includes('cantonese')) {
            return 'yue';
        } else {
            return 'zh'; // Default Chinese (Simplified)
        }
    }

    // Default to English
    console.log('ℹ️ No supported language detected, using en');
    return 'en';
}

function applyDisplayLanguage() {
    const elements = document.querySelectorAll('[data-i18n]');
    elements.forEach(element => {
        const key = element.getAttribute('data-i18n');
        if (i18n[displayLanguage] && i18n[displayLanguage][key]) {
            element.textContent = i18n[displayLanguage][key];
        }
    });

    // Update placeholders
    const placeholders = document.querySelectorAll('[data-i18n-placeholder]');
    placeholders.forEach(element => {
        const key = element.getAttribute('data-i18n-placeholder');
        if (i18n[displayLanguage] && i18n[displayLanguage][key]) {
            element.placeholder = i18n[displayLanguage][key];
        }
    });

    // Update titles
    const titles = document.querySelectorAll('[data-i18n-title]');
    titles.forEach(element => {
        const key = element.getAttribute('data-i18n-title');
        if (i18n[displayLanguage] && i18n[displayLanguage][key]) {
            element.title = i18n[displayLanguage][key];
        }
    });

    // Update connection status
    const badge = document.getElementById('statusBadge');
    if (badge) {
        const statusSpan = badge.querySelector('span:last-child');
        if (statusSpan) {
            if (badge.classList.contains('online')) {
                statusSpan.textContent = i18n[displayLanguage]['online'];
            } else if (badge.classList.contains('offline')) {
                statusSpan.textContent = i18n[displayLanguage]['offline'];
            } else {
                statusSpan.textContent = i18n[displayLanguage]['waiting'];
            }
        }
    }

    // Update theme text
    const currentTheme = document.documentElement.getAttribute('data-theme');
    updateThemeUI(currentTheme);

    console.log('🔄 Applied display language:', displayLanguage);
}

function changeDisplayLanguage() {
    const select = document.getElementById('displayLanguage');
    displayLanguage = select.value;
    localStorage.setItem('displayLanguage', displayLanguage);
    applyDisplayLanguage();
}

/* ===================================
   Settings Management
   =================================== */

function loadSettings() {
    const savedLang = localStorage.getItem('targetLang');
    const savedMode = localStorage.getItem('displayMode');
    const savedVoice = localStorage.getItem('selectedVoice');
    const savedRate = localStorage.getItem('ttsRate');
    const savedVolume = localStorage.getItem('ttsVolume');
    const savedTheme = localStorage.getItem('theme');
    const savedFontSize = localStorage.getItem('fontSize');
    const savedDisplayLanguage = localStorage.getItem('displayLanguage');

    // Load display language
    if (savedDisplayLanguage && i18n[savedDisplayLanguage]) {
        displayLanguage = savedDisplayLanguage;
        console.log('✅ Using saved display language:', savedDisplayLanguage);
    } else {
        displayLanguage = detectDisplayLanguage();
        localStorage.setItem('displayLanguage', displayLanguage);
        console.log('🔍 Auto-detected and saved display language:', displayLanguage);
    }

    document.getElementById('displayLanguage').value = displayLanguage;

    // Load display mode
    if (savedMode) {
        displayMode = savedMode;
        document.getElementById('displayMode').value = savedMode;
        updateDisplayMode();
    }

    // Auto-detect language if not saved
    if (savedLang) {
        targetLang = savedLang;
        console.log('✅ Using saved language:', savedLang);
    } else {
        targetLang = detectUserLanguage();
        localStorage.setItem('targetLang', targetLang);
        console.log('🔍 Auto-detected and saved language:', targetLang);
    }

    document.getElementById('targetLang').value = targetLang;

    if (savedRate) {
        ttsRate = parseFloat(savedRate);
        document.getElementById('rateSlider').value = ttsRate;
        document.getElementById('rateValue').textContent = ttsRate.toFixed(1) + 'x';
    }

    if (savedVolume) {
        ttsVolume = parseFloat(savedVolume);
        document.getElementById('volumeSlider').value = ttsVolume;
        document.getElementById('volumeValue').textContent = Math.round(ttsVolume * 100) + '%';
    }

    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
        updateThemeUI(savedTheme);
    }

    if (savedFontSize) {
        fontSize = parseInt(savedFontSize);
        document.getElementById('fontSizeSlider').value = fontSize;
        document.getElementById('fontSizeValue').textContent = fontSize + 'px';
        applyFontSize();
    }

    return savedVoice;
}

/* ===================================
   Voice Management
   =================================== */

function loadVoices() {
    availableVoices = speechSynthesis.getVoices();

    if (availableVoices.length === 0) {
        return;
    }

    const voiceSelect = document.getElementById('voiceSelect');
    const savedVoice = localStorage.getItem('selectedVoice');
    const ttsLang = TTS_LANG_MAP[targetLang] || targetLang;

    // Filter voices based on target language
    const matchingVoices = availableVoices.filter(function(voice) {
        const voiceLang = voice.lang.toLowerCase();
        const targetLangLower = ttsLang.toLowerCase();

        // Special handling for Chinese variants
        if (targetLang === 'yue') {
            return voiceLang === 'zh-hk' ||
                voiceLang.includes('yue') ||
                (voice.name.includes('粵語') || voice.name.includes('粤语'));
        } else if (targetLang === 'zh-cn') {
            return voiceLang === 'zh-cn' ||
                (voiceLang.startsWith('zh') &&
                    (voice.name.includes('普通话') ||
                        voice.name.includes('China mainland') ||
                        voice.name.includes('中国大陆'))) &&
                !voice.name.includes('Taiwan') &&
                !voice.name.includes('臺灣') &&
                !voice.name.includes('台灣') &&
                !voice.name.includes('Hong Kong') &&
                !voice.name.includes('香港');
        } else if (targetLang === 'zh-tw') {
            return voiceLang === 'zh-tw' ||
                (voiceLang.startsWith('zh') &&
                    (voice.name.includes('Taiwan') ||
                        voice.name.includes('臺灣') ||
                        voice.name.includes('台灣') ||
                        voice.name.includes('國語'))) &&
                !voice.name.includes('China mainland') &&
                !voice.name.includes('中国大陆') &&
                !voice.name.includes('Hong Kong') &&
                !voice.name.includes('香港');
        } else {
            return voiceLang === targetLangLower;
        }
    });

    const voicesToShow = matchingVoices.length > 0 ? matchingVoices : availableVoices;

    voiceSelect.innerHTML = '';

    // Add auto option
    const autoOption = document.createElement('option');
    autoOption.value = '';
    autoOption.textContent = '🤖 Auto (System Default)';
    voiceSelect.appendChild(autoOption);

    // Group voices by language
    const grouped = {};
    voicesToShow.forEach(function(voice) {
        const lang = voice.lang;
        if (!grouped[lang]) grouped[lang] = [];
        grouped[lang].push(voice);
    });

    // Add voice options
    Object.keys(grouped).sort().forEach(function(lang) {
        grouped[lang].forEach(function(voice) {
            const option = document.createElement('option');
            option.value = voice.name;

            // Clean voice name
            let cleanName = voice.name;
            let iterations = 0;
            while (iterations < 10) {
                const before = cleanName;
                cleanName = cleanName.replace(/\s*\([^()]*\)/g, '');
                cleanName = cleanName.replace(/\s*（[^（）]*）/g, '');
                cleanName = cleanName.replace(/\s*\[[^\[\]]*\]/g, '');
                cleanName = cleanName.replace(/\s*【[^【】]*】/g, '');
                if (before === cleanName) break;
                iterations++;
            }

            cleanName = cleanName.replace(/\s+/g, ' ').trim();

            // Remove region keywords
            const regionKeywords = [
                'India', 'Bulgaria', 'Bangladesh', 'Bosnia', 'Herzegovina',
                'Spain', 'Czechia', 'Kingdom', 'Denmark', 'United States',
                'China', 'Taiwan', 'Hong Kong', 'Japan', 'Korea',
                '中国', '台湾', '臺灣', '香港', '日本', '韩国', '大陆'
            ];

            for (let i = 0; i < regionKeywords.length; i++) {
                const keyword = regionKeywords[i];
                const regex = new RegExp('\\s+' + keyword + '$', 'i');
                cleanName = cleanName.replace(regex, '');
            }

            cleanName = cleanName.trim();
            option.textContent = cleanName;
            voiceSelect.appendChild(option);
        });
    });

    // Restore saved voice
    if (savedVoice) {
        const voiceExists = voicesToShow.find(function(v) {
            return v.name === savedVoice;
        });
        if (voiceExists) {
            voiceSelect.value = savedVoice;
            selectedVoice = voiceExists;
        } else {
            selectedVoice = null;
        }
    }

    console.log('✅ Loaded ' + availableVoices.length + ' voices, showing ' + voicesToShow.length + ' for ' + targetLang);
}

function changeVoice() {
    const voiceSelect = document.getElementById('voiceSelect');
    const voiceName = voiceSelect.value;

    if (voiceName) {
        selectedVoice = availableVoices.find(function(v) {
            return v.name === voiceName;
        });
        localStorage.setItem('selectedVoice', voiceName);
        console.log('Selected voice: ' + voiceName);
    } else {
        selectedVoice = null;
        localStorage.removeItem('selectedVoice');
        console.log('Using auto voice selection');
    }
}

function changeLanguage() {
    const select = document.getElementById('targetLang');
    targetLang = select.value;
    localStorage.setItem('targetLang', targetLang);

    loadVoices();

    // Clear cached translations
    translations.forEach(function(item) {
        item.translated = null;
        item.currentLang = null;
    });
    renderTranslations();
}

function changeDisplayMode() {
    const select = document.getElementById('displayMode');
    displayMode = select.value;
    localStorage.setItem('displayMode', displayMode);

    console.log('🔄 Display mode changed to:', displayMode);
    updateDisplayMode();
    renderTranslations();
}

function updateDisplayMode() {
    const languageGroup = document.getElementById('languageSelectGroup');
    const ttsSection = document.querySelector('.sidebar-section:has(#toggleTTS)');
    const mainTitleText = document.getElementById('mainTitleText');
    const emptyStateText = document.getElementById('emptyStateText');
    const emptyStateDesc = document.getElementById('emptyStateDesc');

    if (displayMode === 'transcription') {
        // Hide language selector and TTS in transcription mode
        if (languageGroup) languageGroup.style.display = 'none';
        if (ttsSection) ttsSection.style.display = 'none';

        // Update title
        if (mainTitleText) mainTitleText.textContent = i18n[displayLanguage]['liveTranscriptions'] || 'Live Transcriptions';

        // Update empty state
        if (emptyStateText) emptyStateText.textContent = i18n[displayLanguage]['waitingTranscriptions'] || 'Waiting for transcriptions...';
        if (emptyStateDesc) emptyStateDesc.textContent = i18n[displayLanguage]['waitingDesc'] || 'Transcriptions will appear here in real-time';

        console.log('📝 Transcription mode enabled');
    } else {
        // Show language selector and TTS in translation mode
        if (languageGroup) languageGroup.style.display = 'block';
        if (ttsSection) ttsSection.style.display = 'block';

        // Update title
        if (mainTitleText) mainTitleText.textContent = 'Live Translations';

        // Update empty state
        if (emptyStateText) emptyStateText.textContent = 'Waiting for translations...';
        if (emptyStateDesc) emptyStateDesc.textContent = 'Translations will appear here in real-time';

        console.log('🌐 Translation mode enabled');
    }
}

/* ===================================
   UI Controls
   =================================== */

function toggleMobileMenu() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const toggle = document.getElementById('mobileMenuToggle');
    const isOpen = sidebar.classList.contains('mobile-open');

    if (isOpen) {
        sidebar.classList.remove('mobile-open');
        overlay.classList.remove('active');
        toggle.classList.remove('active');
    } else {
        sidebar.classList.add('mobile-open');
        overlay.classList.add('active');
        toggle.classList.add('active');
    }
}

function closeMobileMenu() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const toggle = document.getElementById('mobileMenuToggle');

    sidebar.classList.remove('mobile-open');
    overlay.classList.remove('active');
    toggle.classList.remove('active');
}

function toggleMobileSearch() {
    const searchBar = document.getElementById('mobileSearchBar');
    const toggle = document.getElementById('mobileSearchToggle');
    const isOpen = searchBar.classList.contains('active');

    if (isOpen) {
        searchBar.classList.remove('active');
        toggle.classList.remove('active');
    } else {
        searchBar.classList.add('active');
        toggle.classList.add('active');
        const searchInput = document.getElementById('searchInputMobile');
        if (searchInput) {
            setTimeout(() => searchInput.focus(), 100);
        }
    }
}

function showAbout() {
    document.getElementById('aboutModal').classList.add('active');
}

function hideAbout(event) {
    if (!event || event.target.id === 'aboutModal' || event.target.classList.contains('about-close')) {
        document.getElementById('aboutModal').classList.remove('active');
    }
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const newTheme = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeUI(newTheme);
}

function updateThemeUI(theme) {
    const icon = document.getElementById('themeIcon');
    const text = document.getElementById('themeText');
    if (theme === 'dark') {
        if (icon) icon.textContent = '☀️';
        if (text) text.textContent = displayLanguage === 'zh' ? '浅色模式' : 'Light Mode';
    } else {
        if (icon) icon.textContent = '🌙';
        if (text) text.textContent = i18n[displayLanguage]['darkMode'];
    }
}

function resetSettings() {
    if (!confirm(i18n[displayLanguage]['confirmReset'])) {
        return;
    }

    // Clear all settings from localStorage
    localStorage.removeItem('displayMode');
    localStorage.removeItem('targetLang');
    localStorage.removeItem('selectedVoice');
    localStorage.removeItem('ttsRate');
    localStorage.removeItem('ttsVolume');
    localStorage.removeItem('theme');
    localStorage.removeItem('fontSize');
    localStorage.removeItem('displayLanguage');

    console.log('🔄 Settings reset to defaults');

    // Reload page to apply defaults
    location.reload();
}

function showSyncIndicator() {
    const indicator = document.getElementById('syncIndicator');
    indicator.classList.add('show');
    setTimeout(function() {
        indicator.classList.remove('show');
    }, 3000);
}

function updateFontSize() {
    fontSize = parseInt(document.getElementById('fontSizeSlider').value);
    document.getElementById('fontSizeValue').textContent = fontSize + 'px';
    localStorage.setItem('fontSize', fontSize);
    applyFontSize();
}

function applyFontSize() {
    const style = document.getElementById('dynamicFontStyle');
    if (style) {
        style.textContent = `.text-target { font-size: ${fontSize}px !important; }`;
    } else {
        const newStyle = document.createElement('style');
        newStyle.id = 'dynamicFontStyle';
        newStyle.textContent = `.text-target { font-size: ${fontSize}px !important; }`;
        document.head.appendChild(newStyle);
    }
}

/* ===================================
   Search Functionality
   =================================== */

function handleSearch() {
    const desktopInput = document.getElementById('searchInput');
    const mobileInput = document.getElementById('searchInputMobile');
    const clearBtn = document.getElementById('searchClear');
    const clearBtnMobile = document.getElementById('searchClearMobile');

    if (document.activeElement === desktopInput && mobileInput) {
        mobileInput.value = desktopInput.value;
    } else if (document.activeElement === mobileInput && desktopInput) {
        desktopInput.value = mobileInput.value;
    }

    const rawQuery = (desktopInput ? desktopInput.value : mobileInput.value).trim();

    // Validate and sanitize search input
    if (rawQuery.length > 500) {
        console.warn('Search query too long');
        return;
    }

    searchQuery = sanitizeInput(rawQuery).toLowerCase();

    if (searchQuery) {
        if (clearBtn) clearBtn.style.display = 'block';
        if (clearBtnMobile) clearBtnMobile.style.display = 'block';
    } else {
        if (clearBtn) clearBtn.style.display = 'none';
        if (clearBtnMobile) clearBtnMobile.style.display = 'none';
    }

    performSearch();
}

function clearSearch() {
    const desktopInput = document.getElementById('searchInput');
    const mobileInput = document.getElementById('searchInputMobile');
    const clearBtn = document.getElementById('searchClear');
    const clearBtnMobile = document.getElementById('searchClearMobile');

    if (desktopInput) desktopInput.value = '';
    if (mobileInput) mobileInput.value = '';
    searchQuery = '';

    if (clearBtn) clearBtn.style.display = 'none';
    if (clearBtnMobile) clearBtnMobile.style.display = 'none';

    performSearch();
}

function performSearch() {
    visibleTranslationIds.clear();
    let matchCount = 0;

    translations.forEach(function(item) {
        const searchableText = (item.corrected + ' ' + (item.translated || '')).toLowerCase();
        const matches = !searchQuery || searchableText.includes(searchQuery);

        if (matches) {
            visibleTranslationIds.add(item.id);
            matchCount++;
        }

        const card = document.getElementById('translation-' + item.id);
        if (card) {
            if (matches) {
                card.style.display = 'block';
                highlightSearchText(card, searchQuery);
            } else {
                card.style.display = 'none';
            }
        }
    });
}

function highlightSearchText(card, query) {
    if (!query) {
        const sourceDiv = card.querySelector('.text-source');
        const targetDiv = card.querySelector('.text-target');

        [sourceDiv, targetDiv].forEach(function(div) {
            if (!div) return;
            const originalText = div.getAttribute('data-original-text');
            if (originalText) {
                div.textContent = originalText;
                div.removeAttribute('data-original-text');
            }
        });
        return;
    }

    const sourceDiv = card.querySelector('.text-source');
    const targetDiv = card.querySelector('.text-target');

    [sourceDiv, targetDiv].forEach(function(div) {
        if (!div) return;

        const originalText = div.getAttribute('data-original-text') || div.textContent;
        if (!div.getAttribute('data-original-text')) {
            div.setAttribute('data-original-text', originalText);
        }

        const regex = new RegExp('(' + escapeRegex(query) + ')', 'gi');
        const highlightedText = originalText.replace(regex, '<mark class="search-highlight">$1</mark>');
        div.innerHTML = highlightedText;
    });
}

function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/* ===================================
   Translation Functions
   =================================== */

async function translateText(text, targetLang) {
    const cacheKey = text + '_' + targetLang;
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) return cached;

    try {
        let translationLang = targetLang;
        let translated = text;

        if (targetLang === 'yue') {
            try {
                const yueUrl = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=yue&dt=t&q=' + encodeURIComponent(text);
                const yueResponse = await fetch(yueUrl);
                const yueData = await yueResponse.json();
                if (yueData && yueData[0] && yueData[0][0] && yueData[0][0][0]) {
                    translated = yueData[0][0][0];
                }
            } catch (err) {
                console.log('Cantonese translation fallback to zh-TW');
                translationLang = 'zh-TW';
            }
        }

        if (translated === text) {
            const url = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=' + translationLang + '&dt=t&q=' + encodeURIComponent(text);
            const response = await fetch(url);
            const data = await response.json();
            if (data && data[0] && data[0][0] && data[0][0][0]) {
                translated = data[0][0][0];
            }
        }

        sessionStorage.setItem(cacheKey, translated);
        return translated;
    } catch (error) {
        console.error('Translation error:', error);
        return text + ' (translation failed)';
    }
}

/* ===================================
   Text-to-Speech Functions
   =================================== */

function speakText(text) {
    if (!('speechSynthesis' in window)) {
        alert('Your browser does not support text-to-speech');
        return;
    }

    speechSynthesis.cancel();

    // Validate and sanitize text before speaking
    const validation = validateText(text, 5000);
    if (!validation.valid) {
        console.error('Invalid text for TTS:', validation.error);
        return;
    }

    const cleanText = validation.text.replace(/\s*\([^)]*\)\s*/g, '').trim();
    if (!cleanText) return;

    const utterance = new SpeechSynthesisUtterance(cleanText);
    const ttsLang = TTS_LANG_MAP[targetLang] || targetLang;
    utterance.lang = ttsLang;
    utterance.rate = ttsRate;
    utterance.volume = ttsVolume;

    if (selectedVoice) {
        utterance.voice = selectedVoice;
        console.log('Using selected voice: ' + selectedVoice.name);
    } else {
        const voices = speechSynthesis.getVoices();
        let autoVoice = voices.find(function(v) {
            return v.lang === ttsLang;
        });
        if (!autoVoice) {
            const baseLang = ttsLang.split('-')[0];
            autoVoice = voices.find(function(v) {
                return v.lang.startsWith(baseLang + '-');
            });
        }
        if (autoVoice) {
            utterance.voice = autoVoice;
            console.log('Using auto voice: ' + autoVoice.name);
        }
    }

    utterance.onerror = function(e) {
        console.error('TTS error:', e);
    };

    speechSynthesis.speak(utterance);
}

function toggleTTS() {
    ttsEnabled = !ttsEnabled;
    const btn = document.getElementById('toggleTTS');
    const icon = btn.querySelector('span:first-child');
    const text = btn.querySelector('span:last-child');

    if (ttsEnabled) {
        btn.classList.add('active');
        icon.textContent = '🔇';
        text.textContent = 'Disable TTS';
    } else {
        btn.classList.remove('active');
        icon.textContent = '🔊';
        text.textContent = 'Enable TTS';
        speechSynthesis.cancel();
    }
}

function updateRate() {
    ttsRate = parseFloat(document.getElementById('rateSlider').value);
    document.getElementById('rateValue').textContent = ttsRate.toFixed(1) + 'x';
    localStorage.setItem('ttsRate', ttsRate);
}

function updateVolume() {
    ttsVolume = parseFloat(document.getElementById('volumeSlider').value);
    document.getElementById('volumeValue').textContent = Math.round(ttsVolume * 100) + '%';
    localStorage.setItem('ttsVolume', ttsVolume);
}

/* ===================================
   Copy Functionality
   =================================== */

function copyTranslation(id) {
    const idStr = String(id);
    const item = translations.find(function(t) {
        return String(t.id) === idStr;
    });

    if (!item) {
        console.error('Translation not found:', id, 'Available IDs:', translations.map(t => t.id));
        return;
    }

    // In transcription mode, copy original text; in translation mode, copy translated text
    const textToCopy = displayMode === 'transcription' ? item.corrected : (item.translated || item.corrected);
    console.log('Attempting to copy:', textToCopy);

    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(textToCopy).then(function() {
            console.log('Copied successfully with clipboard API');
            showCopyFeedback(id);
        }).catch(function(err) {
            console.log('Clipboard API failed, trying fallback:', err);
            copyWithFallback(id, textToCopy);
        });
    } else {
        console.log('Clipboard API not available, using fallback');
        copyWithFallback(id, textToCopy);
    }
}

function copyWithFallback(id, text) {
    try {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.top = '0';
        textArea.style.left = '0';
        textArea.style.width = '2em';
        textArea.style.height = '2em';
        textArea.style.padding = '0';
        textArea.style.border = 'none';
        textArea.style.outline = 'none';
        textArea.style.boxShadow = 'none';
        textArea.style.background = 'transparent';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();

        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);

        if (successful) {
            console.log('Copied successfully with fallback method');
            showCopyFeedback(id);
        } else {
            console.error('Fallback copy failed');
            alert('Failed to copy to clipboard');
        }
    } catch (err) {
        console.error('Fallback copy error:', err);
        alert('Failed to copy to clipboard');
    }
}

function showCopyFeedback(id) {
    const btn = document.getElementById('copy-btn-' + id);
    if (btn) {
        const span = btn.querySelector('span');
        const originalText = span.textContent;

        span.textContent = '✓';
        btn.classList.add('copied');

        setTimeout(function() {
            span.textContent = originalText;
            btn.classList.remove('copied');
        }, 2000);
    }
}

/* ===================================
   Rendering Functions
   =================================== */

async function renderTranslations() {
    const list = document.getElementById('translationsList');
    const itemCount = document.getElementById('itemCount');
    if (itemCount) itemCount.textContent = translations.length;

    if (translations.length === 0) {
        const emptyText = displayMode === 'transcription' ? 'Waiting for transcriptions...' : 'Waiting for translations...';
        const emptyDesc = displayMode === 'transcription' ?
            'Transcriptions will appear here in real-time' :
            'Translations will appear here in real-time';

        list.innerHTML = '\
            <div class="empty-state">\
                <div class="empty-icon">💬</div>\
                <div>' + emptyText + '</div>\
                <small style="display: block; margin-top: 0.5rem; opacity: 0.7;">\
                    ' + emptyDesc + '\
                </small>\
            </div>\
        ';
        return;
    }

    const reversed = [...translations].reverse();
    const items = await Promise.all(
        reversed.map(item => createTranslationHTML(item))
    );

    list.innerHTML = items.join('');

    if (searchQuery) {
        performSearch();
    }
}

async function addTranslation(data) {
    const list = document.getElementById('translationsList');
    const emptyState = list.querySelector('.empty-state');

    if (emptyState) {
        list.innerHTML = '';
    }

    const html = await createTranslationHTML(data);
    list.innerHTML = html + list.innerHTML;
    document.getElementById('itemCount').textContent = translations.length;

    if (searchQuery) {
        performSearch();
    }
}

async function createTranslationHTML(item) {
    const itemId = 'translation-' + item.id;

    // Get source language from item
    const itemSourceLang = item.source_language || item.language || 'en';

    // In transcription mode, only show original text
    if (displayMode === 'transcription') {
        const correctedBadge = item.is_corrected ? '<span class="card-badge">✓ Corrected</span>' : '';
        const correctedClass = item.is_corrected ? 'corrected' : '';

        return '\
            <div class="translation-card ' + correctedClass + '" id="' + itemId + '">\
                <div class="card-header">\
                    <span class="card-time">' + item.timestamp + '</span>\
                    <div class="card-actions">\
                        ' + correctedBadge + '\
                        <button class="copy-btn" id="copy-btn-' + item.id + '" data-translation-id="' + item.id + '" onclick="copyTranslationFromButton(this)" title="Copy transcription">\
                            <span>📋</span>\
                        </button>\
                    </div>\
                </div>\
                <div class="text-target" data-original-text="' + escapeHtml(item.corrected) + '">' + escapeHtml(item.corrected) + '</div>\
            </div>\
        ';
    }

    // Translation mode logic
    // Map source language codes
    const langMap = {
        'en': 'en',
        'zh': 'zh-cn',
        'yue': 'yue',
        'ja': 'ja',
        'ko': 'ko',
        'es': 'es',
        'fr': 'fr',
        'de': 'de',
        'ru': 'ru',
        'ar': 'ar',
        'pt': 'pt',
        'it': 'it',
        'nl': 'nl',
        'pl': 'pl',
        'tr': 'tr',
        'vi': 'vi',
        'th': 'th',
        'id': 'id',
        'ms': 'ms',
        'hi': 'hi',
        'ta': 'ta'
    };

    const normalizedSourceLang = langMap[itemSourceLang] || itemSourceLang;
    const normalizedTargetLang = targetLang;

    // If source language matches target language, don't show source text
    const shouldHideSource = normalizedSourceLang === normalizedTargetLang;

    if (!item.translated || item.currentLang !== targetLang) {
        item.currentLang = targetLang;

        setTimeout(async () => {
            const elem = document.getElementById(itemId);
            if (elem) {
                const targetDiv = elem.querySelector('.text-target');
                if (targetDiv) {
                    targetDiv.innerHTML = '<span class="loading">Translating...</span>';
                }
            }
        }, 0);

        item.translated = await translateText(item.corrected, targetLang);

        setTimeout(() => {
            const elem = document.getElementById(itemId);
            if (elem) {
                const targetDiv = elem.querySelector('.text-target');
                if (targetDiv) {
                    targetDiv.textContent = item.translated;
                    targetDiv.setAttribute('data-original-text', item.translated);
                }
            }
        }, 0);
    }

    const correctedBadge = item.is_corrected ? '<span class="card-badge">✓ Corrected</span>' : '';
    const correctedClass = item.is_corrected ? 'corrected' : '';
    const translatedText = item.translated || 'Translating...';

    // Show source text only if languages don't match
    const sourceHtml = shouldHideSource ? '' :
        '<div class="text-source" data-original-text="' + escapeHtml(item.corrected) + '">' + escapeHtml(item.corrected) + '</div>';

    return '\
        <div class="translation-card ' + correctedClass + '" id="' + itemId + '">\
            <div class="card-header">\
                <span class="card-time">' + item.timestamp + '</span>\
                <div class="card-actions">\
                    ' + correctedBadge + '\
                    <button class="copy-btn" id="copy-btn-' + item.id + '" data-translation-id="' + item.id + '" onclick="copyTranslationFromButton(this)" title="Copy translation">\
                        <span>📋</span>\
                    </button>\
                    <button class="tts-icon" onclick="speakText(this.getAttribute(\'data-text\'))" data-text="' + escapeHtml(translatedText) + '" title="Speak translation">🔊</button>\
                </div>\
            </div>\
            ' + sourceHtml + '\
            <div class="text-target" data-original-text="' + escapeHtml(translatedText) + '">' + escapeHtml(translatedText) + '</div>\
        </div>\
    ';
}

function copyTranslationFromButton(button) {
    const id = button.getAttribute('data-translation-id');
    console.log('Copy button clicked with ID:', id);
    copyTranslation(id);
}

// Keep escapeHtml for backward compatibility, but use sanitizeInput for consistency
function escapeHtml(text) {
    return sanitizeInput(text);
}

/* ===================================
   Data Management
   =================================== */

function clearLocal() {
    if (translations.length === 0) return;
    if (confirm(i18n[displayLanguage]['confirmClear'])) {
        translations = [];
        renderTranslations();
        clearSearch();
    }
}

function exportData() {
    if (translations.length === 0) {
        alert('No translations to export');
        return;
    }

    const format = document.getElementById('exportFormat').value;
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);

    let content, mimeType, extension;

    switch(format) {
        case 'json':
            content = exportAsJSON();
            mimeType = 'application/json';
            extension = 'json';
            break;
        case 'csv':
            content = exportAsCSV();
            mimeType = 'text/csv';
            extension = 'csv';
            break;
        case 'srt':
            content = exportAsSRT();
            mimeType = 'text/plain';
            extension = 'srt';
            break;
        default:
            content = exportAsTXT();
            mimeType = 'text/plain';
            extension = 'txt';
    }

    const blob = new Blob([content], { type: mimeType + ';charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'EzySpeech_' + targetLang + '_' + timestamp + '.' + extension;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function exportAsTXT() {
    let content = '═══════════════════════════════════════════════════\n';
    content += '       EzySpeechTranslate Export\n';
    content += '═══════════════════════════════════════════════════\n\n';
    content += 'Generated: ' + new Date().toLocaleString() + '\n';

    if (displayMode === 'transcription') {
        content += 'Mode: Transcription Only\n';
    } else {
        const langName = document.getElementById('targetLang').selectedOptions[0].text;
        content += 'Mode: Translation\n';
        content += 'Target Language: ' + langName + '\n';
    }

    content += 'Total Entries: ' + translations.length + '\n\n';
    content += '═══════════════════════════════════════════════════\n\n';

    translations.forEach((item, index) => {
        content += '[' + String(index + 1).padStart(3, '0') + '] ' + item.timestamp + '\n';
        if (item.is_corrected) {
            content += '      [✓ CORRECTED]\n';
        }

        if (displayMode === 'transcription') {
            content += '\n      Transcription:\n      ' + item.corrected + '\n';
        } else {
            content += '\n      Original:\n      ' + item.corrected + '\n';
            content += '\n      Translation (' + targetLang.toUpperCase() + '):\n      ' + (item.translated || 'Not translated') + '\n';
        }

        content += '\n' + '─'.repeat(55) + '\n\n';
    });

    content += '═══════════════════════════════════════════════════\n';
    content += '              End of Export\n';
    content += '═══════════════════════════════════════════════════\n';

    return content;
}

function exportAsJSON() {
    const exportData = {
        metadata: {
            generated: new Date().toISOString(),
            mode: displayMode,
            targetLanguage: displayMode === 'translation' ? targetLang : null,
            totalEntries: translations.length
        },
        translations: translations.map(item => ({
            id: item.id,
            timestamp: item.timestamp,
            original: item.corrected,
            translated: displayMode === 'translation' ? (item.translated || null) : null,
            isCorrected: item.is_corrected
        }))
    };

    return JSON.stringify(exportData, null, 2);
}

function exportAsCSV() {
    let csv = '';

    if (displayMode === 'transcription') {
        csv = 'ID,Timestamp,Transcription,Is Corrected\n';
        translations.forEach(item => {
            const row = [
                item.id,
                item.timestamp,
                '"' + (item.corrected || '').replace(/"/g, '""') + '"',
                item.is_corrected ? 'Yes' : 'No'
            ];
            csv += row.join(',') + '\n';
        });
    } else {
        csv = 'ID,Timestamp,Original,Translation,Is Corrected\n';
        translations.forEach(item => {
            const row = [
                item.id,
                item.timestamp,
                '"' + (item.corrected || '').replace(/"/g, '""') + '"',
                '"' + (item.translated || '').replace(/"/g, '""') + '"',
                item.is_corrected ? 'Yes' : 'No'
            ];
            csv += row.join(',') + '\n';
        });
    }

    return csv;
}

function exportAsSRT() {
    let srt = '';

    translations.forEach((item, index) => {
        const sequenceNumber = index + 1;
        const time = item.timestamp;
        const startTime = time + ',000';

        const [hours, minutes, seconds] = time.split(':').map(Number);
        const totalSeconds = hours * 3600 + minutes * 60 + seconds + 3;
        const endHours = Math.floor(totalSeconds / 3600);
        const endMinutes = Math.floor((totalSeconds % 3600) / 60);
        const endSeconds = totalSeconds % 60;
        const endTime = String(endHours).padStart(2, '0') + ':' +
            String(endMinutes).padStart(2, '0') + ':' +
            String(endSeconds).padStart(2, '0') + ',000';

        srt += sequenceNumber + '\n';
        srt += startTime + ' --> ' + endTime + '\n';

        // In transcription mode, use original; in translation mode, use translated
        const text = displayMode === 'transcription' ? item.corrected : (item.translated || item.corrected);
        srt += text + '\n\n';
    });

    return srt;
}

/* ===================================
   Scroll to Top
   =================================== */

const scrollToTopBtn = document.getElementById('scrollToTopBtn');
const mainSection = document.querySelector('.pf-c-page__main-section');

if (mainSection) {
    mainSection.addEventListener('scroll', function() {
        if (mainSection.scrollTop > 300) {
            scrollToTopBtn.classList.add('show');
        } else {
            scrollToTopBtn.classList.remove('show');
        }
    });
}

function scrollToTop() {
    if (mainSection) {
        mainSection.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    }
}

/* ===================================
   Event Listeners
   =================================== */

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        hideAbout();
        closeMobileMenu();
    }
});

/* ===================================
   Socket.IO Events
   =================================== */

socket.on('connect', () => {
    console.log('Connected to server');
    const badge = document.getElementById('statusBadge');
    badge.className = 'connection-badge online';
    badge.querySelector('span:last-child').textContent = i18n[displayLanguage]['online'];
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
    const badge = document.getElementById('statusBadge');
    badge.className = 'connection-badge offline';
    badge.querySelector('span:last-child').textContent = i18n[displayLanguage]['offline'];
});

socket.on('history', async (history) => {
    console.log('Received history:', history.length, 'items');
    translations = history;
    await renderTranslations();
});

socket.on('new_translation', async (data) => {
    console.log('Received new translation:', data);
    translations.push(data);
    await addTranslation(data);

    if (ttsEnabled && data.translated) {
        speakText(data.translated);
    }
});

socket.on('translation_corrected', async (data) => {
    console.log('Translation corrected:', data.id);
    const index = translations.findIndex(t => t.id === data.id);
    if (index !== -1) {
        translations[index] = data;
        await renderTranslations();
    }
});

socket.on('order_updated', async (data) => {
    console.log('Order updated from admin:', data.translations.length, 'items');
    translations = data.translations;
    await renderTranslations();
    showSyncIndicator();
});

socket.on('history_cleared', () => {
    console.log('History cleared');
    translations = [];
    renderTranslations();
    clearSearch();
});

/* ===================================
   Initialization
   =================================== */

if ('speechSynthesis' in window) {
    loadSettings();
    applyDisplayLanguage();

    speechSynthesis.addEventListener('voiceschanged', loadVoices);
    loadVoices();
    setTimeout(loadVoices, 100);

    console.log('✅ EzySpeechTranslate Ready with Auto Language Detection');
} else {
    console.warn('⚠️ Speech Synthesis not supported');
}

console.log('✅ EzySpeechTranslate Client Ready');