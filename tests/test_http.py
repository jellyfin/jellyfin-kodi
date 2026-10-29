from unittest.mock import Mock

from jellyfin_kodi.jellyfin.http import HTTP


def make_http(response):
    client = Mock()
    client.config.data = {
        "auth.server": "http://server",
        "http.timeout": 5,
        "http.user_agent": "test",
    }
    http = HTTP(client)
    http._requests = Mock(return_value=response)
    return http


def make_response(content):
    response = Mock()
    response.content = content
    response.headers = {}
    response.elapsed.total_seconds.return_value = 0
    return response


def test_empty_response_is_not_decoded():
    response = make_response(b"")
    response.json.side_effect = NameError("name 'ValueError' is not defined")

    http = make_http(response)

    assert http.request({"type": "POST", "handler": "Sessions/Playing"}) is None
    response.json.assert_not_called()


def test_json_response_is_returned():
    response = make_response(b'{"Id": "1"}')
    response.json.return_value = {"Id": "1"}

    http = make_http(response)

    assert http.request({"type": "GET", "handler": "Items"}) == {"Id": "1"}
