import argparse
import asyncio

import gemini
import http
import configuration
import helpers


async def run_servers(args):
    print(f'We are {configuration.our_domains}, hosting data from \'{configuration.data_dir}\'')
    print('Serving Gemini on port {}'.format(args.port))
    print('Serving HTTP on port {}'.format(args.http_port))

    gemini_server_coro = await asyncio.start_server(gemini.gemini_tls_handler, args.host, args.port)
    http_server_coro = await asyncio.start_server(http.http_handler, args.host, args.http_port)

    # If we should drop permissions, do it now
    if args.drop_to_user is not None:
        if args.drop_to_group is not None:
            group = args.drop_to_group
        else:
            group = args.drop_to_user

        helpers.drop_privileges(args.drop_to_user, group)

    async with gemini_server_coro:
        await asyncio.gather(
            gemini_server_coro.serve_forever(),
            http_server_coro.serve_forever(),
        )


def list_of_strings(arg):
    return arg.split(',')


def main():
    parser = argparse.ArgumentParser(
        prog='GemHTTP',
        description='Gemini / HTTP server'
    )

    parser.add_argument('--http-port', type=int, default=8080, help='Port to listen on (HTTP)')
    parser.add_argument('--port', type=int, default=1965, help='Port to listen on (Gemini)')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to listen on')

    parser.add_argument('--this-hosts', type=list_of_strings, default='127.0.0.1',
                        help='Hosts that we should respond to. Requests to resources not in this will be refused with'
                             'status code 53 (Proxy Request Refused). You can pass multiple hosts using'
                             'comma-seperation. Default: 127.0.0.1')

    parser.add_argument('-d', '--data-dir', type=str, default='gemtext', help='Data directory')
    parser.add_argument('--certificate', type=str, default='certificate.pem', help='Certificate file')
    parser.add_argument('--private-key', type=str, default='privatekey.pem', help='Private key file')

    logging_group = parser.add_mutually_exclusive_group()

    logging_group.add_argument('-v', '--verbose', action='store_true', help='Verbose mode')
    logging_group.add_argument('--log-requests', action='store_true', help='Log requests')

    parser.add_argument('--parse-images', action='store_true', help='HTTP: convert in-line links to images into image tags')

    drop_permissions_group = parser.add_argument_group('Drop permissions')
    drop_permissions_group.add_argument('--drop-to-user', type=str, help='Drop to user.')
    drop_permissions_group.add_argument('--drop-to-group', type=str, help='Drop to group. Must be given with --drop-to-user.')

    args = parser.parse_args()

    if args.drop_to_group is not None and args.drop_to_user is None:
        parser.error('--drop-to-group requires --drop-to-user')

    configuration.init_server_config(args)

    asyncio.run(run_servers(args))


if __name__ == '__main__':
    main()
