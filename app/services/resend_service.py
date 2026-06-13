import resend
import os


def send_email(to_email: str, subject: str, html_body: str) -> dict:
    resend.api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("FROM_EMAIL", "agent@realestate.ai")

    try:
        response = resend.Emails.send({
            "from": from_email,
            "to": to_email,
            "subject": subject,
            "html": html_body,
        })
        return {"success": True, "id": response["id"]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def text_to_html(text: str) -> str:
    lines = text.strip().split("\n")
    html_lines = []
    for line in lines:
        if line.strip():
            html_lines.append(f"<p>{line}</p>")
        else:
            html_lines.append("<br>")
    return "".join(html_lines)
