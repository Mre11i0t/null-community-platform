"""Runtime compatibility shims applied at app startup.

Kept out of tests' conftest so the SAME fix runs in production — the admin
changelist (and any templated response whose context gets copied) otherwise
500s on Python 3.14.
"""


def apply_basecontext_copy_patch():
    """Django 5.1's ``BaseContext.__copy__`` does ``duplicate = copy(super())``,
    which relies on ``copy.copy()`` transparently following a ``super`` proxy
    through to the underlying instance — that stopped working on Python 3.14
    (``'super' object has no attribute 'dicts'``), 500-ing the Django admin
    changelist and every templated response that copies its render context.
    Not an app bug; patch the copy directly. Redundant once Django ships a
    Python-3.14-safe ``__copy__`` (harmless after that, just dead weight).

    This mirrors the monkeypatch in conftest.py, which only covers the test
    process — production/showcase needs it too.
    """
    from django.template.context import BaseContext

    def _base_context_copy(self):
        duplicate = self.__class__.__new__(self.__class__)
        duplicate.__dict__.update(self.__dict__)
        duplicate.dicts = self.dicts[:]
        return duplicate

    BaseContext.__copy__ = _base_context_copy
