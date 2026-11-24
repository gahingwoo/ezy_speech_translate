"""The admin password: the browser sends a SHA-256 of it, the server keeps a
PBKDF2 verifier of that, and nothing that could give the password back."""
from app.auth.passwords import hash_password, verify
from secure_loader import client_hash, is_verifier, make_verifier


def test_the_browser_side_hash_is_sha256_hex():
    assert hash_password('mabc1915') == client_hash('mabc1915')
    assert len(client_hash('x')) == 64


def test_a_verifier_accepts_its_password_and_nothing_else():
    v = make_verifier(client_hash('right horse battery'), iterations=1000)
    assert is_verifier(v)
    assert verify(client_hash('right horse battery'), v)
    assert not verify(client_hash('wrong horse battery'), v)


def test_bad_input_is_refused_not_raised():
    v = make_verifier(client_hash('x'), iterations=1000)
    assert not verify('', v)
    assert not verify('not-hex', v)
    assert not verify(None, v)
    assert not verify(client_hash('x'), None)
    assert not is_verifier('plain text') and not is_verifier(None)


def test_two_verifiers_of_one_password_differ():
    h = client_hash('same')
    assert make_verifier(h, iterations=1000) != make_verifier(h, iterations=1000)


def test_a_signed_token_reads_back_and_expires():
    import time
    from app.auth.jwt_utils import decode_jwt, encode_jwt
    token = encode_jwt({'username': 'admin', 'role': 'admin'}, 'a-test-secret-long-enough-1234567890', exp_seconds=60)
    assert decode_jwt(token, 'a-test-secret-long-enough-1234567890')['username'] == 'admin'
    assert not decode_jwt(token, 'another-secret-long-enough-1234567890')
    stale = encode_jwt({'username': 'admin'}, 'a-test-secret-long-enough-1234567890', exp_seconds=-5)
    assert not decode_jwt(stale, 'a-test-secret-long-enough-1234567890')
