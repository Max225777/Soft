from app.services.crypto import decrypt_token, encrypt_token, mask_token, new_salt


def test_encrypt_decrypt_roundtrip():
    salt = new_salt()
    payload = encrypt_token("my-super-secret-token", salt)
    assert payload and payload != "my-super-secret-token"
    assert decrypt_token(payload, salt) == "my-super-secret-token"


def test_mask_token():
    assert mask_token("") == ""
    assert mask_token("abcd") == "****"
    assert mask_token("abcdefghij") == "abcd**ghij"
