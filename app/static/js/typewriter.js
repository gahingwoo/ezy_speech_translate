/* Text that arrives the way it was said.
 *
 * A line does not appear all at once when someone speaks it, and a screen that
 * snaps a finished sentence into place reads as a machine catching up. This
 * types the part that is new: when a correction extends what is already shown
 * only the extension is typed, so a growing interim transcription grows rather
 * than being retyped from the start every time a word lands.
 *
 * Both the listener and the screen at the front of the room use it.
 */

function animateTextChange(element, currentText, newText, durationMs = 300) {
    if (currentText === newText) {
        // Already showing same text
        element.textContent = newText;
        return;
    }

    // Clear any existing animation timer
    if (element._typewriterTimer) {
        clearTimeout(element._typewriterTimer);
    }

    // Get what's currently displayed in the element
    const displayedText = element.textContent;
    
    // ✅ Smart height adjustment: measure new text height and only increase, never decrease
    const currentHeight = element.offsetHeight;
    
    // Temporarily show full new text to measure its height
    const oldContent = element.textContent;
    element.textContent = newText;
    const newHeight = element.offsetHeight;
    element.textContent = oldContent; // Restore old content for animation
    
    // Set min-height if content would grow (prevent shrinking)
    if (newHeight > currentHeight) {
        element.style.minHeight = newHeight + 'px';
    } else {
        // Keep current height as minimum if new content is smaller
        element.style.minHeight = currentHeight + 'px';
    }
    
    // Smart diff: find common prefix to avoid clearing text when correcting
    let commonPrefixLen = 0;
    for (let i = 0; i < Math.min(displayedText.length, newText.length); i++) {
        if (displayedText[i] === newText[i]) {
            commonPrefixLen++;
        } else {
            break;
        }
    }

    let charsToType = [];
    
    // ✅ If there's a common prefix, only update the differing part
    if (commonPrefixLen > 0) {
        // Keep the common prefix, remove suffix that changed, add new suffix
        element.textContent = displayedText.substring(0, commonPrefixLen);
        // Add new characters after the common prefix
        for (let i = commonPrefixLen; i < newText.length; i++) {
            charsToType.push(newText[i]);
        }
    } else if (displayedText && newText.startsWith(displayedText)) {
        // ✅ Pure extension case - just add new characters
        for (let i = displayedText.length; i < newText.length; i++) {
            charsToType.push(newText[i]);
        }
    } else {
        // ❌ Text completely different - clear and retype all
        element.textContent = '';
        for (let i = 0; i < newText.length; i++) {
            charsToType.push(newText[i]);
        }
    }

    // If nothing new to type, just update and return
    if (charsToType.length === 0) {
        element.textContent = newText;
        return;
    }

    // Typewriter effect: type out new characters one by one
    let charIdx = 0;
    const charDurationMs = Math.max(10, durationMs / charsToType.length);  // Adaptive speed based on new chars count
    
    function typeNextChar() {
        if (charIdx < charsToType.length) {
            // Append new character instead of replacing entire text
            element.textContent += charsToType[charIdx];
            charIdx++;
            element._typewriterTimer = setTimeout(typeNextChar, charDurationMs);
        }
    }
    
    // Start typewriter animation
    typeNextChar();
}
