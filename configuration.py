import argparse
import pathlib
import ssl
import os


tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
our_domains = []
data_dir = pathlib.Path()

all_args: argparse.Namespace


def init_server_config(args):
    global tls_context, our_domains, data_dir, all_args
    all_args = args
    our_domains = args.this_hosts

    if os.path.isabs(args.data_dir):
        data_dir = pathlib.Path(args.data_dir)
    else:
        data_dir = pathlib.Path.cwd() / args.data_dir

    tls_context.load_cert_chain(args.certificate, args.private_key)