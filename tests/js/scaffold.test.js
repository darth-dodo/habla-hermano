import { describe, it, expect, beforeEach, beforeAll, vi } from 'vitest';
import { insertWord, insertStarter, initScaffoldDelegation } from '../../src/static/js/modules/scaffold.js';

describe('scaffold module', () => {
    let input;

    beforeEach(() => {
        document.body.innerHTML = `<textarea id="message-input"></textarea>`;
        input = document.getElementById('message-input');
    });

    // ============================================
    // insertWord
    // ============================================

    describe('insertWord', () => {
        it('inserts word at cursor position', () => {
            input.value = 'Yo como';
            input.selectionStart = input.selectionEnd = 7; // end of "Yo como"

            insertWord('pan');

            expect(input.value).toBe('Yo como pan ');
        });

        it('inserts word in the middle of existing text', () => {
            input.value = 'Yo arroz';
            input.selectionStart = input.selectionEnd = 3; // after "Yo "

            insertWord('como');

            expect(input.value).toBe('Yo como arroz');
        });

        it('strips translation in parentheses from the word', () => {
            input.value = '';
            input.selectionStart = input.selectionEnd = 0;

            insertWord('hola (hello)');

            expect(input.value).toBe('hola ');
        });

        it('strips translation with spaces before parentheses', () => {
            input.value = '';
            input.selectionStart = input.selectionEnd = 0;

            insertWord('buenos dias  (good morning)');

            expect(input.value).toBe('buenos dias ');
        });

        it('adds space before when cursor is not at start and no preceding space', () => {
            input.value = 'Hola';
            input.selectionStart = input.selectionEnd = 4; // after "Hola"

            insertWord('amigo');

            expect(input.value).toBe('Hola amigo ');
        });

        it('does not add space before at start of empty input', () => {
            input.value = '';
            input.selectionStart = input.selectionEnd = 0;

            insertWord('Hola');

            expect(input.value).toBe('Hola ');
        });

        it('does not add space before when preceding character is already a space', () => {
            input.value = 'Hola ';
            input.selectionStart = input.selectionEnd = 5; // after "Hola "

            insertWord('amigo');

            expect(input.value).toBe('Hola amigo ');
        });

        it('replaces selected text with the word', () => {
            input.value = 'Yo quiero agua';
            input.selectionStart = 10; // start of "agua"
            input.selectionEnd = 14;   // end of "agua"

            insertWord('leche');

            expect(input.value).toBe('Yo quiero leche ');
        });

        it('focuses the input after insertion', () => {
            const focusSpy = vi.spyOn(input, 'focus');

            insertWord('hola');

            expect(focusSpy).toHaveBeenCalled();
        });

        it('places cursor after the inserted word', () => {
            input.value = '';
            input.selectionStart = input.selectionEnd = 0;

            insertWord('gracias');

            // "gracias " is 8 chars, cursor should be at position 8
            expect(input.selectionStart).toBe(8);
            expect(input.selectionEnd).toBe(8);
        });

        it('does nothing when message-input element does not exist', () => {
            document.body.innerHTML = '';

            // Should not throw
            expect(() => insertWord('hola')).not.toThrow();
        });
    });

    // ============================================
    // insertStarter
    // ============================================

    describe('insertStarter', () => {
        it('replaces entire input content with the starter', () => {
            input.value = 'some existing text';

            insertStarter('Me gusta');

            expect(input.value).toBe('Me gusta ');
        });

        it('adds a trailing space after the starter', () => {
            input.value = '';

            insertStarter('Quiero');

            expect(input.value).toBe('Quiero ');
            expect(input.value.endsWith(' ')).toBe(true);
        });

        it('focuses input and places cursor at end', () => {
            const focusSpy = vi.spyOn(input, 'focus');

            insertStarter('Puedo');

            expect(focusSpy).toHaveBeenCalled();
            expect(input.selectionStart).toBe(6); // "Puedo " length
            expect(input.selectionEnd).toBe(6);
        });

        it('does nothing when message-input element does not exist', () => {
            document.body.innerHTML = '';

            expect(() => insertStarter('Hola')).not.toThrow();
        });
    });

    // ============================================
    // initScaffoldDelegation (event delegation)
    // ============================================

    describe('initScaffoldDelegation', () => {
        beforeAll(() => {
            initScaffoldDelegation();
        });

        beforeEach(() => {
            document.body.innerHTML = `
                <textarea id="message-input"></textarea>
                <div id="scaffold-area">
                    <button data-insert-word="hola (hello)">hola (hello)</button>
                    <button data-insert-starter="Me llamo">Me llamo...</button>
                </div>
            `;
            input = document.getElementById('message-input');
            input.selectionStart = input.selectionEnd = 0;
        });

        it('inserts word when data-insert-word button is clicked', () => {
            const wordBtn = document.querySelector('[data-insert-word]');
            wordBtn.click();

            expect(input.value).toBe('hola ');
        });

        it('inserts starter when data-insert-starter button is clicked', () => {
            const starterBtn = document.querySelector('[data-insert-starter]');
            starterBtn.click();

            expect(input.value).toBe('Me llamo ');
        });

        it('handles dynamically added buttons', () => {
            const newBtn = document.createElement('button');
            newBtn.setAttribute('data-insert-word', 'gracias (thank you)');
            newBtn.textContent = 'gracias (thank you)';
            document.getElementById('scaffold-area').appendChild(newBtn);

            newBtn.click();

            expect(input.value).toBe('gracias ');
        });

        it('does not interfere with non-scaffold buttons', () => {
            const otherBtn = document.createElement('button');
            otherBtn.textContent = 'Other';
            document.body.appendChild(otherBtn);

            otherBtn.click();

            expect(input.value).toBe('');
        });
    });
});
