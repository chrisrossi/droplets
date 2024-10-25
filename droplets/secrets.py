import base64
import getpass
import pathlib
import subprocess
import tempfile

import docopt
import yaml

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

SALT = b"\x9a0\x07@\x0eg\x8c\x8b\xadz\x16@\xe3ob;"


def secrets_cli():
    """
    Edit secrets in a YAML file.

    Usage:
        secrets <filename>

    Options:
        -h --help    Show this screen
    """
    args = docopt.docopt(secrets_cli.__doc__)
    path = pathlib.Path(args["<filename>"]).resolve()
    if path.exists():
        edit_secrets(path)
    else:
        new_secrets(path)


def get_yaml_secrets(path, save_passphrase=None):
    """
    TODO
    """
    contents = get_secrets(path, save_passphrase=save_passphrase)
    return yaml.load(contents, Loader=yaml.FullLoader)


def get_secrets(path, save_passphrase=None):
    """
    Called from inventory script to get secrets.
    """
    passphrase = None
    never = False

    if save_passphrase:
        save_passphrase = pathlib.Path(save_passphrase).resolve()
        if save_passphrase.exists():
            with open(save_passphrase) as f:
                passphrase = f.read().strip()
                if passphrase == "":
                    never = True

    if not passphrase:
        passphrase, contents = _challenge(path)
        if save_passphrase and not never:
            answer = None
            while answer not in ("yes", "no", "never"):
                answer = input("Save passphrase to file (yes|no|never)? ")

            if answer == "never":
                with open(save_passphrase, "w") as f:
                    f.write("")

            elif answer == "yes":
                with open(save_passphrase, "w") as f:
                    f.write(passphrase)

    else:
        contents = _decrypt(path, passphrase)

    return contents


def edit_secrets(path):
    passphrase, contents = _challenge(path)
    contents = _edit_contents(path, contents)
    _encrypt(path, passphrase, contents)


def new_secrets(path):
    print(f"Creating new file: {path}")
    passphrase = _new_passphrase()
    contents = _edit_contents(path, b"")
    _encrypt(path, passphrase, contents)


def _edit_contents(path, contents):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = pathlib.Path(tmpdir) / "secrets.yaml"
        with open(tmp, "wb") as f:
            f.write(contents)

        subprocess.run(["editor", str(tmp)])

        with open(tmp, "rb") as f:
            return f.read()


def _new_passphrase():
    while True:
        passphrase = getpass.getpass("enter new passphrase> ")
        verify = getpass.getpass("verify new passphrase again to verify> ")
        if passphrase == verify:
            return passphrase

        print("Passphrases do not match")


def _challenge(path):
    while True:
        try:
            passphrase = getpass.getpass("passphrase> ").strip()
            return passphrase, _decrypt(path, passphrase)
        except InvalidToken:
            pass


def _decrypt(path, passphrase):
    cipher = _get_cipher(passphrase)
    with open(path, "rb") as f:
        encrypted = f.read()
    return cipher.decrypt(encrypted)


def _encrypt(path, passphrase, contents):
    cipher = _get_cipher(passphrase)
    encrypted = cipher.encrypt(contents)
    with open(path, "wb") as f:
        f.write(encrypted)


def _get_cipher(passphrase):
    passphrase = passphrase.encode("utf-8")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=SALT,
        iterations=390000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(passphrase))
    return Fernet(key)
