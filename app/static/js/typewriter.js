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

    // Stop any animation already running on this element.
    if (element._typewriterTimer) {
        cancelAnimationFrame(element._typewriterTimer);
        element._typewriterTimer = null;
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
    
    // Hold the taller of the two heights so the box does not jump about while
    // the characters arrive. Held only for the animation: keeping it after was
    // permanent, so any line that had once been long stayed that tall for the
    // rest of the session even when it was emptied, and a stage measuring
    // itself read as full when it was not.
    element.style.minHeight = Math.max(newHeight, currentHeight) + 'px';
    
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
        element.style.minHeight = '';
        return;
    }

    // Driven by the clock, not by a count of characters. One timer per
    // character floored at 10ms, which made the duration a function of the
    // length: a 260 character sentence took two and a half seconds instead of
    // the 400ms asked for, and on a live feed the next interim update arrived
    // before it finished and restarted it, so the end of a long sentence was
    // never reached at all. Now however long the text, it is whole after
    // durationMs, and a dropped frame is caught up rather than fallen behind.
    const base = element.textContent;
    const total = charsToType.length;
    const started = performance.now();
    let charIdx = 0;

    function step(now) {
        const progress = Math.min(1, (now - started) / durationMs);
        const want = Math.max(1, Math.round(total * progress));
        if (want > charIdx) {
            element.textContent = base + charsToType.slice(0, want).join('');
            charIdx = want;
        }
        if (progress < 1) {
            element._typewriterTimer = requestAnimationFrame(step);
            return;
        }
        // Exactly the text asked for, whatever the arithmetic rounded to, and
        // the height handed back so the next line is free to be shorter.
        element.textContent = base + charsToType.join('');
        element._typewriterTimer = null;
        element.style.minHeight = '';
        if (typeof element._onTypewriterDone === 'function') {
            element._onTypewriterDone();
        }
    }

    element._typewriterTimer = requestAnimationFrame(step);
}
