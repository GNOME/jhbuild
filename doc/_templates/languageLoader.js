// SPDX-License-Identifier: BSD-3-Clause

// FIXME: None of the Intl functions actually validate locales... so for now hardcode them.
const languages = $LANGUAGES

function loadLanguage(newLang) {
    let url = new URL(window.location.href);

    let splitPath = url.pathname.split('/');
    let maybeLang = splitPath[splitPath.length - 2];
    let oldLang;

    if (languages.includes(maybeLang)) {
        oldLang = maybeLang;
    } else {
        oldLang = 'en';
    }

    if (newLang === oldLang)
        return;

    if (newLang === 'en') {
        splitPath.splice(splitPath.length - 2, 1);
    } else if (oldLang === 'en') {
        splitPath.splice(splitPath.length - 1, 0, newLang);
    } else {
        splitPath.splice(splitPath.length - 2, 1, newLang);
    }

    url.pathname = splitPath.join('/');
    window.location.href = url.toString();
}