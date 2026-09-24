"""The only door to the router. Every failure leaves here as a RouterError with a code
that copy.py can turn into a sentence."""
from __future__ import annotations

import re

from collections import OrderedDict

from huawei_lte_api import exceptions as hx
from huawei_lte_api.Connection import Connection

LOGIN_WRONG = (
    hx.LoginErrorUsernamePasswordWrongException,
    hx.LoginErrorPasswordWrongException,
    hx.LoginErrorUsernameWrongException,
    hx.LoginErrorInvalidCredentialsException,
)
TIMEOUT = (5, 30)   # seconds to connect, to read; a lock-freq write on firmware 4.x takes a few


class RouterError(Exception):
    """`code` selects the message; `detail` carries the technical remainder for the small print."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def normalise_url(url: str) -> str:
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url.rstrip("/") + "/"


def host(url: str) -> str:
    """The address as a person types it: 192.168.8.1, not http://192.168.8.1/."""
    return re.sub(r"^https?://", "", normalise_url(url)).rstrip("/")


def _unreachable(error: OSError) -> RouterError:
    # requests' errors subclass OSError: refused, timed out, no route, connection reset
    return RouterError("unreachable", f"{type(error).__name__}: {error}")


class Router:
    def __init__(self, url: str, password: str, username: str = "admin", connection_factory=Connection):
        self.url = normalise_url(url)
        self.username = username
        self._password = password
        self._factory = connection_factory

    def _session(self):
        if not self._password:
            # a CPE with no admin password at all cannot be signed into by this app
            raise RouterError("no_password")
        try:
            return self._factory(self.url, username=self.username, password=self._password, timeout=TIMEOUT)
        except LOGIN_WRONG as error:
            raise RouterError("bad_password", str(error)) from error
        except hx.LoginErrorUsernamePasswordOverrunException as error:
            raise RouterError("locked_out", type(error).__name__) from error
        except OSError as error:
            raise _unreachable(error) from error
        except Exception as error:
            raise RouterError("not_huawei_api", f"{type(error).__name__}: {error}") from error

    def get(self, endpoint: str) -> dict:
        with self._session() as session:
            try:
                if endpoint.startswith("config/"):
                    return session.get(endpoint.removeprefix("config/"), prefix="config")
                return session.get(endpoint)
            except hx.ResponseErrorException as error:
                raise RouterError("api_refused", f"{endpoint}: {error}") from error
            except OSError as error:
                raise _unreachable(error) from error

    def post(self, endpoint: str, data: OrderedDict) -> str:
        with self._session() as session:
            try:
                return session.post_set(endpoint, data)
            except hx.ResponseErrorException as error:
                raise RouterError("api_refused", f"{endpoint}: {error}") from error
            except OSError as error:
                raise _unreachable(error) from error
