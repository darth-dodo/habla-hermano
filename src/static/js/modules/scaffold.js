/**
 * Habla Hermano - Scaffold Module
 * Phase 16: Word bank and sentence starter helpers.
 */

import { getMessageInput } from './dom.js';

// ============================================
// Scaffolding Functions (Word Bank & Sentence Starter)
// ============================================

/**
 * Insert word from word bank into message input
 * @param {string} word - The word to insert (may include translation in parentheses)
 */
export function insertWord(word) {
    const messageInput = getMessageInput();
    if (!messageInput) return;

    // Extract just the word (remove translation in parentheses if present)
    const cleanWord = word.replace(/\s*\([^)]*\)\s*$/, '').trim();

    // Get cursor position
    const start = messageInput.selectionStart;
    const end = messageInput.selectionEnd;
    const text = messageInput.value;

    // Add space before if needed (not at start and previous char isn't space)
    const needsSpaceBefore = start > 0 && text[start - 1] !== ' ';
    // Add space after for easier continuation
    const insertText = (needsSpaceBefore ? ' ' : '') + cleanWord + ' ';

    // Insert at cursor position
    messageInput.value = text.slice(0, start) + insertText + text.slice(end);

    // Focus and set cursor position after inserted word
    messageInput.focus();
    const newPos = start + insertText.length;
    messageInput.selectionStart = messageInput.selectionEnd = newPos;
}

/**
 * Insert sentence starter (replaces input content)
 * @param {string} starter - The sentence starter to insert
 */
export function insertStarter(starter) {
    const messageInput = getMessageInput();
    if (!messageInput) return;

    // Replace entire input with sentence starter
    messageInput.value = starter + ' ';

    // Focus and place cursor at end
    messageInput.focus();
    messageInput.selectionStart = messageInput.selectionEnd = messageInput.value.length;
}
