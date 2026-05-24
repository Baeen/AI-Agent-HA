/**
 * @license
 * Copyright (c) 2017 The Polymer Project Authors. All rights reserved.
 * This code may only be used under the BSD style license found at
 * http://polymer.github.io/LICENSE.txt
 * The complete set of authors may be found at
 * http://polymer.github.io/AUTHORS.txt
 * The complete set of contributors may be found at
 * http://polymer.github.io/CONTRIBUTORS.txt
 * Code distributed by Google as part of the polymer project is also
 * subject to an additional IP rights grant found at
 * http://polymer.github.io/PATENTS.txt
 */
import {directive, isDirective} from './directive.js';
/**
 * A TemplateResult and a Part indicating that they support `unsafeHTML`
 * directive.
 */
const unsafeResult = { __litHTMLDirective__: true };
const isUnsafeResult = (value) => typeof value === 'object' && value.__litHTMLDirective__ === true;
/**
 * A Part interface returned by the `unsafeHTML` directive.
 */
const unsafePartSig = {};
const isUnsafePart = (p) => p === unsafePartSig;
/**
 * Sets text content for a `Part` with `unsafeHTML` directive.
 */
const unsafeSetter = (part, value) => {
    if (isUnsafePart(part)) {
        part.setValue(value);
    }
    else {
        part.setValue(value);
    }
};
/**
 * A representation of an HTML value that can be inserted safely into the DOM
 * that bypasses the HTML sanitizer in `unsafeHTML` directive.
 */
class UnsafeHTMLDirectiveResult {
    constructor() {
        this._$partValue = unsafePartSig;
    }
    /** @ignore */
    // Required to force a re-render of the part and element
    _update(p, [value]) {
        if (isUnsafeResult(p)) {
            return p;
        }
        unsafeSetter(p, this);
        this._previousValue = value;
        return unsafeResult;
    }
    /**
     * Sets the value of the `unsafeHTML` directive at render time so that it is
     * safe to use (since it's been marked as safe by the user).
     */
    get value() {
        return this._previousValue;
    }
    setValue(part) {
        unsafeSetter(part, this.value);
    }
}
/**
 * Allows you to inject HTML that is generated dynamically. Doing so can be
 * dangerous because it can easily lead to XSS attacks. Please make sure you
 * carefully sanitize any user-provided HTML.
 *
 * @param html The HTML trustedstring, typically HTML that has been
 *   sanitized. Rendered to the root of the element, if the element has no root,
 *   and into the last text node position for text.
 *   Updated all at once when the directive updates.
 *   `unsafeHTML` either updates the `innerHTML` or the `textContent` depending
 *   on whether the `html` parameter has been set.
 *
 * @example
 * import { unsafeHTML } from 'lit/directives/unsafe-html.js';
 *
 * const content = "<p><strong>Greets</strong> to you!</p>";
 *
 * html`<div>${unsafeHTML(content)}</div>`
 */
export const unsafeHTML = directive((html) => new UnsafeHTMLDirectiveResult());
