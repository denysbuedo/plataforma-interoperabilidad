from fastapi.testclient import TestClient
from mes_common.security import Principal, authenticated_principal
from mes_notification_service import main


def test_email_endpoint_requires_authentication() -> None:
    with TestClient(main.app) as client:
        response = client.post(
            "/api/v1/notifications/email",
            json={"recipient": "dest@example.org", "subject": "Test", "text_body": "Hello"},
        )

    assert response.status_code == 401


def test_email_endpoint_submits_to_relay_for_notification_sender(monkeypatch) -> None:
    submitted: list[dict[str, object]] = []

    def fake_send_email(**kwargs: object) -> None:
        submitted.append(kwargs)

    main.app.dependency_overrides[authenticated_principal] = lambda: Principal(
        subject="service-account",
        username=None,
        roles=frozenset({"notification-sender"}),
        claims={},
    )
    monkeypatch.setattr(main, "send_email", fake_send_email)
    try:
        with TestClient(main.app) as client:
            response = client.post(
                "/api/v1/notifications/email",
                json={
                    "recipient": "dest@example.org",
                    "subject": "Test",
                    "text_body": "Hello",
                    "html_body": "<p>Hello</p>",
                },
            )
    finally:
        main.app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json() == {"status": "accepted_by_relay"}
    assert submitted == [
        {
            "settings": main.settings,
            "recipient": "dest@example.org",
            "subject": "Test",
            "text_body": "Hello",
            "html_body": "<p>Hello</p>",
        }
    ]
