/*
 * Country -> State/Region field wiring, shared by every form that collects an
 * address (sign-up, company add/edit, profile, listings, franchise territory).
 *
 * The platform lists all 196 countries, but only a minority have a subdivision
 * list on file (accounts.constants.COUNTRY_STATES). Those get the validated
 * dropdown; every other country gets a free-text box, because "pick from an
 * empty dropdown" is not a thing a user can do and State is required on most of
 * these forms.
 *
 * Both controls carry the SAME name attribute and exactly one is enabled at a
 * time — a disabled control is not submitted, so the POST always carries a
 * single value. The server validates against COUNTRY_STATES only when a list
 * exists for the chosen country, so the typed value is accepted as-is.
 *
 * Usage:
 *   var stateField = initCountryStateField({
 *     countryEl: document.getElementById('id_country'),
 *     selectEl:  document.getElementById('id_state'),
 *     textEl:    document.getElementById('id_state_text'),   // optional
 *     states:    COUNTRY_STATES_MAP,
 *     placeholder: 'Select a state…',
 *     emptyPlaceholder: 'Select a country first…',           // optional
 *   });
 *   stateField.rebuild();          // keep the current value
 *   stateField.rebuild('');        // clear (country just changed)
 *   stateField.value();            // whichever control is live
 *   stateField.activeEl();
 *
 * The country's `change` event is wired automatically.
 */
(function (global) {
  "use strict";

  function initCountryStateField(opts) {
    var countryEl = opts.countryEl;
    var selectEl = opts.selectEl;
    var textEl = opts.textEl || null;
    var states = opts.states || {};
    var placeholder = opts.placeholder || "";
    var emptyPlaceholder = opts.emptyPlaceholder || placeholder;

    if (!countryEl || !selectEl) return null;

    function activeEl() {
      if (!selectEl.disabled) return selectEl;
      return textEl;
    }

    function value() {
      var el = activeEl();
      return el ? el.value : "";
    }

    function rebuild(preserveValue) {
      var options = (countryEl.value && states[countryEl.value]) || [];
      var current = preserveValue != null ? preserveValue : value();

      // No subdivision list for this country -> free-text box.
      if (!options.length) {
        selectEl.innerHTML = '<option value="">' + emptyPlaceholder + "</option>";
        selectEl.disabled = true;
        selectEl.style.display = "none";
        if (textEl) {
          // Nothing to type against until a country is chosen.
          textEl.disabled = !countryEl.value;
          textEl.style.display = "";
          textEl.value = current || "";
        } else {
          // No text fallback on this form: leave the dropdown visible and
          // disabled, which is the pre-196 behaviour.
          selectEl.style.display = "";
        }
        return;
      }

      if (textEl) {
        textEl.disabled = true;
        textEl.style.display = "none";
      }

      var html = '<option value="">' + placeholder + "</option>";
      for (var i = 0; i < options.length; i++) {
        var name = options[i];
        var selected = name === current ? " selected" : "";
        html += '<option value="' + name + '"' + selected + ">" + name + "</option>";
      }
      selectEl.innerHTML = html;
      selectEl.disabled = false;
      selectEl.style.display = "";
    }

    countryEl.addEventListener("change", function () {
      rebuild("");
    });

    return { rebuild: rebuild, value: value, activeEl: activeEl };
  }

  global.initCountryStateField = initCountryStateField;
})(window);
