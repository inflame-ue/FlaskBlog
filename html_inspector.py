# imports
import bleach


# function block
def strip_invalid_html(html_code):
    allowed_tags = ['a', 'abbr', 'acronym', 'address', 'b', 'br', 'div', 'dl', 'dt',
                    'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img',
                    'li', 'ol', 'p', 'pre', 'q', 's', 'small', 'strike',
                    'span', 'sub', 'sup', 'table', 'tbody', 'td', 'tfoot', 'th',
                    'thead', 'tr', 'tt', 'u', 'ul'
                    ]

    allowed_attributes = {
        'a': ['href', 'target', 'title'],
        'img': ['src', 'alt', 'width', 'height'],
    }

    # clean the html with bleach
    cleaned_html = bleach.clean(html_code, tags=allowed_tags, attributes=allowed_attributes, strip=True)

    return cleaned_html
