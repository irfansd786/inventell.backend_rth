from app.core import security
from app.models.order import ALLOWED_TRANSITIONS


def test_password_hash_roundtrip():
    hashed = security.get_password_hash('admin123')
    assert hashed != 'admin123'
    assert security.verify_password('admin123', hashed)
    assert not security.verify_password('wrong', hashed)


def test_jwt_roundtrip():
    access = security.create_access_token('admin@invintell.com', 'MANAGER')
    payload = security.decode_token(access, 'access')
    assert payload['sub'] == 'admin@invintell.com'

    refresh = security.create_refresh_token('admin@invintell.com')
    payload = security.decode_token(refresh, 'refresh')
    assert payload['sub'] == 'admin@invintell.com'


def test_order_lifecycle_is_linear():
    assert ALLOWED_TRANSITIONS['PENDING'] == ('ALLOCATED', 'CANCELLED')
    assert ALLOWED_TRANSITIONS['ALLOCATED'] == ('PICKING', 'CANCELLED')
    assert ALLOWED_TRANSITIONS['PICKING'] == ('PACKING', 'CANCELLED')
    assert ALLOWED_TRANSITIONS['PACKING'] == ('READY', 'CANCELLED')
    assert ALLOWED_TRANSITIONS['READY'] == ('DISPATCHED',)
    assert ALLOWED_TRANSITIONS['DISPATCHED'] == tuple()
    # No backward jumps anywhere in the happy path
    order = ['PENDING', 'ALLOCATED', 'PICKING', 'PACKING', 'READY', 'DISPATCHED']
    for i, status in enumerate(order[:-1]):
        assert order[i + 1] in ALLOWED_TRANSITIONS[status]
