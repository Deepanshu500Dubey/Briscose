import '@testing-library/jest-dom/vitest';

// jsdom doesn't implement the Pointer Capture APIs or scrollIntoView that
// Radix UI's interactive primitives (DropdownMenu, Select, etc.) probe
// before opening — without these no-op polyfills, @testing-library/user-event
// clicks on a Radix trigger silently fail to open the menu under jsdom.
if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false;
}
if (!Element.prototype.setPointerCapture) {
  Element.prototype.setPointerCapture = () => {};
}
if (!Element.prototype.releasePointerCapture) {
  Element.prototype.releasePointerCapture = () => {};
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
