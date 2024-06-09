import asyncio
import urllib.parse
import pathlib
from pprint import pprint

import helpers
import configuration
import gemtext_to_html

http_response_codes = {
    200: 'OK',
    307: 'Temporary Redirect',
    400: 'Bad Request',
    404: 'Not Found',
    501: 'Not Implemented',
}


class HTTPRequest:
    def __init__(self, request_str, headers):
        if configuration.all_args.log_requests or configuration.all_args.verbose:
            print(f'HTTP Request: {request_str}')

        if configuration.all_args.verbose:
            print(f'HTTP Request Headers: {headers}')

        split_request_str = request_str.split(' ')

        # Until proven otherwise, assume the request is OK
        self.response_code = 200
        self.has_data = False

        # We only support GET requests
        if split_request_str[0] != 'GET':
            self.response_code = 501

        if len(split_request_str) != 3:
            if configuration.all_args.verbose:
                print(f'Setting response code to 400 becaue the request string is too long or weird (split has '
                      f'{len(split_request_str)} entries instead of 3; \"{request_str}\")')
            self.response_code = 400

        self.__resolve_file_path(split_request_str[1])

        # If we got a reason to have a Bad Request here, dont bother trying to read anything, as that could
        # potentially be dangerous
        if self.response_code == 400:
            self.__generate_response_headers()
            return

        if self.raw_file_path != self.unresolved_file_path:
            # The path contains relative shit, redirect to the actual path
            self.response_code = 307
        elif not self.file_path.exists(follow_symlinks=False):
            if configuration.all_args.log_requests or configuration.all_args.verbose:
                print(f'HTTP: Couldn\'t find {self.file_path}')
            self.response_code = 404
        elif self.raw_file_path.endswith('.gmi'):
            self.__handle_gemtext()
            self.has_data = True
        else:
            self.has_data = True

        self.__generate_response_headers()

    async def write_response(self, writer: asyncio.StreamWriter):
        if configuration.all_args.verbose:
            print(f'HTTP Response: {self.response_code}')
            print(f'HTTP Response Headers: {self.response_headers}')

        await send_http_response(self.response_code, self.response_headers, writer)

        if self.has_data:
            if self.raw_file_path.endswith('.gmi'):
                writer.write(self.converted_html.encode('utf-8'))
                await writer.drain()
            else:
                with open(self.file_path, 'rb') as file:
                    while True:
                        chunk = file.read(1 * 1024 * 1024)
                        if not chunk:
                            break
                        writer.write(chunk)
                        await writer.drain()

    def __generate_response_headers(self):
        self.response_headers = {
            'Server': 'GemHTTP',
        }

        if self.response_code == 307:
            # We need to redirect
            self.response_headers['Location'] = f'{self.raw_file_path}'
        elif self.response_code == 200:
            # The file exists, and everything is OK, we can send data
            # We will use our gemtext-to-html implementation for gemtext, so if the file is a gemtext file,
            # we will lie about the content type here
            if self.raw_file_path.endswith('.gmi'):
                self.response_headers['Content-Type'] = 'text/html; charset=UTF-8'
                self.response_headers['Content-Length'] = len(self.converted_html)
            else:
                self.response_headers['Content-Type'] = helpers.get_mime_type(self.file_path)
                self.response_headers['Content-Length'] = self.file_path.stat().st_size

    def __resolve_file_path(self, file_path: str):
        parsed_url = urllib.parse.urlparse(file_path)

        if len(parsed_url.scheme) and parsed_url.scheme not in ['http', 'https']:
            self.response_code = 400

        if len(parsed_url.netloc) and parsed_url.netloc not in configuration.our_domains:
            if configuration.all_args.verbose:
                print(f'Setting response code to 400 because this appears to be a proxy request (requested domain was:'
                      f'{parsed_url.netloc})')
            self.response_code = 400

        file_path = parsed_url.path.strip()
        if file_path.endswith('/'):
            file_path += 'index.gmi'

        if file_path.startswith('/'):
            file_path = file_path.lstrip('/')

        self.raw_file_path = helpers.resolve_url(file_path)
        self.unresolved_file_path = file_path
        self.file_path = configuration.data_dir / pathlib.Path(self.raw_file_path)

    def __handle_gemtext(self):
        assert self.file_path.exists()

        with open(self.file_path, 'r') as f:
            self.converted_html = gemtext_to_html.gemtext_to_html(f.read(), self.file_path.name)


async def send_http_response(status_code: int, response_headers: {}, writer: asyncio.StreamWriter):
    assert status_code in http_response_codes

    writer.write(b'HTTP/1.1 ' + str(status_code).encode() + b' ' + http_response_codes[status_code].encode() + b'\r\n')
    for header in response_headers.items():
        writer.write(str(header[0]).encode() + b': ' + str(header[1]).encode() + b'\r\n')

    writer.write(b'\r\n')


async def http_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        http_request = (await reader.readline()).decode('utf-8').strip()

        headers = []
        while True:
            header = (await reader.readline()).decode('utf-8').strip()
            if not len(header):
                break
            headers.append(header)

            if len(headers) > 64:
                print('Breaking off HTTP request on account of having too many HTTP headers!')
                writer.close()
                return
    except asyncio.LimitOverrunError:
        print('TODO: handle asyncio.LimitOverrunError')
        writer.close()
        return

    request = HTTPRequest(http_request, headers)
    await request.write_response(writer)

    await writer.drain()
    writer.close()
