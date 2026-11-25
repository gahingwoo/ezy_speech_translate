"""What the listener server refuses before a request reaches its route."""
from app.user import core
from app.user import routes_pages  # noqa: F401  (/api/health)


def test_an_api_token_never_looks_like_an_sql_comment():
    assert not any('--' in core.generate_api_session_token() for _ in range(5000))


def test_a_query_with_two_dashes_is_served():
    # As a token, a search, or a date range written with them
    r = core.app.test_client().get('/api/health?api_token=IK_dd--EiPZo0W')
    assert r.status_code == 200


def test_an_obvious_injection_is_still_refused():
    r = core.app.test_client().get('/api/health?q=1%20union%20select%20password')
    assert r.status_code == 400
