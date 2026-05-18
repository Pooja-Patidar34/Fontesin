/* ============================================================
   FONTESIN – Block emojis in password inputs, and restrict
   email inputs to RFC-compliant characters only.
   ============================================================ */
(function () {
  // BMP emoji-bearing ranges are confined to Miscellaneous Symbols (U+2600+)
  // and Dingbats (U+2700+). The previous lower bound of U+2011 swept in
  // typographic punctuation \u2014 em-dash (U+2014), en-dash (U+2013), smart
  // quotes (U+2018-U+201D), ellipsis (U+2026), arrows, math operators,
  // box drawing, geometric shapes \u2014 and falsely flagged seeded admin copy
  // (e.g. plan `best_for` text "\u2026within their own state \u2014 limited\u2026") as
  // an emoji on every form save. The Private Use Area (U+E000-U+F8FF) is
  // also intentionally excluded because icon fonts (Font Awesome and
  // similar) live there and would trip the same false positive.
  var EMOJI_RE = /([\u2700-\u27BF]|\uD83C[\uDC00-\uDFFF]|\uD83D[\uDC00-\uDFFF]|\uD83E[\uDD00-\uDDFF]|[\u2600-\u26FF]|\uD83C[\uDDE6-\uDDFF]|[\u{1F1E6}-\u{1F1FF}]|[\u{1F300}-\u{1FAFF}])/u;
  var EMOJI_GLOBAL_RE = /([\u2700-\u27BF]|\uD83C[\uDC00-\uDFFF]|\uD83D[\uDC00-\uDFFF]|\uD83E[\uDD00-\uDDFF]|[\u2600-\u26FF]|[\u{1F1E6}-\u{1F1FF}]|[\u{1F300}-\u{1FAFF}])/gu;

  // RFC 5322 local-part allowed atext + dot; plus "@" and domain chars (letters, digits, ".", "-").
  // Permissive-but-bounded: a-z A-Z 0-9 and ! # $ % & ' * + / = ? ^ _ ` { | } ~ . - @
  var EMAIL_ALLOWED_RE = /^[A-Za-z0-9!#$%&'*+/=?^_`{|}~.\-@]*$/;
  var EMAIL_DISALLOWED_GLOBAL_RE = /[^A-Za-z0-9!#$%&'*+/=?^_`{|}~.\-@]/g;

  // Human names: letters (incl. accented), spaces, apostrophes, hyphens, periods.
  var NAME_ALLOWED_RE = /^[A-Za-z\u00C0-\u024F\u1E00-\u1EFF '\-.]*$/;
  var NAME_DISALLOWED_GLOBAL_RE = /[^A-Za-z\u00C0-\u024F\u1E00-\u1EFF '\-.]/g;
  var NAME_FIELD_RE = /(^|[_\-\s])(first|last|middle|full)[_\-\s]?name$|^(fname|lname|firstname|lastname)$/i;

  // Date of birth detection.
  var DOB_FIELD_RE = /(birth[_\-]?date|date[_\-]?of[_\-]?birth|\bdob\b|\bbirth\b)/i;

  // Phone: digits, spaces, leading +, hyphens, parentheses.
  var PHONE_ALLOWED_RE = /^[+\d\s().\-]*$/;
  var PHONE_DISALLOWED_GLOBAL_RE = /[^+\d\s().\-]/g;
  var PHONE_FIELD_RE = /(^|[_\-])(phone|mobile|tel|telephone|contact[_\-]?number)([_\-]|$)/i;

  // LinkedIn field detection + full URL validator.
  var LINKEDIN_FIELD_RE = /linked[_\-]?in/i;
  // Matches profiles like https://www.linkedin.com/in/username, /pub/, /company/, localized subdomains (in., uk., etc.)
  var LINKEDIN_URL_RE = /^https?:\/\/(?:[a-z]{2,3}\.)?linkedin\.com\/(?:in|pub|company|school|profile)\/[A-Za-z0-9\-_%]+\/?(?:\?[^\s]*)?$/i;

  // Website field detection + generic URL validator.
  var WEBSITE_FIELD_RE = /(^|[_\-])(website|homepage|site|url)([_\-]|$)/i;
  var WEBSITE_URL_RE = /^https?:\/\/([A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,}(?::\d{1,5})?(?:\/[^\s]*)?$/;
  var URL_ALLOWED_RE = /^[A-Za-z0-9:\/?#\[\]@!$&'()*+,;=._~\-%]*$/;
  var URL_DISALLOWED_GLOBAL_RE = /[^A-Za-z0-9:\/?#\[\]@!$&'()*+,;=._~\-%]/g;

  function todayISO() {
    var d = new Date();
    var y = d.getFullYear();
    var m = String(d.getMonth() + 1).padStart(2, '0');
    var day = String(d.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + day;
  }

  function ensureToastContainer() {
    var container = document.getElementById('ne-toast-container');
    if (container) return container;
    container = document.createElement('div');
    container.id = 'ne-toast-container';
    container.style.cssText = 'position:fixed;top:20px;right:20px;z-index:999999;display:flex;flex-direction:column;gap:10px;pointer-events:none;';
    document.body.appendChild(container);
    return container;
  }

  function showInlineToast(msg) {
    var container = ensureToastContainer();
    var toast = document.createElement('div');
    toast.style.cssText = 'min-width:280px;max-width:400px;padding:14px 18px;border-radius:10px;background:#fee2e2;color:#b91c1c;border:1px solid #fecaca;font-size:.88rem;font-weight:500;box-shadow:0 6px 24px rgba(0,0,0,.12);pointer-events:auto;display:flex;align-items:center;gap:10px;animation:neToastIn .2s ease;';
    toast.innerHTML = '<span style="font-size:1rem;">\u26A0\uFE0F</span><span>' + msg.replace(/</g, '&lt;') + '</span>';
    container.appendChild(toast);
    setTimeout(function () {
      toast.style.transition = 'opacity .25s, transform .25s';
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(20px)';
      setTimeout(function () { toast.remove(); }, 250);
    }, 3500);
  }

  function notify(msg) {
    if (typeof window.showToast === 'function') {
      window.showToast(msg, 'error');
    } else if (typeof window.showNotification === 'function') {
      window.showNotification(msg, 'error');
    } else {
      showInlineToast(msg);
    }
  }

  function stripEmojis(value) {
    return value.replace(EMOJI_GLOBAL_RE, '');
  }

  function stripInvalidEmailChars(value) {
    return value.replace(EMAIL_DISALLOWED_GLOBAL_RE, '');
  }

  function isEmailInput(input) {
    if (!input || input.tagName !== 'INPUT') return false;
    if ((input.type || '').toLowerCase() === 'email') return true;
    var name = (input.name || '').toLowerCase();
    var id = (input.id || '').toLowerCase();
    return name === 'email' || /email/.test(name) || /email/.test(id);
  }

  function isNameInput(input) {
    if (!input || input.tagName !== 'INPUT') return false;
    var type = (input.type || 'text').toLowerCase();
    if (type !== 'text' && type !== 'search') return false;
    var name = input.name || '';
    var id = input.id || '';
    return NAME_FIELD_RE.test(name) || NAME_FIELD_RE.test(id);
  }

  function stripInvalidNameChars(value) {
    return value.replace(NAME_DISALLOWED_GLOBAL_RE, '');
  }

  var NAME_MAX_LENGTH = 50;

  function attachName(input) {
    if (input.dataset.nameGuardBound === '1') return;
    input.dataset.nameGuardBound = '1';

    var existingMax = parseInt(input.getAttribute('maxlength') || '0', 10);
    if (!existingMax || existingMax > NAME_MAX_LENGTH) {
      input.setAttribute('maxlength', String(NAME_MAX_LENGTH));
    }

    input.addEventListener('input', function () {
      var val = input.value;
      if (EMOJI_RE.test(val)) {
        input.value = stripInvalidNameChars(stripEmojis(val));
        notify('Emojis are not allowed in name.');
        return;
      }
      if (!NAME_ALLOWED_RE.test(val)) {
        input.value = stripInvalidNameChars(val);
        notify('Name can only contain letters, spaces, hyphens and apostrophes.');
        return;
      }
      if (val.length > NAME_MAX_LENGTH) {
        input.value = val.slice(0, NAME_MAX_LENGTH);
        notify('Name cannot exceed ' + NAME_MAX_LENGTH + ' characters.');
      }
    });

    input.addEventListener('paste', function (e) {
      var clip = (e.clipboardData || window.clipboardData);
      if (!clip) return;
      var text = clip.getData('text');
      if (!text) return;
      var hasEmoji = EMOJI_RE.test(text);
      var hasBadChar = !NAME_ALLOWED_RE.test(text);
      var start = input.selectionStart || 0;
      var end = input.selectionEnd || 0;
      var combinedLength = (input.value.length - (end - start)) + text.length;
      var wouldOverflow = combinedLength > NAME_MAX_LENGTH;

      if (hasEmoji || hasBadChar || wouldOverflow) {
        e.preventDefault();
        notify(hasEmoji
          ? 'Emojis are not allowed in name.'
          : (hasBadChar
              ? 'Name can only contain letters, spaces, hyphens and apostrophes.'
              : 'Name cannot exceed ' + NAME_MAX_LENGTH + ' characters.'));
        var clean = stripInvalidNameChars(stripEmojis(text));
        var available = NAME_MAX_LENGTH - (input.value.length - (end - start));
        if (available < 0) available = 0;
        clean = clean.slice(0, available);
        input.value = input.value.slice(0, start) + clean + input.value.slice(end);
        var pos = start + clean.length;
        try { input.setSelectionRange(pos, pos); } catch (err) { /* noop */ }
      }
    });
  }

  function attachPassword(input) {
    if (input.dataset.noEmojiBound === '1') return;
    input.dataset.noEmojiBound = '1';

    input.addEventListener('input', function () {
      if (EMOJI_RE.test(input.value)) {
        input.value = stripEmojis(input.value);
        notify('Emojis are not allowed in password.');
      }
    });

    input.addEventListener('paste', function (e) {
      var clip = (e.clipboardData || window.clipboardData);
      if (!clip) return;
      var text = clip.getData('text');
      if (text && EMOJI_RE.test(text)) {
        e.preventDefault();
        notify('Emojis are not allowed in password.');
        var clean = stripEmojis(text);
        var start = input.selectionStart || 0;
        var end = input.selectionEnd || 0;
        input.value = input.value.slice(0, start) + clean + input.value.slice(end);
        var pos = start + clean.length;
        try { input.setSelectionRange(pos, pos); } catch (err) { /* noop */ }
      }
    });
  }

  function attachEmail(input) {
    if (input.dataset.emailGuardBound === '1') return;
    input.dataset.emailGuardBound = '1';

    input.addEventListener('input', function () {
      var val = input.value;
      if (EMOJI_RE.test(val)) {
        input.value = stripEmojis(input.value).replace(EMAIL_DISALLOWED_GLOBAL_RE, '');
        notify('Emojis are not allowed in email.');
        return;
      }
      if (!EMAIL_ALLOWED_RE.test(val)) {
        input.value = stripInvalidEmailChars(val);
        notify('Email can only contain letters, digits and . _ - + special characters.');
      }
    });

    input.addEventListener('paste', function (e) {
      var clip = (e.clipboardData || window.clipboardData);
      if (!clip) return;
      var text = clip.getData('text');
      if (!text) return;
      var hasEmoji = EMOJI_RE.test(text);
      var hasBadChar = !EMAIL_ALLOWED_RE.test(text);
      if (hasEmoji || hasBadChar) {
        e.preventDefault();
        notify(hasEmoji
          ? 'Emojis are not allowed in email.'
          : 'Email can only contain letters, digits and . _ - + special characters.');
        var clean = stripInvalidEmailChars(stripEmojis(text));
        var start = input.selectionStart || 0;
        var end = input.selectionEnd || 0;
        input.value = input.value.slice(0, start) + clean + input.value.slice(end);
        var pos = start + clean.length;
        try { input.setSelectionRange(pos, pos); } catch (err) { /* noop */ }
      }
    });
  }

  function isDobInput(input) {
    if (!input || input.tagName !== 'INPUT') return false;
    if ((input.type || '').toLowerCase() !== 'date') return false;
    var name = input.name || '';
    var id = input.id || '';
    return DOB_FIELD_RE.test(name) || DOB_FIELD_RE.test(id);
  }

  function attachDob(input) {
    if (input.dataset.dobGuardBound === '1') return;
    input.dataset.dobGuardBound = '1';

    var today = todayISO();
    if (!input.max || input.max > today) {
      input.max = today;
    }

    input.addEventListener('input', validateDob);
    input.addEventListener('change', validateDob);
    input.addEventListener('blur', validateDob);

    function validateDob() {
      if (!input.value) return;
      if (input.value > todayISO()) {
        notify('Date of Birth cannot be in the future.');
        input.value = '';
        input.focus();
      }
    }
  }

  function isPhoneInput(input) {
    if (!input || input.tagName !== 'INPUT') return false;
    var type = (input.type || 'text').toLowerCase();
    if (type === 'tel') return true;
    if (type !== 'text' && type !== 'search') return false;
    var name = input.name || '';
    var id = input.id || '';
    return PHONE_FIELD_RE.test(name) || PHONE_FIELD_RE.test(id);
  }

  function stripInvalidPhoneChars(value) {
    return value.replace(PHONE_DISALLOWED_GLOBAL_RE, '');
  }

  function attachPhone(input) {
    if (input.dataset.phoneGuardBound === '1') return;
    input.dataset.phoneGuardBound = '1';

    input.addEventListener('input', function () {
      var val = input.value;
      if (EMOJI_RE.test(val)) {
        input.value = stripInvalidPhoneChars(stripEmojis(val));
        notify('Emojis are not allowed in phone number.');
        return;
      }
      if (!PHONE_ALLOWED_RE.test(val)) {
        input.value = stripInvalidPhoneChars(val);
        notify('Phone number can only contain digits, spaces, +, -, ( and ).');
      }
    });

    input.addEventListener('paste', function (e) {
      var clip = (e.clipboardData || window.clipboardData);
      if (!clip) return;
      var text = clip.getData('text');
      if (!text) return;
      var hasEmoji = EMOJI_RE.test(text);
      var hasBadChar = !PHONE_ALLOWED_RE.test(text);
      if (hasEmoji || hasBadChar) {
        e.preventDefault();
        notify(hasEmoji
          ? 'Emojis are not allowed in phone number.'
          : 'Phone number can only contain digits, spaces, +, -, ( and ).');
        var clean = stripInvalidPhoneChars(stripEmojis(text));
        var start = input.selectionStart || 0;
        var end = input.selectionEnd || 0;
        input.value = input.value.slice(0, start) + clean + input.value.slice(end);
        var pos = start + clean.length;
        try { input.setSelectionRange(pos, pos); } catch (err) { /* noop */ }
      }
    });
  }

  function isWebsiteInput(input) {
    if (!input || input.tagName !== 'INPUT') return false;
    var type = (input.type || 'text').toLowerCase();
    var name = input.name || '';
    var id = input.id || '';
    // Exclude LinkedIn fields (handled separately).
    if (LINKEDIN_FIELD_RE.test(name) || LINKEDIN_FIELD_RE.test(id)) return false;
    if (type === 'url') return true;
    if (type !== 'text' && type !== 'search') return false;
    return WEBSITE_FIELD_RE.test(name) || WEBSITE_FIELD_RE.test(id);
  }

  function stripInvalidUrlChars(value) {
    return value.replace(URL_DISALLOWED_GLOBAL_RE, '');
  }

  function attachWebsite(input) {
    if (input.dataset.websiteGuardBound === '1') return;
    input.dataset.websiteGuardBound = '1';

    input.addEventListener('input', function () {
      var val = input.value;
      if (EMOJI_RE.test(val)) {
        input.value = stripInvalidUrlChars(stripEmojis(val));
        notify('Emojis are not allowed in website URL.');
        return;
      }
      if (!URL_ALLOWED_RE.test(val)) {
        input.value = stripInvalidUrlChars(val);
        notify('Website URL contains invalid characters.');
      }
    });

    input.addEventListener('paste', function (e) {
      var clip = (e.clipboardData || window.clipboardData);
      if (!clip) return;
      var text = clip.getData('text');
      if (!text) return;
      var hasEmoji = EMOJI_RE.test(text);
      var hasBadChar = !URL_ALLOWED_RE.test(text);
      if (hasEmoji || hasBadChar) {
        e.preventDefault();
        notify(hasEmoji
          ? 'Emojis are not allowed in website URL.'
          : 'Website URL contains invalid characters.');
        var clean = stripInvalidUrlChars(stripEmojis(text));
        var start = input.selectionStart || 0;
        var end = input.selectionEnd || 0;
        input.value = input.value.slice(0, start) + clean + input.value.slice(end);
        var pos = start + clean.length;
        try { input.setSelectionRange(pos, pos); } catch (err) { /* noop */ }
      }
    });

    input.addEventListener('blur', function () {
      var val = (input.value || '').trim();
      if (!val) { input.style.borderColor = ''; return; }
      if (!WEBSITE_URL_RE.test(val)) {
        notify('Enter a valid website URL (e.g. https://yourcompany.com).');
        input.style.borderColor = '#ef4444';
      } else {
        input.style.borderColor = '';
      }
    });
  }

  function isLinkedInInput(input) {
    if (!input || input.tagName !== 'INPUT') return false;
    var name = input.name || '';
    var id = input.id || '';
    return LINKEDIN_FIELD_RE.test(name) || LINKEDIN_FIELD_RE.test(id);
  }

  function attachLinkedIn(input) {
    if (input.dataset.linkedinGuardBound === '1') return;
    input.dataset.linkedinGuardBound = '1';

    function stripBadChars(value) {
      return value
        .replace(EMOJI_GLOBAL_RE, '')
        .replace(/[^A-Za-z0-9:\/?#\[\]@!$&'()*+,;=._~\-%]/g, '');
    }

    input.addEventListener('input', function () {
      var val = input.value;
      if (EMOJI_RE.test(val)) {
        input.value = stripBadChars(val);
        notify('Emojis are not allowed in LinkedIn URL.');
        return;
      }
      var cleaned = stripBadChars(val);
      if (cleaned !== val) {
        input.value = cleaned;
        notify('LinkedIn URL contains invalid characters.');
      }
    });

    input.addEventListener('paste', function (e) {
      var clip = (e.clipboardData || window.clipboardData);
      if (!clip) return;
      var text = clip.getData('text');
      if (!text) return;
      var cleaned = stripBadChars(text);
      if (cleaned !== text) {
        e.preventDefault();
        notify(EMOJI_RE.test(text)
          ? 'Emojis are not allowed in LinkedIn URL.'
          : 'LinkedIn URL contains invalid characters.');
        var start = input.selectionStart || 0;
        var end = input.selectionEnd || 0;
        input.value = input.value.slice(0, start) + cleaned + input.value.slice(end);
        var pos = start + cleaned.length;
        try { input.setSelectionRange(pos, pos); } catch (err) { /* noop */ }
      }
    });

    input.addEventListener('blur', function () {
      var val = (input.value || '').trim();
      if (!val) return;
      if (!LINKEDIN_URL_RE.test(val)) {
        notify('Enter a valid LinkedIn URL (e.g. https://linkedin.com/in/username).');
        input.style.borderColor = '#ef4444';
      } else {
        input.style.borderColor = '';
      }
    });
  }

  // Generic emoji guard for any other text-like input/textarea.
  function attachGenericEmojiGuard(el) {
    if (!el) return;
    if (el.dataset.genericEmojiBound === '1') return;
    var tag = el.tagName;
    if (tag !== 'INPUT' && tag !== 'TEXTAREA') return;
    if (tag === 'INPUT') {
      var type = (el.type || 'text').toLowerCase();
      // Skip non-text input types — nothing useful to guard.
      var skipTypes = ['checkbox', 'radio', 'file', 'hidden', 'submit', 'reset', 'button', 'image', 'range', 'color'];
      if (skipTypes.indexOf(type) !== -1) return;
    }
    el.dataset.genericEmojiBound = '1';

    el.addEventListener('input', function () {
      if (EMOJI_RE.test(el.value)) {
        el.value = stripEmojis(el.value);
        notify('Emojis are not allowed.');
      }
    });

    el.addEventListener('paste', function (e) {
      var clip = (e.clipboardData || window.clipboardData);
      if (!clip) return;
      var text = clip.getData('text');
      if (text && EMOJI_RE.test(text)) {
        e.preventDefault();
        notify('Emojis are not allowed.');
        var clean = stripEmojis(text);
        var start = el.selectionStart || 0;
        var end = el.selectionEnd || 0;
        el.value = el.value.slice(0, start) + clean + el.value.slice(end);
        var pos = start + clean.length;
        try { el.setSelectionRange(pos, pos); } catch (err) { /* noop */ }
      }
    });
  }

  function attach(input) {
    if ((input.type || '').toLowerCase() === 'password') {
      attachPassword(input);
    } else if (isEmailInput(input)) {
      attachEmail(input);
    } else if (isDobInput(input)) {
      attachDob(input);
    } else if (isLinkedInInput(input)) {
      attachLinkedIn(input);
    } else if (isWebsiteInput(input)) {
      attachWebsite(input);
    } else if (isPhoneInput(input)) {
      attachPhone(input);
    } else if (isNameInput(input)) {
      attachName(input);
    } else {
      attachGenericEmojiGuard(input);
    }
  }

  function scan(root) {
    var r = root || document;
    r.querySelectorAll('input[type="password"]').forEach(attach);
    r.querySelectorAll('input[type="email"], input[name="email"], input[name*="email" i], input[id*="email" i]').forEach(attach);
    r.querySelectorAll(
      'input[name*="first_name" i], input[name*="last_name" i], input[name*="middle_name" i], input[name*="full_name" i],' +
      'input[name*="firstName" i], input[name*="lastName" i], input[name="fname"], input[name="lname"],' +
      'input[id*="first_name" i], input[id*="last_name" i], input[id*="middle_name" i], input[id*="full_name" i],' +
      'input[id*="firstName" i], input[id*="lastName" i]'
    ).forEach(attach);
    r.querySelectorAll('input[type="date"]').forEach(attach);
    r.querySelectorAll('input[name*="linkedin" i], input[id*="linkedin" i]').forEach(attach);
    r.querySelectorAll(
      'input[type="url"], input[name*="website" i], input[name*="homepage" i],' +
      'input[name$="_url" i], input[id*="website" i], input[id*="homepage" i]'
    ).forEach(attach);
    r.querySelectorAll(
      'input[type="tel"], input[name*="phone" i], input[name*="mobile" i],' +
      'input[name*="telephone" i], input[id*="phone" i], input[id*="mobile" i],' +
      'input[id*="telephone" i]'
    ).forEach(attach);

    // Universal sweep: every remaining input and textarea gets the generic emoji guard.
    r.querySelectorAll('input, textarea').forEach(attach);
  }

  document.addEventListener('DOMContentLoaded', function () {
    scan(document);

    var mo = new MutationObserver(function (mutations) {
      mutations.forEach(function (m) {
        m.addedNodes.forEach(function (node) {
          if (node.nodeType !== 1) return;
          if (node.matches && (node.matches('input') || node.matches('textarea'))) {
            attach(node);
          } else if (node.querySelectorAll) {
            scan(node);
          }
        });
      });
    });
    mo.observe(document.body, { childList: true, subtree: true });

    // Guard submit: block emoji in passwords; block emoji / invalid chars in emails.
    document.addEventListener('submit', function (e) {
      var form = e.target;
      if (!form || !form.querySelectorAll) return;

      var pwInputs = form.querySelectorAll('input[type="password"]');
      for (var i = 0; i < pwInputs.length; i++) {
        if (EMOJI_RE.test(pwInputs[i].value)) {
          e.preventDefault();
          notify('Emojis are not allowed in password.');
          pwInputs[i].focus();
          return;
        }
      }

      var emailInputs = form.querySelectorAll('input[type="email"], input[name="email"], input[name*="email" i], input[id*="email" i]');
      for (var j = 0; j < emailInputs.length; j++) {
        var v = emailInputs[j].value;
        if (!v) continue;
        if (EMOJI_RE.test(v)) {
          e.preventDefault();
          notify('Emojis are not allowed in email.');
          emailInputs[j].focus();
          return;
        }
        if (!EMAIL_ALLOWED_RE.test(v)) {
          e.preventDefault();
          notify('Email can only contain letters, digits and . _ - + special characters.');
          emailInputs[j].focus();
          return;
        }
      }

      var dobInputs = form.querySelectorAll('input[type="date"]');
      var todayStr = todayISO();
      for (var d = 0; d < dobInputs.length; d++) {
        if (!isDobInput(dobInputs[d])) continue;
        var dv = dobInputs[d].value;
        if (dv && dv > todayStr) {
          e.preventDefault();
          notify('Date of Birth cannot be in the future.');
          dobInputs[d].focus();
          return;
        }
      }

      var phoneInputs = form.querySelectorAll(
        'input[type="tel"], input[name*="phone" i], input[name*="mobile" i],' +
        'input[name*="telephone" i], input[id*="phone" i], input[id*="mobile" i],' +
        'input[id*="telephone" i]'
      );
      for (var p = 0; p < phoneInputs.length; p++) {
        var pv = phoneInputs[p].value;
        if (!pv) continue;
        if (EMOJI_RE.test(pv)) {
          e.preventDefault();
          notify('Emojis are not allowed in phone number.');
          phoneInputs[p].focus();
          return;
        }
        if (!PHONE_ALLOWED_RE.test(pv)) {
          e.preventDefault();
          notify('Phone number can only contain digits, spaces, +, -, ( and ).');
          phoneInputs[p].focus();
          return;
        }
      }

      var websiteInputs = form.querySelectorAll(
        'input[type="url"], input[name*="website" i], input[name*="homepage" i],' +
        'input[name$="_url" i], input[id*="website" i], input[id*="homepage" i]'
      );
      for (var w = 0; w < websiteInputs.length; w++) {
        if (!isWebsiteInput(websiteInputs[w])) continue;
        var wv = (websiteInputs[w].value || '').trim();
        if (!wv) continue;
        if (EMOJI_RE.test(wv)) {
          e.preventDefault();
          notify('Emojis are not allowed in website URL.');
          websiteInputs[w].focus();
          return;
        }
        if (!WEBSITE_URL_RE.test(wv)) {
          e.preventDefault();
          notify('Enter a valid website URL (e.g. https://yourcompany.com).');
          websiteInputs[w].focus();
          return;
        }
      }

      var linkedinInputs = form.querySelectorAll('input[name*="linkedin" i], input[id*="linkedin" i]');
      for (var l = 0; l < linkedinInputs.length; l++) {
        var lv = (linkedinInputs[l].value || '').trim();
        if (!lv) continue;
        if (EMOJI_RE.test(lv)) {
          e.preventDefault();
          notify('Emojis are not allowed in LinkedIn URL.');
          linkedinInputs[l].focus();
          return;
        }
        if (!LINKEDIN_URL_RE.test(lv)) {
          e.preventDefault();
          notify('Enter a valid LinkedIn URL (e.g. https://linkedin.com/in/username).');
          linkedinInputs[l].focus();
          return;
        }
      }

      var nameInputs = form.querySelectorAll('input[type="text"], input:not([type])');
      for (var k = 0; k < nameInputs.length; k++) {
        if (!isNameInput(nameInputs[k])) continue;
        var nv = nameInputs[k].value;
        if (!nv) continue;
        if (EMOJI_RE.test(nv)) {
          e.preventDefault();
          notify('Emojis are not allowed in name.');
          nameInputs[k].focus();
          return;
        }
        if (!NAME_ALLOWED_RE.test(nv)) {
          e.preventDefault();
          notify('Name can only contain letters, spaces, hyphens and apostrophes.');
          nameInputs[k].focus();
          return;
        }
        if (nv.length > NAME_MAX_LENGTH) {
          e.preventDefault();
          notify('Name cannot exceed ' + NAME_MAX_LENGTH + ' characters.');
          nameInputs[k].focus();
          return;
        }
      }

      // Universal catch-all: any remaining input/textarea with emojis.
      var allFields = form.querySelectorAll('input, textarea');
      for (var a = 0; a < allFields.length; a++) {
        var fld = allFields[a];
        if (fld.type && ['checkbox', 'radio', 'file', 'hidden', 'submit', 'reset', 'button', 'image', 'range', 'color'].indexOf(fld.type.toLowerCase()) !== -1) continue;
        var fv = fld.value;
        if (fv && EMOJI_RE.test(fv)) {
          e.preventDefault();
          notify('Emojis are not allowed.');
          fld.focus();
          return;
        }
      }
    }, true);
  });
})();
