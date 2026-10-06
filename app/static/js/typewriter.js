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
    // Already on its way to exactly this: an interim result is often sent
    // again unchanged, and restarting would only delay the end of the line.
    if (element._typewriterTimer && element._twTarget === newText) return;

    if (element._typewriterTimer) {
        cancelAnimationFrame(element._typewriterTimer);
        element._typewriterTimer = null;
    }

    // What the reader can see: the typed part, not the tail of an animation
    // cut short, which is in the element but hidden.
    const rest = element._twRest;
    const all = element.textContent;
    const shown = rest && rest.parentNode === element
        ? all.slice(0, all.length - rest.textContent.length)
        : all;
    element._twRest = null;
    element._twTarget = newText;

    // Keep whatever still matches, so a correction retypes only what changed
    // and a growing transcription only types the words that are new.
    let keep = 0;
    const most = Math.min(shown.length, newText.length);
    while (keep < most && shown.charCodeAt(keep) === newText.charCodeAt(keep)) keep++;

    if (keep === newText.length) {
        element.textContent = newText;
        element.style.minHeight = '';
        return;
    }

    // The whole line goes in at once, with the part not yet typed hidden. It
    // used to type into an element holding only the typed part, and to stop
    // that growing a line at a time it measured the finished text first: write
    // it, read the height, write the old text back, read again. Two forced
    // layouts of the whole page on every interim update, dearer the longer the
    // service ran. Laid out whole, the box is its final height from the first
    // frame and the words are where they will end up, so nothing is measured,
    // and a balanced or centred line no longer rewraps as each letter lands.
    const typed = document.createTextNode(newText.slice(0, keep));
    const tail = document.createElement('span');
    tail.setAttribute('aria-hidden', 'true');
    tail.style.visibility = 'hidden';
    const tailText = document.createTextNode(newText.slice(keep));
    tail.appendChild(tailText);
    element.replaceChildren(typed, tail);
    element._twRest = tail;

    // Driven by the clock, not by a count of characters: however long the
    // text, it is whole after durationMs, and a dropped frame is caught up
    // rather than fallen behind.
    const total = newText.length - keep;
    const started = performance.now();
    let at = keep;

    function step(now) {
        // Something else wrote the element (a thinking state, a fit that
        // measured and restored it). It is theirs now.
        if (tail.parentNode !== element) {
            element._typewriterTimer = null;
            return;
        }
        const progress = Math.min(1, (now - started) / durationMs);
        let want = keep + Math.max(1, Math.round(total * progress));
        // Never between the two halves of a surrogate pair.
        const c = newText.charCodeAt(want - 1);
        if (want < newText.length && c >= 0xD800 && c <= 0xDBFF) want++;
        if (want > at) {
            typed.data = newText.slice(0, want);
            tailText.data = newText.slice(want);
            at = want;
        }
        if (progress < 1 && at < newText.length) {
            element._typewriterTimer = requestAnimationFrame(step);
            return;
        }
        // One plain text node again, and any height held for the line handed
        // back so the next one is free to be shorter.
        element.textContent = newText;
        element._twRest = null;
        element._typewriterTimer = null;
        element.style.minHeight = '';
        if (typeof element._onTypewriterDone === 'function') {
            element._onTypewriterDone();
        }
    }

    element._typewriterTimer = requestAnimationFrame(step);
}
