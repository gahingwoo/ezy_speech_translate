# EzySpeechTranslate Multi-language Guide
# 多语言支持指南

## Overview / 概览

The new multi-language version supports:
新的多语言版本支持：

- **Source Language / 源语言**: English (detected by Whisper)
- **Target Languages / 目标语言**: All Google Translate supported languages (100+)
- **Translation Location / 翻译位置**: Client-side (reduces server load)
- **Admin Interface / 管理界面**: English & Chinese bilingual

## 🌍 Supported Languages / 支持的语言

### Popular Languages / 常用语言

| Language | Code | 语言 | 代码 |
|----------|------|------|------|
| Chinese (Simplified) | zh-cn | 简体中文 | zh-cn |
| Chinese (Traditional) | zh-tw | 繁体中文 | zh-tw |
| Spanish | es | 西班牙语 | es |
| French | fr | 法语 | fr |
| German | de | 德语 | de |
| Japanese | ja | 日语 | ja |
| Korean | ko | 韩语 | ko |
| Russian | ru | 俄语 | ru |
| Arabic | ar | 阿拉伯语 | ar |
| Portuguese | pt | 葡萄牙语 | pt |
| Italian | it | 意大利语 | it |
| Dutch | nl | 荷兰语 | nl |
| Polish | pl | 波兰语 | pl |
| Turkish | tr | 土耳其语 | tr |
| Vietnamese | vi | 越南语 | vi |
| Thai | th | 泰语 | th |
| Indonesian | id | 印尼语 | id |
| Malay | ms | 马来语 | ms |
| Hindi | hi | 印地语 | hi |

### All 100+ Languages / 全部 100+ 种语言

The client interface supports all languages available in Google Translate API.
客户端界面支持 Google Translate API 中所有可用的语言。

---

## 🚀 Quick Start / 快速开始

### Start Multi-language Version / 启动多语言版本

```bash
# Start backend / 启动后端
python app_multilang.py

# Start admin interface / 启动管理界面
python admin_gui_multilang.py

# Or use the launcher / 或使用启动器
python start.py
```

### Access Client / 访问客户端

Open browser / 打开浏览器:
```
http://localhost:5000
```

---

## 💡 Key Features / 核心特性

### 1. Client-side Translation / 客户端翻译

**Architecture / 架构:**
```
Server (Whisper ASR) → English Text
                         ↓
                    Broadcast to Clients
                         ↓
Client (Google Translate API) → Target Language
```

**Benefits / 优势:**
- ✅ Reduces server load / 减轻服务器负载
- ✅ Each user can choose their own language / 每个用户可选择自己的语言
- ✅ Real-time language switching / 实时切换语言
- ✅ Scales to unlimited concurrent translations / 支持无限并发翻译

### 2. Real-time Language Switching / 实时语言切换

Users can change target language at any time without restarting.
用户可以随时更改目标语言，无需重启。

```javascript
// All history will be automatically re-translated
// 所有历史记录将自动重新翻译
```

### 3. Translation Caching / 翻译缓存

Translations are cached in browser session storage to avoid repeated API calls.
翻译结果缓存在浏览器会话存储中，避免重复 API 调用。

### 4. Bilingual Admin Interface / 双语管理界面

The admin interface supports English and Chinese.
管理界面支持英文和中文。

**Switch Language / 切换语言:**
- Use dropdown in control panel / 使用控制面板中的下拉菜单
- Or start with: `python admin_gui_multilang.py --lang cn`

---

## 📖 Usage Guide / 使用指南

### For Administrators / 管理员使用

1. **Select Language / 选择语言**
   ```bash
   python admin_gui_multilang.py --lang en  # English
   python admin_gui_multilang.py --lang cn  # 中文
   ```

2. **Start Recording / 开始录制**
   - Select audio device / 选择音频设备
   - Click "Start Recording" / 点击"开始录制"
   - Speak in English / 用英语讲话

3. **Correct Translations / 校对翻译**
   - Edit the English source text / 编辑英文原文
   - Click "Save" / 点击"保存"
   - All clients will receive the correction / 所有客户端将收到校对

### For Audience / 听众使用

1. **Open Client Page / 打开客户端页面**
   ```
   http://localhost:5000
   ```

2. **Select Target Language / 选择目标语言**
   - Use the dropdown menu / 使用下拉菜单
   - Choose your preferred language / 选择您的首选语言
   - Translation happens automatically / 自动翻译

3. **Enable TTS (Optional) / 启用 TTS（可选）**
   - Click "Enable TTS" / 点击"启用 TTS"
   - Adjust speed and volume / 调整速度和音量
   - Hear translations in your language / 听到您语言的翻译

4. **Download Subtitles / 下载字幕**
   - Click "Download" / 点击"下载"
   - Saves bilingual subtitle file / 保存双语字幕文件

---

## 🔧 Technical Details / 技术细节

### Translation Flow / 翻译流程

```
1. Microphone → PyAudio
2. Audio Data → Whisper ASR
3. English Text → WebSocket Broadcast
4. Each Client → Google Translate API
5. Target Language → Display & TTS
```

### API Usage / API 使用

**Client-side Translation Code:**
```javascript
async function translateText(text, targetLang) {
    const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=${targetLang}&dt=t&q=${encodeURIComponent(text)}`;
    const response = await fetch(url);
    const data = await response.json();
    return data[0][0][0];
}
```

### Caching Strategy / 缓存策略

```javascript
// Cache key format
const cacheKey = `${sourceText}_${targetLang}`;

// Stored in sessionStorage
sessionStorage.setItem(cacheKey, translatedText);

// Retrieved on subsequent requests
const cached = sessionStorage.getItem(cacheKey);
```

---

## 🎯 Use Cases / 使用场景

### Case 1: International Conference / 国际会议

**Setup:**
- Speaker speaks English / 演讲者说英语
- Attendees from multiple countries / 来自多个国家的与会者

**Solution:**
- Each attendee selects their language / 每位与会者选择自己的语言
- Real-time translation on their device / 在其设备上实时翻译
- No need for multiple translators / 无需多个翻译员

### Case 2: Online Webinar / 在线研讨会

**Setup:**
- Host presents in English / 主持人用英语演示
- Global audience / 全球观众

**Solution:**
- Share the client URL / 分享客户端 URL
- Users choose their language / 用户选择自己的语言
- Automatic subtitle generation / 自动生成字幕

### Case 3: Lecture Recording / 讲座录制

**Setup:**
- English lecture / 英语讲座
- Need subtitles in multiple languages / 需要多种语言的字幕

**Solution:**
- Record the session / 录制会话
- Download subtitles in each language / 下载各种语言的字幕
- Post-process for video / 后期处理视频

---

## ⚙️ Configuration / 配置

### Add More Languages / 添加更多语言

Edit `templates/index_multilang.html`:

```html
<select class="select-box" id="targetLang">
    <option value="NEW_LANG_CODE">Language Name</option>
    <!-- Add your language here -->
</select>
```

### Change Default Language / 更改默认语言

```javascript
let targetLang = 'zh-cn'; // Change this to your default
```

### Adjust Translation Speed / 调整翻译速度

The translation happens asynchronously. You can adjust the loading indicator:

```javascript
setTimeout(async () => {
    // Translation code here
}, 0); // Adjust delay if needed
```

---

## 🐛 Troubleshooting / 故障排除

### Problem: Translation Not Working / 翻译不工作

**Symptoms / 症状:**
- Shows "Translating..." indefinitely / 一直显示"翻译中..."
- No translated text appears / 没有翻译文本出现

**Solutions / 解决方案:**

1. **Check Network Connection / 检查网络连接**
   ```bash
   # Test Google Translate API
   curl "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-cn&dt=t&q=hello"
   ```

2. **Clear Browser Cache / 清除浏览器缓存**
   ```javascript
   // Open browser console
   sessionStorage.clear();
   location.reload();
   ```

3. **Check CORS / 检查跨域**
   - Google Translate API should work from any origin
   - If blocked, use a CORS proxy

### Problem: TTS Not Speaking / TTS 不朗读

**Solutions / 解决方案:**

1. **Check Browser Support / 检查浏览器支持**
   ```javascript
   if ('speechSynthesis' in window) {
       console.log('TTS supported');
   }
   ```

2. **Select Voice / 选择语音**
   - Some languages may not have voices installed
   - Try different browsers (Chrome, Edge have best support)

3. **Adjust Language Code / 调整语言代码**
   ```javascript
   // Edit getLangCode() function
   const langMap = {
       'your-lang': 'correct-voice-code'
   };
   ```

### Problem: Admin Interface Not Loading / 管理界面不加载

**Solutions / 解决方案:**

```bash
# Install PyQt6
pip install PyQt6

# Or use PySide6
pip install PySide6

# Or use the original single-language version
python admin_gui.py
```

---

## 📊 Performance Optimization / 性能优化

### Reduce API Calls / 减少 API 调用

**Current Implementation / 当前实现:**
```javascript
// Caching in sessionStorage
const cached = sessionStorage.getItem(cacheKey);
if (cached) return cached;
```

**Advanced Optimization / 高级优化:**
```javascript
// Use IndexedDB for persistent caching
const db = await openDB('translations', 1);
const cached = await db.get('cache', cacheKey);
```

### Batch Translations / 批量翻译

For large history, translate in batches:

```javascript
async function batchTranslate(items, batchSize = 5) {
    for (let i = 0; i < items.length; i += batchSize) {
        const batch = items.slice(i, i + batchSize);
        await Promise.all(batch.map(item => translateText(item)));
    }
}
```

### Preload Common Translations / 预加载常用翻译

```javascript
// Preload common phrases
const commonPhrases = ['Hello', 'Thank you', 'Welcome'];
commonPhrases.forEach(phrase => translateText(phrase, targetLang));
```

---

## 🔒 Privacy & Security / 隐私与安全

### Data Flow / 数据流

**Server / 服务器:**
- Only processes English audio and text / 仅处理英语音频和文本
- No translation data stored / 不存储翻译数据
- No logging of translated content / 不记录翻译内容

**Client / 客户端:**
- Translation happens in browser / 翻译在浏览器中进行
- Uses Google Translate public API / 使用 Google Translate 公共 API
- Cached in sessionStorage (cleared on close) / 缓存在 sessionStorage（关闭时清除）

### Alternative: Self-hosted Translation / 替代方案：自托管翻译

If you need complete privacy:

```python
# Use local translation models
from transformers import MarianMTModel, MarianTokenizer

model_name = 'Helsinki-NLP/opus-mt-en-zh'
tokenizer = MarianTokenizer.from_pretrained(model_name)
model = MarianMTModel.from_pretrained(model_name)

def translate(text):
    inputs = tokenizer(text, return_tensors="pt")
    outputs = model.generate(**inputs)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)
```

---

## 📚 API Reference / API 参考

### Backend Endpoints / 后端端点

```
GET  /api/languages      - Get supported languages list
GET  /api/status         - Get system status
GET  /api/devices        - Get audio devices
POST /api/start          - Start recording
POST /api/stop           - Stop recording
GET  /api/history        - Get translation history
POST /api/correct        - Correct translation
POST /api/clear          - Clear history
```

### WebSocket Events / WebSocket 事件

**Server → Client:**
```
connect              - Connection established
disconnect           - Connection lost
history              - Initial history data
new_translation      - New English text
translation_corrected - Text corrected by admin
history_cleared      - History cleared
```

---

## 🎓 Advanced Usage / 高级用法

### Custom Language Selection / 自定义语言选择

Add a language selector based on user preference:

```javascript
// Detect browser language
const browserLang = navigator.language.slice(0, 2);
document.getElementById('targetLang').value = browserLang;
```

### Multiple Target Languages / 多目标语言

Display translations in multiple languages simultaneously:

```javascript
const targetLanguages = ['zh-cn', 'es', 'fr'];
for (const lang of targetLanguages) {
    const translated = await translateText(text, lang);
    displayTranslation(lang, translated);
}
```

### Export Multi-language Subtitles / 导出多语言字幕

```javascript
function downloadMultiLang() {
    const languages = ['zh-cn', 'es', 'fr'];
    languages.forEach(async lang => {
        const content = await generateSubtitles(lang);
        downloadFile(`subtitles_${lang}.txt`, content);
    });
}
```

---

## 📝 Development Notes / 开发说明

### File Structure / 文件结构

```
New Files / 新文件:
├── app_multilang.py              # Multi-language backend
├── admin_gui_multilang.py        # Bilingual admin GUI
└── templates/
    └── index_multilang.html      # Multi-language client

Original Files (still compatible) / 原始文件（仍兼容）:
├── app.py
├── admin_gui.py
└── templates/
    └── index.html
```

### Migration Guide / 迁移指南

**From single-language to multi-language:**

1. Backup current data / 备份当前数据
2. Start new backend: `python app_multilang.py`
3. Connect with new client: `http://localhost:5000`
4. All existing features still work / 所有现有功能仍然有效

---

## 🌟 Future Enhancements / 未来增强

- [ ] Offline translation support / 离线翻译支持
- [ ] Custom translation models / 自定义翻译模型
- [ ] Real-time collaboration / 实时协作
- [ ] Mobile app integration / 移动应用集成
- [ ] Video subtitle overlay / 视频字幕叠加
- [ ] Multi-speaker detection / 多说话人检测
- [ ] Translation quality scoring / 翻译质量评分

---

## 📞 Support / 支持

For issues or questions / 如有问题或疑问:
- Run diagnostics / 运行诊断: `python diagnose.py`
- Check documentation / 查看文档: `README.md`
- Report issues / 报告问题: GitHub Issues

---

**Enjoy multi-language real-time translation! / 享受多语言实时翻译！** 🎉