import argparse

import configuration

html_top = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>{page_title}</title></head><body>"""

html_bottom = """</body></html>"""

# List from https://developer.mozilla.org/en-US/docs/Web/Media/Formats/Image_types
recognized_image_formats = (
    '.apng', '.avif', '.gif', '.jpg', '.jpeg', '.jfif', '.pjpeg', '.pjp', '.png', '.svg', '.webp', '.bmp', '.ico',
    '.cur', '.tif', '.tiff'
)


# Gemtext to HTML converter.
# filename is only used as a standard title if otherwise no suitable title could be found.
def gemtext_to_html(gemtext: str, filename: str) -> str:
    lines = gemtext.split('\n')
    output = ''
    title: None | str = None

    in_preformatted_mode = False

    # Process gemtext
    for line in lines:
        line = line.strip()

        if title is None and line.startswith('# '):
            title = line[2:]

        if not in_preformatted_mode:
            # Header lines
            if line.startswith('#'):
                amount_hashes = len(line) - len(line.lstrip('#'))
                if amount_hashes > 6:
                    print('GemtextConverter: [WARNING] amount of hashes in heading line is more than 6; this is not '
                          'supported in HTML or in gemtext; limiting to 6')
                    amount_hashes = 6
                elif amount_hashes > 3:
                    print('GemtextConverter: [WARNING] amount of hashes in heading line is more than 3; this is not '
                          'supported in gemtext')
                output += f'<h{amount_hashes}>{line[(amount_hashes + 1):]}</h{amount_hashes}>'
            # Link lines
            elif line.startswith('=> '):
                split_line = line.split()
                if len(split_line) >= 3:
                    link_text = ' '.join(split_line[2:])
                else:
                    link_text = split_line[1]

                link_url = split_line[1]
                if configuration.all_args.parse_images and link_url.endswith(recognized_image_formats):
                    output += f'<img src=\"{link_url}\" alt=\"{link_text}\"/>'
                else:
                    output += f'<a href=\"{link_url}\">{link_text}</a>'
            # Empty lines
            elif not len(line):
                pass
            # Preformat toggle line
            elif line.startswith('```'):
                in_preformatted_mode = True
                output += f'<pre>'
            # Text lines
            else:
                output += f'<p>{line}</p>'
        else:
            if line.startswith('```'):
                in_preformatted_mode = False
                output += f'</pre>'
            else:
                output += line + '\n'

    if in_preformatted_mode:
        print('GemtextConverter: [WARNING] preformatted mode is never disabled')
        output += '</pre>'

    output = html_top.format(page_title=title) + output + html_bottom
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('gemtext')
    parser.add_argument('--parse-images', action='store_true')

    args = parser.parse_args()

    with open(args.gemtext, 'r') as f:
        gemtext = f.read()

    print(gemtext_to_html(gemtext, args.gemtext))
