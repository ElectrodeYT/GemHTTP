import os
import pwd
import grp
import pathlib
import urllib.parse

import magic

import configuration

mime = magic.Magic(mime=True, mime_encoding=True)
mime_encoding_only = magic.Magic(mime_encoding=True)


def get_mime_type(file_path: pathlib.Path, append_size=False) -> str:
    assert file_path.exists() and file_path.is_file()

    if file_path.suffix == '.gmi':
        mime_type = f'text/gemini; charset={mime_encoding_only.from_file(str(file_path))}'
    else:
        mime_type = mime.from_file(str(file_path))

    if append_size and file_path.exists() and file_path.is_file():
        mime_type += f"; size={file_path.stat().st_size}"

    if configuration.all_args.verbose:
        print(f'Determined MIME type string as \"{mime_type}\"')

    return mime_type


def resolve_url(url: str) -> str:
    parts = list(urllib.parse.urlsplit(url))
    segments = parts[2].split('/')
    segments = [segment + '/' for segment in segments[:-1]] + [segments[-1]]
    resolved = []
    for segment in segments:
        if segment in ('../', '..'):
            if resolved[0:]:
                resolved.pop()
        elif segment not in ('./', '.'):
            resolved.append(segment)
    parts[2] = ''.join(resolved)
    unsplit = urllib.parse.urlunsplit(parts)

    if url.startswith('/') and not unsplit.startswith('/'):
        unsplit = '/' + unsplit
    return unsplit


# Stolen shamelessly from stack overflow
def drop_privileges(uid_name='nobody', gid_name='nogroup'):
    if os.getuid() != 0:
        # We're not root so, like, whatever dude
        return

    # Get the uid/gid from the name
    running_uid = pwd.getpwnam(uid_name).pw_uid
    running_gid = grp.getgrnam(gid_name).gr_gid

    # Remove group privileges
    os.setgroups([])

    # Try setting the new uid/gid
    os.setgid(running_gid)
    os.setuid(running_uid)

    # Ensure a very conservative umask
    old_umask = os.umask(0o077)

    print(f'Dropped privs to {uid_name} ({running_uid}) and {gid_name} ({running_gid}).')
