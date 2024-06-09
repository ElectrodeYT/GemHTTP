import asyncio
import time
import urllib.parse
import pathlib
import magic

from pprint import pprint

import helpers
import configuration


async def gemini_send_status_code(status_code: int, writer: asyncio.StreamWriter, additional_data=''):
    writer.write(str(status_code).encode() + additional_data.encode() + b'\r\n')


async def gemini_tls_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    await writer.start_tls(configuration.tls_context)

    try:
        request = (await reader.readline()).decode('utf-8').rstrip()
    except asyncio.LimitOverrunError:
        await gemini_send_status_code(59, writer)
        await writer.drain()
        writer.close()
        return

    parsed_url = urllib.parse.urlparse(request)

    if configuration.all_args.log_requests:
        print(f'Gemini Request: \'{request}\'')

    if parsed_url.scheme != 'gemini':
        # Weird, and not correct; send back status 59 (bad request)
        await gemini_send_status_code(59, writer)
        await writer.drain()
        writer.close()
        return

    if parsed_url.netloc not in configuration.our_domains:
        # This is a proxy request, and we do not support proxying.
        print(f'Rejecting request to \'{request}\' as it is a proxy request')
        await gemini_send_status_code(53, writer)
        await writer.drain()
        writer.close()
        return

    # If the path ends with '/', append index.gmi
    actual_path = parsed_url.path
    if actual_path.endswith('/'):
        actual_path += 'index.gmi'
    actual_path = actual_path.strip('/')

    # If we have any kind of relative weirdness, redirect to a clean version
    # This will also redirect things like '/' -> '/index.gmi'
    resolved_path = helpers.resolve_url(actual_path)
    if resolved_path != actual_path:
        print(f'Redirecting request from {actual_path} to {resolved_path}')
        await gemini_send_status_code(30, writer, additional_data=resolved_path)
        await writer.drain()
        writer.close()
        return

    # If the file does not exist, error out
    if not (configuration.data_dir / actual_path).exists():
        print(f'Request {actual_path} could not be found')
        await gemini_send_status_code(51, writer)
        await writer.drain()
        writer.close()
        return

    # Send OK request
    file_path = configuration.data_dir / actual_path
    await gemini_send_status_code(20, writer, additional_data=helpers.get_mime_type(file_path, append_size=True))

    with open(str(file_path), 'rb') as f:
        while True:
            chunk = f.read(1 * 1024 * 1024)  # Read the file in 1MB increments
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()

    writer.close()

    if configuration.all_args.verbose:
        print('Request handled')
