from github import GithubException
from base64 import b64encode
from nacl import encoding, public


def create_secret(repo, secret_name, secret_value):
    try:
        # Get the public key for the repo
        key_info = repo.get_public_key()

        # Base64 decode the public key and convert to an object
        public_key = public.PublicKey(key_info.key.encode(), encoding.Base64Encoder())

        # Encrypt the secret (we need to convert the secret to bytes first)
        sealed_box = public.SealedBox(public_key)
        encrypted = sealed_box.encrypt(secret_value.encode())

        # Create secret
        repo.create_secret(secret_name, b64encode(encrypted).decode())
    except GithubException as e:
        print(f"Failed to add {secret_name} secret to {repo.name} repository.")
        print(e)
