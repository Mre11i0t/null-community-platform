import pytest
from django.urls import reverse

from tests.factories import PageFactory

pytestmark = pytest.mark.django_db


def test_published_page_is_visible(client):
    page = PageFactory(published=True, title="Code of Conduct")

    response = client.get(reverse("content:page_detail", args=[page.slug]))

    assert response.status_code == 200
    assert response.context["page"] == page


def test_unpublished_page_404s(client):
    page = PageFactory(published=False)

    response = client.get(reverse("content:page_detail", args=[page.slug]))

    assert response.status_code == 404


def test_slug_is_generated_and_unique_per_page():
    page1 = PageFactory(name="How To Start A Chapter")
    page2 = PageFactory(name="How To Start A Chapter")

    assert page1.slug != page2.slug
    assert page1.slug
    assert page2.slug
