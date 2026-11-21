from email.message import EmailMessage

from mes_common.mail import send_email
from mes_common.settings import Settings
from pydantic import SecretStr


class FakeSocket:
    pass


class FakeTlsContext:
    def __init__(self) -> None:
        self.server_name: str | None = None

    def wrap_socket(self, sock: FakeSocket, *, server_hostname: str) -> FakeSocket:
        self.server_name = server_hostname
        return sock


class FakeSmtp:
    def __init__(self, **kwargs: object) -> None:
        self.sock: FakeSocket | None = FakeSocket()
        self.file: object | None = None
        self.logged_in = False
        self.sent_message: EmailMessage | None = None

    def __enter__(self) -> "FakeSmtp":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def connect(self, host: str | None, port: int) -> None:
        assert host == "10.46.4.22"
        assert port == 25

    def ehlo(self) -> None:
        return None

    def has_extn(self, name: str) -> bool:
        return name == "starttls"

    def docmd(self, command: str) -> tuple[int, bytes]:
        assert command == "STARTTLS"
        return 220, b"ready"

    def login(self, user: str, password: str) -> None:
        assert user == "smtp-user"
        assert password == "smtp-password"
        self.logged_in = True

    def send_message(self, message: EmailMessage) -> None:
        self.sent_message = message


def test_send_email_uses_starttls_server_name_and_verified_settings(monkeypatch) -> None:
    tls_context = FakeTlsContext()
    smtp = FakeSmtp()
    monkeypatch.setattr("mes_common.mail.ssl.create_default_context", lambda: tls_context)
    monkeypatch.setattr("mes_common.mail.smtplib.SMTP", lambda **_kwargs: smtp)
    settings = Settings(
        service_name="notification-service",
        smtp_host="10.46.4.22",
        smtp_port=25,
        smtp_tls_server_name="correo.mes.gob.cu",
        smtp_user="smtp-user",
        smtp_password=SecretStr("smtp-password"),
        email_from="noreply@example.org",
    )

    send_email(
        settings=settings,
        recipient="recipient@example.org",
        subject="Subject",
        text_body="Plain body",
        html_body="<p>HTML body</p>",
    )

    assert tls_context.server_name == "correo.mes.gob.cu"
    assert smtp.logged_in
    assert smtp.sent_message is not None
    assert smtp.sent_message["To"] == "recipient@example.org"
    plain_part = smtp.sent_message.get_body(preferencelist=("plain",))
    assert plain_part is not None
    assert plain_part.get_content().strip() == "Plain body"
