"""Set the admin password.

    python -m app.auth.set_password            (asks for it)
    python -m app.auth.set_password --generate (makes one and shows it once)

Writes only its hash to config/secrets.key. Restart both servers afterwards.
In Docker:  docker compose exec ezyspeech ezyspeech password
"""
import getpass
import os
import secrets
import sys

from app.auth.passwords import store_admin_password

KEY = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'secrets.key')


def main(argv):
    if '--generate' in argv:
        password = '-'.join(secrets.token_hex(2) + secrets.token_hex(2)[:2] for _ in range(4))
    else:
        password = getpass.getpass('New admin password: ')
        if getpass.getpass('Again: ') != password:
            sys.exit('They do not match; nothing was changed.')
    if len(password) < 8:
        sys.exit('At least 8 characters; nothing was changed.')
    store_admin_password(os.path.abspath(KEY), password)
    if '--generate' in argv:
        print('Admin password: ' + password)
    print('Saved as a hash in config/secrets.key. Restart both servers.')


if __name__ == '__main__':
    main(sys.argv[1:])
