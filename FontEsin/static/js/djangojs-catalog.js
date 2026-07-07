/**
 * String catalog for makemessages -d djangojs extraction only.
 * Runtime translations are consumed via gettext() in main.js and no_emoji.js.
 */
/* global gettext */
(function () {
  if (typeof gettext !== 'function') {
    return;
  }
  gettext('Error');
  gettext('Success');
  gettext('Warning');
  gettext('Info');
  gettext('Feature coming soon');
  gettext('Emojis are not allowed in name.');
  gettext('Name can only contain letters, spaces, hyphens and apostrophes.');
  gettext('Name cannot exceed %(max)s characters.');
  gettext('Emojis are not allowed in password.');
  gettext('Emojis are not allowed in email.');
  gettext('Email can only contain letters, digits and . _ - + special characters.');
  gettext('Date of Birth cannot be in the future.');
  gettext('Emojis are not allowed in phone number.');
  gettext('Phone number can only contain digits, spaces, +, -, ( and ).');
  gettext('Emojis are not allowed in website URL.');
  gettext('Website URL contains invalid characters.');
  gettext('Enter a valid website URL (e.g. https://yourcompany.com).');
  gettext('Emojis are not allowed in LinkedIn URL.');
  gettext('LinkedIn URL contains invalid characters.');
  gettext('Enter a valid LinkedIn URL (e.g. https://linkedin.com/in/username).');
  gettext('Emojis are not allowed.');
  gettext('Unable to start verification session.');
  gettext('Please complete all required fields.');
  gettext('First name must contain only letters. Digits and emojis are not allowed.');
  gettext('Last name must contain only letters. Digits and emojis are not allowed.');
  gettext('Enter a valid email address (e.g. john@company.com).');
  gettext('Please select your country.');
  gettext('Phone number must contain only digits.');
  gettext('Phone number for %(country)s must be %(min)s-%(max)s digits.');
  gettext('Phone number for %(country)s must be %(min)s digits.');
  gettext('Password must be at least 8 characters.');
  gettext('Password must include at least one letter and one number.');
  gettext('Passwords do not match.');
  gettext('This email is already registered. Please log in or use a different email.');
  gettext('Please select a role before continuing.');
  gettext('Please select a company before continuing.');
  gettext('You must agree to the Terms of Service.');
  gettext('You must consent to GDPR data processing.');
})();
