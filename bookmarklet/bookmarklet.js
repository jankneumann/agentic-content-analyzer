/**
 * Newsletter Aggregator - Save URL Bookmarklet
 *
 * This bookmarklet opens the save page with the current page URL,
 * title, and any selected text pre-filled.
 *
 * Usage:
 *   Replace YOUR_APP_URL with your Newsletter Aggregator instance URL.
 *   Create a bookmark with the minified version as the URL.
 *
 * Minified version (replace YOUR_APP_URL):
 *   javascript:(function(){var b='YOUR_APP_URL';var u=encodeURIComponent(location.href);var t=encodeURIComponent(document.title);var s=encodeURIComponent((window.getSelection()||'').toString().slice(0,500));window.open(b+'/api/v1/content/save?url='+u+'&title='+t+'&excerpt='+s,'_blank','width=600,height=500');})();
 */
(function () {
  // Base URL of your Newsletter Aggregator instance
  var baseUrl = 'YOUR_APP_URL';

  // Capture current page info
  var url = encodeURIComponent(location.href);
  var title = encodeURIComponent(document.title);
  var selection = (window.getSelection() || '').toString().slice(0, 500);
  var excerpt = encodeURIComponent(selection);

  // Open save page with pre-filled data
  var saveUrl =
    baseUrl +
    '/api/v1/content/save?url=' +
    url +
    '&title=' +
    title +
    '&excerpt=' +
    excerpt;

  window.open(saveUrl, '_blank', 'width=600,height=500');
})();
